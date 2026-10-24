"""Browse the medication database at http://127.0.0.1:8000."""

import json
import sqlite3
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

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
el('zone').textContent=Intl.DateTimeFormat().resolvedOptions().timeZone;
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
el('refresh').onclick=refresh;
el('prev').onclick=()=>{page--;render()};el('next').onclick=()=>{page++;render()};
refresh();setInterval(refresh,5000);
</script>
</html>'''


class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
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

    def send_json(self, status, data):
        body = json.dumps(data).encode()
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Cache-Control', 'no-store')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == '/':
            body, content_type, status = PAGE.encode(), 'text/html; charset=utf-8', 200
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
    with sqlite3.connect(DATABASE) as db:
        db.execute('CREATE TABLE IF NOT EXISTS medication_events (id INTEGER PRIMARY KEY, taken_at_utc TEXT NOT NULL)')
    print('Dashboard and API listening on all network interfaces, port 8000', flush=True)
    try:
        ThreadingHTTPServer(('0.0.0.0', 8000), Handler).serve_forever()
    except KeyboardInterrupt:
        print('\nStopped.')
