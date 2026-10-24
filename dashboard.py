"""Browse the medication database at http://127.0.0.1:8000."""

import errno
import json
import os
import re
import sqlite3
import threading
import urllib.error
import urllib.request
from datetime import date, datetime, time, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from voice_tools import (TOOLS, execute_tool, initialize_database, list_requests,
                         list_patients, save_patient, list_invitations,
                         mark_invitation_played, dispatch_social_request)
from voice_tools import create_lunch_question, get_lunch_question, update_lunch_question

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
<header><div><div class="eyebrow">Atech / Home assistant</div><h1>Medication log</h1><p>Button confirmations, recorded as they happen.</p><a href="/staff">Staff view →</a></div><button id="refresh">Refresh</button></header>
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

STAFF_PAGE = '''<!doctype html>
<html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Tagly · Staff</title>
<style>
:root{font-family:'Helvetica Neue',Arial,sans-serif;color:#2f3437;background:#f7f6f3}*{box-sizing:border-box}body{margin:0}main{max-width:1040px;margin:auto;padding:56px 28px}header{display:flex;justify-content:space-between;align-items:center;gap:20px;margin-bottom:32px}.eyebrow,th{font-size:11px;text-transform:uppercase;letter-spacing:.12em;color:#787774}h1{font:normal 48px Georgia,serif;letter-spacing:-.04em;margin:12px 0}h2{font-size:18px;font-weight:500;margin:0}p{color:#787774;line-height:1.6}a{color:#2f3437}button{background:#2f3437;color:white;border:0;border-radius:4px;padding:10px 14px;cursor:pointer}button:disabled{opacity:.4;cursor:default}button.secondary{background:#eee;color:#2f3437}section,.schedule{background:white;border:1px solid #eaeaea;border-radius:8px;overflow:hidden;margin-bottom:20px}.schedule{padding:24px}.section-head{padding:22px 24px;display:flex;justify-content:space-between;align-items:center;gap:16px}table{width:100%;border-collapse:collapse;text-align:left}th,td{padding:15px 20px;border-top:1px solid #eaeaea}td{font-size:14px}.status{background:#edf3ec;color:#346538;padding:5px 9px;border-radius:4px;font-size:12px}.alert{background:#f8eeee;color:#8c3030}.muted{color:#787774}.alert-row{display:flex;align-items:center;justify-content:space-between;gap:16px;padding:18px 24px;border-top:1px solid #eaeaea}.alert-actions{display:flex;gap:8px}.schedule form,.test-actions{display:flex;gap:10px;align-items:end;flex-wrap:wrap}.schedule label{display:grid;gap:6px;font-size:12px;color:#787774}.schedule input{font:inherit;padding:10px;border:1px solid #ddd;border-radius:4px}.schedule p{margin:10px 0 0;font-size:13px}.test-actions{padding:18px 24px;border-top:1px solid #eaeaea}.test-actions button{background:#6c6c66}.family{padding:22px 24px}.family p{color:#2f3437;white-space:pre-line}.empty{padding:20px 24px;border-top:1px solid #eaeaea;color:#787774}footer{font-size:12px;color:#787774;margin:16px 0}#message{color:#8c3030}@media(max-width:600px){main{padding:32px 16px}h1{font-size:40px}.section-head,.alert-row{padding:18px 14px;align-items:flex-start;flex-direction:column}th,td{padding:13px 10px}.family{padding:18px 14px}}
</style><main>
<header><div><div class="eyebrow">Atech / Tagly · Staff</div><h1>Daily care</h1><p>Patient 1 · today’s routine and requests</p><a href="/">Medication log →</a></div><button id="refresh">Refresh</button></header>
<div id="message" role="status"></div>
<section><div class="section-head"><h2>Today’s status</h2><span class="eyebrow" id="today-date"></span></div><table><thead><tr><th>Routine</th><th>Status</th><th>Last activity</th></tr></thead><tbody id="status-rows"></tbody></table></section>
<section><div class="section-head"><h2>Open alerts</h2><span class="eyebrow">Staff action needed</span></div><div id="alerts"></div></section>
<section><div class="section-head"><h2>Wake deadline</h2><span class="eyebrow">Patient 1</span></div><div class="schedule"><form id="wake-form"><label>Deadline<input id="wake-time" type="time" value="09:00" required></label><button>Save deadline</button></form><p id="wake-status">Default: 09:00 local time.</p></div></section>
<section><div class="section-head"><h2>Today’s event log</h2><span class="eyebrow">Newest first</span></div><div style="overflow:auto"><table><thead><tr><th>Time</th><th>Event</th><th>Source</th></tr></thead><tbody id="event-rows"></tbody></table></div><div class="empty" id="event-empty" hidden>No events recorded today.</div><div class="test-actions"><span class="eyebrow">TEST ONLY</span><button data-test="presence">Gets up</button><button data-test="meds_taken">Takes pills</button><button data-test="company">Wants company</button></div></section>
<section><div class="section-head"><h2>Family update</h2><span class="eyebrow">Based on today’s recorded events</span></div><div class="family"><button id="family-button">Write update</button><p id="family-text"></p></div></section>
<footer id="updated">Loading today’s activity… · Refreshes every 5 seconds</footer></main>
<script>
const el=id=>document.getElementById(id),labels={presence:'Up',meds_taken:'Pills confirmed',company:'Company requested',no_wake:'No morning activity',meds_missed:'Pills not confirmed'};
function time(value){return new Date(value).toLocaleTimeString([], {hour:'2-digit',minute:'2-digit'})}
async function call(url,options={}){const r=await fetch(url,{cache:'no-store',...options});const d=await r.json();if(!r.ok)throw Error(d.error||'Request failed');return d}
async function refresh(){el('refresh').disabled=true;try{const d=await call('/api/staff');el('today-date').textContent=new Date().toLocaleDateString([], {weekday:'long',month:'short',day:'numeric'});el('status-rows').replaceChildren();for(const item of d.status){const tr=document.createElement('tr');for(const value of [item.name,item.status,item.at?time(item.at):'—']){const td=document.createElement('td');td.textContent=value;if(value==='Up'||value==='Confirmed')td.innerHTML='<span class="status">'+value+'</span>';tr.append(td)}el('status-rows').append(tr)}
el('alerts').replaceChildren();if(!d.alerts.length)el('alerts').innerHTML='<div class="empty">No open alerts.</div>';for(const a of d.alerts){const row=document.createElement('div');row.className='alert-row';const title=document.createElement('strong');title.textContent=a.title;const actions=document.createElement('div');actions.className='alert-actions';if(a.type==='company'){const way=document.createElement('button');way.textContent=a.status==='on_the_way'?'On my way ✓':'On my way';way.disabled=a.status==='on_the_way';way.onclick=()=>alertAction(a.id,'on_my_way');actions.append(way)}const done=document.createElement('button');done.className='secondary';done.textContent='Done';done.onclick=()=>alertAction(a.id,'done');actions.append(done);row.append(title,actions);el('alerts').append(row)}
el('event-rows').replaceChildren();for(const event of d.events){const tr=document.createElement('tr');for(const value of [time(event.at_utc),labels[event.type]||event.type,event.source]){const td=document.createElement('td');td.textContent=value;tr.append(td)}el('event-rows').append(tr)}el('event-empty').hidden=d.events.length>0;if(d.wake.enabled)el('wake-time').value=d.wake.time;el('wake-status').textContent='Local time · '+d.wake.timezone;el('message').textContent='';el('updated').textContent='Updated '+new Date().toLocaleTimeString()+' · Refreshes every 5 seconds'}catch(e){el('message').textContent='Could not load staff view: '+e.message}finally{el('refresh').disabled=false}}
async function alertAction(id,action){try{await call('/api/alerts/'+id,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({action})});await refresh()}catch(e){el('message').textContent=e.message}}
el('refresh').onclick=refresh;document.querySelectorAll('[data-test]').forEach(b=>b.onclick=async()=>{b.disabled=true;try{await call('/api/events',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({type:b.dataset.test,source:'simulated'})});await refresh()}catch(e){el('message').textContent=e.message}finally{b.disabled=false}});
el('wake-form').onsubmit=async e=>{e.preventDefault();try{const d=await call('/api/wake',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({time:el('wake-time').value,timezone:Intl.DateTimeFormat().resolvedOptions().timeZone})});el('wake-status').textContent='Deadline set to '+d.time+' · '+d.timezone;await refresh()}catch(error){el('message').textContent=error.message}};
el('family-button').onclick=async()=>{el('family-button').disabled=true;try{const d=await call('/api/family-update?patient_id=1',{method:'POST'});el('family-text').textContent=d.message}catch(e){el('message').textContent=e.message}finally{el('family-button').disabled=false}};
refresh();setInterval(refresh,5000);
</script></html>'''


VOICE_PANEL = '''<section style="margin:24px 0;background:white;border:1px solid #ddd;border-radius:8px;padding:24px"><h2>Voice requests</h2><p>Requests received from the board · updates every 2 seconds</p><div id="voice-requests" role="status">Loading…</div></section>
<script>(()=>{async function loadVoice(){const box=document.getElementById('voice-requests');try{const response=await fetch('/api/voice/requests',{cache:'no-store'});if(!response.ok)throw Error('Could not load requests');const rows=await response.json();box.replaceChildren();if(!rows.length){box.textContent='No voice requests yet.';return}const names={request_help:'Help requested',request_floor_activity:'Company / activity',choose_lunch:'Lunch preference',medication_reminder:'Medication reminder'};for(const row of rows.slice(0,20)){const card=document.createElement('div');card.style.cssText='border-top:1px solid #eee;padding:16px 0';const title=document.createElement('strong');title.textContent=(names[row.tool]||row.tool)+' · '+new Date(row.result.created_at_utc).toLocaleTimeString();const details=document.createElement('p');details.textContent=Object.entries(row.arguments).filter(([k,v])=>v!==''&&k!=='timezone').map(([k,v])=>k+': '+v).join(' · ');const status=document.createElement('div');status.textContent=row.result.message||row.result.status;card.append(title,details,status);box.append(card)}}catch(error){box.textContent=error.message}}loadVoice();setInterval(loadVoice,2000)})();</script>'''
PAGE = PAGE.replace('</main>', VOICE_PANEL + '</main>')
STAFF_PAGE = STAFF_PAGE.replace('</main>', VOICE_PANEL + '</main>')

LUNCH_PANEL = '''<section class="schedule" style="padding:24px;margin-bottom:24px"><h2>Ask patient about lunch</h2><p>The board speaks these options. The patient holds button 1 to answer.</p>
<form id="lunch-form"><label>Option 1<input id="lunch-option-one" value="Vegetarian pasta" maxlength="80" required><select id="lunch-category-one"><option value="vegetarian">Vegetarian</option><option value="meat">Meat</option><option value="vegan">Vegan</option><option value="fish">Fish</option><option value="other">Other</option></select></label>
<label>Option 2<input id="lunch-option-two" value="Chicken and rice" maxlength="80" required><select id="lunch-category-two"><option value="meat">Meat</option><option value="vegetarian">Vegetarian</option><option value="vegan">Vegan</option><option value="fish">Fish</option><option value="other">Other</option></select></label>
<button id="ask-lunch">Ask patient</button><button id="cancel-lunch" type="button" hidden>Cancel question</button></form><p id="lunch-status" role="status">Ready to ask.</p></section>
<script>(()=>{const byId=id=>document.getElementById(id);let current=null;async function loadLunch(){try{const response=await fetch('/api/lunch',{cache:'no-store'});if(!response.ok)throw Error('Could not load lunch status');current=(await response.json()).question;const active=current&&['queued','awaiting_answer'].includes(current.status);byId('ask-lunch').disabled=!!active;byId('cancel-lunch').hidden=!active;const labels={queued:'Queued — waiting for the board to speak.',awaiting_answer:'Question spoken — waiting for the patient’s answer.',cancelled:'Question cancelled. Ready to ask again.'};byId('lunch-status').textContent=!current?'Ready to ask.':current.status==='answered'?'Patient answered: '+(current.details||current.choice)+' · '+current.choice:labels[current.status]}catch(error){byId('lunch-status').textContent=error.message}}
byId('lunch-form').onsubmit=async event=>{event.preventDefault();byId('ask-lunch').disabled=true;try{const options=[{label:byId('lunch-option-one').value,choice:byId('lunch-category-one').value},{label:byId('lunch-option-two').value,choice:byId('lunch-category-two').value}];const response=await fetch('/api/lunch/ask',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({patient_id:1,options})});const data=await response.json();if(!response.ok)throw Error(data.error);await loadLunch()}catch(error){byId('lunch-status').textContent=error.message;byId('ask-lunch').disabled=false}};
byId('cancel-lunch').onclick=async()=>{if(!current)return;await fetch('/api/lunch/'+current.id+'/cancel',{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'});await loadLunch()};loadLunch();setInterval(loadLunch,2000)})();</script>'''
PAGE = PAGE.replace('<div class="metrics">', LUNCH_PANEL + '<div class="metrics">')
STAFF_PAGE = STAFF_PAGE.replace('<section><div class="section-head"><h2>Wake deadline', LUNCH_PANEL + '<section><div class="section-head"><h2>Wake deadline')


def connect(readonly=False):
    if readonly:
        return sqlite3.connect(DATABASE.as_uri() + '?mode=ro', uri=True)
    return sqlite3.connect(DATABASE)


def settings_for(db):
    return dict(db.execute('SELECT key, value FROM dashboard_settings'))


def default_timezone(settings):
    configured = settings.get('wake_timezone') or settings.get('reminder_timezone')
    if configured:
        return configured
    local_zone = datetime.now().astimezone().tzinfo
    return getattr(local_zone, 'key', None) or 'UTC'


def day_bounds(zone_name, now=None):
    zone = ZoneInfo(zone_name)
    local_now = (now or datetime.now(timezone.utc)).astimezone(zone)
    start = datetime.combine(local_now.date(), time.min, zone).astimezone(timezone.utc)
    end = datetime.combine(local_now.date() + timedelta(days=1), time.min, zone).astimezone(timezone.utc)
    return local_now, start.isoformat(timespec='seconds'), end.isoformat(timespec='seconds')


def check_alerts():
    now = datetime.now(timezone.utc)
    stamp = now.isoformat(timespec='seconds')
    with connect() as db:
        db.row_factory = sqlite3.Row
        settings = settings_for(db)
        zone_name = default_timezone(settings)
        local_now, start, end = day_bounds(zone_name, now)
        patient_id = 1
        any_today = db.execute('SELECT 1 FROM device_events WHERE patient_id=? AND at_utc>=? AND at_utc<? LIMIT 1', (patient_id, start, end)).fetchone()
        if not any_today:
            any_today = db.execute('SELECT 1 FROM medication_events WHERE taken_at_utc>=? AND taken_at_utc<? LIMIT 1', (start, end)).fetchone()
        if not any_today and local_now.time().replace(tzinfo=None) > time.fromisoformat(settings.get('wake_time', '09:00')):
            existing = db.execute("SELECT 1 FROM alerts WHERE patient_id=? AND type='no_wake' AND created_utc>=? AND created_utc<?", (patient_id, start, end)).fetchone()
            if not existing:
                db.execute("INSERT INTO alerts (patient_id,type,title,created_utc,status) VALUES (?,?,?,?, 'open')", (patient_id, 'no_wake', 'No morning activity', stamp))
        reminder_time = settings.get('reminder_time')
        reminder_zone = settings.get('reminder_timezone')
        if reminder_time and reminder_zone:
            local_reminder_now, reminder_start, reminder_end = day_bounds(reminder_zone, now)
            reminder_local = datetime.combine(local_reminder_now.date(), time.fromisoformat(reminder_time), ZoneInfo(reminder_zone))
            reminder_utc = reminder_local.astimezone(timezone.utc)
            if now > reminder_utc + timedelta(minutes=30):
                got_meds = db.execute('SELECT 1 FROM device_events WHERE patient_id=? AND type="meds_taken" AND at_utc>=? AND at_utc<? LIMIT 1', (patient_id, reminder_utc.isoformat(timespec='seconds'), reminder_end)).fetchone()
                if not got_meds:
                    got_meds = db.execute('SELECT 1 FROM medication_events WHERE taken_at_utc>=? AND taken_at_utc<? LIMIT 1', (reminder_utc.isoformat(timespec='seconds'), reminder_end)).fetchone()
                existing = db.execute("SELECT 1 FROM alerts WHERE patient_id=? AND type='meds_missed' AND created_utc>=? AND created_utc<?", (patient_id, reminder_start, reminder_end)).fetchone()
                if not got_meds and not existing:
                    db.execute("INSERT INTO alerts (patient_id,type,title,created_utc,status) VALUES (?,?,?,?, 'open')", (patient_id, 'meds_missed', 'Pills not confirmed', stamp))
        # Activity after an alert closes morning and medication alerts automatically.
        for alert in db.execute("SELECT id,type,created_utc FROM alerts WHERE patient_id=? AND status='open' AND type IN ('no_wake','meds_missed')", (patient_id,)).fetchall():
            event_type = 'meds_taken' if alert['type'] == 'meds_missed' else None
            if event_type:
                activity = db.execute('SELECT 1 FROM device_events WHERE patient_id=? AND type=? AND at_utc>=? LIMIT 1', (patient_id, event_type, alert['created_utc'])).fetchone()
                if not activity:
                    activity = db.execute('SELECT 1 FROM medication_events WHERE taken_at_utc>=? LIMIT 1', (alert['created_utc'],)).fetchone()
            else:
                activity = db.execute('SELECT 1 FROM device_events WHERE patient_id=? AND at_utc>=? LIMIT 1', (patient_id, alert['created_utc'])).fetchone()
                if not activity:
                    activity = db.execute('SELECT 1 FROM medication_events WHERE taken_at_utc>=? LIMIT 1', (alert['created_utc'],)).fetchone()
            if activity:
                db.execute("UPDATE alerts SET status='done',closed_utc=? WHERE id=?", (stamp, alert['id']))


def alert_worker():
    while True:
        try:
            check_alerts()
        except (sqlite3.Error, ValueError, ZoneInfoNotFoundError):
            pass
        threading.Event().wait(30)


def current_board_state(db, patient_id):
    db.row_factory = sqlite3.Row
    alert = db.execute("SELECT status FROM alerts WHERE patient_id=? AND type='company' AND status IN ('open','on_the_way') ORDER BY id DESC LIMIT 1", (patient_id,)).fetchone()
    if alert:
        word, say = ('UNTERWEGS', 'Das Team ist unterwegs.') if alert['status'] == 'on_the_way' else ('KOMMT GLEICH', 'Jemand kommt gleich zu Ihnen.')
    else:
        word, say = '', ''
    previous = db.execute('SELECT content,seq FROM board_state WHERE patient_id=?', (patient_id,)).fetchone()
    content = word + '\n' + say
    if previous is None:
        seq = 1
        db.execute('INSERT INTO board_state (patient_id,content,seq) VALUES (?,?,?)', (patient_id, content, seq))
    elif previous['content'] != content:
        seq = previous['seq'] + 1
        db.execute('UPDATE board_state SET content=?,seq=? WHERE patient_id=?', (content, seq, patient_id))
    else:
        seq = previous['seq']
    return {'word': word, 'say': say, 'seq': seq}


def family_message(events):
    if not events:
        return 'Heute liegen bisher keine Ereignisse vor. Wir melden uns, sobald es Neuigkeiten gibt.\nEN: There are no events recorded yet today. We will share an update when there is news.'
    names = {'presence': 'ist heute aufgestanden', 'meds_taken': 'hat die Medikamente bestätigt', 'company': 'hat um Gesellschaft gebeten'}
    facts = [names[event['type']] for event in events if event['type'] in names]
    german = 'Heute: ' + '; außerdem '.join(facts) + '. Wir wünschen einen angenehmen Tag.'
    english = 'Today: ' + '; also '.join({'presence':'got up','meds_taken':'confirmed taking medication','company':'asked for company'}[event['type']] for event in events if event['type'] in names) + '.'
    return german + '\nEN: ' + english


def create_family_message(events):
    api_key = os.environ.get('OPENAI_API_KEY')
    if not api_key:
        env_file = Path(__file__).with_name('.env')
        if env_file.exists():
            for line in env_file.read_text().splitlines():
                if line.strip().startswith('OPENAI_API_KEY='):
                    api_key = line.split('=', 1)[1].strip().strip('"\'')
                    break
    fallback = family_message(events)
    if not api_key or not events:
        return fallback
    facts = '\n'.join(f"{event['at_utc']}: {event['type']}" for event in events)
    payload = json.dumps({'model':'gpt-4o-mini','messages':[{'role':'system','content':'Write a warm, concise 2–3 sentence family update in German using only the supplied events. Add one final line beginning EN: with an accurate English translation. Never infer health, mood, or events.'},{'role':'user','content':facts}]}).encode()
    request = urllib.request.Request('https://api.openai.com/v1/chat/completions', data=payload, headers={'Authorization':'Bearer '+api_key,'Content-Type':'application/json'})
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            return json.loads(response.read())['choices'][0]['message']['content'].strip()
    except (urllib.error.URLError, KeyError, ValueError):
        return fallback


class Handler(BaseHTTPRequestHandler):
    def send_json(self, status, data):
        body = json.dumps(data, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Cache-Control', 'no-store')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def read_json(self):
        length = int(self.headers.get('Content-Length', '0'))
        if not 0 < length <= 4096 or self.headers.get_content_type() != 'application/json':
            raise ValueError('Send a JSON object (maximum 4096 bytes) with Content-Type: application/json.')
        value = json.loads(self.rfile.read(length))
        if not isinstance(value, dict):
            raise ValueError('Expected a JSON object.')
        return value

    def do_POST(self):
        path = urlparse(self.path)
        lunch_action = re.fullmatch(r'/api/lunch/([1-9]\d*)/(spoken|cancel)', path.path)
        if path.path == '/api/lunch/ask' or lunch_action:
            try:
                data = self.read_json()
                if lunch_action:
                    if data: raise ValueError('Expected an empty object.')
                    result = update_lunch_question(DATABASE, 1, int(lunch_action[1]), lunch_action[2])
                else:
                    if set(data) != {'patient_id', 'options'}: raise ValueError('Provide patient_id and options.')
                    result = create_lunch_question(DATABASE, data['patient_id'], data['options'])
                self.send_json(200, {'question': result})
            except (ValueError, UnicodeDecodeError) as error:
                self.send_json(400, {'error': str(error)})
            except sqlite3.Error:
                self.send_json(503, {'error': 'Database unavailable.'})
            return
        played = re.fullmatch(r'/api/patients/([1-9]\d*)/invitations/([1-9]\d*)/played', path.path)
        dispatch = re.fullmatch(r'/api/social/requests/([1-9]\d*)/dispatch', path.path)
        if path.path.startswith('/api/voice/tools/') or path.path == '/api/patients' or played or dispatch:
            try:
                data = self.read_json()
                if path.path.startswith('/api/voice/tools/'):
                    if not {'request_id', 'arguments'} <= set(data) or set(data) - {'request_id', 'arguments', 'patient_id'}:
                        raise ValueError('Expected request_id, arguments, and optional patient_id.')
                    result = execute_tool(DATABASE, path.path.removeprefix('/api/voice/tools/'), data['arguments'], data['request_id'], data.get('patient_id', 1))
                elif played or dispatch:
                    if data: raise ValueError('Expected an empty object.')
                    result = dispatch_social_request(DATABASE, int(dispatch[1])) if dispatch else mark_invitation_played(DATABASE, int(played[1]), int(played[2]))
                else:
                    result = save_patient(DATABASE, data)
                self.send_json(200, result)
            except (ValueError, UnicodeDecodeError, ZoneInfoNotFoundError) as error:
                self.send_json(400, {'error': str(error)})
            except sqlite3.Error:
                self.send_json(503, {'error': 'Database unavailable. Retry only with the same request_id.'})
            return
        if path.path == '/api/reminder':
            try:
                data = self.read_json()
                if set(data) != {'time', 'timezone'} or not isinstance(data['time'], str) or not re.fullmatch(r'\d{2}:\d{2}', data['time']):
                    raise ValueError('Expected time and timezone; time must use HH:MM format.')
                reminder_time = time.fromisoformat(data['time'])
                ZoneInfo(data['timezone'])
                with connect() as db:
                    for key, value in [('reminder_time', reminder_time.strftime('%H:%M')), ('reminder_timezone', data['timezone'])]:
                        db.execute('INSERT INTO dashboard_settings (key,value) VALUES (?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value', (key,value))
                self.send_json(200, {'enabled':True,'time':reminder_time.strftime('%H:%M'),'timezone':data['timezone']})
            except (ValueError, UnicodeDecodeError, ZoneInfoNotFoundError) as error:
                self.send_json(400, {'error':str(error)})
            except sqlite3.Error:
                self.send_json(503, {'error':'Database unavailable.'})
            return
        if path.path == '/api/wake':
            try:
                data = self.read_json()
                if set(data) != {'time','timezone'} or not isinstance(data['time'], str) or not re.fullmatch(r'\d{2}:\d{2}', data['time']):
                    raise ValueError('Expected time and timezone; time must use HH:MM format.')
                wake_time = time.fromisoformat(data['time'])
                ZoneInfo(data['timezone'])
                with connect() as db:
                    for key,value in [('wake_time',wake_time.strftime('%H:%M')),('wake_timezone',data['timezone'])]:
                        db.execute('INSERT INTO dashboard_settings (key,value) VALUES (?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value', (key,value))
                self.send_json(200, {'enabled':True,'time':wake_time.strftime('%H:%M'),'timezone':data['timezone']})
            except (ValueError, UnicodeDecodeError, ZoneInfoNotFoundError) as error:
                self.send_json(400, {'error':str(error)})
            except sqlite3.Error:
                self.send_json(503, {'error':'Database unavailable.'})
            return
        if path.path == '/api/family-update':
            patient_id = int(parse_qs(path.query).get('patient_id',['1'])[0])
            if patient_id != 1:
                self.send_json(400, {'error':'Only Patient 1 is configured.'}); return
            try:
                with connect(True) as db:
                    settings = settings_for(db)
                    _, start, end = day_bounds(default_timezone(settings))
                    db.row_factory = sqlite3.Row
                    events = [dict(row) for row in db.execute('SELECT type,at_utc FROM device_events WHERE patient_id=? AND at_utc>=? AND at_utc<? ORDER BY at_utc', (patient_id,start,end))]
                    known_meds = {event['at_utc'] for event in events if event['type'] == 'meds_taken'}
                    for row in db.execute('SELECT taken_at_utc FROM medication_events WHERE taken_at_utc>=? AND taken_at_utc<? ORDER BY taken_at_utc', (start,end)):
                        if row['taken_at_utc'] not in known_meds:
                            events.append({'type':'meds_taken','at_utc':row['taken_at_utc']})
                    events.sort(key=lambda event:event['at_utc'])
                self.send_json(200, {'message':create_family_message(events)})
            except (sqlite3.Error, ValueError, ZoneInfoNotFoundError):
                self.send_json(503, {'error':'Could not build today’s family update.'})
            return
        if path.path.startswith('/api/alerts/'):
            try:
                alert_id = int(path.path.rsplit('/',1)[1])
                data = self.read_json()
                actions = {'on_my_way':('on_the_way',None), 'done':('done',datetime.now(timezone.utc).isoformat(timespec='seconds'))}
                if data.get('action') not in actions or set(data) != {'action'}:
                    raise ValueError('Action must be on_my_way or done.')
                status, closed = actions[data['action']]
                with connect() as db:
                    cursor = db.execute("UPDATE alerts SET status=?,closed_utc=? WHERE id=? AND status IN ('open','on_the_way')", (status,closed,alert_id))
                    if cursor.rowcount != 1:
                        self.send_json(404, {'error':'Alert not found or already closed.'}); return
                self.send_json(200, {'id':alert_id,'status':status})
            except (ValueError, UnicodeDecodeError) as error:
                self.send_json(400, {'error':str(error)})
            except sqlite3.Error:
                self.send_json(503, {'error':'Database unavailable.'})
            return
        if path.path != '/api/events':
            self.send_error(404); return
        try:
            data = self.read_json()
            allowed = {'taken_at_utc','type','patient_id','source'}
            if set(data) - allowed:
                raise ValueError('Unexpected event fields.')
            event_type = data.get('type','meds_taken')
            if event_type not in ('meds_taken','presence','company'):
                raise ValueError('type must be meds_taken, presence, or company.')
            patient_id = data.get('patient_id',1)
            if not isinstance(patient_id,int) or patient_id != 1:
                raise ValueError('Only Patient 1 is configured.')
            source = data.get('source','device')
            if not isinstance(source,str) or not source:
                raise ValueError('source must be a non-empty string.')
            taken_at = datetime.now(timezone.utc)
            if 'taken_at_utc' in data:
                if not isinstance(data['taken_at_utc'],str): raise ValueError('taken_at_utc must include a timezone.')
                taken_at = datetime.fromisoformat(data['taken_at_utc'].replace('Z','+00:00'))
                if taken_at.tzinfo is None: raise ValueError('taken_at_utc must include a timezone.')
            timestamp = taken_at.astimezone(timezone.utc).isoformat(timespec='seconds')
            with connect() as db:
                if event_type == 'company':
                    db.execute('BEGIN IMMEDIATE')
                db.execute('INSERT INTO device_events (patient_id,type,at_utc,source) VALUES (?,?,?,?)', (patient_id,event_type,timestamp,source))
                if event_type == 'meds_taken':
                    cursor = db.execute('INSERT INTO medication_events (taken_at_utc) VALUES (?)', (timestamp,))
                    event_id = cursor.lastrowid
                else:
                    event_id = db.execute('SELECT last_insert_rowid()').fetchone()[0]
                if event_type == 'company':
                    opened = db.execute("SELECT 1 FROM alerts WHERE patient_id=? AND type='company' AND status IN ('open','on_the_way')", (patient_id,)).fetchone()
                    if not opened:
                        db.execute("INSERT INTO alerts (patient_id,type,title,created_utc,status) VALUES (?,?,?,?, 'open')", (patient_id,'company','Would like company',timestamp))
            self.send_json(201, {'id':event_id,'taken_at_utc':timestamp})
        except (ValueError, UnicodeDecodeError) as error:
            self.send_json(400, {'error':str(error)})
        except sqlite3.Error:
            self.send_json(503, {'error':'Database unavailable. Try again shortly.'})

    def do_DELETE(self):
        if self.path != '/api/reminder': self.send_error(404); return
        try:
            with connect() as db: db.execute("DELETE FROM dashboard_settings WHERE key IN ('reminder_time','reminder_timezone')")
            self.send_json(200, {'enabled':False})
        except sqlite3.Error: self.send_json(503, {'error':'Database unavailable.'})

    def do_GET(self):
        path = urlparse(self.path)
        if path.path in ('/api/lunch', '/api/lunch/pending'):
            try:
                patient_id = int(parse_qs(path.query).get('patient_id', ['1'])[0])
                self.send_json(200, {'question': get_lunch_question(DATABASE, patient_id, path.path.endswith('/pending'))})
            except ValueError:
                self.send_json(400, {'error': 'Invalid patient ID.'})
            except sqlite3.Error:
                self.send_json(503, {'error': 'Database unavailable.'})
            return
        inbox = re.fullmatch(r'/api/patients/([1-9]\d*)/invitations(/next)?', path.path)
        if path.path in ('/api/voice/tools', '/api/voice/requests', '/api/patients', '/api/social/invitations') or inbox:
            try:
                if path.path == '/api/voice/tools': result = TOOLS
                elif path.path == '/api/voice/requests': result = list_requests(DATABASE)
                elif path.path == '/api/patients': result = list_patients(DATABASE)
                elif inbox:
                    rows = list_invitations(DATABASE, int(inbox[1]), bool(inbox[2]))
                    result = {'invitation': rows[0] if rows else None} if inbox[2] else rows
                else: result = list_invitations(DATABASE)
                self.send_json(200, result)
            except sqlite3.Error:
                self.send_json(503, {'error': 'Database unavailable.'})
            return
        if path.path == '/':
            body, content_type, status = PAGE.encode(), 'text/html; charset=utf-8', 200
        elif path.path == '/staff':
            body, content_type, status = STAFF_PAGE.encode(), 'text/html; charset=utf-8', 200
        elif path.path == '/api/reminder':
            try:
                with connect(True) as db: settings = settings_for(db)
                enabled = 'reminder_time' in settings and 'reminder_timezone' in settings
                self.send_json(200, {'enabled':enabled, **({'time':settings['reminder_time'],'timezone':settings['reminder_timezone']} if enabled else {})}); return
            except sqlite3.Error: self.send_json(503, {'error':'Database unavailable.'}); return
        elif path.path == '/api/reminder/next':
            try:
                with connect(True) as db: settings = settings_for(db)
                if 'reminder_time' not in settings or 'reminder_timezone' not in settings: body = b'disabled'
                else:
                    now = datetime.now(timezone.utc); local = now.astimezone(ZoneInfo(settings['reminder_timezone']))
                    scheduled = datetime.combine(local.date(), time.fromisoformat(settings['reminder_time']), ZoneInfo(settings['reminder_timezone']))
                    body = f'{int(scheduled.timestamp())}|{int(now.timestamp())}|{local.date().isoformat()}'.encode()
                status, content_type = 200, 'text/plain; charset=utf-8'
            except (sqlite3.Error, ValueError, ZoneInfoNotFoundError): body,status,content_type=b'Unable to read reminder schedule.',503,'text/plain; charset=utf-8'
        elif path.path == '/api/wake':
            try:
                with connect(True) as db: settings = settings_for(db)
                self.send_json(200, {'enabled':True,'time':settings.get('wake_time','09:00'),'timezone':default_timezone(settings)}); return
            except sqlite3.Error: self.send_json(503, {'error':'Database unavailable.'}); return
        elif path.path == '/api/events':
            try:
                with connect(True) as db:
                    db.row_factory=sqlite3.Row
                    body=json.dumps([dict(row) for row in db.execute('SELECT id,taken_at_utc FROM medication_events ORDER BY taken_at_utc DESC,id DESC')]).encode()
                status,content_type=200,'application/json'
            except sqlite3.Error: body,status,content_type=json.dumps({'error':'Database unavailable.'}).encode(),503,'application/json'
        elif path.path == '/api/alerts':
            try:
                patient_id=int(parse_qs(path.query).get('patient_id',['1'])[0])
                with connect(True) as db:
                    db.row_factory=sqlite3.Row
                    alerts=[dict(row) for row in db.execute("SELECT id,type,title,created_utc,status,note FROM alerts WHERE patient_id=? AND status IN ('open','on_the_way') ORDER BY created_utc DESC",(patient_id,))]
                self.send_json(200,alerts); return
            except (sqlite3.Error, ValueError, ZoneInfoNotFoundError): self.send_json(503, {'error':'Could not read alerts.'}); return
        elif path.path == '/api/board/state':
            try:
                patient_id=int(parse_qs(path.query).get('patient_id',['1'])[0])
                if patient_id != 1: self.send_json(400,{'error':'Only Patient 1 is configured.'}); return
                with connect() as db: state=current_board_state(db,patient_id)
                self.send_json(200,state); return
            except sqlite3.Error: self.send_json(503,{'error':'Database unavailable.'}); return
        elif path.path == '/api/staff':
            try:
                with connect(True) as db:
                    db.row_factory=sqlite3.Row; settings=settings_for(db); zone=default_timezone(settings); _,start,end=day_bounds(zone)
                    events=[dict(row) for row in db.execute('SELECT id,type,at_utc,source FROM device_events WHERE patient_id=1 AND at_utc>=? AND at_utc<? ORDER BY at_utc DESC',(start,end))]
                    known_meds = {event['at_utc'] for event in events if event['type'] == 'meds_taken'}
                    for row in db.execute('SELECT id,taken_at_utc FROM medication_events WHERE taken_at_utc>=? AND taken_at_utc<? ORDER BY taken_at_utc DESC',(start,end)):
                        if row['taken_at_utc'] not in known_meds:
                            events.append({'id':row['id'],'type':'meds_taken','at_utc':row['taken_at_utc'],'source':'legacy'})
                    events.sort(key=lambda event:event['at_utc'], reverse=True)
                    alerts=[dict(row) for row in db.execute("SELECT id,type,title,created_utc,status,note FROM alerts WHERE patient_id=1 AND status IN ('open','on_the_way') ORDER BY created_utc DESC")]
                    latest={}
                    for event in reversed(events): latest[event['type']]=event['at_utc']
                    status=[{'name':'Morning','status':'Up' if 'presence' in latest else 'Waiting','at':latest.get('presence')},{'name':'Medication','status':'Confirmed' if 'meds_taken' in latest else 'Waiting','at':latest.get('meds_taken')},{'name':'Company','status':'Requested' if 'company' in latest else 'No request','at':latest.get('company')}]
                self.send_json(200, {'events':events,'alerts':alerts,'status':status,'wake':{'enabled':True,'time':settings.get('wake_time','09:00'),'timezone':zone}}); return
            except (sqlite3.Error, ValueError, ZoneInfoNotFoundError): self.send_json(503, {'error':'Could not load staff view.'}); return
        else: self.send_error(404); return
        self.send_response(status); self.send_header('Content-Type',content_type); self.send_header('Cache-Control','no-store'); self.send_header('Content-Length',str(len(body))); self.end_headers(); self.wfile.write(body)


if __name__ == '__main__':
    initialize_database(DATABASE)
    try:
        server = ThreadingHTTPServer(('0.0.0.0',8000),Handler)
    except OSError as error:
        if error.errno == errno.EADDRINUSE:
            raise SystemExit('Port 8000 is already in use. Stop the existing dashboard server before starting another one.') from None
        raise
    with connect() as db:
        db.execute('CREATE TABLE IF NOT EXISTS medication_events (id INTEGER PRIMARY KEY, taken_at_utc TEXT NOT NULL)')
        db.execute('CREATE TABLE IF NOT EXISTS dashboard_settings (key TEXT PRIMARY KEY, value TEXT NOT NULL)')
        db.execute('CREATE TABLE IF NOT EXISTS device_events (id INTEGER PRIMARY KEY, patient_id INTEGER NOT NULL, type TEXT NOT NULL, at_utc TEXT NOT NULL, source TEXT NOT NULL)')
        db.execute('CREATE TABLE IF NOT EXISTS alerts (id INTEGER PRIMARY KEY, patient_id INTEGER NOT NULL, type TEXT NOT NULL, title TEXT NOT NULL, created_utc TEXT NOT NULL, status TEXT NOT NULL, closed_utc TEXT, note TEXT)')
        db.execute('CREATE TABLE IF NOT EXISTS board_state (patient_id INTEGER PRIMARY KEY, content TEXT NOT NULL, seq INTEGER NOT NULL)')
    threading.Thread(target=alert_worker, daemon=True).start()
    print('Dashboard and API listening on all network interfaces, port 8000', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print('\nStopped.')
    finally:
        server.server_close()
