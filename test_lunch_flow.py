"""Exercise the dashboard -> spoken prompt -> lunch answer with temporary SQLite."""

import base64
import io
import json
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
import voice_assistant as voice
from voice_tools import execute_tool, initialize_database


class LunchFlowTest(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.database = Path(self.folder.name) / 'test.sqlite3'
        initialize_database(self.database)
        self.database_patch = patch.object(dashboard, 'DATABASE', self.database)
        self.database_patch.start()
        self.backend = ThreadingHTTPServer(('127.0.0.1', 0), dashboard.Handler)
        self.voice_server = ThreadingHTTPServer(('127.0.0.1', 0), voice.VoiceHandler)
        self.backend_url = 'http://127.0.0.1:' + str(self.backend.server_port)
        self.voice_url = 'http://127.0.0.1:' + str(self.voice_server.server_port)
        self.backend_patch = patch.object(voice, 'BACKEND_URL', self.backend_url)
        self.backend_patch.start()
        self.session_patch = patch.object(voice, 'SESSION_FILE', Path(self.folder.name) / 'session.json')
        self.session_patch.start()
        voice.conversation_history = []
        voice.has_disclosed_voice = False
        self.threads = []
        for server in (self.backend, self.voice_server):
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            self.threads.append(thread)

    def tearDown(self):
        for server in (self.backend, self.voice_server):
            server.shutdown()
            server.server_close()
        for thread in self.threads:
            thread.join()
        self.session_patch.stop()
        self.backend_patch.stop()
        self.database_patch.stop()
        self.folder.cleanup()

    def request(self, path, data=None, host=None):
        request = urllib.request.Request((host or self.backend_url) + path,
            data=None if data is None else json.dumps(data).encode(),
            headers={'Content-Type': 'application/json'})
        return urllib.request.urlopen(request, timeout=5)

    def ask(self):
        with self.request('/api/lunch/ask', {'patient_id': 1, 'options': [
            {'label': 'Vegetarian pasta', 'choice': 'vegetarian'},
            {'label': 'Chicken and rice', 'choice': 'meat'},
        ]}) as response:
            return json.load(response)['question']

    def current(self):
        with self.request('/api/lunch') as response:
            return json.load(response)['question']

    def test_playback_ack_and_short_answer(self):
        question = self.ask()
        with patch.object(voice, 'lunch_prompt_audio', return_value=b'\x00\x00' * 160):
            with self.request('/api/voice/prompt', host=self.voice_url) as response:
                self.assertEqual(response.headers['X-Lunch-Question-ID'], str(question['id']))
                self.assertEqual(len(response.read()), 320)
        self.assertEqual(self.current()['status'], 'queued')
        with self.request('/api/voice/prompt/' + str(question['id']) + '/played', {}, self.voice_url) as response:
            self.assertEqual(response.status, 204)
        self.assertEqual(self.current()['status'], 'awaiting_answer')
        with self.request('/api/voice/prompt', host=self.voice_url) as response:
            self.assertEqual(response.status, 204)

        wav = io.BytesIO()
        with wave.open(wav, 'wb') as output:
            output.setnchannels(1)
            output.setsampwidth(2)
            output.setframerate(24000)
            output.writeframes(b'\x00\x00' * 240)
        calls = []

        def model(path, data, content_type):
            body = json.loads(data)
            calls.append(body)
            if len(calls) == 1:
                self.assertIn('Vegetarian pasta', body['messages'][0]['content'])
                self.assertEqual(body['messages'][-1]['content'], 'The first one.')
                message = {'role': 'assistant', 'content': None, 'tool_calls': [{
                    'id': 'lunch-test', 'type': 'function', 'function': {
                        'name': 'choose_lunch', 'arguments': json.dumps({'choice': 'vegetarian', 'details': 'Vegetarian pasta'})}}]}
            else:
                message = {'role': 'assistant', 'audio': {'transcript': 'Vegetarian pasta recorded.', 'data': base64.b64encode(wav.getvalue()).decode()}}
            return json.dumps({'choices': [{'message': message}]}).encode()

        with patch.object(voice, 'openai_request', model):
            reply, speech = voice.create_voice_reply('The first one.')
        self.assertEqual(reply, 'Vegetarian pasta recorded.')
        self.assertEqual(len(speech), 320)
        answered = self.current()
        self.assertEqual(answered['id'], question['id'])
        self.assertEqual(answered['status'], 'answered')
        self.assertEqual(answered['choice'], 'vegetarian')
        self.assertEqual(answered['details'], 'Vegetarian pasta')
        result = execute_tool(self.database, 'choose_lunch', {'choice': 'vegetarian', 'details': 'Vegetarian pasta'}, 'lunch-test')
        self.assertEqual(result['question_id'], question['id'])

    def test_duplicate_active_question_and_cancel(self):
        question = self.ask()
        with self.assertRaises(urllib.error.HTTPError) as error:
            self.ask()
        self.assertEqual(error.exception.code, 400)
        error.exception.close()
        with self.request('/api/lunch/' + str(question['id']) + '/cancel', {}) as response:
            self.assertEqual(json.load(response)['question']['status'], 'cancelled')
        with self.request('/api/lunch/' + str(question['id']) + '/spoken', {}) as response:
            self.assertEqual(json.load(response)['question']['status'], 'cancelled')
        self.assertGreater(self.ask()['id'], question['id'])

    def test_invalid_options_do_not_queue(self):
        with self.assertRaises(urllib.error.HTTPError) as error:
            with self.request('/api/lunch/ask', {'patient_id': 1, 'options': []}):
                pass
        self.assertEqual(error.exception.code, 400)
        error.exception.close()
        self.assertIsNone(self.current())


if __name__ == '__main__':
    unittest.main()
