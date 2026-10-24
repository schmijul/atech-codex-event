"""Exercise real HTTP/SQLite behavior with a temporary database; no API charges."""

import base64
import io
import json
import sqlite3
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
import wave
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

import dashboard
import voice_assistant
from voice_tools import execute_tool, initialize_database


class VoiceToolsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory = tempfile.TemporaryDirectory()
        cls.database = Path(cls.directory.name) / 'test.sqlite3'
        initialize_database(cls.database)
        cls.database_patch = patch.object(dashboard, 'DATABASE', cls.database)
        cls.database_patch.start()
        cls.server = ThreadingHTTPServer(('127.0.0.1', 0), dashboard.Handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.url = 'http://127.0.0.1:' + str(cls.server.server_port)
        cls.backend_patch = patch.object(voice_assistant, 'BACKEND_URL', cls.url)
        cls.backend_patch.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()
        cls.backend_patch.stop()
        cls.database_patch.stop()
        cls.directory.cleanup()

    def request(self, path, body=None, method=None):
        request = urllib.request.Request(self.url + path,
                                         data=json.dumps(body).encode() if body is not None else None,
                                         headers={'Content-Type': 'application/json'}, method=method)
        with urllib.request.urlopen(request) as response:
            return json.loads(response.read())

    def setUp(self):
        with sqlite3.connect(self.database) as db:
            for table in ('medication_events', 'dashboard_settings', 'social_invitations', 'voice_requests'):
                db.execute('DELETE FROM ' + table)
            db.execute('DELETE FROM patients WHERE id != 1')
            db.execute("UPDATE patients SET name = 'Patient 1', floor = NULL WHERE id = 1")
        voice_assistant.conversations.clear()

    def test_four_cases_and_repeat_delivery(self):
        examples = [
            ('request_help', {'details': 'Please help me stand up.', 'urgent': False}, 'pending'),
            ('request_floor_activity', {'activity': 'cards'}, 'needs_floor'),
            ('choose_lunch', {'choice': 'vegetarian', 'details': 'No meat please.'}, 'recorded'),
            ('medication_reminder', {'action': 'status', 'time': '', 'timezone': ''}, 'ok'),
        ]
        for name, arguments, status in examples:
            with self.subTest(name=name):
                payload = {'request_id': 'case-' + name, 'arguments': arguments}
                result = self.request('/api/voice/tools/' + name, payload)
                self.assertEqual(result['case'], name)
                self.assertEqual(result['status'], status)
                self.assertEqual(result, self.request('/api/voice/tools/' + name, payload))
        history = self.request('/api/voice/requests')
        self.assertEqual(sum(row['request_id'].startswith('case-') for row in history), 4)
        self.assertEqual(self.request('/api/events'), [])

    def test_medication_schedule_shared_with_dashboard(self):
        result = execute_tool(self.database, 'medication_reminder',
                              {'action': 'set', 'time': '09:15', 'timezone': 'Europe/Berlin'}, 'set-time')
        self.assertTrue(result['enabled'])
        self.assertEqual(self.request('/api/reminder')['time'], '09:15')
        self.request('/api/reminder', {'time': '10:30', 'timezone': 'Europe/Berlin'})
        status = execute_tool(self.database, 'medication_reminder',
                              {'action': 'status', 'time': '', 'timezone': ''}, 'read-changed-time')
        self.assertEqual(status['time'], '10:30')
        confirmation = self.request('/api/events', {})
        status = execute_tool(self.database, 'medication_reminder',
                              {'action': 'status', 'time': '', 'timezone': ''}, 'read-button')
        self.assertEqual(status['last_button_confirmation'], confirmation['taken_at_utc'])
        execute_tool(self.database, 'medication_reminder',
                     {'action': 'disable', 'time': '', 'timezone': ''}, 'disable-time')
        self.assertEqual(self.request('/api/reminder'), {'enabled': False})
        # The only confirmation is the explicit button/API write above.
        self.assertEqual(len(self.request('/api/events')), 1)

    def test_rejects_invalid_arguments_without_writing(self):
        examples = [
            ('request_help', {'details': 'Help', 'urgent': 'false'}),
            ('request_help', {'details': '', 'urgent': False}),
            ('choose_lunch', {'choice': 'unknown', 'details': ''}),
            ('request_floor_activity', {'activity': ''}),
            ('medication_reminder', {'action': 'set', 'time': '25:00', 'timezone': 'Europe/Berlin'}),
            ('medication_reminder', {'action': 'set', 'time': '08:00', 'timezone': 'Invalid/Zone'}),
            ('medication_reminder', {'action': 'confirm_taken', 'time': '', 'timezone': ''}),
            ('unknown_tool', {}),
        ]
        count = len(self.request('/api/voice/requests'))
        for name, arguments in examples:
            with self.subTest(name=name, arguments=arguments):
                with self.assertRaises(urllib.error.HTTPError) as error:
                    self.request('/api/voice/tools/' + name, {'request_id': 'invalid', 'arguments': arguments})
                self.assertEqual(error.exception.code, 400)
        self.assertEqual(len(self.request('/api/voice/requests')), count)
        payload = {'request_id': 'reuse', 'arguments': {'choice': 'meat', 'details': ''}}
        self.request('/api/voice/tools/choose_lunch', payload)
        payload['arguments']['choice'] = 'vegetarian'
        with self.assertRaises(urllib.error.HTTPError) as error:
            self.request('/api/voice/tools/choose_lunch', payload)
        self.assertEqual(error.exception.code, 400)

    def test_audio_tool_round_trip_and_followup_context(self):
        wav = io.BytesIO()
        with wave.open(wav, 'wb') as output:
            output.setnchannels(1)
            output.setsampwidth(2)
            output.setframerate(24000)
            output.writeframes(b'\x00\x00' * 240)
        spoken = {'role': 'assistant', 'audio': {
            'data': base64.b64encode(wav.getvalue()).decode(), 'transcript': 'Your lunch preference is recorded.'}}
        calls = []

        def model(path, data, content_type):
            request = json.loads(data)
            calls.append(request)
            if len(calls) == 1:
                message = {'role': 'assistant', 'content': None, 'tool_calls': [{
                    'id': 'audio-lunch', 'type': 'function', 'function': {
                        'name': 'choose_lunch', 'arguments': '{"choice":"vegan","details":""}'}}]}
            else:
                message = spoken
            return json.dumps({'choices': [{'message': message}]}).encode()

        with patch.object(voice_assistant, 'openai_request', model):
            transcript, pcm = voice_assistant.create_voice_reply(b'fake input wav', 'test-board')
            self.assertEqual(transcript, spoken['audio']['transcript'])
            self.assertEqual(len(pcm), 320)
            self.assertEqual(json.loads(calls[1]['messages'][-1]['content'])['choice'], 'vegan')
            voice_assistant.create_voice_reply(b'followup wav', 'test-board')
        self.assertTrue(any(message.get('content') == transcript for message in calls[2]['messages']))
        self.assertEqual(len(calls[0]['tools']), 4)
        self.assertTrue(any(row['request_id'] == 'audio-lunch' for row in self.request('/api/voice/requests')))

    def test_backend_failure_is_returned_to_model(self):
        call = {'id': 'unavailable', 'function': {'name': 'request_help', 'arguments': '{"details":"Help","urgent":true}'}}
        with patch.object(voice_assistant.urllib.request, 'urlopen', side_effect=TimeoutError):
            self.assertIn('error', voice_assistant.call_backend(call))

    def test_tool_discovery_and_concurrent_retry(self):
        from concurrent.futures import ThreadPoolExecutor

        self.assertEqual(len(self.request('/api/voice/tools')), 4)
        payload = {'request_id': 'same-delivery', 'arguments': {'details': 'Need assistance.', 'urgent': False}}
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(self.request, '/api/voice/tools/request_help', payload) for _ in range(2)]
            results = [future.result() for future in futures]
        self.assertEqual(results[0], results[1])
        self.assertEqual(len(self.request('/api/voice/requests')), 1)

    def test_social_request_invites_only_other_residents_on_same_floor(self):
        self.request('/api/patients', {'id': 1, 'name': 'Requester', 'floor': '2'})
        neighbor = self.request('/api/patients', {'id': None, 'name': 'Neighbor', 'floor': '2'})
        other_floor = self.request('/api/patients', {'id': None, 'name': 'Other floor', 'floor': '3'})
        payload = {'request_id': 'cards', 'patient_id': 1, 'arguments': {'activity': 'play cards'}}
        result = self.request('/api/voice/tools/request_floor_activity', payload)
        self.assertEqual(result['status'], 'invitations_created')
        self.assertEqual(result['invitation_count'], 1)
        self.assertEqual(self.request('/api/voice/tools/request_floor_activity', payload), result)
        invitations = self.request('/api/social/invitations')
        self.assertEqual(len(invitations), 1)
        self.assertEqual(invitations[0]['recipient_id'], neighbor['id'])
        self.assertEqual(self.request('/api/patients/1/invitations'), [])
        self.assertEqual(self.request(f"/api/patients/{other_floor['id']}/invitations"), [])
        invitation = self.request(f"/api/patients/{neighbor['id']}/invitations/next")['invitation']
        self.assertEqual(invitation['activity'], 'play cards')
        self.assertIsNone(invitation['played_at_utc'])
        wrong_ack = f"/api/patients/{other_floor['id']}/invitations/{invitation['id']}/played"
        with self.assertRaises(urllib.error.HTTPError) as error:
            self.request(wrong_ack, {})
        self.assertEqual(error.exception.code, 400)
        correct_ack = f"/api/patients/{neighbor['id']}/invitations/{invitation['id']}/played"
        self.request(correct_ack, {})
        self.request(correct_ack, {})
        self.assertIsNone(self.request(f"/api/patients/{neighbor['id']}/invitations/next")['invitation'])
        self.assertIsNotNone(self.request('/api/social/invitations')[0]['played_at_utc'])
        self.assertEqual(self.request('/api/voice/requests')[0]['patient_id'], 1)

    def test_resident_identity_and_missing_floor(self):
        payload = {'request_id': 'unknown-patient', 'patient_id': 200, 'arguments': {'activity': 'cards'}}
        with self.assertRaises(urllib.error.HTTPError):
            self.request('/api/voice/tools/request_floor_activity', payload)
        payload.update(request_id='missing-floor', patient_id=1)
        self.assertEqual(self.request('/api/voice/tools/request_floor_activity', payload)['status'], 'needs_floor')
        self.request('/api/patients', {'id': 1, 'name': 'Patient 1', 'floor': '1'})
        payload['request_id'] = 'no-neighbors'
        self.assertEqual(self.request('/api/voice/tools/request_floor_activity', payload)['status'], 'no_neighbors')
        self.assertEqual(self.request('/api/social/invitations'), [])

    def test_dispatch_missing_floor_request_after_directory_is_ready(self):
        result = self.request('/api/voice/tools/request_floor_activity', {
            'request_id': 'configure-floor-later', 'arguments': {'activity': 'cards'}})
        self.assertEqual(result['status'], 'needs_floor')
        self.request('/api/patients', {'id': 1, 'name': 'Patient 1', 'floor': '2'})
        self.request('/api/patients', {'id': None, 'name': 'Neighbor', 'floor': '2'})
        path = f"/api/social/requests/{result['id']}/dispatch"
        sent = self.request(path, {})
        self.assertEqual(sent['invitation_count'], 1)
        self.assertEqual(self.request(path, {}), sent)
        self.assertEqual(len(self.request('/api/social/invitations')), 1)



if __name__ == '__main__':
    unittest.main()
