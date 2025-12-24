/* app.js — Smart Hostel Sentinel (offline AI) */

// STORAGE KEYS
const LS_ROOMS = 'sh_rooms_v3';
const LS_ISSUES = 'sh_issues_v3';
const LS_USER = 'sh_user_v3';

// Helpers
const $ = (sel) => document.querySelector(sel);
const $all = (sel) => Array.from(document.querySelectorAll(sel));
const nowISO = () => new Date().toISOString();
const addDaysISO = (d) => new Date(Date.now() + d*24*3600*1000).toISOString();
const uid = () => Math.random().toString(36).slice(2,9);

// Seed rooms if not present
function seedRooms(){
  if (localStorage.getItem(LS_ROOMS)) return;
  const blocks = ['A','B','C'];
  const rooms = [];
  const ts = nowISO();
  blocks.forEach(b=>{
    for(let f=1;f<=3;f++){
      const floor = `Floor${f}`;
      for(let r=1;r<=8;r++){
        rooms.push({ id:`${b}-${floor}-R${r}`, block:b, floor, number:r, status:'green', last_updated:ts });
      }
    }
  });
  localStorage.setItem(LS_ROOMS, JSON.stringify(rooms));
}

function seedIssues(){
  if (localStorage.getItem(LS_ISSUES)) return;
  const issues = [];
  // small sample: none initially; you can optionally seed historic resolved issues here
  localStorage.setItem(LS_ISSUES, JSON.stringify(issues));
}

function loadRooms(){ return JSON.parse(localStorage.getItem(LS_ROOMS) || '[]'); }
function loadIssues(){ return JSON.parse(localStorage.getItem(LS_ISSUES) || '[]'); }
function loadUser(){ return JSON.parse(localStorage.getItem(LS_USER) || 'null'); }
function saveRooms(r){ localStorage.setItem(LS_ROOMS, JSON.stringify(r)); }
function saveIssues(i){ localStorage.setItem(LS_ISSUES, JSON.stringify(i)); }
function saveUser(u){ localStorage.setItem(LS_USER, JSON.stringify(u)); }

// App state
let state = {
  user: loadUser(),
  rooms: loadRooms(),
  issues: loadIssues(),
  view: 'dashboard',
  charts: {},
  insights: []
};

// init seeds
seedRooms();
seedIssues();
state.rooms = loadRooms();
state.issues = loadIssues();

// UI wiring
function setStatus(txt){ $('#status').innerText = txt; }
function renderAuth(){
  const area = $('#authArea');
  area.innerHTML = '';
  if (state.user){
    const div = document.createElement('div'); div.style.display='flex'; div.style.alignItems='center'; div.style.gap='8px';
    div.innerHTML = `<div class="muted small">Hi</div><div style="font-weight:700">${state.user.name}</div><div class="muted small">·</div>`;
    const role = document.createElement('div'); role.className='role-pill'; role.textContent = state.user.role;
    const logout = document.createElement('button'); logout.className='ghost'; logout.textContent='Logout'; logout.onclick = ()=>{ localStorage.removeItem(LS_USER); state.user=null; render(); };
    area.appendChild(div); area.appendChild(role); area.appendChild(logout);
  } else {
    const btn = document.createElement('button'); btn.className='btn'; btn.textContent='Sign in'; btn.onclick = openLogin;
    area.appendChild(btn);
  }
  $('#roleBadge').innerText = state.user ? state.user.role : 'guest';
}

// menu
$all('.side-item').forEach(it=>{
  it.onclick = ()=> {
    $all('.side-item').forEach(x=>x.classList.remove('active'));
    it.classList.add('active');
    state.view = it.dataset.view;
    render();
  };
});

// login modal (simple)
function openLogin(){
  const name = prompt('Enter display name (demo):', 'student1');
  if (!name) return;
  const role = prompt('Role (student/supervisor/electrician/caretaker/director):','student') || 'student';
  state.user = { name, username: name, role };
  saveUser(state.user);
  render();
  alert(`Signed in as ${name} (${role})`);
}

// render core
function render(){
  renderAuth();
  const content = $('#content');
  content.innerHTML = '';
  if (!state.user){
    // welcome card
    const w = document.createElement('div'); w.className='glass'; w.style.padding='18px';
    w.innerHTML = `<div style="display:flex;justify-content:space-between;align-items:center"><div><div style="font-size:20px;font-weight:800">Welcome</div><div class="muted small">Sign in to continue</div></div><div><button class="btn" onclick="openLogin()">Sign in</button></div></div>`;
    content.appendChild(w);
    setStatus('Not signed in');
    return;
  }
  setStatus(`Signed in as ${state.user.name} (${state.user.role})`);

  if (state.view === 'dashboard') renderDashboard(content);
  if (state.view === 'map') renderMap(content);
  if (state.view === 'issues') renderIssues(content);
  if (state.view === 'ai') renderAI(content);
  if (state.view === 'admin') renderAdmin(content);
}

// dashboard
function computeInsights(){
  const open = state.issues.filter(i=>i.status==='open');
  const byRoom = {};
  open.forEach(i=> byRoom[i.room_id] = (byRoom[i.room_id]||0)+1);
  const topRooms = Object.keys(byRoom).sort((a,b)=>byRoom[b]-byRoom[a]).slice(0,5).map(rid=>({ title:`Repeated open issues in ${rid}`, detail:`${byRoom[rid]} open issues — consider maintenance.` }));
  // predict
  const p = predictIssues(state.issues);
  state.insights = [...topRooms, { title:'Predicted next 7 days', detail: `~${Math.round(p.next7)} estimated issues.` }];
}

function renderDashboard(container){
  computeInsights();
  const stats = document.createElement('div'); stats.className='grid-3';
  const totalRooms = state.rooms.length;
  const openCount = state.issues.filter(i=>i.status==='open').length;
  const insCount = state.insights.length;
  stats.innerHTML = `<div class="glass stat"><div class="stat-icon">🏠</div><div><div class="muted small">Total Rooms</div><div style="font-weight:800;font-size:18px">${totalRooms}</div></div></div>
                     <div class="glass stat"><div class="stat-icon">⚠️</div><div><div class="muted small">Open Issues</div><div style="font-weight:800;font-size:18px">${openCount}</div></div></div>
                     <div class="glass stat"><div class="stat-icon">🤖</div><div><div class="muted small">Insights</div><div style="font-weight:800;font-size:18px">${insCount}</div></div></div>`;
  container.appendChild(stats);

  const two = document.createElement('div'); two.className='grid-2'; two.style.marginTop='12px';
  const left = document.createElement('div'); left.className='glass'; left.innerHTML = '<div style="display:flex;justify-content:space-between;align-items:center"><div style="font-weight:800">Live Map</div><div class="muted small">Click a room</div></div><div id="mapGrid" style="margin-top:10px"></div>';
  const right = document.createElement('div');
  const aiBox = document.createElement('div'); aiBox.className='glass'; aiBox.style.marginBottom='12px'; aiBox.innerHTML='<div style="font-weight:800">AI Insights</div><div id="insightsArea" style="margin-top:8px"></div>';
  const quick = document.createElement('div'); quick.className='glass'; quick.innerHTML='<div style="font-weight:700">Quick Actions</div><div style="display:flex;gap:8px;margin-top:8px"><button class="small" id="mkMap">Open Map</button><button class="small" id="mkIssues">Open Issues</button><button class="small" id="mkRefresh">Refresh</button></div>';
  right.appendChild(aiBox); right.appendChild(quick);
  two.appendChild(left); two.appendChild(right);
  container.appendChild(two);

  // fill map and insights
  renderMapGrid($('#mapGrid'));
  const insArea = $('#insightsArea'); insArea.innerHTML = '';
  state.insights.forEach(it => { const div = document.createElement('div'); div.className='insight'; div.innerHTML = `<div style="font-weight:700">${it.title}</div><div class="muted small">${it.detail}</div>`; insArea.appendChild(div); });

  // quick actions
  $('#mkMap').onclick = ()=> { state.view='map'; render(); };
  $('#mkIssues').onclick = ()=> { state.view='issues'; render(); };
  $('#mkRefresh').onclick = ()=> { refreshState(); alert('Refreshed'); };
}

// render map
function renderMap(content){
  const wrap = document.createElement('div'); wrap.className='glass';
  wrap.innerHTML = '<div style="display:flex;justify-content:space-between;align-items:center"><div style="font-weight:800">Rooms Map</div><div class="muted small">Report issues by clicking a room</div></div><div id="mapBlocks" style="margin-top:10px"></div>';
  content.appendChild(wrap);
  renderMapGrid($('#mapBlocks'));
}

function renderMapGrid(parent){
  parent.innerHTML = '';
  const blocks = {};
  state.rooms.forEach(r=> { blocks[r.block] = blocks[r.block] || {}; blocks[r.block][r.floor] = blocks[r.block][r.floor] || []; blocks[r.block][r.floor].push(r); });
  Object.keys(blocks).forEach(b => {
    const bwrap = document.createElement('div'); bwrap.style.marginBottom='12px';
    const hdr = document.createElement('div'); hdr.style.display='flex'; hdr.style.justifyContent='space-between'; hdr.innerHTML = `<div style="font-weight:700">Block ${b}</div><div class="muted small">${Object.keys(blocks[b]).length} floors</div>`;
    bwrap.appendChild(hdr);
    const grid = document.createElement('div'); grid.style.display='grid'; grid.style.gap='10px';
    Object.keys(blocks[b]).forEach(fl => {
      const fcard = document.createElement('div'); fcard.className='glass'; fcard.style.padding='10px';
      fcard.innerHTML = `<div style="display:flex;justify-content:space-between"><div style="font-weight:700">${fl}</div><div class="muted small">${blocks[b][fl].length} rooms</div></div>`;
      const rgrid = document.createElement('div'); rgrid.className='room-grid'; rgrid.style.marginTop='8px';
      blocks[b][fl].forEach(r => {
        const rc = document.createElement('div');
        rc.className = 'room-card ' + (r.status==='green' ? 'room-green' : r.status==='yellow' ? 'room-yellow' : 'room-red');
        rc.textContent = r.id.split('-').pop();
        rc.title = `${r.id} — ${r.status}`;
        rc.onclick = ()=> reportModal(r);
        rgrid.appendChild(rc);
      });
      fcard.appendChild(rgrid);
      grid.appendChild(fcard);
    });
    bwrap.appendChild(grid);
    parent.appendChild(bwrap);
  });
}

// issues view
function renderIssues(content){
  const wrap = document.createElement('div'); wrap.className='glass';
  wrap.innerHTML = '<div style="display:flex;justify-content:space-between;align-items:center"><div style="font-weight:800">Open Issues</div><div class="muted small">Manage & resolve</div></div>';
  const list = document.createElement('div'); list.style.marginTop='10px';
  const open = state.issues.filter(i=>i.status==='open');
  if (!open.length) list.innerHTML = '<div class="muted small">No open issues</div>';
  open.forEach(it=>{
    const item = document.createElement('div'); item.className='glass'; item.style.display='flex'; item.style.justifyContent='space-between'; item.style.marginTop='8px';
    item.innerHTML = `<div><div style="font-weight:700">${it.title}</div><div class="muted small">${it.description}</div><div class="muted small">Room: ${it.room_id} • Reporter: ${it.reporter}</div></div>`;
    const actions = document.createElement('div');
    const canResolve = ['electrician','supervisor','caretaker'].includes(state.user.role);
    if (canResolve){
      const btn = document.createElement('button'); btn.className='btn'; btn.textContent='Resolve'; btn.onclick = ()=> { if(confirm('Mark resolved?')) resolveIssue(it.id, state.user.name); };
      actions.appendChild(btn);
    } else {
      actions.innerHTML = `<div class="muted small">No actions for role</div>`;
    }
    item.appendChild(actions);
    list.appendChild(item);
  });
  wrap.appendChild(list);
  content.appendChild(wrap);
}

// AI view (charts + chat + heatmap)
function renderAI(content){
  computeInsights();
  const wrap = document.createElement('div'); wrap.className='glass';
  wrap.innerHTML = `<div style="display:flex;justify-content:space-between;align-items:center"><div style="font-weight:800">AI Dashboard</div><div class="muted small">Predictions · Heatmap · Assistant</div></div>`;
  const inner = document.createElement('div'); inner.style.marginTop='10px';
  const left = document.createElement('div'); left.className='glass'; left.style.marginBottom='10px';
  left.innerHTML = `<div style="font-weight:700">Issue Trend</div><canvas id="trend" style="height:200px;margin-top:8px"></canvas><div id="trendSummary" class="muted small" style="margin-top:6px"></div>`;
  const right = document.createElement('div'); right.style.display='flex'; right.style.flexDirection='column'; right.style.gap='10px';
  const chat = document.createElement('div'); chat.className='glass'; chat.innerHTML = `<div style="font-weight:700">AI Assistant</div><div class="muted small">Ask about hotspots, predictions, or search rooms</div><div id="chatLog" class="chat-log" style="margin-top:8px"></div><input id="chatInput" class="input" placeholder="e.g. predict issues next week"><div style="display:flex;gap:8px;margin-top:8px"><button id="askBtn" class="btn">Ask</button><button id="nlBtn" class="small">Natural Search</button></div>`;
  const heat = document.createElement('div'); heat.className='glass'; heat.innerHTML = `<div style="font-weight:700">Heatmap</div><div id="heatmap" style="margin-top:8px"></div>`;
  right.appendChild(chat); right.appendChild(heat);

  const container = document.createElement('div'); container.style.display='grid'; container.style.gridTemplateColumns='1fr 360px'; container.style.gap='12px';
  container.appendChild(left); container.appendChild(right);
  inner.appendChild(container);
  wrap.appendChild(inner);
  content.appendChild(wrap);

  drawTrend();
  renderHeatmap($('#heatmap'));
  $('#askBtn').onclick = ()=> { const q = $('#chatInput').value.trim(); if (!q) return; assistantAsk(q); $('#chatInput').value=''; };
  $('#nlBtn').onclick = ()=> { const q = $('#chatInput').value.trim(); if (!q) return; naturalSearch(q); $('#chatInput').value=''; };
}

// admin view
function renderAdmin(content){
  if (!['supervisor','director'].includes(state.user.role)){
    content.innerHTML = '<div class="glass"><div class="muted small">Admin access denied for your role.</div></div>';
    return;
  }
  const wrap = document.createElement('div'); wrap.className='glass';
  wrap.innerHTML = `<div style="font-weight:800">Admin Data</div><pre style="margin-top:8px;background:rgba(0,0,0,0.2);padding:10px;border-radius:8px">ROOMS: ${JSON.stringify(state.rooms.slice(0,50),null,2)}\n\nISSUES: ${JSON.stringify(state.issues.slice(0,50),null,2)}</pre>`;
  content.appendChild(wrap);
}

// report modal (prompt-based for simplicity)
function reportModal(room){
  if (!state.user) { alert('Sign in first'); return; }
  const title = prompt(`Report issue for ${room.id} — title:`, 'Light not working');
  if (!title) return;
  const desc = prompt('Short description:', 'Tube light is flickering');
  if (!desc) return;
  const sev = prompt('Severity (red/yellow):','yellow') === 'red' ? 'red' : 'yellow';
  const issue = { id: uid(), title: title.slice(0,200), description: desc.slice(0,1000), room_id: room.id, reporter: state.user.name, severity: sev, status: 'open', created_at: nowISO(), deadline: addDaysISO(30), resolved_at: null };
  state.issues.unshift(issue); saveIssues(state.issues);
  // update room
  state.rooms = state.rooms.map(r => r.id === room.id ? {...r, status: sev==='red' ? 'red' : 'yellow', last_updated: nowISO()} : r);
  saveRooms(state.rooms);
  alert('Issue reported (saved locally).');
  render();
}

// resolve
function resolveIssue(id, resolver){
  state.issues = state.issues.map(it => it.id === id ? {...it, status:'resolved', resolved_at: nowISO(), resolver} : it);
  saveIssues(state.issues);
  // update room status
  const issue = state.issues.find(it=>it.id===id);
  if (issue){
    const rId = issue.room_id;
    const openCount = state.issues.filter(it=>it.room_id===rId && it.status==='open').length;
    state.rooms = state.rooms.map(r=> r.id===rId ? {...r, status: openCount===0 ? 'green' : 'yellow', last_updated: nowISO()} : r);
    saveRooms(state.rooms);
  }
  alert('Issue resolved');
  render();
}

// trend chart
function drawTrend(){
  const canvas = document.getElementById('trend');
  if (!canvas) return;
  const days = 30;
  const labels = [];
  const data = [];
  for(let i=days-1;i>=0;i--){
    const d = new Date(Date.now() - i*24*3600*1000);
    labels.push(`${d.getMonth()+1}/${d.getDate()}`);
    const cnt = state.issues.filter(it=> {
      const diff = Math.floor((Date.now() - new Date(it.created_at).getTime())/(24*3600*1000));
      return diff === i;
    }).length;
    data.push(cnt);
  }
  if (state.charts.trend) state.charts.trend.destroy();
  state.charts.trend = new Chart(canvas.getContext('2d'), { type:'line', data:{ labels, datasets:[{ label:'Issues/day', data, borderColor:'#10b981', backgroundColor:'rgba(16,185,129,0.12)', fill:true, tension:0.3 }]}, options:{responsive:true, plugins:{legend:{display:false}}} });
  $('#trendSummary').innerText = `Total issues (last ${days} days): ${data.reduce((a,b)=>a+b,0)} • Avg/day: ${(data.reduce((a,b)=>a+b,0)/days).toFixed(2)}`;
}

// heatmap
function renderHeatmap(container){
  container.innerHTML = '';
  const blocks = ['A','B','C'];
  blocks.forEach(b=>{
    const wrap = document.createElement('div'); wrap.style.marginBottom='8px';
    const title = document.createElement('div'); title.innerText = 'Block ' + b; title.style.fontWeight='700'; title.style.marginBottom='6px';
    wrap.appendChild(title);
    const heat = document.createElement('div'); heat.className='heatmap';
    for(let i=1;i<=8;i++){
      // count open issues for room number i in all floors
      let intensity = 0;
      state.rooms.filter(r=> r.block===b && r.number===i).forEach(rr => intensity += state.issues.filter(it=>it.room_id===rr.id && it.status==='open').length);
      const cell = document.createElement('div'); cell.className='heat';
      if (intensity===0) cell.style.background='rgba(255,255,255,0.02)';
      else if (intensity===1) cell.style.background='rgba(16,185,129,0.3)';
      else if (intensity===2) cell.style.background='rgba(250,204,21,0.35)';
      else cell.style.background='rgba(239,68,68,0.5)';
      heat.appendChild(cell);
    }
    wrap.appendChild(heat);
    container.appendChild(wrap);
  });
}

// assistant (simple rule + NL)
function appendChat(who, text){
  const log = $('#chatLog');
  if (!log) return;
  const el = document.createElement('div'); el.style.marginBottom='8px';
  el.innerHTML = `<div style="font-size:12px;color:var(--muted)">${who}</div><div style="padding:8px;border-radius:8px;margin-top:6px;background:rgba(255,255,255,0.02)">${text}</div>`;
  log.appendChild(el); log.scrollTop = log.scrollHeight;
}

function assistantAsk(q){
  appendChat('You', q);
  const lower = q.toLowerCase();
  if (lower.includes('predict') || lower.includes('next week') || lower.includes('forecast')){
    const p = predictIssues(state.issues);
    appendChat('AI', `Prediction: approx ${Math.round(p.next7)} issues in next 7 days (trend slope ${p.slope.toFixed(2)}).`);
    return;
  }
  if (lower.includes('rooms with') || lower.includes('show rooms')){
    const keyword = lower.split('rooms with ')[1] || lower.split('show rooms ')[1] || '';
    const matches = state.issues.filter(it=> it.description.toLowerCase().includes(keyword) || it.title.toLowerCase().includes(keyword));
    if (!matches.length) { appendChat('AI', 'No matching issues found.'); return; }
    const rooms = [...new Set(matches.map(m=>m.room_id))].slice(0,10);
    appendChat('AI', `Matches: ${rooms.join(', ')}`);
    return;
  }
  if (lower.includes('hotspot') || lower.includes('which block')){
    const byBlock = {};
    state.issues.filter(i=>i.status==='open').forEach(it=>{
      const room = state.rooms.find(r=>r.id===it.room_id);
      if (room) byBlock[room.block] = (byBlock[room.block]||0)+1;
    });
    const sorted = Object.keys(byBlock).sort((a,b)=>byBlock[b]-byBlock[a]);
    if (!sorted.length) appendChat('AI','No open issues.');
    else appendChat('AI', `Hotspots: ${sorted.join(', ')} (counts: ${sorted.map(s=>byBlock[s]).join(', ')})`);
    return;
  }
  appendChat('AI','Try asking: "predict issues next week", "show rooms with plumbing", or "which block is hotspot"');
}

// NL search quick
function naturalSearch(q){
  appendChat('You', q);
  const low = q.toLowerCase();
  if (low.includes('vacant') || low.includes('available')){
    const vac = state.rooms.filter(r=>r.status==='green').map(r=>r.id).slice(0,20);
    appendChat('AI', `Vacant rooms (sample): ${vac.join(', ') || 'none'}`);
    return;
  }
  appendChat('AI', 'No direct structured result. Try: "vacant rooms", "vacant rooms floor 2", "rooms with water".');
}

// prediction helper (linear fit)
function predictIssues(issues){
  const days = 30;
  const counts = Array(days).fill(0);
  const now = Date.now();
  issues.forEach(it=>{
    const created = new Date(it.created_at).getTime();
    const diff = Math.floor((now - created)/(24*3600*1000));
    if (diff < days) counts[days-1-diff] += 1;
  });
  const x = [], y = [];
  counts.forEach((c,i)=>{ x.push(i); y.push(c); });
  const n = x.length;
  const sumx = x.reduce((a,b)=>a+b,0), sumy = y.reduce((a,b)=>a+b,0);
  let sumxy = 0, sumxx = 0;
  for(let i=0;i<n;i++){ sumxy += x[i]*y[i]; sumxx += x[i]*x[i]; }
  const slope = (n*sumxy - sumx*sumy) / (n*sumxx - sumx*sumx + 1e-9);
  const intercept = (sumy - slope*sumx)/n;
  let next7 = 0;
  for(let i=n;i<n+7;i++){ const v = Math.max(0, intercept + slope*i); next7 += v; }
  return { slope, intercept, next7 };
}

// anomaly detection (simple)
function detectAnomaly(issues){
  const now = Date.now();
  const getCount = (fromDaysAgo,toDaysAgo) => {
    const from = now - toDaysAgo*24*3600*1000;
    const to = now - fromDaysAgo*24*3600*1000;
    return issues.filter(it=> new Date(it.created_at).getTime() >= from && new Date(it.created_at).getTime() <= to).length;
  };
  const last3 = getCount(0,3);
  const prev7 = getCount(3,10);
  const avgPrev = prev7 / 7;
  if (avgPrev > 0 && (last3/3) > avgPrev * 2.0) return { alert:true, message:`Spike detected: recent avg ${(last3/3).toFixed(1)} > prev ${(avgPrev).toFixed(1)}.` };
  return { alert:false };
}

// export/reset
$('#exportBtn').onclick = ()=> {
  const data = { rooms: state.rooms, issues: state.issues };
  const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a'); a.href = url; a.download = 'hostel_export.json'; a.click(); URL.revokeObjectURL(url);
};
$('#resetBtn').onclick = ()=> {
  if (!confirm('Reset data?')) return;
  localStorage.removeItem(LS_ROOMS); localStorage.removeItem(LS_ISSUES); seedRooms(); seedIssues(); state.rooms = loadRooms(); state.issues = loadIssues(); render();
};

// refresh from storage
function refreshState(){ state.rooms = loadRooms(); state.issues = loadIssues(); }

// mount
function init(){
  computeInsights();
  render();
  const anomaly = detectAnomaly(state.issues);
  if (anomaly.alert) setStatus('ALERT: ' + anomaly.message);
  else setStatus('Ready (offline simulated-AI)');
}
init();

