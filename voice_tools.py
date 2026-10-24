"""Voice-agent function definitions and their SQLite-backed actions."""

import json
import re
import sqlite3
from datetime import datetime, time, timezone
from zoneinfo import ZoneInfo


TOOLS = [
    {
        'type': 'function',
        'function': {
            'name': 'request_help',
            'description': 'Record that the patient needs assistance. Use for explicit help requests or immediate distress. This records a pending request; it does not contact staff or emergency services.',
            'parameters': {
                'type': 'object',
                'properties': {
                    'details': {'type': 'string', 'description': 'What help the patient asked for, in their language.'},
                    'urgent': {'type': 'boolean', 'description': 'True for immediate danger or urgent help; false for routine assistance.'},
                },
                'required': ['details', 'urgent'],
                'additionalProperties': False,
            },
        },
    },
    {
        'type': 'function',
        'function': {
            'name': 'request_floor_activity',
            'description': 'Request company or games with other residents on the patient\'s floor. Looks up the registered floor and creates dashboard and spoken-device invitations for other residents there. Do not use for general stories about friends.',
            'parameters': {
                'type': 'object',
                'properties': {
                    'activity': {'type': 'string', 'description': 'Requested game or social activity, e.g. cards or chatting.'},
                },
                'required': ['activity'],
                'additionalProperties': False,
            },
        },
    },
    {
        'type': 'function',
        'function': {
            'name': 'choose_lunch',
            'description': 'Record the patient\'s lunch/menu answer, including a short answer to your preceding lunch question. Ask for clarification if the answer or dietary category is unclear. This records a preference, not a kitchen order.',
            'parameters': {
                'type': 'object',
                'properties': {
                    'choice': {'type': 'string', 'enum': ['vegetarian', 'meat', 'vegan', 'fish', 'other']},
                    'details': {'type': 'string', 'description': 'Specific dish or dietary wishes the patient actually stated; empty if none.'},
                },
                'required': ['choice', 'details'],
                'additionalProperties': False,
            },
        },
    },
    {
        'type': 'function',
        'function': {
            'name': 'medication_reminder',
            'description': 'Read, set, or disable the existing dashboard daily medication reminder. Read status for questions about medication or taking it. Medication confirmations are recorded with the physical meds-taken button, never by this tool. Only set/disable when explicitly requested.',
            'parameters': {
                'type': 'object',
                'properties': {
                    'action': {'type': 'string', 'enum': ['status', 'set', 'disable']},
                    'time': {'type': 'string', 'description': 'HH:MM for set, or empty for status/disable. Ask for missing or ambiguous time.'},
                    'timezone': {'type': 'string', 'description': 'IANA timezone for set, e.g. Europe/Berlin, or empty for status/disable. Use provided local context.'},
                },
                'required': ['action', 'time', 'timezone'],
                'additionalProperties': False,
            },
        },
    },
]


def initialize_database(database):
    with sqlite3.connect(database) as db:
        db.execute('CREATE TABLE IF NOT EXISTS medication_events (id INTEGER PRIMARY KEY, taken_at_utc TEXT NOT NULL)')
        db.execute('CREATE TABLE IF NOT EXISTS dashboard_settings (key TEXT PRIMARY KEY, value TEXT NOT NULL)')
        db.execute('CREATE TABLE IF NOT EXISTS patients (id INTEGER PRIMARY KEY, name TEXT NOT NULL, floor TEXT)')
        db.execute("INSERT OR IGNORE INTO patients (id, name) VALUES (1, 'Patient 1')")
        db.execute('''CREATE TABLE IF NOT EXISTS voice_requests (
            id INTEGER PRIMARY KEY, request_id TEXT NOT NULL UNIQUE,
            patient_id INTEGER NOT NULL,
            created_at_utc TEXT NOT NULL, tool TEXT NOT NULL,
            arguments TEXT NOT NULL, result TEXT NOT NULL)''')
        db.execute('''CREATE TABLE IF NOT EXISTS social_invitations (
            id INTEGER PRIMARY KEY, request_id TEXT NOT NULL, sender_id INTEGER NOT NULL,
            recipient_id INTEGER NOT NULL, activity TEXT NOT NULL,
            created_at_utc TEXT NOT NULL, played_at_utc TEXT,
            UNIQUE(request_id, recipient_id))''')


def invite_neighbors(db, request_id, patient_id, activity):
    floor = db.execute('SELECT floor FROM patients WHERE id = ?', (patient_id,)).fetchone()[0]
    recipients = [] if not floor else db.execute(
        'SELECT id FROM patients WHERE floor = ? COLLATE NOCASE AND id != ?', (floor, patient_id)).fetchall()
    timestamp = datetime.now(timezone.utc).isoformat(timespec='seconds')
    db.executemany('INSERT OR IGNORE INTO social_invitations (request_id, sender_id, recipient_id, activity, created_at_utc) VALUES (?, ?, ?, ?, ?)',
                   [(request_id, patient_id, row[0], activity, timestamp) for row in recipients])
    status = 'invitations_created' if recipients else ('no_neighbors' if floor else 'needs_floor')
    return {'status': status, 'floor': floor, 'invitation_count': len(recipients),
            'message': f'Created {len(recipients)} dashboard invitations. Device announcements are pending playback.' if recipients else
            ('No other residents are registered on this floor.' if floor else 'Set the patient\'s floor in the dashboard directory before inviting people.')}


def execute_tool(database, name, arguments, request_id, patient_id=1):
    if type(patient_id) is not int or patient_id < 1:
        raise ValueError('patient_id must be a positive integer.')
    definition = next((tool['function'] for tool in TOOLS if tool['function']['name'] == name), None)
    if definition is None:
        raise ValueError('Unknown voice tool.')
    if not isinstance(request_id, str) or not request_id.strip() or len(request_id) > 200:
        raise ValueError('request_id must be a nonempty string of at most 200 characters.')
    schema = definition['parameters']
    if not isinstance(arguments, dict) or set(arguments) != set(schema['required']):
        raise ValueError('Expected arguments: ' + ', '.join(schema['required']))
    for key, spec in schema['properties'].items():
        value = arguments[key]
        if spec['type'] == 'boolean':
            if type(value) is not bool:
                raise ValueError(key + ' must be a boolean.')
        elif not isinstance(value, str) or len(value) > 2000:
            raise ValueError(key + ' must be a string of at most 2000 characters.')
        elif key not in ('details', 'time', 'timezone') and not value.strip():
            raise ValueError(key + ' cannot be empty.')
        if 'enum' in spec and value not in spec['enum']:
            raise ValueError(key + ' must be one of: ' + ', '.join(spec['enum']))
    if name == 'request_help' and not arguments['details'].strip():
        raise ValueError('Help details cannot be empty.')
    if name == 'request_floor_activity' and len(arguments['activity']) > 100:
        raise ValueError('Activity must be at most 100 characters.')
    if name == 'medication_reminder':
        if arguments['action'] == 'set':
            if not re.fullmatch(r'\d{2}:\d{2}', arguments['time']):
                raise ValueError('time must use HH:MM format.')
            time.fromisoformat(arguments['time'])
            ZoneInfo(arguments['timezone'])
        elif arguments['time'] or arguments['timezone']:
            raise ValueError('Use empty time and timezone for status/disable.')

    timestamp = datetime.now(timezone.utc).isoformat(timespec='seconds')
    encoded = json.dumps(arguments, sort_keys=True, ensure_ascii=False)
    with sqlite3.connect(database) as db:
        # Serialize retries and save the action/result in the same transaction.
        db.execute('BEGIN IMMEDIATE')
        previous = db.execute('SELECT tool, arguments, patient_id, result FROM voice_requests WHERE request_id = ?', (request_id,)).fetchone()
        if previous:
            if previous[:3] != (name, encoded, patient_id):
                raise ValueError('request_id was already used with different arguments.')
            return json.loads(previous[3])
        patient = db.execute('SELECT name, floor FROM patients WHERE id = ?', (patient_id,)).fetchone()
        if not patient:
            raise ValueError('Unknown patient_id. Add this resident to the dashboard directory first.')
        if name == 'medication_reminder' and patient_id != 1:
            raise ValueError('Medication reminders are currently configured only for Patient 1.')

        result = {'case': name, 'patient_id': patient_id, 'created_at_utc': timestamp}
        if name == 'request_help':
            result.update(status='pending', urgent=arguments['urgent'], notified=False,
                          message='Help request recorded. Nobody has been contacted. Use the call button or contact a person for help now; for immediate danger, call local emergency services.')
            if db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='alerts'").fetchone():
                db.execute("INSERT INTO alerts (patient_id,type,title,created_utc,status,note) VALUES (?,?,?,?,?,?)",
                           (patient_id, 'help', ('Urgent help: ' if arguments['urgent'] else 'Help requested: ') + arguments['details'], timestamp, 'open', 'Voice request ' + request_id))
        elif name == 'request_floor_activity':
            result.update(invite_neighbors(db, request_id, patient_id, arguments['activity']))
        elif name == 'choose_lunch':
            result.update(status='recorded', choice=arguments['choice'], ordered=False,
                          message='Lunch preference recorded; no kitchen order has been sent.')
        else:
            if arguments['action'] == 'set':
                db.executemany('INSERT INTO dashboard_settings (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value',
                               [('reminder_time', arguments['time']), ('reminder_timezone', arguments['timezone'])])
            elif arguments['action'] == 'disable':
                db.execute("DELETE FROM dashboard_settings WHERE key IN ('reminder_time', 'reminder_timezone')")
            settings = dict(db.execute("SELECT key, value FROM dashboard_settings WHERE key IN ('reminder_time', 'reminder_timezone')"))
            last = db.execute('SELECT taken_at_utc FROM medication_events ORDER BY taken_at_utc DESC, id DESC LIMIT 1').fetchone()
            result.update(status='ok', action=arguments['action'],
                          enabled='reminder_time' in settings and 'reminder_timezone' in settings,
                          time=settings.get('reminder_time'), timezone=settings.get('reminder_timezone'),
                          last_button_confirmation=last[0] if last else None,
                          message='Use the physical meds-taken button to confirm medication. A button confirmation is not proof of ingestion. The board polls schedule changes every 30 seconds.')
        cursor = db.execute('INSERT INTO voice_requests (request_id, patient_id, created_at_utc, tool, arguments, result) VALUES (?, ?, ?, ?, ?, ?)',
                            (request_id, patient_id, timestamp, name, encoded, '{}'))
        result['id'] = cursor.lastrowid
        db.execute('UPDATE voice_requests SET result = ? WHERE id = ?', (json.dumps(result), result['id']))
    return result


def list_requests(database):
    with sqlite3.connect(database) as db:
        rows = db.execute('SELECT request_id, tool, arguments, result, patient_id FROM voice_requests ORDER BY id DESC LIMIT 100')
        return [{'request_id': row[0], 'tool': row[1], 'arguments': json.loads(row[2]),
                 'result': json.loads(row[3]), 'patient_id': row[4]} for row in rows]


def dispatch_social_request(database, event_id):
    with sqlite3.connect(database) as db:
        db.execute('BEGIN IMMEDIATE')
        row = db.execute("SELECT request_id, patient_id, arguments, result FROM voice_requests WHERE id = ? AND tool = 'request_floor_activity'", (event_id,)).fetchone()
        if not row:
            raise ValueError('Social request not found.')
        result = json.loads(row[3])
        if result['status'] in ('needs_floor', 'no_neighbors'):
            result.update(invite_neighbors(db, row[0], row[1], json.loads(row[2])['activity']))
            db.execute('UPDATE voice_requests SET result = ? WHERE id = ?', (json.dumps(result), event_id))
    return result


def save_patient(database, data):
    if not isinstance(data, dict) or set(data) != {'id', 'name', 'floor'}:
        raise ValueError('Expected id (null for a new person), name, and floor.')
    if data['id'] is not None and (type(data['id']) is not int or data['id'] < 1):
        raise ValueError('id must be a positive integer or null.')
    for key in ('name', 'floor'):
        if not isinstance(data[key], str) or not data[key].strip() or len(data[key]) > 100:
            raise ValueError(key + ' must be nonempty and at most 100 characters.')
    with sqlite3.connect(database) as db:
        if data['id'] is None:
            cursor = db.execute('INSERT INTO patients (name, floor) VALUES (?, ?)', (data['name'].strip(), data['floor'].strip()))
            patient_id = cursor.lastrowid
        else:
            cursor = db.execute('UPDATE patients SET name = ?, floor = ? WHERE id = ?', (data['name'].strip(), data['floor'].strip(), data['id']))
            if not cursor.rowcount:
                raise ValueError('Unknown resident id.')
            patient_id = data['id']
    return {'id': patient_id, 'name': data['name'].strip(), 'floor': data['floor'].strip()}


def list_patients(database):
    with sqlite3.connect(database) as db:
        db.row_factory = sqlite3.Row
        return [dict(row) for row in db.execute('SELECT id, name, floor FROM patients ORDER BY id')]


def list_invitations(database, patient_id=None, pending_only=False):
    with sqlite3.connect(database) as db:
        db.row_factory = sqlite3.Row
        query = '''SELECT i.*, sender.name AS sender_name, recipient.name AS recipient_name
                   FROM social_invitations i JOIN patients sender ON sender.id = i.sender_id
                   JOIN patients recipient ON recipient.id = i.recipient_id'''
        clauses, parameters = [], []
        if patient_id is not None:
            clauses.append('i.recipient_id = ?')
            parameters.append(patient_id)
        if pending_only:
            clauses.append('i.played_at_utc IS NULL')
        if clauses:
            query += ' WHERE ' + ' AND '.join(clauses)
        query += ' ORDER BY i.id ' + ('ASC LIMIT 1' if pending_only else 'DESC LIMIT 100')
        return [dict(row) for row in db.execute(query, parameters)]


def mark_invitation_played(database, patient_id, invitation_id):
    timestamp = datetime.now(timezone.utc).isoformat(timespec='seconds')
    with sqlite3.connect(database) as db:
        cursor = db.execute('UPDATE social_invitations SET played_at_utc = COALESCE(played_at_utc, ?) WHERE id = ? AND recipient_id = ?',
                            (timestamp, invitation_id, patient_id))
        if not cursor.rowcount:
            raise ValueError('Invitation not found for this resident.')
    return {'id': invitation_id, 'status': 'played'}
