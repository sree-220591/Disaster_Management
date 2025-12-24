#!/usr/bin/env python3
"""
single_hostel_interface.py

Single-file Python server (no Flask) that serves a small UI demonstrating:
- Three hostel boxes (Hostel 1, Hostel 2, Hostel 3)
- Clicking any hostel shows Floor 1 / Floor 2 / Floor 3 options for that hostel
- Clicking any floor shows the rooms for that floor (rooms displayed as colored boxes; default green)

Run:
    python3 single_hostel_interface.py
Open in browser:
    http://127.0.0.1:8000

This file uses only Python stdlib (http.server, sqlite not used here). Frontend is plain HTML/CSS/JS.
"""
import http.server
import socketserver
import json
import urllib.parse
import os
from datetime import datetime

HOST = "0.0.0.0"
PORT = 8000

# -- Static HTML, CSS, JS --
HTML = r"""<!doctype html>
<html>
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width,initial-scale=1" />
<title>Hostel Interface — Three Hostels</title>
<link rel="stylesheet" href="/styles.css">
</head>
<body>
  <div class="container">
    <header>
      <h1>Smart Hostel Sentinel — Hostels Overview</h1>
      <p class="muted">Click a hostel to view its floors; click a floor to view rooms.</p>
    </header>

    <main>
      <section class="card">
        <h2>Choose a Hostel</h2>
        <div id="hostel-list" class="hostel-grid"></div>
      </section>

      <section id="floors-card" class="card hidden">
        <div class="row">
          <button id="btn-back-hostels">← Back to Hostels</button>
          <h3 id="selected-hostel-title" style="margin-left:12px">Hostel</h3>
        </div>
        <div id="floors" class="floor-buttons" style="margin-top:12px"></div>
      </section>

      <section id="rooms-card" class="card hidden">
        <div class="row">
          <button id="btn-back-floors">← Back to Floors</button>
          <h3 id="selected-floor-title" style="margin-left:12px">Floor</h3>
        </div>
        <div id="rooms-grid" class="rooms-grid" style="margin-top:12px"></div>
      </section>
    </main>

    <footer class="muted">Demo interface — three hostels, each with 3 floors, each floor with 8 rooms.</footer>
  </div>

<script src="/app.js"></script>
</body>
</html>
"""

STYLES = r"""/* styles.css */
:root{--bg:#f7fafc;--card:#fff;--muted:#6b7280;--accent:#2563eb}
*{box-sizing:border-box}
body{font-family:Inter,Segoe UI,Roboto,Arial,sans-serif;background:var(--bg);margin:0;padding:18px;color:#111}
.container{max-width:980px;margin:0 auto}
header{margin-bottom:12px}
h1{margin:0;font-size:20px}
.muted{color:var(--muted)}
.card{background:var(--card);padding:14px;border-radius:10px;box-shadow:0 6px 18px rgba(15,23,42,0.06);margin-bottom:12px}
.hostel-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:12px}
.hostel-box{padding:18px;border-radius:10px;border:1px solid #e6eef6;background:#fff;cursor:pointer;display:flex;flex-direction:column;justify-content:center;align-items:center;min-height:120px}
.hostel-box:hover{transform:translateY(-4px);transition:transform .15s ease}
.floor-buttons{display:flex;gap:12px;flex-wrap:wrap}
.floor-btn{padding:10px 14px;border-radius:8px;border:1px solid #dbeafe;background:#eef2ff;cursor:pointer}
.rooms-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(110px,1fr));gap:10px;margin-top:8px}
.room{padding:12px;border-radius:8px;text-align:center;border:1px solid #e6edf3}
.room.small{padding:8px;font-size:13px}
.status-green{background:#ecfdf5;border-color:#bbf7d0}
.status-yellow{background:#fffbeb;border-color:#fef08a}
.status-red{background:#fff1f2;border-color:#fca5a5}
.row{display:flex;align-items:center}
.hidden{display:none}
button{font-family:inherit;padding:8px 10px;border-radius:8px;border:1px solid #cbd5e1;background:#fff;cursor:pointer}
@media(max-width:560px){.hostel-grid{grid-template-columns:1fr}}
"""

APP_JS = r"""// app.js
// Simple frontend that fetches /api/hostels (static JSON) and renders UI.
// Interaction: hostels -> floors -> rooms

const apiBase = '/api';

let hostelsData = null;
let selectedHostel = null;
let selectedFloor = null;

const el = id => document.getElementById(id);

function show(id){
  ['hostel-list-card','floors-card','rooms-card'].forEach(x=>{});
  // manage cards
  document.querySelectorAll('.card').forEach(c=>{
    // all kept; we'll hide specific sections by id
  });
}

// Render hostels as three boxes
async function loadHostels(){
  const res = await fetch(apiBase + '/hostels');
  hostelsData = await res.json();
  const container = document.getElementById('hostel-list');
  container.innerHTML = '';
  hostelsData.forEach(h => {
    const d = document.createElement('div');
    d.className = 'hostel-box';
    d.innerHTML = `<div style="font-weight:600">${h.title}</div><div class="muted" style="margin-top:6px">${h.floors.length} floors</div>`;
    d.onclick = () => openHostel(h.id);
    container.appendChild(d);
  });
  // ensure initial visibility
  document.getElementById('floors-card').classList.add('hidden');
  document.getElementById('rooms-card').classList.add('hidden');
  document.getElementById('hostel-list').parentElement.classList.remove('hidden');
}

// When clicking hostel
function openHostel(hostelId){
  selectedHostel = hostelsData.find(h => h.id === hostelId);
  el('selected-hostel-title').innerText = selectedHostel.title;
  // render floor buttons
  const floorsDiv = el('floors');
  floorsDiv.innerHTML = '';
  selectedHostel.floors.forEach(f => {
    const b = document.createElement('button');
    b.className = 'floor-btn';
    b.innerText = f.title;
    b.onclick = () => openFloor(f.title);
    floorsDiv.appendChild(b);
  });
  // show/hide
  document.getElementById('hostel-list').parentElement.classList.add('hidden');
  document.getElementById('rooms-card').classList.add('hidden');
  document.getElementById('floors-card').classList.remove('hidden');
}

// When clicking floor
function openFloor(floorTitle){
  selectedFloor = selectedHostel.floors.find(fl => fl.title === floorTitle);
  el('selected-floor-title').innerText = `${selectedHostel.title} — ${selectedFloor.title}`;
  const roomsGrid = el('rooms-grid');
  roomsGrid.innerHTML = '';
  selectedFloor.rooms.forEach(r => {
    const div = document.createElement('div');
    div.className = 'room small ' + (r.status === 'green' ? 'status-green' : r.status === 'yellow' ? 'status-yellow' : 'status-red');
    div.innerHTML = `<div style="font-weight:600">${r.id}</div><div class="muted" style="margin-top:6px">${r.label}</div>`;
    roomsGrid.appendChild(div);
  });
  // show/hide
  document.getElementById('floors-card').classList.add('hidden');
  document.getElementById('rooms-card').classList.remove('hidden');
}

// Back buttons wiring
document.addEventListener('DOMContentLoaded', ()=>{
  el('btn-back-hostels').onclick = () => {
    document.getElementById('floors-card').classList.add('hidden');
    document.getElementById('rooms-card').classList.add('hidden');
    document.getElementById('hostel-list').parentElement.classList.remove('hidden');
  };
  el('btn-back-floors').onclick = () => {
    document.getElementById('rooms-card').classList.add('hidden');
    document.getElementById('floors-card').classList.remove('hidden');
  };
  loadHostels();
});
"""

# -- JSON data for hostels (three hostels, each with 3 floors and 8 rooms) --
def make_hostels_json():
    hostels = []
    for i, hid in enumerate(['H1', 'H2', 'H3'], start=1):
        h = {"id": hid, "title": f"Hostel {i}", "floors": []}
        for fnum in range(1, 4):
            floor_title = f"Floor {fnum}"
            rooms = []
            for rnum in range(1, 9):
                room_id = f"{hid}-F{fnum}-R{rnum}"
                rooms.append({
                    "id": room_id,
                    "label": f"Room {rnum}",
                    "status": "green"  # default all green for now
                })
            h["floors"].append({"title": floor_title, "rooms": rooms})
        hostels.append(h)
    return hostels

HOSTELS_JSON = make_hostels_json()
HOSTELS_JSON_BYTES = json.dumps(HOSTELS_JSON).encode('utf-8')


# -- HTTP handler --
class Handler(http.server.BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def _send(self, status=200, body=b"", ctype="text/plain"):
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        if body:
            self.wfile.write(body)

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        if path == "/" or path == "/index.html":
            self._send(200, HTML.encode('utf-8'), "text/html; charset=utf-8")
            return
        if path == "/styles.css":
            self._send(200, STYLES.encode('utf-8'), "text/css; charset=utf-8")
            return
        if path == "/app.js":
            self._send(200, APP_JS.encode('utf-8'), "application/javascript; charset=utf-8")
            return
        if path == "/api/hostels":
            self._send(200, HOSTELS_JSON_BYTES, "application/json; charset=utf-8")
            return

        # not found
        self._send(404, b"Not Found")

    def do_POST(self):
        # no POST endpoints in this simple demo
        self._send(404, b"Not Found")


# -- Run server --
def run():
    with socketserver.ThreadingTCPServer((HOST, PORT), Handler) as httpd:
        sa = httpd.socket.getsockname()
        print(f"Serving on http://127.0.0.1:{sa[1]} — open in your browser")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("Shutting down.")
            httpd.shutdown()

if __name__ == "__main__":
    run()