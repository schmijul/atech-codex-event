"""Browse the medication database at http://127.0.0.1:8000."""

import json
import re
import sqlite3
from datetime import datetime, time, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from voice_tools import (TOOLS, execute_tool, initialize_database, list_requests,
                         list_patients, save_patient, list_invitations, mark_invitation_played, dispatch_social_request)

DATABASE = Path(__file__).with_name('meds_taken.sqlite3')
PAGE = '''<!doctype html>
<html lang="en">
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Medication log</title>
<style>
:root{font-family:'Helvetica Neue',Arial,sans-serif;color:#2f3437;background:#f7f6f3}
*{box-sizing:border-box}body{margin:0}main{max-width:1040px;margin:auto;padding:64px 28px}
header{display:flex;justify-content:space-between;align-items:center;gap:20px;margin-bottom:40px}
.eyebrow,th{font-size:11px;text-transform:uppercase;letter-spacing:.12em;color:#787774}
h1{font:normal 52px Georgia,serif;letter-spacing:-.04em;margin:12px 0}p{color:#787774;line-height:1.6}
button{background:#2f3437;color:white;border:0;border-radius:4px;padding:12px 18px;cursor:pointer}
button:disabled{opacity:.4;cursor:default}button:hover:enabled{background:#444}
.metrics{display:grid;grid-template-columns:1fr 1fr 1.5fr;border:1px solid #eaeaea;border-radius:8px;background:white;margin-bottom:40px}
.metric{padding:28px;border-right:1px solid #eaeaea}.metric:last-child{border:0}
.value{font-size:32px;margin-top:14px;letter-spacing:-.03em}.value small{font-size:14px;color:#787774}
section{background:white;border:1px solid #eaeaea;border-radius:8px;overflow:hidden}
.schedule{background:white;border:1px solid #eaeaea;border-radius:8px;padding:24px;margin-bottom:24px}
.schedule form{display:flex;align-items:end;gap:12px;flex-wrap:wrap;margin-top:16px}
.schedule label{display:grid;gap:6px;font-size:12px;color:#787774}
.schedule input{font:inherit;padding:10px;border:1px solid #ddd;border-radius:4px}
.schedule-status{font-size:13px;margin:12px 0 0}
.section-head{padding:24px;display:flex;align-items:center;justify-content:space-between;gap:20px}
h2{font-size:18px;font-weight:500;margin:0}table{width:100%;border-collapse:collapse;text-align:left}
th,td{padding:17px 24px;border-top:1px solid #eaeaea}td{font-size:14px}
.tag{background:#edf3ec;color:#346538;padding:5px 9px;border-radius:4px;font-size:12px}
footer{display:flex;justify-content:space-between;align-items:center;gap:16px;margin-top:20px;font-size:12px;color:#787774}
.controls{display:flex;gap:8px}.controls button{padding:8px 12px}#error{color:#9f2f2d}#empty{padding:32px 24px;border-top:1px solid #eaeaea}
@media(max-width:600px){main{padding:32px 16px}h1{font-size:40px}.metrics{grid-template-columns:1fr}.metric{border-right:0;border-bottom:1px solid #eaeaea}th,td{padding:16px 12px}footer{flex-wrap:wrap}.section-head{padding:20px 12px}}
</style>
<main>
<header><div><div class="eyebrow">Atech / Home assistant</div><h1>Medication log</h1><p>Button confirmations, recorded as they happen.</p></div><button id="refresh">Refresh</button></header>
<div id="error" role="status"></div>
<section class="schedule"><h2>Daily reminder</h2><p>Choose when the board should start its medication reminder. The time uses this browser’s local timezone: <span id="schedule-zone"></span>.</p><form id="schedule-form"><label>Start time<input id="reminder-time" type="time" required></label><button id="save-reminder">Save reminder</button><button id="disable-reminder" type="button">Turn off</button></form><p class="schedule-status" id="schedule-status" role="status">Loading reminder…</p></section>
<div class="metrics"><div class="metric"><div class="eyebrow">Today</div><div class="value" id="today">—</div></div><div class="metric"><div class="eyebrow">All confirmations</div><div class="value" id="total">—</div></div><div class="metric"><div class="eyebrow">Last recorded</div><div class="value" id="latest">—</div></div></div>
<section><div class="section-head"><h2>Confirmation history</h2><span class="eyebrow">Newest first</span></div><table><thead><tr><th>ID</th><th>Date & time</th><th>Event</th></tr></thead><tbody id="rows"></tbody></table><div id="empty" hidden>No confirmations yet. Start the logger and press the medication button to record one.</div></section>
<footer><span id="status">Reading meds_taken.sqlite3…</span><div class="controls"><button id="prev">Previous</button><button id="next">Next</button></div></footer>
<p style="font-size:12px">Times shown in <span id="zone"></span>. A confirmation records a button press; no medication schedule is configured.</p>
</main>
<script>
let events=[], page=0;
const size=50, el=id=>document.getElementById(id);
const date=value=>new Date(value);
const sameDay=(a,b)=>a.getFullYear()===b.getFullYear()&&a.getMonth()===b.getMonth()&&a.getDate()===b.getDate();
const timeZone=Intl.DateTimeFormat().resolvedOptions().timeZone;
el('zone').textContent=timeZone;el('schedule-zone').textContent=timeZone;
function render(){
 const now=new Date();
 el('today').textContent=events.filter(e=>sameDay(date(e.taken_at_utc),now)).length;
 el('total').textContent=events.length;
 el('latest').textContent=events.length?date(events[0].taken_at_utc).toLocaleString([], {month:'short',day:'numeric',hour:'2-digit',minute:'2-digit'}):'No events';
 el('rows').replaceChildren();
 for(const event of events.slice(page*size,(page+1)*size)){
  const tr=document.createElement('tr');
  for(const value of [event.id,date(event.taken_at_utc).toLocaleString(),'Confirmed']){
   const td=document.createElement('td');td.textContent=value;tr.append(td);
  }
  tr.lastChild.className='confirmation';el('rows').append(tr);
 }
 el('empty').hidden=events.length>0;
 el('prev').disabled=page===0;el('next').disabled=(page+1)*size>=events.length;
}
async function refresh(){
 el('refresh').disabled=true;
 try{
  const response=await fetch('/api/events',{cache:'no-store'});
  const data=await response.json();if(!response.ok)throw Error(data.error);
  events=data;page=Math.min(page,Math.max(0,Math.ceil(events.length/size)-1));render();
  el('error').textContent='';el('status').textContent='meds_taken.sqlite3 · Updated '+new Date().toLocaleTimeString()+' · Refreshes every 5s';
 }catch(error){el('error').textContent='Could not read the database: '+error.message;el('status').textContent='Update failed · Retrying every 5s';}
 finally{el('refresh').disabled=false;}
}
async function loadReminder(){
 try{
  const response=await fetch('/api/reminder',{cache:'no-store'}),data=await response.json();
  if(!response.ok)throw Error(data.error);
  if(data.enabled){el('reminder-time').value=data.time;el('schedule-status').textContent='Daily reminder starts at '+data.time+' ('+data.timezone+').';}
  else el('schedule-status').textContent='No daily reminder is scheduled.';
 }catch(error){el('schedule-status').textContent='Could not load reminder: '+error.message;}
}
el('schedule-form').onsubmit=async event=>{
 event.preventDefault();el('save-reminder').disabled=true;
 try{
  const response=await fetch('/api/reminder',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({time:el('reminder-time').value,timezone:timeZone})});
  const data=await response.json();if(!response.ok)throw Error(data.error);
  el('schedule-status').textContent='Daily reminder starts at '+data.time+' ('+data.timezone+').';
 }catch(error){el('schedule-status').textContent='Could not save reminder: '+error.message;}
 finally{el('save-reminder').disabled=false;}
};
el('disable-reminder').onclick=async()=>{
 el('disable-reminder').disabled=true;
 try{const response=await fetch('/api/reminder',{method:'DELETE'}),data=await response.json();if(!response.ok)throw Error(data.error);el('schedule-status').textContent='No daily reminder is scheduled.';}
 catch(error){el('schedule-status').textContent='Could not turn off reminder: '+error.message;}
 finally{el('disable-reminder').disabled=false;}
};
el('refresh').onclick=refresh;
el('prev').onclick=()=>{page--;render()};el('next').onclick=()=>{page++;render()};
refresh();loadReminder();setInterval(refresh,5000);
</script>
</html>'''


class Handler(BaseHTTPRequestHandler):
    def read_json(self):
        length = int(self.headers.get('Content-Length', '0'))
        if not 0 < length <= 16384 or self.headers.get_content_type() != 'application/json':
            raise ValueError('Send a JSON object of at most 16384 bytes.')
        data = json.loads(self.rfile.read(length))
        if not isinstance(data, dict):
            raise ValueError('Expected a JSON object.')
        return data

    def do_POST(self):
        played = re.fullmatch(r'/api/patients/([1-9]\d*)/invitations/([1-9]\d*)/played', self.path)
        dispatch = re.fullmatch(r'/api/social/requests/([1-9]\d*)/dispatch', self.path)
        if self.path == '/api/patients' or played or dispatch:
            try:
                data = self.read_json()
                if played or dispatch:
                    if data:
                        raise ValueError('Expected an empty JSON object.')
                    result = dispatch_social_request(DATABASE, int(dispatch[1])) if dispatch else mark_invitation_played(DATABASE, int(played[1]), int(played[2]))
                else:
                    result = save_patient(DATABASE, data)
                self.send_json(200, result)
            except (ValueError, UnicodeDecodeError) as error:
                self.send_json(400, {'error': str(error)})
            except sqlite3.Error:
                self.send_json(503, {'error': 'Database unavailable.'})
            return
        if self.path.startswith('/api/voice/tools/'):
            try:
                data = self.read_json()
                if not {'request_id', 'arguments'} <= set(data) or set(data) - {'request_id', 'arguments', 'patient_id'}:
                    raise ValueError('Expected request_id, arguments, and optional patient_id.')
                result = execute_tool(DATABASE, self.path.removeprefix('/api/voice/tools/'), data['arguments'], data['request_id'], data.get('patient_id', 1))
                self.send_json(200, result)
            except (ValueError, UnicodeDecodeError, ZoneInfoNotFoundError) as error:
                self.send_json(400, {'error': str(error)})
            except sqlite3.Error:
                self.send_json(503, {'error': 'Database unavailable. Retry only with the same request_id.'})
            return
        if self.path == '/api/reminder':
            try:
                length = int(self.headers.get('Content-Length', '0'))
                if not 0 < length <= 4096 or self.headers.get_content_type() != 'application/json':
                    raise ValueError('Send a JSON object with time and timezone.')
                data = json.loads(self.rfile.read(length))
                if not isinstance(data, dict) or set(data) != {'time', 'timezone'}:
                    raise ValueError('Expected time and timezone.')
                if not isinstance(data['time'], str) or not re.fullmatch(r'\d{2}:\d{2}', data['time']):
                    raise ValueError('time must use HH:MM format.')
                reminder_time = time.fromisoformat(data['time'])
                if not isinstance(data['timezone'], str):
                    raise ValueError('timezone must be an IANA timezone name.')
                ZoneInfo(data['timezone'])
                with sqlite3.connect(DATABASE) as db:
                    db.execute('INSERT INTO dashboard_settings (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value', ('reminder_time', reminder_time.strftime('%H:%M')))
                    db.execute('INSERT INTO dashboard_settings (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value', ('reminder_timezone', data['timezone']))
                self.send_json(200, {'enabled': True, 'time': reminder_time.strftime('%H:%M'), 'timezone': data['timezone']})
            except (ValueError, UnicodeDecodeError, ZoneInfoNotFoundError) as error:
                self.send_json(400, {'error': str(error)})
            except sqlite3.Error:
                self.send_json(503, {'error': 'Database unavailable.'})
            return
        if self.path != '/api/events':
            self.send_error(404)
            return
        try:
            length = int(self.headers.get('Content-Length', '0'))
            if not 0 < length <= 4096:
                raise ValueError('Send a JSON object (maximum 4096 bytes).')
            if self.headers.get_content_type() != 'application/json':
                raise ValueError('Use Content-Type: application/json.')
            data = json.loads(self.rfile.read(length))
            if not isinstance(data, dict) or set(data) - {'taken_at_utc'}:
                raise ValueError('Expected {} or an object containing taken_at_utc.')
            taken_at = datetime.now(timezone.utc)
            if 'taken_at_utc' in data:
                if not isinstance(data['taken_at_utc'], str):
                    raise ValueError('taken_at_utc must be an ISO-8601 timestamp with timezone.')
                taken_at = datetime.fromisoformat(data['taken_at_utc'].replace('Z', '+00:00'))
                if taken_at.tzinfo is None:
                    raise ValueError('taken_at_utc must include a timezone.')
            timestamp = taken_at.astimezone(timezone.utc).isoformat(timespec='seconds')
            with sqlite3.connect(DATABASE) as db:
                cursor = db.execute('INSERT INTO medication_events (taken_at_utc) VALUES (?)', (timestamp,))
                event_id = cursor.lastrowid
            self.send_json(201, {'id': event_id, 'taken_at_utc': timestamp})
        except (ValueError, UnicodeDecodeError) as error:
            self.send_json(400, {'error': str(error)})
        except sqlite3.Error:
            self.send_json(503, {'error': 'Database unavailable. Try again shortly.'})

    def do_DELETE(self):
        if self.path != '/api/reminder':
            self.send_error(404)
            return
        try:
            with sqlite3.connect(DATABASE) as db:
                db.execute("DELETE FROM dashboard_settings WHERE key IN ('reminder_time', 'reminder_timezone')")
            self.send_json(200, {'enabled': False})
        except sqlite3.Error:
            self.send_json(503, {'error': 'Database unavailable.'})

    def send_json(self, status, data):
        body = json.dumps(data).encode()
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Cache-Control', 'no-store')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        inbox = re.fullmatch(r'/api/patients/([1-9]\d*)/invitations(/next)?', self.path)
        if self.path in ('/api/patients', '/api/social/invitations') or inbox:
            try:
                if self.path == '/api/patients':
                    result = list_patients(DATABASE)
                elif inbox:
                    rows = list_invitations(DATABASE, int(inbox[1]), bool(inbox[2]))
                    result = {'invitation': rows[0] if rows else None} if inbox[2] else rows
                else:
                    result = list_invitations(DATABASE)
                self.send_json(200, result)
            except sqlite3.Error:
                self.send_json(503, {'error': 'Database unavailable.'})
            return
        if self.path in ('/api/voice/tools', '/api/voice/requests'):
            try:
                self.send_json(200, TOOLS if self.path.endswith('/tools') else list_requests(DATABASE))
            except sqlite3.Error:
                self.send_json(503, {'error': 'Database unavailable.'})
            return
        if self.path == '/':
            body, content_type, status = PAGE.encode(), 'text/html; charset=utf-8', 200
        elif self.path == '/api/reminder':
            try:
                with sqlite3.connect(DATABASE.as_uri() + '?mode=ro', uri=True) as db:
                    settings = dict(db.execute("SELECT key, value FROM dashboard_settings WHERE key IN ('reminder_time', 'reminder_timezone')"))
                if 'reminder_time' in settings and 'reminder_timezone' in settings:
                    body = json.dumps({'enabled': True, 'time': settings['reminder_time'], 'timezone': settings['reminder_timezone']}).encode()
                else:
                    body = json.dumps({'enabled': False}).encode()
                status = 200
            except sqlite3.Error:
                body, status = json.dumps({'error': 'Database unavailable.'}).encode(), 503
            content_type = 'application/json'
        elif self.path == '/api/reminder/next':
            try:
                with sqlite3.connect(DATABASE.as_uri() + '?mode=ro', uri=True) as db:
                    settings = dict(db.execute("SELECT key, value FROM dashboard_settings WHERE key IN ('reminder_time', 'reminder_timezone')"))
                if 'reminder_time' not in settings or 'reminder_timezone' not in settings:
                    body = b'disabled'
                else:
                    now_utc = datetime.now(timezone.utc)
                    local_now = now_utc.astimezone(ZoneInfo(settings['reminder_timezone']))
                    scheduled_local = datetime.combine(local_now.date(), time.fromisoformat(settings['reminder_time']), ZoneInfo(settings['reminder_timezone']))
                    body = f'{int(scheduled_local.timestamp())}|{int(now_utc.timestamp())}|{local_now.date().isoformat()}'.encode()
                status = 200
            except (sqlite3.Error, ValueError, ZoneInfoNotFoundError):
                body, status = b'Unable to read reminder schedule.', 503
            content_type = 'text/plain; charset=utf-8'
        elif self.path == '/api/events':
            try:
                # Read-only connections let the serial logger keep writing independently.
                with sqlite3.connect(DATABASE.as_uri() + '?mode=ro', uri=True) as db:
                    db.row_factory = sqlite3.Row
                    rows = db.execute('SELECT id, taken_at_utc FROM medication_events ORDER BY taken_at_utc DESC, id DESC')
                    body = json.dumps([dict(row) for row in rows]).encode()
                status = 200
            except sqlite3.Error:
                body = json.dumps({'error': 'Database unavailable. Start meds_logger.py and check the database file.'}).encode()
                status = 503
            content_type = 'application/json'
        else:
            self.send_error(404)
            return
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.send_header('Cache-Control', 'no-store')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)


if __name__ == '__main__':
    initialize_database(DATABASE)
    print('Dashboard and API listening on all network interfaces, port 8000', flush=True)
    try:
        ThreadingHTTPServer(('0.0.0.0', 8000), Handler).serve_forever()
    except KeyboardInterrupt:
        print('\nStopped.')
