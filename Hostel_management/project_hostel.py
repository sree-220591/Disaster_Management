#!/usr/bin/env python3
"""
Single-file Smart Hostel Sentinel demo server (no Flask).
- Uses only Python standard library to serve a single-page app (HTML/CSS/JS)
  and REST-like endpoints backed by SQLite.
- Run: python3 single_hostel_sentinel.py
- Open http://127.0.0.1:8000 in your browser.

Features:
- Roles: student, supervisor, electrician, warden, caretaker, director.
- Seeded Blocks A/B/C, Floors Floor1..Floor3, Rooms R1..R8.
- Students can report issues for their room.
- Electrician sees open issues and can mark them resolved.
- Supervisor can view blocks → floors → rooms; rooms are color-coded by status.
- Issues have 30-day deadlines.
- No external dependencies.
"""

import http.server
import socketserver
import sqlite3
import json
import urllib.parse
import os
from datetime import datetime, timedelta
import threading

HOST = "0.0.0.0"
PORT = 8000
DB_PATH = "hostel_sentinel.db"

HTML = r"""<!doctype html>
<html>
<head>
  <meta charset="utf-8" />
  <title>Smart Hostel Sentinel — Demo (Single File)</title>
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <link rel="stylesheet" href="/styles.css">
</head>
<body>
  <div class="container">
    <header>
      <h1>Smart Hostel Sentinel</h1>
      <div id="user-info"></div>
    </header>

    <main>
      <section id="login-section" class="card">
        <h2>Login (demo)</h2>
        <p>Use seeded usernames: <code>student1</code>, <code>student2</code>, <code>supervisor1</code>, <code>electrician1</code></p>
        <input id="username" placeholder="username" />
        <select id="role">
          <option value="student">student</option>
          <option value="supervisor">supervisor</option>
          <option value="electrician">electrician</option>
          <option value="warden">warden</option>
          <option value="caretaker">caretaker</option>
          <option value="director">director</option>
        </select>
        <button id="btn-login">Login</button>
      </section>

      <section id="supervisor-view" class="card hidden">
        <h2>Supervisor: Blocks</h2>
        <div id="blocks" class="grid"></div>
        <div style="margin-top:10px;"><button id="btn-logout">Logout</button></div>
      </section>

      <section id="floor-view" class="card hidden">
        <button id="btn-back-block">Back to Blocks</button>
        <h2 id="floor-title"></h2>
        <div id="rooms" class="grid"></div>
      </section>

      <section id="room-view" class="card hidden">
        <button id="btn-back-floor">Back to Floor</button>
        <h2 id="room-title"></h2>
        <div id="room-details"></div>

        <h3>Report an issue</h3>
        <input id="issue-title" placeholder="Short title" />
        <textarea id="issue-desc" placeholder="Describe problem"></textarea>
        <select id="issue-sev"><option value="yellow">Yellow (can be spared)</option><option value="red">Red (urgent)</option></select>
        <button id="btn-report">Report Issue</button>

        <h3>Issues for this room</h3>
        <div id="room-issues"></div>
      </section>

      <section id="electrician-view" class="card hidden">
        <h2>Electrician: Open Issues (Resolve)</h2>
        <div id="open-issues"></div>
      </section>

      <section id="student-view" class="card hidden">
        <h2>Student: My Room</h2>
        <div id="my-room"></div>
        <h3>My Issues</h3>
        <div id="my-issues"></div>
      </section>
    </main>

    <footer>
      <small>Demo — Smart Hostel Sentinel (single-file server)</small>
    </footer>
  </div>

<script src="/app.js"></script>
</body>
</html>
"""

STYLES = r"""/* styles.css - minimal styling */
body { font-family: Arial, sans-serif; background:#f4f6f8; color:#222; margin:0; padding:18px; }
.container { max-width:1000px; margin:0 auto; }
header { display:flex; justify-content:space-between; align-items:center; margin-bottom:12px; }
h1 { margin:0; font-size:20px; }
.card { background:white; padding:16px; border-radius:8px; box-shadow:0 1px 3px rgba(0,0,0,0.06); margin-bottom:12px; }
.hidden { display:none; }
.grid { display:grid; grid-template-columns: repeat(auto-fill, minmax(220px,1fr)); gap:12px; }
.block { padding:12px; border-radius:6px; cursor:pointer; border:1px solid #ddd; text-align:center; }
.room { padding:10px; border-radius:6px; border:1px solid #ddd; cursor:pointer; }
.status-green { background:#ecfdf5; border-color:#bbf7d0; }
.status-yellow { background:#fffbeb; border-color:#fef08a; }
.status-red { background:#fff1f2; border-color:#fca5a5; }
.issue { padding:8px; border:1px solid #eee; margin-bottom:8px; border-radius:6px; background:#fff; }
button { padding:8px 10px; border:none; background:#2563eb; color:white; border-radius:6px; cursor:pointer; }
input, textarea, select { width:100%; padding:8px; margin:6px 0; border:1px solid #ddd; border-radius:6px; box-sizing:border-box; }
small { color:#666; }
@media (max-width:600px) {
  .grid { grid-template-columns: repeat(auto-fill, minmax(160px,1fr)); }
}
"""

APP_JS = r"""// app.js - frontend logic (served from single Python file)
const apiBase = '/api';

let currentUser = null;
let selectedBlock = null;
let selectedFloor = null;
let selectedRoom = null;

// DOM refs
const loginSection = document.getElementById('login-section');
const supervisorView = document.getElementById('supervisor-view');
const electricianView = document.getElementById('electrician-view');
const studentView = document.getElementById('student-view');
const floorView = document.getElementById('floor-view');
const roomView = document.getElementById('room-view');

const blocksDiv = document.getElementById('blocks');
const roomsDiv = document.getElementById('rooms');
const roomDetails = document.getElementById('room-details');
const roomIssuesDiv = document.getElementById('room-issues');
const openIssuesDiv = document.getElementById('open-issues');
const myRoomDiv = document.getElementById('my-room');
const myIssuesDiv = document.getElementById('my-issues');

document.getElementById('btn-login').onclick = async () => {
  const username = document.getElementById('username').value.trim();
  const role = document.getElementById('role').value;
  if (!username) return alert('enter username');
  // try login
  const res = await fetch(apiBase + '/login', {
    method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({username})
  });
  if (res.status === 404) {
    // create demo user locally (not persisted server-side)
    currentUser = { username, name: username, role, room_id: role === 'student' ? 'A-Floor1-R1' : null };
  } else {
    currentUser = await res.json();
    // allow role override for demo convenience
    currentUser.role = role || currentUser.role;
  }
  onLogin();
};

document.getElementById('btn-logout').onclick = () => {
  currentUser = null;
  showSection('login');
};

document.getElementById('btn-back-block').onclick = () => { showSection('supervisor'); };
document.getElementById('btn-back-floor').onclick = () => { showSection('floor'); };

function showSection(name) {
  [loginSection, supervisorView, electricianView, studentView, floorView, roomView].forEach(s => s.classList.add('hidden'));
  if (name === 'login') loginSection.classList.remove('hidden');
  if (name === 'supervisor') supervisorView.classList.remove('hidden');
  if (name === 'electrician') electricianView.classList.remove('hidden');
  if (name === 'student') studentView.classList.remove('hidden');
  if (name === 'floor') floorView.classList.remove('hidden');
  if (name === 'room') roomView.classList.remove('hidden');
}

async function onLogin() {
  document.getElementById('user-info').innerText = `${currentUser.name || currentUser.username} (${currentUser.role})`;
  if (currentUser.role === 'supervisor') {
    await loadBlocks();
    showSection('supervisor');
  } else if (currentUser.role === 'electrician') {
    await loadOpenIssues();
    showSection('electrician');
  } else if (currentUser.role === 'student') {
    await loadMyRoom();
    showSection('student');
  } else {
    await loadBlocks();
    showSection('supervisor');
  }
}

async function loadBlocks() {
  blocksDiv.innerHTML = '';
  const res = await fetch(apiBase + '/rooms');
  const rooms = await res.json();
  const groups = {};
  rooms.forEach(r => { groups[r.block] = groups[r.block] || []; groups[r.block].push(r); });
  Object.keys(groups).sort().forEach(block => {
    const blockElem = document.createElement('div');
    blockElem.className = 'block';
    blockElem.innerHTML = `<strong>Block ${block}</strong><div>${groups[block].length} rooms</div><div style="margin-top:8px"><button data-block="${block}">Open</button></div>`;
    blocksDiv.appendChild(blockElem);
    blockElem.querySelector('button').onclick = () => openBlock(block);
  });
}

async function openBlock(block) {
  selectedBlock = block;
  document.getElementById('floor-title').innerText = `Block ${block}`;
  const res = await fetch(apiBase + `/rooms?block=${block}`);
  const rooms = await res.json();
  const floors = {};
  rooms.forEach(r => { floors[r.floor] = floors[r.floor] || []; floors[r.floor].push(r); });
  roomsDiv.innerHTML = '';
  Object.keys(floors).sort().forEach(fl => {
    const div = document.createElement('div');
    div.className = 'block';
    div.innerHTML = `<strong>${fl}</strong><div>${floors[fl].length} rooms</div><div style="margin-top:8px"><button data-floor="${fl}">Open Floor</button></div>`;
    roomsDiv.appendChild(div);
    div.querySelector('button').onclick = () => openFloor(fl);
  });
  showSection('floor');
}

async function openFloor(floor) {
  selectedFloor = floor;
  const res = await fetch(apiBase + `/rooms?block=${selectedBlock}&floor=${floor}`);
  const rooms = await res.json();
  roomsDiv.innerHTML = '';
  rooms.forEach(r => {
    const div = document.createElement('div');
    div.className = 'room ' + (r.status === 'green' ? 'status-green' : r.status === 'yellow' ? 'status-yellow' : 'status-red');
    div.innerHTML = `<strong>${r.id}</strong><div>Status: ${r.status}</div>`;
    div.onclick = () => openRoom(r.id);
    roomsDiv.appendChild(div);
  });
  document.getElementById('floor-title').innerText = `Block ${selectedBlock} — ${floor}`;
}

async function openRoom(roomId) {
  selectedRoom = roomId;
  document.getElementById('room-title').innerText = roomId;
  const all = await fetch(apiBase + `/rooms?block=${selectedBlock}&floor=${selectedFloor}`);
  const rooms = await all.json();
  const room = rooms.find(r => r.id === roomId);
  roomDetails.innerHTML = `<div>Room: ${room.id}</div><div>Floor: ${room.floor}</div><div>Status: ${room.status}</div><div>Last updated: ${new Date(room.last_updated).toLocaleString()}</div>`;
  await loadRoomIssues(roomId);
  showSection('room');

  document.getElementById('btn-report').onclick = async () => {
    const title = document.getElementById('issue-title').value.trim();
    const desc = document.getElementById('issue-desc').value.trim();
    const sev = document.getElementById('issue-sev').value;
    if (!title || !desc) return alert('fill title and description');
    const res = await fetch(apiBase + '/issues', {
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({title, description: desc, room_id: roomId, reporter: currentUser.username, severity: sev})
    });
    const j = await res.json();
    if (j.ok) {
      alert('Issue reported');
      document.getElementById('issue-title').value = '';
      document.getElementById('issue-desc').value = '';
      await loadRoomIssues(roomId);
    } else {
      alert('Error: ' + JSON.stringify(j));
    }
  };
}

async function loadRoomIssues(roomId) {
  const res = await fetch(apiBase + `/issues?room_id=${roomId}`);
  const issues = await res.json();
  roomIssuesDiv.innerHTML = '';
  if (issues.length === 0) roomIssuesDiv.innerHTML = '<div class="issue">No issues</div>';
  issues.forEach(it => {
    const div = document.createElement('div');
    div.className = 'issue';
    div.innerHTML = `<div><strong>${it.title}</strong> <small>(${it.severity})</small></div>
                     <div>${it.description}</div>
                     <div><small>Reported: ${it.reporter} — ${new Date(it.created_at).toLocaleString()}</small></div>
                     <div><small>Deadline: ${new Date(it.deadline).toLocaleDateString()}</small></div>`;
    roomIssuesDiv.appendChild(div);
  });
}

async function loadOpenIssues() {
  const res = await fetch(apiBase + `/issues?status=open`);
  const issues = await res.json();
  openIssuesDiv.innerHTML = '';
  if (!issues.length) openIssuesDiv.innerHTML = '<div class="issue">No open issues</div>';
  issues.forEach(it => {
    const div = document.createElement('div');
    div.className = 'issue';
    div.innerHTML = `<div><strong>${it.title}</strong> <small>${it.room_id}</small></div>
                     <div>${it.description}</div>
                     <div><small>Reported: ${it.reporter} — ${new Date(it.created_at).toLocaleString()}</small></div>
                     <div><small>Deadline: ${new Date(it.deadline).toLocaleDateString()}</small></div>
                     <div style="margin-top:8px"><button data-id="${it.id}">Mark Resolved</button></div>`;
    openIssuesDiv.appendChild(div);
    div.querySelector('button').onclick = async () => {
      const res = await fetch(apiBase + `/issues/${it.id}/resolve`, {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({resolver: currentUser.username})});
      const j = await res.json();
      if (j.ok) {
        alert('Resolved');
        await loadOpenIssues();
      } else alert('Error');
    };
  });
}

async function loadMyRoom() {
  myRoomDiv.innerHTML = '';
  if (!currentUser.room_id) currentUser.room_id = 'A-Floor1-R1';
  const parts = currentUser.room_id.split('-');
  const res = await fetch(apiBase + `/rooms?block=${parts[0]}&floor=${parts[1]}`);
  const rooms = await res.json();
  const room = rooms.find(r => r.id === currentUser.room_id);
  myRoomDiv.innerHTML = `<div class="room ${room.status==='green'?'status-green':room.status==='yellow'?'status-yellow':'status-red'}"><strong>${room.id}</strong><div>Status: ${room.status}</div></div>`;
  await loadMyIssues();
}

async function loadMyIssues() {
  const res = await fetch(apiBase + `/issues`);
  const issues = await res.json();
  const mine = issues.filter(i => i.reporter === currentUser.username);
  myIssuesDiv.innerHTML = '';
  if (!mine.length) myIssuesDiv.innerHTML = '<div class="issue">No issues reported by you.</div>';
  mine.forEach(it => {
    const div = document.createElement('div');
    div.className = 'issue';
    div.innerHTML = `<div><strong>${it.title}</strong> <small>${it.room_id}</small></div>
                     <div>${it.description}</div>
                     <div><small>Status: ${it.status} — Deadline: ${new Date(it.deadline).toLocaleDateString()}</small></div>`;
    myIssuesDiv.appendChild(div);
  });
}
"""

# --------------------------
# Database helpers & seed
# --------------------------
def init_db(conn):
    cur = conn.cursor()
    # Create tables
    cur.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        name TEXT NOT NULL,
        role TEXT NOT NULL,
        room_id TEXT
    )
    """)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS rooms (
        id TEXT PRIMARY KEY,
        block TEXT NOT NULL,
        floor TEXT NOT NULL,
        number TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'green',
        last_updated TEXT NOT NULL
    )
    """)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS issues (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        description TEXT NOT NULL,
        room_id TEXT NOT NULL,
        reporter TEXT NOT NULL,
        severity TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'open',
        created_at TEXT NOT NULL,
        deadline TEXT NOT NULL,
        resolved_at TEXT
    )
    """)
    conn.commit()

def seed_if_empty(conn):
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM rooms")
    c = cur.fetchone()[0]
    if c > 0:
        return
    print("Seeding database with sample rooms and users...")
    blocks = ['A','B','C']
    ts = datetime.utcnow().isoformat()
    for b in blocks:
        for fnum in range(1,4):
            floor = f"Floor{fnum}"
            for rnum in range(1,9):
                rid = f"{b}-{floor}-R{rnum}"
                cur.execute("INSERT INTO rooms (id, block, floor, number, status, last_updated) VALUES (?, ?, ?, ?, ?, ?)",
                            (rid, b, floor, str(rnum), 'green', ts))
    # sample users
    users = [
        ('student1','S. Reddy','student','A-Floor1-R1'),
        ('student2','M. Rao','student','A-Floor1-R2'),
        ('supervisor1','Sup One','supervisor',None),
        ('electrician1','Elec One','electrician',None),
    ]
    for u in users:
        try:
            cur.execute("INSERT INTO users (username,name,role,room_id) VALUES (?,?,?,?)", u)
        except sqlite3.IntegrityError:
            pass
    conn.commit()

# --------------------------
# HTTP Request Handler
# --------------------------
class Handler(http.server.BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def _send(self, code=200, data=b"", content_type="text/plain"):
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def _read_json(self):
        length = int(self.headers.get('Content-Length', 0))
        if length == 0:
            return {}
        raw = self.rfile.read(length)
        try:
            return json.loads(raw.decode('utf-8'))
        except:
            return {}

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        qs = urllib.parse.parse_qs(parsed.query)

        if path == "/" or path == "/index.html":
            self._send(200, HTML.encode('utf-8'), "text/html; charset=utf-8")
            return
        if path == "/styles.css":
            self._send(200, STYLES.encode('utf-8'), "text/css; charset=utf-8")
            return
        if path == "/app.js":
            self._send(200, APP_JS.encode('utf-8'), "application/javascript; charset=utf-8")
            return

        # API routes
        if path.startswith("/api/rooms"):
            # possible filters: block, floor
            params = qs
            block = params.get('block', [None])[0]
            floor = params.get('floor', [None])[0]
            conn = sqlite3.connect(DB_PATH)
            cur = conn.cursor()
            if block and floor:
                cur.execute("SELECT id, block, floor, number, status, last_updated FROM rooms WHERE block=? AND floor=?", (block, floor))
            elif block:
                cur.execute("SELECT id, block, floor, number, status, last_updated FROM rooms WHERE block=?", (block,))
            else:
                cur.execute("SELECT id, block, floor, number, status, last_updated FROM rooms")
            rows = cur.fetchall()
            conn.close()
            out = []
            for r in rows:
                out.append({
                    "id": r[0],
                    "block": r[1],
                    "floor": r[2],
                    "number": r[3],
                    "status": r[4],
                    "last_updated": r[5]
                })
            bs = json.dumps(out).encode('utf-8')
            self._send(200, bs, "application/json; charset=utf-8")
            return

        if path.startswith("/api/issues"):
            # GET issues (with optional room_id, status)
            params = qs
            if self.command != "GET":
                self._send(405, b"Method Not Allowed")
                return
            room_id = params.get('room_id', [None])[0]
            status = params.get('status', [None])[0]
            conn = sqlite3.connect(DB_PATH)
            cur = conn.cursor()
            query = "SELECT id, title, description, room_id, reporter, severity, status, created_at, deadline, resolved_at FROM issues"
            conds = []
            vals = []
            if room_id:
                conds.append("room_id=?"); vals.append(room_id)
            if status == "open":
                conds.append("status='open'")
            if conds:
                query += " WHERE " + " AND ".join(conds)
            query += " ORDER BY created_at DESC"
            cur.execute(query, tuple(vals))
            rows = cur.fetchall()
            conn.close()
            out = []
            for r in rows:
                out.append({
                    "id": r[0],
                    "title": r[1],
                    "description": r[2],
                    "room_id": r[3],
                    "reporter": r[4],
                    "severity": r[5],
                    "status": r[6],
                    "created_at": r[7],
                    "deadline": r[8],
                    "resolved_at": r[9]
                })
            self._send(200, json.dumps(out).encode('utf-8'), "application/json; charset=utf-8")
            return

        # catch-all 404 for other paths
        self._send(404, b"Not Found")

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        if path == "/api/login":
            data = self._read_json()
            username = (data.get("username") or "").strip()
            if not username:
                self._send(400, json.dumps({"error":"username required"}).encode('utf-8'), "application/json")
                return
            conn = sqlite3.connect(DB_PATH)
            cur = conn.cursor()
            cur.execute("SELECT username,name,role,room_id FROM users WHERE username=?", (username,))
            row = cur.fetchone()
            conn.close()
            if not row:
                self._send(404, json.dumps({"error":"user not found"}).encode('utf-8'), "application/json")
                return
            out = {"username": row[0], "name": row[1], "role": row[2], "room_id": row[3]}
            self._send(200, json.dumps(out).encode('utf-8'), "application/json")
            return

        if path == "/api/issues":
            data = self._read_json()
            required = ['title','description','room_id','reporter','severity']
            if not all(k in data for k in required):
                self._send(400, json.dumps({"error":"missing fields"}).encode('utf-8'), "application/json")
                return
            title = data['title'][:200]
            description = data['description'][:4000]
            room_id = data['room_id']
            reporter = data['reporter']
            severity = data['severity'] if data['severity'] in ('yellow','red') else 'yellow'
            created_at = datetime.utcnow().isoformat()
            deadline = (datetime.utcnow() + timedelta(days=30)).isoformat()
            conn = sqlite3.connect(DB_PATH)
            cur = conn.cursor()
            cur.execute("INSERT INTO issues (title,description,room_id,reporter,severity,status,created_at,deadline) VALUES (?,?,?,?,?,?,?,?)",
                        (title,description,room_id,reporter,severity,'open',created_at,deadline))
            # update room status
            cur.execute("SELECT id FROM rooms WHERE id=?", (room_id,))
            if cur.fetchone():
                new_status = 'red' if severity=='red' else 'yellow'
                cur.execute("UPDATE rooms SET status=?, last_updated=? WHERE id=?", (new_status, created_at, room_id))
            conn.commit()
            issue_id = cur.lastrowid
            conn.close()
            self._send(200, json.dumps({"ok":True,"issue_id":issue_id}).encode('utf-8'), "application/json")
            return

        # resolve endpoint: /api/issues/<id>/resolve
        if path.startswith("/api/issues/") and path.endswith("/resolve"):
            parts = path.split("/")
            try:
                issue_id = int(parts[3])
            except:
                self._send(400, json.dumps({"error":"bad issue id"}).encode('utf-8'), "application/json")
                return
            data = self._read_json()
            resolver = data.get('resolver','unknown')
            conn = sqlite3.connect(DB_PATH)
            cur = conn.cursor()
            cur.execute("SELECT room_id FROM issues WHERE id=?", (issue_id,))
            row = cur.fetchone()
            if not row:
                conn.close()
                self._send(404, json.dumps({"error":"issue not found"}).encode('utf-8'), "application/json")
                return
            room_id = row[0]
            resolved_at = datetime.utcnow().isoformat()
            cur.execute("UPDATE issues SET status='resolved', resolved_at=? WHERE id=?", (resolved_at, issue_id))
            # check if open issues remain for room
            cur.execute("SELECT COUNT(*) FROM issues WHERE room_id=? AND status='open'", (room_id,))
            open_count = cur.fetchone()[0]
            if open_count == 0:
                cur.execute("UPDATE rooms SET status='green', last_updated=? WHERE id=?", (resolved_at, room_id))
            else:
                cur.execute("UPDATE rooms SET status='yellow', last_updated=? WHERE id=?", (resolved_at, room_id))
            conn.commit()
            conn.close()
            self._send(200, json.dumps({"ok":True}).encode('utf-8'), "application/json")
            return

        self._send(404, b"Not Found")

# --------------------------
# Run server
# --------------------------
def run_server():
    # ensure DB and seed
    conn = sqlite3.connect(DB_PATH)
    init_db(conn)
    seed_if_empty(conn)
    conn.close()

    with socketserver.ThreadingTCPServer((HOST, PORT), Handler) as httpd:
        sa = httpd.socket.getsockname()
        print(f"Serving HTTP on {sa[0]} port {sa[1]} (http://127.0.0.1:{sa[1]}/) ...")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nShutting down server.")
            httpd.shutdown()

if __name__ == "__main__":
    run_server()