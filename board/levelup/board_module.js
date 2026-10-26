/* ================= wall board (Stellar Unicorn) ================= */
// Sends the dragon, tonight's X Effect card and celebrations to the Stellar Unicorn on the wall
// through the viewer's "stellar1" connector. Every call is fire-and-forget: the app never waits on the board.
const BOARD = { server: "stellar1", mcp: null, on: true, sent: {}, state: "", busy: false, t: null };
try { BOARD.on = localStorage.getItem(LS + "boardOff") !== "1"; BOARD.sent = JSON.parse(localStorage.getItem(LS + "boardSent") || "{}") || {}; } catch (e) {}
const PY = __PY_TEMPLATES__;
const pyStr = s => JSON.stringify(String(s)).replace(/[^\x20-\x7e]/g, c => "\\u" + c.charCodeAt(0).toString(16).padStart(4, "0"));
const rgbOf = hex => { const n = parseInt(hex.slice(1), 16); return [n >> 16, (n >> 8) & 255, n & 255]; };
const pyRgb = c => "(" + c.join(", ") + ")";
// The creature's 30×30 pixel layers, squeezed into the board's 16×16 (area-weighted, faces kept crisp).
function boardSprite(stage, mood) {
  const L = creature(stage, mood, { grids: true }), N = 30;
  let x0 = N, y0 = N, x1 = -1, y1 = -1;
  for (let y = 0; y < N; y++) for (let x = 0; x < N; x++) if (L.comp[y][x] || L.flame[y][x]) { x0 = Math.min(x0, x); y0 = Math.min(y0, y); x1 = Math.max(x1, x); y1 = Math.max(y1, y); }
  const bw = x1 - x0 + 1, bh = y1 - y0 + 1, s = Math.max(1, bw / 16, bh / 16);
  const tw = Math.min(16, Math.round(bw / s)), th = Math.min(16, Math.round(bh / s));
  const ox = Math.floor((16 - tw) / 2), oy = 16 - th, cols = [], idx = c => { let i = cols.indexOf(c); if (i < 0) { cols.push(c); i = cols.length - 1; } return i; };
  const spr = Array(256).fill("."), flm = Array(256).fill("."), glow = Array(256).fill("."), eyes = [];
  const sample = (layers, tx, ty, need) => {
    const sx0 = x0 + tx * s, sy0 = y0 + ty * s, w = {}; let tot = 0, fl = 0;
    for (let y = Math.floor(sy0); y < sy0 + s; y++) for (let x = Math.floor(sx0); x < sx0 + s; x++) {
      if (x < 0 || y < 0 || x >= N || y >= N) continue;
      const a = (Math.min(x + 1, sx0 + s) - Math.max(x, sx0)) * (Math.min(y + 1, sy0 + s) - Math.max(y, sy0)); if (a <= 0) continue;
      let c = null, isF = false; for (const [g, f] of layers) if (g[y][x]) { c = g[y][x]; isF = f; break; }
      if (!c) continue; tot += a; w[c] = (w[c] || 0) + a; if (isF) fl += a;
    }
    const area = s * s; if (tot < area * need) return null;
    let best = null; if ((w[OUT] || 0) >= area * .38) best = OUT; else for (const c in w) if (!best || w[c] > w[best]) best = c;
    return { c: best, flame: fl >= tot * .5 };
  };
  const BX0 = -ox, BY0 = -oy;
  for (let ty = 0; ty < 16; ty++) for (let tx = 0; tx < 16; tx++) {
    const i = ty * 16 + tx, sx = tx + BX0, sy = ty + BY0;
    const p = sample([[L.flame, true], [L.comp, false]], sx, sy, .45);
    if (p) { spr[i] = String.fromCharCode(65 + idx(p.c)); if (p.flame) flm[i] = "#"; if (p.c === OUT && sy < th * .6) eyes.push(i); continue; }
    const q = sample([[L.orbit, false], [L.spin, false], [L.fx, false]], sx, sy, .3);
    if (q && q.c !== OUT) glow[i] = String.fromCharCode(65 + idx(q.c));
  }
  const bodyI = idx(PAL[stage][0]);
  if (cols.length > 26) cols.length = 26;
  return `COLORS = [${cols.map(c => pyRgb(rgbOf(c))).join(", ")}]
SPRITE = ${pyStr(spr.join(""))}
FLAME = ${pyStr(flm.join(""))}
GLOW = ${pyStr(glow.join(""))}
EYES = (${eyes.join(", ")}${eyes.length === 1 ? "," : ""})
BODY = ${bodyI < 26 ? bodyI : 0}
ACCENT = ${pyRgb(rgbOf(PAL[stage][2]))}
`;
}
function boardInfo() {
  const ct = C.ct; let streak = 0; { let d = C.byDay[ct] ? ct : addDays(ct, -1); while (C.byDay[d]) { streak++; d = addDays(d, -1); } }
  return { name: (S.profile.avatar && S.profile.avatar.name) || "Ember", form: FORMS[C.stage][1], lvl: C.lvl, pct: Math.floor(C.rem / C.need * 100), streak };
}
const pyHead = (title, ct) => `# ${title}\n# Made by the Level Up app on ${ct}. It rewrites this file whenever things change.\n`;
// One colour per habit, spread around the colour wheel (starting at a warm pink).
function habRgb(i, n) {
  const h = ((i / Math.max(1, n)) + .97) % 1 * 6, k = Math.floor(h), f = h - k, q = Math.round(255 * (1 - f)), t = Math.round(255 * f);
  const c = [[255, t, 0], [q, 255, 0], [0, 255, t], [0, q, 255], [t, 0, 255], [255, 0, q]][k % 6];
  return c.map(v => Math.round(v * .85 + 30));
}
const activeHabits = ct => S.habits.habits.filter(h => { const i = diff(h.start, ct); return i >= 0 && i < 49; }).slice(0, 16);
function boardFiles() {
  const B = boardInfo(), ct = C.ct, H = S.habits;
  const active = activeHabits(ct);
  const avatar = pyHead(`${B.name} the ${B.form}, from Level Up`, ct) +
    `NAME = ${pyStr(B.name)}\nFORM = ${pyStr(B.form)}\nLEVEL = ${B.lvl}\nXP_PCT = ${B.pct}\nSTREAK = ${B.streak}\nDONE = ${active.filter(h => marked(h, ct)).length}\nTOTAL = ${active.length}\nMOOD = ${pyStr(C.mood)}\n` +
    boardSprite(C.stage, C.mood) + PY.common + PY.avatar;
  const card = pyHead("Tonight's X Effect card, from Level Up", ct) +
    `DATE = ${pyStr(ct)}\nHABITS = [\n${active.map((h, i) => `    (${pyStr(h.name)}, ${crushedM(h, ct) ? 2 : marked(h, ct) ? 1 : 0}, ${pyRgb(habRgb(i, active.length))}),`).join("\n")}\n]\n` + PY.common + PY.today;
  return { "avatar.py": avatar, "today_card.py": card };
}
function celebratePy(kind, hid) {
  const ct = C.ct, act = activeHabits(ct), i = Math.max(0, act.findIndex(h => h.id === hid)), word = kind === "legend" ? "LEGENDARY DAY!" : kind === "perfect" ? "PERFECT DAY!" : "";
  return pyHead("A habit just got checked off in Level Up", ct) + `KIND = ${pyStr(kind)}\nCOLOR = ${pyRgb(habRgb(i, act.length))}\nWORD = ${pyStr(word)}\n` + PY.common + PY.celebrate;
}
function levelupPy(lvl, evolved) {
  const ct = C.ct;
  return pyHead(`Level ${lvl}${evolved ? ": evolution!" : "!"}`, ct) + `LEVEL = ${lvl}\nEVOLVED = ${evolved ? "True" : "False"}\nMOOD = "party"\n` + boardSprite(C.stage, "party") + PY.common + PY.levelup;
}
function boardNote(msg) { BOARD.state = msg; const el = $("boardState"); if (el) el.textContent = msg; }
async function boardCall(input) {
  if (!BOARD.mcp || !BOARD.on || RO) return false;
  try { await BOARD.mcp.callTool(BOARD.server, "upload_program", input, { cache: false }); return true; }
  catch (e) {
    const c = e && e.code;
    if (c === "server_not_connected") { BOARD.mcp = null; boardNote("Add the stellar1 connector in claude.ai to link the board."); }
    else if (c === "not_in_manifest" || c === "approval_required" || c === "not_granted") { BOARD.mcp = null; boardNote("Board not allowed for this page. Allow stellar1 in the page's permissions."); }
    else if (c === "needs_reauth") { BOARD.mcp = null; boardNote("Reconnect stellar1 in claude.ai Settings → Connectors."); }
    else if (c === "tool_error") boardNote("The board said: " + String(e.message || "error").slice(0, 120));
    else boardNote("Couldn't reach the board just now.");
    return false;
  }
}
// Keep avatar.py and today_card.py on the board current (saved, not started: the playlist shows them).
function boardSync(now) {
  if (!BOARD.mcp || !BOARD.on || RO || !C || !store.ready) return;
  clearTimeout(BOARD.t);
  BOARD.t = setTimeout(async () => {
    if (BOARD.busy) { boardSync(); return; }
    BOARD.busy = true;
    try {
      const F = boardFiles(); let n = 0, ok = true;
      for (const name of Object.keys(F)) {
        if (BOARD.sent[name] === F[name]) continue;
        if (await boardCall({ name, code: F[name], run: false })) { BOARD.sent[name] = F[name]; n++; } else { ok = false; break; }
      }
      try { localStorage.setItem(LS + "boardSent", JSON.stringify(BOARD.sent)); } catch (e) {}
      if (ok) boardNote(n ? "Board updated " + new Date().toLocaleTimeString([], { hour: "numeric", minute: "2-digit" }) : "Board is up to date");
    } finally { BOARD.busy = false; }
  }, now ? 0 : 4000);
}
function boardShow(name, code) { boardCall({ name, code, run: true }); }
function renderBoardCard() {
  const t = $("boardOn"); if (!t) return;
  t.checked = BOARD.on; $("boardState").textContent = BOARD.state || (BOARD.mcp ? "" : "Linking…");
}
