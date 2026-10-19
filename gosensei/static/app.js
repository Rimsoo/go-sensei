"use strict";

const LETTERS = "ABCDEFGHJKLMNOPQRSTUVWXYZ";
const SVGNS = "http://www.w3.org/2000/svg";
const $ = (s) => document.querySelector(s);

let S = null;            // dernier état reçu du serveur
let chat = [];           // historique du chat
let busy = false;
let preview = null;      // suite (pv) survolée : {color, moves}
let highlight = null;    // coordonnée survolée dans le chat
let hover = null;        // intersection survolée
let renderQueued = false;
const opts = { suggest: true, owner: false, numbers: false };

// ------------------------------------------------------------------ utilitaires
const gtpToXY = (s, size) => {
  if (!s || s.toLowerCase() === "pass") return null;
  const x = LETTERS.indexOf(s[0].toUpperCase());
  const y = size - parseInt(s.slice(1), 10);
  return x >= 0 && x < size && y >= 0 && y < size ? [x, y] : null;
};
const xyToGtp = (x, y, size) => LETTERS[x] + (size - y);
const pov = (v, c) => (v == null ? null : c === "B" ? v : -v);
const fmt = (v) => (v == null ? "?" : (v >= 0 ? "+" : "−") + Math.abs(v).toFixed(1));
const colorName = (c) => (c === "B" ? "Noir" : "Blanc");
const esc = (s) => s.replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));

function el(tag, attrs = {}, parent) {
  const e = document.createElementNS(SVGNS, tag);
  for (const k in attrs) e.setAttribute(k, attrs[k]);
  if (parent) parent.appendChild(e);
  return e;
}

function lossColor(loss) {
  if (loss <= 0.3) return "#3ec1a8";
  if (loss <= 1.0) return "#7bd36b";
  if (loss <= 3.0) return "#e3c548";
  if (loss <= 6.0) return "#e8893f";
  return "#e0564f";
}

const MARK_COLORS = { red: "#e0453c", green: "#2fa86b", blue: "#3d7fe0", yellow: "#e9b81f", purple: "#9b5de5" };

async function post(path, body = {}) {
  const r = await fetch(path, { method: "POST", headers: { "Content-Type": "application/json", "X-Go-Sensei": "1" }, body: JSON.stringify(body) });
  const j = await r.json().catch(() => ({}));
  if (!r.ok || j.error) { toast(j.error || `Erreur ${r.status}`); throw new Error(j.error); }
  return j;
}

let toastTimer;
function toast(msg) {
  const t = $("#toast");
  t.textContent = msg;
  t.classList.remove("hidden");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => t.classList.add("hidden"), 4000);
}

function queueRender() {
  if (renderQueued) return;
  renderQueued = true;
  requestAnimationFrame(() => { renderQueued = false; render(); });
}

// ------------------------------------------------------------------ plateau
function displayedMoves() {
  const size = S.game.size;
  const out = [];
  for (const [c, m] of S.pathMoves) out.push([c, gtpToXY(m, size)]);
  return out;
}

function starPoints(size) {
  if (size === 9) return [[2, 2], [6, 2], [4, 4], [2, 6], [6, 6]];
  if (size === 13) return [3, 6, 9].flatMap((a) => [3, 6, 9].map((b) => [a, b]));
  if (size === 19) return [3, 9, 15].flatMap((a) => [3, 9, 15].map((b) => [a, b]));
  return [];
}

function renderBoard() {
  const svg = $("#board");
  svg.innerHTML = "";
  if (!S || !S.game) return;
  const size = S.game.size;
  const m = 0.95;
  svg.setAttribute("viewBox", `${-m} ${-m} ${size - 1 + 2 * m} ${size - 1 + 2 * m}`);

  const defs = el("defs", {}, svg);
  defs.innerHTML = `
    <radialGradient id="gb" cx="35%" cy="32%" r="70%"><stop offset="0" stop-color="#5a5a5a"/><stop offset=".55" stop-color="#151515"/><stop offset="1" stop-color="#000"/></radialGradient>
    <radialGradient id="gw" cx="35%" cy="32%" r="75%"><stop offset="0" stop-color="#fff"/><stop offset=".7" stop-color="#e6e6e2"/><stop offset="1" stop-color="#b9b9b3"/></radialGradient>
    <linearGradient id="wood" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#e3bb74"/><stop offset=".5" stop-color="#d6a95e"/><stop offset="1" stop-color="#c99a4f"/></linearGradient>
    <filter id="sh" x="-30%" y="-30%" width="160%" height="160%"><feDropShadow dx=".06" dy=".08" stdDeviation=".05" flood-opacity=".5"/></filter>`;

  el("rect", { x: -m, y: -m, width: size - 1 + 2 * m, height: size - 1 + 2 * m, fill: "url(#wood)" }, svg);
  const grid = el("g", { stroke: "#3b2a12", "stroke-width": 0.035, "stroke-linecap": "square" }, svg);
  for (let i = 0; i < size; i++) {
    el("line", { x1: 0, y1: i, x2: size - 1, y2: i }, grid);
    el("line", { x1: i, y1: 0, x2: i, y2: size - 1 }, grid);
  }
  for (const [x, y] of starPoints(size)) el("circle", { cx: x, cy: y, r: 0.09, fill: "#3b2a12" }, svg);

  const coords = el("g", { fill: "#5a4220", "font-size": 0.32, "text-anchor": "middle", "dominant-baseline": "central", "font-weight": 600 }, svg);
  for (let i = 0; i < size; i++) {
    for (const yy of [-0.62, size - 1 + 0.62]) el("text", { x: i, y: yy }, coords).textContent = LETTERS[i];
    for (const xx of [-0.62, size - 1 + 0.62]) el("text", { x: xx, y: i }, coords).textContent = String(size - i);
  }

  const stones = new Map(S.stones.map(([x, y, c]) => [x + "," + y, c]));
  const a = S.analysis;
  const own = opts.owner && a && a.ownership ? a.ownership : null;

  // Territoires (sous les pierres)
  if (own) {
    const g = el("g", {}, svg);
    for (let y = 0; y < size; y++) for (let x = 0; x < size; x++) {
      const v = own[y * size + x];
      if (stones.has(x + "," + y) || Math.abs(v) < 0.15) continue;
      const s = 0.62 * Math.min(1, Math.abs(v));
      el("rect", { x: x - s / 2, y: y - s / 2, width: s, height: s, rx: 0.05,
        fill: v > 0 ? "#111" : "#fafafa", opacity: 0.25 + 0.5 * Math.abs(v) }, g);
    }
  }

  // Numéros de coups
  const numbers = new Map();
  if (opts.numbers) displayedMoves().forEach(([c, p], i) => { if (p) numbers.set(p[0] + "," + p[1], i + 1); });

  // Pierres
  const sg = el("g", {}, svg);
  for (const [x, y, c] of S.stones) {
    const v = own ? own[y * size + x] : 0;
    const dead = own && ((c === "B" && v < -0.5) || (c === "W" && v > 0.5));
    el("circle", { cx: x, cy: y, r: 0.475, fill: c === "B" ? "url(#gb)" : "url(#gw)", filter: "url(#sh)", opacity: dead ? 0.55 : 1 }, sg);
    if (dead) el("rect", { x: x - 0.17, y: y - 0.17, width: 0.34, height: 0.34, fill: c === "B" ? "#fafafa" : "#111" }, sg);
    const n = numbers.get(x + "," + y);
    if (n) {
      const t = el("text", { x, y: y + 0.01, "text-anchor": "middle", "dominant-baseline": "central", "font-size": n > 99 ? 0.3 : 0.38,
        fill: c === "B" ? "#eee" : "#222", "font-weight": 600 }, sg);
      t.textContent = n;
    }
  }

  // Dernier coup
  if (S.last && !numbers.size) {
    const c = stones.get(S.last[0] + "," + S.last[1]);
    el("circle", { cx: S.last[0], cy: S.last[1], r: 0.2, fill: "none", stroke: c === "B" ? "#fff" : "#111", "stroke-width": 0.07 }, svg);
  }

  // Coup réellement joué ensuite dans la partie
  const nextMain = !S.inVariation && S.moveNumber < S.main.length ? gtpToXY(S.main[S.moveNumber], size) : null;

  // Suggestions de KataGo
  if (opts.suggest && a && a.moves.length && !preview) {
    const c = a.toPlay;
    const best = pov(a.moves[0].score, c);
    const total = a.moves.reduce((s, m) => s + m.visits, 0);
    const g = el("g", {}, svg);
    a.moves.filter((mv, i) => i < 8 && (i === 0 || mv.visits >= Math.max(3, total * 0.03))).forEach((mv, i) => {
      const p = gtpToXY(mv.move, size);
      if (!p) return;
      const sc = pov(mv.score, c);
      const col = lossColor(best - sc);
      el("circle", { cx: p[0], cy: p[1], r: 0.43, fill: col, opacity: 0.88, stroke: i === 0 ? "#0b5e4f" : "none", "stroke-width": 0.06 }, g);
      const t = el("text", { x: p[0], y: p[1] + 0.01, "text-anchor": "middle", "dominant-baseline": "central", "font-size": 0.3, "font-weight": 700, fill: "#111" }, g);
      t.textContent = fmt(sc);
    });
  }
  if (nextMain && opts.suggest && !preview) {
    el("circle", { cx: nextMain[0], cy: nextMain[1], r: 0.47, fill: "none", stroke: "#3d7fe0", "stroke-width": 0.07, "stroke-dasharray": "0.12 0.08" }, svg);
  }

  // Aperçu d'une suite (survol d'une suggestion)
  if (preview) {
    const g = el("g", {}, svg);
    let c = preview.color;
    const seen = new Set();
    preview.moves.forEach((mv, i) => {
      const p = gtpToXY(mv, size);
      if (p && !seen.has(p + "")) {
        seen.add(p + "");
        el("circle", { cx: p[0], cy: p[1], r: 0.46, fill: c === "B" ? "url(#gb)" : "url(#gw)", opacity: 0.78 }, g);
        const t = el("text", { x: p[0], y: p[1] + 0.01, "text-anchor": "middle", "dominant-baseline": "central", "font-size": 0.38, "font-weight": 700, fill: c === "B" ? "#fff" : "#111" }, g);
        t.textContent = i + 1;
      }
      c = c === "B" ? "W" : "B";
    });
  }

  // Annotations de Sensei
  const mg = el("g", {}, svg);
  for (const mk of S.marks) {
    const { x, y } = mk;
    const onStone = stones.get(x + "," + y);
    const col = MARK_COLORS[mk.color] || (onStone === "B" ? "#fff" : onStone === "W" ? "#111" : "#c0392b");
    if (mk.shape === "area") {
      el("rect", { x: x - 0.5, y: y - 0.5, width: 1, height: 1, fill: MARK_COLORS[mk.color] || "#e9b81f", opacity: 0.38 }, mg);
    } else if (mk.shape === "triangle") {
      el("polygon", { points: `${x},${y - 0.3} ${x + 0.27},${y + 0.18} ${x - 0.27},${y + 0.18}`, fill: "none", stroke: col, "stroke-width": 0.08 }, mg);
    } else if (mk.shape === "circle") {
      el("circle", { cx: x, cy: y, r: 0.27, fill: "none", stroke: col, "stroke-width": 0.08 }, mg);
    } else if (mk.shape === "square") {
      el("rect", { x: x - 0.22, y: y - 0.22, width: 0.44, height: 0.44, fill: "none", stroke: col, "stroke-width": 0.08 }, mg);
    } else if (mk.shape === "cross") {
      el("path", { d: `M${x - 0.22},${y - 0.22}L${x + 0.22},${y + 0.22}M${x + 0.22},${y - 0.22}L${x - 0.22},${y + 0.22}`, stroke: col, "stroke-width": 0.09 }, mg);
    }
    if (mk.label) {
      if (!onStone && mk.shape !== "area") el("circle", { cx: x, cy: y, r: 0.33, fill: "#dcb36b" }, mg);
      const t = el("text", { x, y: y + 0.01, "text-anchor": "middle", "dominant-baseline": "central", "font-size": mk.label.length > 1 ? 0.36 : 0.5,
        "font-weight": 800, fill: MARK_COLORS[mk.color] || (onStone === "B" ? "#fff" : "#111") }, mg);
      t.textContent = mk.label;
    }
  }

  // Surbrillance (coordonnée survolée dans le chat)
  if (highlight) {
    const p = gtpToXY(highlight, size);
    if (p) {
      const r = el("circle", { cx: p[0], cy: p[1], r: 0.5, fill: "none", stroke: "#ff3d7f", "stroke-width": 0.1 }, svg);
      el("animate", { attributeName: "r", values: "0.35;0.62;0.35", dur: "1.1s", repeatCount: "indefinite" }, r);
    }
  }

  // Pierre fantôme sous la souris
  if (hover && !stones.has(hover[0] + "," + hover[1])) {
    el("circle", { cx: hover[0], cy: hover[1], r: 0.46, fill: S.toPlay === "B" ? "url(#gb)" : "url(#gw)", opacity: 0.45, "pointer-events": "none" }, svg);
  }

  // Zones cliquables
  const hit = el("g", {}, svg);
  for (let y = 0; y < size; y++) for (let x = 0; x < size; x++) {
    const r = el("rect", { x: x - 0.5, y: y - 0.5, width: 1, height: 1, class: "hit" }, hit);
    r.addEventListener("mouseenter", () => { if (!hover || hover[0] !== x || hover[1] !== y) { hover = [x, y]; queueRender(); } });
    r.addEventListener("click", () => post("/api/play", { move: xyToGtp(x, y, size) }).catch(() => {}));
  }
  svg.onmouseleave = () => { hover = null; queueRender(); };
}

// ------------------------------------------------------------------ panneaux
function scoreAt(t) {
  if (!S.review) return null;
  const pt = S.review.curve.find((c) => c[0] === t);
  return pt ? pt[2] : null;
}

function renderInfo() {
  const g = S.game;
  $("#game-title").textContent = g ? `${g.black} vs ${g.white} · ${g.size}×${g.size} · komi ${g.komi}${g.result ? " · " + g.result : ""}` : "Aucune partie";
  if (S.engine) renderEngine(S.engine);
  if (!g) return;
  for (const c of ["B", "W"]) {
    const p = $("#pl-" + c);
    p.querySelector(".name").textContent = c === "B" ? g.black : g.white;
    p.querySelector(".caps").textContent = `${S.captures[c]} prisonnier${S.captures[c] > 1 ? "s" : ""}`;
    p.classList.toggle("student", g.student === c);
    p.classList.toggle("toplay", S.toPlay === c);
  }
  const total = S.main.length;
  const mn = $("#movenum");
  mn.innerHTML = S.inVariation
    ? `Coup <b>${S.moveNumber}</b> <span class="muted">(variante depuis le coup ${S.cursor})</span>`
    : `Coup <b>${S.moveNumber}</b> / ${total}${S.lastPass ? " · passe" : ""}`;
  $("#btn-main").classList.toggle("hidden", !S.inVariation);

  // Barre d'évaluation
  const a = S.analysis;
  const wr = a && a.winrate != null ? a.winrate : null;
  const sc = a && a.score != null ? a.score : (S.lineEvals || [])[S.moveNumber];
  $("#evalbar .fill").style.width = `${(wr != null ? wr : 0.5) * 100}%`;
  $("#evalbar .label").textContent = sc == null ? "…" : `${sc >= 0 ? "Noir" : "Blanc"} +${Math.abs(sc).toFixed(1)}`;

  // Résumé + coups suggérés
  const sum = $("#an-summary"), list = $("#an-moves");
  list.innerHTML = "";
  if (!a) {
    sum.innerHTML = `<span class="muted">Analyse en cours…</span>`;
    $("#an-visits").textContent = "";
  } else {
    const c = a.toPlay;
    $("#an-visits").textContent = `${a.visits} visites${a.final ? "" : "…"}`;
    let html = `Au trait : <b>${colorName(c)}</b> · ${Math.abs(a.score) < 0.5 ? "équilibré" : `<b>${a.score > 0 ? "Noir" : "Blanc"}</b> mène de ${Math.abs(a.score).toFixed(1)} pts`} · victoire Noir ${(a.winrate * 100).toFixed(0)}%`;
    if (!S.inVariation && S.moveNumber < S.main.length) {
      const before = scoreAt(S.moveNumber), after = scoreAt(S.moveNumber + 1);
      const mc = S.mainColors[S.moveNumber];
      if (before != null && after != null) {
        const loss = (before - after) * (mc === "B" ? 1 : -1);
        html += `<br><span class="muted">Coup joué ensuite dans la partie (cercle bleu) :</span> <b>${S.main[S.moveNumber]}</b> `
          + `<span style="color:${lossColor(loss)}">${loss > 0.05 ? "−" + loss.toFixed(1) + " pts" : "bon coup"}</span>`;
      }
    }
    sum.innerHTML = html;
    const best = pov(a.moves[0] ? a.moves[0].score : 0, c);
    const tot = a.moves.reduce((s, m) => s + m.visits, 0);
    a.moves.filter((mv, i) => i === 0 || mv.visits >= Math.max(3, tot * 0.01)).slice(0, 6).forEach((mv) => {
      const sc2 = pov(mv.score, c);
      const d = document.createElement("div");
      d.className = "an-move";
      d.innerHTML = `<span class="dot" style="background:${lossColor(best - sc2)}"></span><span class="mv">${mv.move}</span><span class="sc">${fmt(sc2)} · ${(pov(mv.winrate - 0.5, c) * 100 + 50).toFixed(0)}%</span>`;
      d.title = "Survol : voir la suite · Clic : jouer ce coup";
      d.onmouseenter = () => { if (!preview || preview.key !== mv.move) { preview = { key: mv.move, color: c, moves: mv.pv }; queueRender(); } };
      d.onmouseleave = () => { preview = null; queueRender(); };
      d.onclick = () => { preview = null; post("/api/play", { move: mv.move }).catch(() => {}); };
      list.appendChild(d);
    });
  }

  // Erreurs
  const box = $("#mistakes");
  box.innerHTML = "";
  const r = S.review;
  const st = $("#review-status");
  if (!r) st.textContent = "";
  else if (r.status === "done") st.textContent = "revue terminée";
  else if (r.status === "error") st.textContent = "revue : erreur";
  else st.textContent = `revue KataGo : ${r.done}/${r.total}`;
  if (r) {
    const mine = r.mistakes.filter((m) => !g.student || m.color === g.student);
    if (!mine.length) box.innerHTML = `<span class="muted small-text">${r.status === "done" ? "Aucune erreur notable 🎉" : "Analyse de la partie en cours…"}</span>`;
    for (const m of mine) {
      const b = document.createElement("button");
      b.className = `mistake ${m.level}` + (S.moveNumber === m.move_number - 1 && !S.inVariation ? " current" : "");
      b.textContent = `${m.move_number}. ${m.played} −${m.loss.toFixed(1)}`;
      b.title = `${colorName(m.color)} a joué ${m.played} (${m.level}, −${m.loss} pts). Mieux : ${m.best}. Clic : position juste avant ce coup.`;
      b.onclick = () => post("/api/goto", { n: m.move_number - 1 });
      box.appendChild(b);
    }
  }
}

function renderGraph() {
  const svg = $("#graph");
  svg.innerHTML = "";
  if (!S || !S.game) return;
  const W = svg.clientWidth || 600, H = svg.clientHeight || 96;
  svg.setAttribute("viewBox", `0 0 ${W} ${H}`);
  const line = S.line || [];
  const evals = S.lineEvals || [];
  const total = Math.max(1, S.main.length, line.length - 1);
  const curve = S.review ? S.review.curve.filter((c) => c[2] != null) : [];
  const vals = curve.map((c) => Math.abs(c[2])).concat(evals.filter((v) => v != null).map(Math.abs));
  const maxAbs = Math.ceil(Math.min(60, Math.max(10, ...vals)));
  const X = (t) => 4 + (t / total) * (W - 8);
  const Y = (s) => H / 2 - (Math.max(-maxAbs, Math.min(maxAbs, s)) / maxAbs) * (H / 2 - 6);
  el("line", { x1: 0, y1: H / 2, x2: W, y2: H / 2, stroke: "#3a404c", "stroke-width": 1 }, svg);
  const branch = S.branch;
  // Partie réelle (estompée quand on regarde une variante)
  if (curve.length > 1) {
    const pts = curve.map((c) => `${X(c[0])},${Y(c[2])}`).join(" ");
    el("polygon", { points: `${X(curve[0][0])},${H / 2} ${pts} ${X(curve[curve.length - 1][0])},${H / 2}`,
      fill: branch == null ? "#5fb3a133" : "#5fb3a114" }, svg);
    el("polyline", { points: pts, fill: "none", stroke: "#5fb3a1", "stroke-width": 2, opacity: branch == null ? 1 : 0.35 }, svg);
  }
  // Variante de la ligne affichée, depuis son point de départ
  if (branch != null) {
    const pts = [];
    for (let t = branch - 1; t < evals.length; t++) if (evals[t] != null) pts.push(`${X(t)},${Y(evals[t])}`);
    if (pts.length > 1) el("polyline", { points: pts.join(" "), fill: "none", stroke: "#e8893f", "stroke-width": 2.5 }, svg);
    for (let t = branch; t < evals.length; t++) {
      if (evals[t] == null) el("circle", { cx: X(t), cy: H / 2, r: 2, fill: "#e8893f88" }, svg); // en cours d'analyse
    }
    el("text", { x: W - 4, y: 12, fill: "#e8893f", "font-size": 11, "text-anchor": "end" }, svg).textContent = "variante";
  }
  const xc = X(S.moveNumber);
  el("line", { x1: xc, y1: 0, x2: xc, y2: H, stroke: "#e7e9ee", "stroke-width": 1.5, "stroke-dasharray": "3 3" }, svg);
  if (S.review) {
    for (const m of S.review.mistakes) {
      if (S.game.student && m.color !== S.game.student) continue;
      const s = scoreAt(m.move_number);
      if (s == null) continue;
      el("circle", { cx: X(m.move_number), cy: Y(s), r: m.level === "gaffe" ? 5 : m.level === "erreur" ? 4 : 3,
        fill: m.level === "gaffe" ? "#e0564f" : m.level === "erreur" ? "#e3b448" : "#b8c27a",
        opacity: branch == null ? 1 : 0.4 }, svg);
    }
  }
  el("text", { x: 4, y: 12, fill: "#8d94a3", "font-size": 11 }, svg).textContent = `Noir +${maxAbs}`;
  el("text", { x: 4, y: H - 4, fill: "#8d94a3", "font-size": 11 }, svg).textContent = `Blanc +${maxAbs}`;
  svg.onclick = (e) => {
    const r = svg.getBoundingClientRect();
    const t = Math.max(0, Math.round(((e.clientX - r.left - 4) / (r.width - 8)) * total));
    // Dans la ligne affichée (variante comprise) si possible, sinon dans la partie
    if (t < line.length) post("/api/goto-node", { id: line[t] });
    else post("/api/goto", { n: Math.min(S.main.length, t) });
  };
}

// ------------------------------------------------------------------ arbre des coups
const TREE_DX = 22, TREE_DY = 22;
function layoutTree() {
  const nodes = new Map(S.tree.map((n) => [n.id, n]));
  const pos = new Map();
  let maxRow = 0, maxDepth = 0;
  // Parcours en profondeur : le premier enfant reste sur la ligne, les autres ouvrent une nouvelle ligne.
  const stack = [[0, 0, 0]];
  while (stack.length) {
    const [id, depth, row] = stack.pop();
    const n = nodes.get(id);
    if (!n) continue;
    pos.set(id, { x: depth, y: row });
    maxDepth = Math.max(maxDepth, depth);
    const kids = n.kids || [];
    // Empilés à l'envers pour traiter le premier enfant (ligne principale) en premier.
    const extra = kids.slice(1).map((k) => [k, depth + 1, ++maxRow]).reverse();
    for (const e of extra) stack.push(e);
    if (kids.length) stack.push([kids[0], depth + 1, row]);
  }
  return { nodes, pos, maxRow, maxDepth };
}

function renderTree() {
  const svg = $("#tree");
  svg.innerHTML = "";
  if (!S || !S.game || !S.tree) return;
  const { nodes, pos, maxRow, maxDepth } = layoutTree();
  const W = (maxDepth + 2) * TREE_DX, H = (maxRow + 1) * TREE_DY + 16;
  svg.setAttribute("width", W);
  svg.setAttribute("height", H);
  svg.setAttribute("viewBox", `0 0 ${W} ${H}`);
  const px = (p) => 12 + p.x * TREE_DX, py = (p) => 18 + p.y * TREE_DY;
  const onLine = new Set(S.line || []);
  const mistakes = new Map((S.review ? S.review.mistakes : [])
    .filter((m) => !S.game.student || m.color === S.game.student).map((m) => [m.move_number, m.level]));
  // Numéros de coups
  for (let d = 10; d <= maxDepth; d += 10) el("text", { x: 12 + d * TREE_DX, y: 9, fill: "#8d94a3", "font-size": 9, "text-anchor": "middle" }, svg).textContent = d;
  // Liens
  for (const n of S.tree) {
    if (n.parent == null) continue;
    const a = pos.get(n.parent), b = pos.get(n.id);
    if (!a || !b) continue;
    const d = a.y === b.y ? `M${px(a)},${py(a)}L${px(b)},${py(b)}` : `M${px(a)},${py(a)}L${px(b) - TREE_DX / 2},${py(b)}L${px(b)},${py(b)}`;
    el("path", { d, fill: "none", stroke: onLine.has(n.id) ? "#8d94a3" : "#3a404c", "stroke-width": onLine.has(n.id) ? 2 : 1.5 }, svg);
  }
  // Nœuds
  for (const n of S.tree) {
    const p = pos.get(n.id);
    if (!p) continue;
    const g = el("g", { class: "tnode" }, svg);
    const cx = px(p), cy = py(p);
    if (n.id === S.current) el("circle", { cx, cy, r: 10, fill: "none", stroke: "#ff3d7f", "stroke-width": 2.5 }, g);
    if (n.c == null) {
      el("rect", { x: cx - 5, y: cy - 5, width: 10, height: 10, rx: 2, fill: "#8d94a3" }, g);
    } else {
      const lvl = n.main ? mistakes.get(p.x) : null;
      const ring = n.src === "sensei" ? "#5fb3a1" : n.src === "user" ? "#3d7fe0"
        : lvl === "gaffe" ? "#e0564f" : lvl === "erreur" ? "#e3b448" : lvl ? "#b8c27a" : "#555";
      el("circle", { cx, cy, r: 6.5, fill: n.c === "B" ? "#111" : "#eee", stroke: ring, "stroke-width": n.main && !lvl ? 1 : 2.5 }, g);
      if (n.marked) el("circle", { cx: cx + 6, cy: cy - 6, r: 2.5, fill: "#9b5de5" }, g);
    }
    const who = n.src === "sensei" ? " · variante de Sensei" : n.src === "user" ? " · ta variante" : "";
    el("title", {}, g).textContent = n.c == null ? "Début" : `Coup ${p.x} · ${n.c === "B" ? "Noir" : "Blanc"} ${n.m}${who}`
      + (n.main ? "" : "\nClic droit : supprimer cette variante");
    el("circle", { cx, cy, r: 10, fill: "transparent" }, g); // zone cliquable
    g.addEventListener("click", () => post("/api/goto-node", { id: n.id }).catch(() => {}));
    g.addEventListener("contextmenu", (e) => {
      e.preventDefault();
      if (!n.main && confirm("Supprimer cette variante (et sa suite) ?")) post("/api/delete-node", { id: n.id }).catch(() => {});
    });
  }
  // Garder la position actuelle visible
  const cur = pos.get(S.current);
  const wrap = $("#tree-wrap");
  if (cur) {
    const x = px(cur), y = py(cur);
    if (x < wrap.scrollLeft + 30 || x > wrap.scrollLeft + wrap.clientWidth - 30) wrap.scrollLeft = x - wrap.clientWidth / 2;
    if (y < wrap.scrollTop + 10 || y > wrap.scrollTop + wrap.clientHeight - 10) wrap.scrollTop = y - wrap.clientHeight / 2;
  }
  const nVar = S.tree.filter((n) => !n.main && nodes.get(n.parent) && nodes.get(n.parent).main).length;
  $("#tree-info").textContent = nVar ? `${nVar} variante${nVar > 1 ? "s" : ""} · bleu = toi, vert = Sensei · clic : y aller · ↑↓ : changer de variante` : "joue un coup sur le plateau pour créer une variante";
}

function render() {
  if (!S) return;
  renderInfo();
  renderBoard();
  renderTree();
  renderGraph();
}

// ------------------------------------------------------------------ chat
const TOOL_FR = {
  get_position: "regarde le plateau", get_game_review: "lit la revue de la partie", go_to_move: "va au coup",
  play_moves: "joue une variante", undo: "recule", back_to_game: "revient à la partie", analyze_position: "analyse avec KataGo",
  evaluate_moves: "compare des coups", annotate: "annote le plateau", clear_annotations: "efface les annotations",
  list_games: "liste les parties", load_game: "ouvre une partie", read_student_profile: "lit ton carnet", save_student_note: "note dans ton carnet",
};

function inline(s) {
  return s
    .replace(/`([^`]+)`/g, "<code>$1</code>")
    .replace(/\*\*([^*]+)\*\*/g, "<b>$1</b>")
    .replace(/(^|[^*])\*([^*\n]+)\*/g, "$1<i>$2</i>");
}

function markdown(src) {
  const lines = esc(src).split("\n");
  let html = "", list = null, para = [];
  const flushPara = () => { if (para.length) { html += `<p>${inline(para.join("<br>"))}</p>`; para = []; } };
  const closeList = () => { if (list) { html += `</${list}>`; list = null; } };
  for (const line of lines) {
    let m;
    if ((m = line.match(/^\s*[-*•]\s+(.*)/))) {
      flushPara();
      if (list !== "ul") { closeList(); html += "<ul>"; list = "ul"; }
      html += `<li>${inline(m[1])}</li>`;
    } else if ((m = line.match(/^\s*\d+[.)]\s+(.*)/))) {
      flushPara();
      if (list !== "ol") { closeList(); html += "<ol>"; list = "ol"; }
      html += `<li>${inline(m[1])}</li>`;
    } else if ((m = line.match(/^#{1,4}\s+(.*)/))) {
      flushPara(); closeList();
      html += `<h4>${inline(m[1])}</h4>`;
    } else if ((m = line.match(/^&gt;\s?(.*)/))) {
      flushPara(); closeList();
      html += `<blockquote>${inline(m[1])}</blockquote>`;
    } else if (!line.trim()) {
      flushPara(); closeList();
    } else {
      closeList();
      para.push(line);
    }
  }
  flushPara(); closeList();
  return linkCoords(html);
}

function linkCoords(html) {
  const size = S && S.game ? S.game.size : 19;
  return html.split(/(<[^>]+>)/).map((part) => part.startsWith("<") ? part :
    part.replace(/\b([A-HJ-T])(\d{1,2})\b/g, (all, l, n) => {
      const x = LETTERS.indexOf(l), y = parseInt(n, 10);
      return x < size && y >= 1 && y <= size ? `<span class="coord" data-c="${all}">${all}</span>` : all;
    })).join("");
}

function renderChat() {
  const box = $("#messages");
  const atBottom = box.scrollHeight - box.scrollTop - box.clientHeight < 60;
  box.innerHTML = "";
  $("#ai-label").textContent = chatInfo.enabled ? `· ${AI_LABELS[chatInfo.provider] || ""}` : "";
  for (const id of ["#quick", "#chat-form"]) $(id).classList.toggle("hidden", !chatInfo.enabled);
  if (!chatInfo.enabled) {
    box.innerHTML = `<div class="chat-disabled"><p><b>Le professeur IA est désactivé.</b></p>
      <p>Le plateau, l'analyse KataGo et la revue de tes erreurs fonctionnent sans lui.
      Pour avoir des explications en français, choisis une IA (Claude, ChatGPT, DeepSeek, Ollama…).</p>
      ${chatInfo.error ? `<p style="color:var(--danger)">${esc(chatInfo.error)}</p>` : ""}
      <button class="btn primary" onclick="openSettings('ai')">Configurer une IA</button></div>`;
    return;
  }
  if (!chat.length) {
    box.innerHTML = `<div class="empty-chat"><p><b>Pose-moi n'importe quelle question sur la position affichée.</b></p>
      <p>Je vois le même plateau que toi : je peux jouer des variantes, dessiner dessus et vérifier avec KataGo.</p>
      <p>Astuce : clique sur une erreur (en haut) pour te placer juste avant, puis demande « pourquoi ? ».</p></div>`;
  }
  chat.forEach((m, i) => {
    const d = document.createElement("div");
    d.className = "msg " + m.role + (busy && i === chat.length - 1 && m.role === "assistant" ? " thinking" : "");
    if (m.role === "user") d.textContent = m.text;
    else {
      const tools = (m.tools || []).map((t) => `<span class="tool">🔧 ${TOOL_FR[t] || t}</span>`).join("");
      const links = (m.nodes || []).map((n) => `<button class="node-link${S && n.id === S.current ? " active" : ""}" data-node="${n.id}">`
        + `${n.label.startsWith("variante") ? "🔀" : "📍"} ${esc(n.label)}</button>`).join("");
      d.innerHTML = (tools ? `<div class="tools">${tools}</div>` : "") + `<div class="body">${markdown(m.text || "")}</div>`
        + (links ? `<div class="node-links">${links}</div>` : "");
    }
    box.appendChild(d);
  });
  if (atBottom || busy) box.scrollTop = box.scrollHeight;
  $("#btn-send").classList.toggle("hidden", busy);
  $("#btn-stop").classList.toggle("hidden", !busy);
}

$("#messages").addEventListener("click", (e) => {
  const b = e.target.closest(".node-link");
  if (b) post("/api/goto-node", { id: parseInt(b.dataset.node, 10) }).catch(() => toast("Cette position n'existe plus (variante supprimée ?)"));
});
$("#messages").addEventListener("mouseover", (e) => {
  const c = e.target.closest(".coord");
  const v = c ? c.dataset.c : null;
  if (v !== highlight) { highlight = v; queueRender(); }
});

async function sendChat(text) {
  text = text.trim();
  if (!text || busy) return;
  chat.push({ role: "user", text });
  busy = true;
  renderChat();
  try {
    await post("/api/chat", { text });
  } catch {
    chat.pop();
    busy = false;
    renderChat();
  }
}

$("#chat-form").addEventListener("submit", (e) => {
  e.preventDefault();
  const i = $("#chat-input");
  const t = i.value;
  i.value = "";
  sendChat(t);
});
$("#chat-input").addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); $("#chat-form").requestSubmit(); }
});
$("#quick").addEventListener("click", (e) => { const b = e.target.closest("button"); if (b) sendChat(b.dataset.q); });
$("#btn-stop").onclick = () => post("/api/chat/stop");
$("#btn-reset").onclick = () => { if (confirm("Commencer une nouvelle conversation ? (Ton carnet de progression est conservé.)")) post("/api/chat/reset"); };

// ------------------------------------------------------------------ parties
let games = [], sizeFilter = "", sourceFilter = "";
const fmtDate = (t) => new Date(t * 1000).toLocaleString("fr-FR", { day: "2-digit", month: "2-digit", year: "2-digit", hour: "2-digit", minute: "2-digit" });

async function refreshGames() {
  games = await (await fetch("/api/games")).json();
  renderGames();
}
async function openGames() {
  $("#games-modal").classList.remove("hidden");
  if (!CFG) await loadConfig();
  const user = CFG.config.ogs.username;
  $("#btn-sync").classList.toggle("hidden", !user);
  $("#sync-user").textContent = user || "";
  await refreshGames();
  $("#game-search").focus();
}
function renderGames() {
  const sources = [...new Set(games.map((g) => g.folder))];
  const sf = $("#source-filter");
  sf.innerHTML = ["", ...sources].map((f) => `<button data-src="${esc(f)}" class="${f === sourceFilter ? "active" : ""}">${f ? esc(f) : "Toutes sources"}</button>`).join("");
  const q = $("#game-search").value.trim().toLowerCase();
  const list = games.filter((g) => (!sizeFilter || String(g.size) === sizeFilter) && (!sourceFilter || g.folder === sourceFilter)
    && (!q || (g.black + " " + g.white).toLowerCase().includes(q)));
  const box = $("#games-list");
  box.innerHTML = list.length ? "" : `<p class="muted">Aucune partie.</p>`;
  for (const g of list) {
    const d = document.createElement("div");
    d.className = "game-row" + (S && S.game && S.game.id === g.id ? " active" : "");
    const name = (c) => {
      const n = c === "B" ? g.black : g.white, r = c === "B" ? g.black_rank : g.white_rank;
      const txt = `${c === "B" ? "⚫" : "⚪"} ${esc(n)}${r ? ` <span class="rank">${esc(r)}</span>` : ""}`;
      return g.student === c ? `<b>${txt}</b>` : txt;
    };
    const outcome = g.outcome ? `<span class="outcome ${g.outcome}">${g.outcome === "win" ? "Victoire" : "Défaite"}</span>` : `<span class="muted small-text">${esc(g.result || "")}</span>`;
    d.innerHTML = `<span class="muted">${fmtDate(g.played)}</span><span class="vs">${name("B")} &nbsp;vs&nbsp; ${name("W")}</span>`
      + `<span>${g.size}×${g.size}</span><span class="muted">${g.moves} coups</span>${outcome}<span class="src">${esc(g.folder)}</span>`;
    d.onclick = async () => { await post("/api/load", { id: g.id }); $("#games-modal").classList.add("hidden"); };
    box.appendChild(d);
  }
}
$("#btn-games").onclick = openGames;
$("#game-search").addEventListener("input", renderGames);
$("#size-filter").addEventListener("click", (e) => {
  const b = e.target.closest("button");
  if (!b) return;
  sizeFilter = b.dataset.size;
  document.querySelectorAll("#size-filter button").forEach((x) => x.classList.toggle("active", x === b));
  renderGames();
});
$("#source-filter").addEventListener("click", (e) => {
  const b = e.target.closest("button");
  if (b) { sourceFilter = b.dataset.src; renderGames(); }
});
async function ogsImport(query) {
  $("#ogs-status").textContent = "Import depuis OGS en cours… (peut prendre une minute)";
  try {
    const r = await post("/api/ogs", { query });
    games = r.games;
    $("#ogs-status").textContent = r.username ? `${r.username} : ${r.new} nouvelle(s) partie(s).` : "Partie importée.";
    if (r.username) { await loadConfig(); openGames(); } else renderGames();
  } catch {
    $("#ogs-status").textContent = "Échec de l'import.";
  }
}
$("#ogs-form").addEventListener("submit", (e) => {
  e.preventDefault();
  const q = $("#ogs-input").value.trim();
  if (q) ogsImport(q);
});
$("#btn-sync").onclick = () => ogsImport(CFG.config.ogs.username);

async function importFiles(files) {
  let last = null;
  for (const f of files) {
    if (!/\.sgf$/i.test(f.name)) { toast(`${f.name} n'est pas un fichier .sgf`); continue; }
    try { last = await post("/api/import-sgf", { name: f.name, content: await f.text() }); } catch {}
  }
  if (last) { $("#games-modal").classList.add("hidden"); }
}
$("#sgf-file").addEventListener("change", (e) => { importFiles([...e.target.files]); e.target.value = ""; });
let dragDepth = 0;
window.addEventListener("dragenter", (e) => { if ([...e.dataTransfer.types].includes("Files")) { dragDepth++; $("#drop").classList.remove("hidden"); } });
window.addEventListener("dragleave", () => { if (--dragDepth <= 0) { dragDepth = 0; $("#drop").classList.add("hidden"); } });
window.addEventListener("dragover", (e) => e.preventDefault());
window.addEventListener("drop", (e) => {
  e.preventDefault();
  dragDepth = 0;
  $("#drop").classList.add("hidden");
  importFiles([...e.dataTransfer.files]);
});

// Fermer les fenêtres modales (clic à côté, ✕, Échap)
document.querySelectorAll(".modal").forEach((m) => m.addEventListener("click", (e) => {
  if (e.target === m || e.target.closest("[data-close]")) m.classList.add("hidden");
}));

// ------------------------------------------------------------------ moteur KataGo
function renderEngine(E) {
  ENGINE = E;
  const eng = $("#engine");
  eng.textContent = "KataGo : " + (E.label || "?");
  eng.classList.toggle("ok", E.state === "ready");
  const setup = $("#engine-setup");
  const show = ["absent", "downloading", "error"].includes(E.state) || (E.state === "tuning");
  setup.classList.toggle("hidden", !show);
  if (!show) return;
  const downloading = E.state === "downloading";
  $("#btn-install").classList.toggle("hidden", downloading || E.state === "tuning");
  $("#install-progress").classList.toggle("hidden", !downloading);
  $("#install-progress > div").style.width = `${E.progress || 0}%`;
  setup.querySelector("h3").textContent = E.state === "tuning" ? "Calibrage de la carte graphique…"
    : E.state === "error" ? "KataGo a un problème" : "Installer le moteur d'analyse";
  $("#engine-msg").textContent = E.state === "tuning"
    ? "Première utilisation : KataGo optimise ses calculs pour ta carte graphique (1 à 2 minutes, une seule fois)."
    : E.message || "";
  if (E.state === "error") $("#btn-install").textContent = "Réessayer";
}
$("#btn-install").onclick = () => post("/api/engine/install");

// ------------------------------------------------------------------ réglages
let CFG = null, ENGINE = null;
const AI_LABELS = { "claude-code": "Claude Code", anthropic: "Claude (API)", openai: "API compatible OpenAI", none: "" };

async function loadConfig() {
  CFG = await (await fetch("/api/config")).json();
  return CFG;
}
function field(name) { return $(`#settings-form [name="${name}"]`); }
function getPath(obj, path) { return path.split(".").reduce((o, k) => (o ? o[k] : undefined), obj); }

async function openSettings(tab = "ai") {
  await loadConfig();
  const c = CFG.config;
  const presetSel = field("ai.preset");
  presetSel.innerHTML = Object.entries(CFG.presets).map(([k, p]) => `<option value="${k}">${esc(p.label)}</option>`).join("");
  for (const el of $("#settings-form").querySelectorAll("[name]")) {
    const v = getPath(c, el.name);
    if (el.type === "checkbox") el.checked = !!v;
    else if (v !== undefined && el.name !== "ai.api_key") el.value = Array.isArray(v) ? v.join("\n") : v;
  }
  field("ai.preset").value = c.ai.preset || "openai";
  field("ai.api_key").value = "";
  updateKeyNote();
  const cq = c.sources.conquest;
  field("sources.conquest_mode").value = cq === "auto" ? "auto" : cq ? "path" : "off";
  field("sources.conquest_path").value = cq !== "auto" ? cq : "";
  $("#conquest-detect").textContent = c.detected.conquest ? `Trouvé : ${c.detected.conquest}` : "Jeu non détecté sur ce PC.";
  $("#claude-detect").textContent = c.detected.claude_cli ? "✓ commande claude trouvée." : "⚠ commande claude introuvable.";
  renderEngineInfo();
  $("#about").innerHTML = `<b>Go Sensei ${esc(CFG.version)}</b><br>Réglages : <code>${esc(CFG.paths.config)}</code><br>
    Données (revues, parties OGS, carnet de l'élève, KataGo) : <code>${esc(CFG.paths.data)}</code><br><br>
    Analyse : <a href="https://github.com/lightvector/KataGo" target="_blank">KataGo</a> (licence MIT).
    Parties en ligne : <a href="https://online-go.com" target="_blank">OGS</a>.`;
  updateSettingsVisibility();
  showTab(tab);
  $("#settings-status").textContent = "";
  $("#settings-modal").classList.remove("hidden");
}
function renderEngineInfo() {
  const E = ENGINE || CFG.engine;
  const bins = Object.entries(E.binaries || {}).map(([k, v]) => `${k} : <code>${esc(v)}</code>`).join("<br>") || "aucun";
  $("#engine-info").innerHTML = `État : <b>${esc(E.label)}</b>${E.message ? ` — ${esc(E.message)}` : ""}<br>
    Programme(s) : ${bins}<br>Réseau : ${E.model ? `<code>${esc(E.model)}</code>` : "aucun"}`;
}
function showTab(tab) {
  document.querySelectorAll("#settings-tabs button").forEach((b) => b.classList.toggle("active", b.dataset.tab === tab));
  document.querySelectorAll("#settings-form [data-pane]").forEach((p) => p.classList.toggle("hidden", p.dataset.pane !== tab));
}
function updateKeyNote() {
  // Une clé par service : on indique si le service choisi dans le formulaire en a une.
  const prov = field("ai.provider").value;
  const slot = prov === "anthropic" ? "anthropic" : prov === "openai" ? (field("ai.preset").value || "custom") : null;
  const has = slot && CFG && (CFG.config.ai.key_slots || []).includes(slot);
  $("#key-note").textContent = has ? "Une clé est enregistrée pour ce service (laisser vide pour la garder)."
    : slot ? "Aucune clé enregistrée pour ce service." : "";
}

function updateSettingsVisibility() {
  const prov = field("ai.provider").value;
  document.querySelectorAll("#settings-form [data-show]").forEach((el) => el.classList.toggle("hidden", !el.dataset.show.split(" ").includes(prov)));
  document.querySelector("[data-conquest-path]").classList.toggle("hidden", field("sources.conquest_mode").value !== "path");
}
$("#settings-tabs").addEventListener("click", (e) => { const b = e.target.closest("button"); if (b) showTab(b.dataset.tab); });
field("ai.provider").addEventListener("change", () => { $("#model-list").innerHTML = ""; field("ai.model").value = ""; updateSettingsVisibility(); updateKeyNote(); });
field("sources.conquest_mode").addEventListener("change", updateSettingsVisibility);
field("ai.preset").addEventListener("change", () => {
  const p = CFG.presets[field("ai.preset").value];
  if (p && p.base_url) field("ai.base_url").value = p.base_url;
  field("ai.model").value = "";
  updateKeyNote();
});
$("#btn-models").onclick = async () => {
  const body = { provider: field("ai.provider").value, base_url: field("ai.base_url").value, api_key: field("ai.api_key").value };
  $("#settings-status").textContent = "Recherche des modèles…";
  try {
    const r = await post("/api/ai/models", body);
    $("#model-list").innerHTML = r.models.map((m) => `<option value="${esc(m)}">`).join("");
    $("#settings-status").textContent = `${r.models.length} modèle(s) : clique dans le champ Modèle pour choisir.`;
  } catch { $("#settings-status").textContent = "Impossible de lister les modèles (adresse ou clé ?)."; }
};
$("#btn-engine-restart").onclick = () => post("/api/engine/restart");
$("#btn-engine-install").onclick = () => post("/api/engine/install");
$("#settings-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const num = (n) => parseInt(field(n).value || "0", 10) || 0;
  const mode = field("sources.conquest_mode").value;
  const patch = {
    ai: { provider: field("ai.provider").value, preset: field("ai.preset").value, base_url: field("ai.base_url").value.trim(),
          model: field("ai.model").value.trim(), api_key: field("ai.api_key").value.trim() },
    katago: { backend: field("katago.backend").value, live_visits: num("katago.live_visits"), review_visits: num("katago.review_visits"),
              binary: field("katago.binary").value.trim(), model: field("katago.model").value.trim() },
    ogs: { username: field("ogs.username").value.trim(), auto_sync: field("ogs.auto_sync").checked, sync_count: num("ogs.sync_count") || 30 },
    sources: { conquest: mode === "auto" ? "auto" : mode === "off" ? "" : field("sources.conquest_path").value.trim(),
               folders: field("sources.folders").value.split("\n").map((x) => x.trim()).filter(Boolean) },
  };
  try {
    CFG = await post("/api/config", patch);
    $("#settings-status").textContent = "✓ Enregistré";
    field("ai.api_key").value = "";
    updateKeyNote();
    loadChat();
  } catch { $("#settings-status").textContent = "Échec de l'enregistrement."; }
});
$("#btn-settings").onclick = () => openSettings();

// ------------------------------------------------------------------ quitter
$("#btn-quit").onclick = () => {
  if (confirm("Quitter Go Sensei ? (KataGo et le professeur IA seront arrêtés)")) post("/api/shutdown").catch(() => {});
};
function showShutdown() {
  $("#shutdown").classList.remove("hidden");
  setTimeout(() => window.close(), 300);
}

// ------------------------------------------------------------------ contrôles
document.querySelectorAll("[data-step]").forEach((b) => {
  b.onclick = () => {
    const k = parseInt(b.dataset.step, 10);
    if (Math.abs(k) === 999) post("/api/goto", { n: k > 0 ? S.main.length : 0 });
    else post("/api/step", { k });
  };
});
$("#btn-main").onclick = () => post("/api/main");
for (const k of Object.keys(opts)) {
  const box = $("#opt-" + (k === "suggest" ? "suggest" : k === "owner" ? "owner" : "numbers"));
  try { const v = localStorage.getItem("gs-" + k); if (v != null) box.checked = v === "1"; } catch {}
  opts[k] = box.checked;
  box.onchange = () => { opts[k] = box.checked; try { localStorage.setItem("gs-" + k, box.checked ? "1" : "0"); } catch {} queueRender(); };
}
document.addEventListener("keydown", (e) => {
  const openModal = document.querySelector(".modal:not(.hidden)");
  if (openModal) {
    if (e.key === "Escape") openModal.classList.add("hidden");
    return;
  }
  if (!S || !S.game || e.target.closest("textarea, input")) return;
  const step = (k) => post("/api/step", { k }).catch(() => {});
  if (e.key === "ArrowUp") post("/api/sibling", { d: -1 }).catch(() => {});
  else if (e.key === "ArrowDown") post("/api/sibling", { d: 1 }).catch(() => {});
  else if (e.key === "ArrowLeft") step(e.shiftKey ? -5 : -1);
  else if (e.key === "ArrowRight") step(e.shiftKey ? 5 : 1);
  else if (e.key === "Home") post("/api/goto", { n: 0 });
  else if (e.key === "End") post("/api/goto", { n: S.main.length });
  else if (e.key === "Escape") post("/api/main");
  else return;
  e.preventDefault();
});
let wheelLock = 0;
$("#board-wrap").addEventListener("wheel", (e) => {
  e.preventDefault();
  const now = Date.now();
  if (now - wheelLock < 90) return;
  wheelLock = now;
  post("/api/step", { k: e.deltaY > 0 ? 1 : -1 }).catch(() => {});
}, { passive: false });
window.addEventListener("resize", queueRender);

// ------------------------------------------------------------------ temps réel
function connect() {
  const es = new EventSource("/events");
  es.addEventListener("state", (e) => {
    const prev = S && S.current;
    S = JSON.parse(e.data);
    queueRender();
    if (prev !== S.current) renderChat(); // met à jour le lien de position actif
  });
  es.addEventListener("chat", (e) => {
    const ev = JSON.parse(e.data);
    if (ev.kind === "start") {
      busy = true;
      chat.push({ role: "assistant", text: "", tools: [] });
    } else if (ev.kind === "delta") {
      const last = chat[chat.length - 1];
      if (last && last.role === "assistant") last.text += ev.text;
    } else if (ev.kind === "node") {
      const last = chat[chat.length - 1];
      if (last && last.role === "assistant") {
        last.nodes = last.nodes || [];
        const prev = last.nodes[last.nodes.length - 1];
        if (prev && prev.id === ev.id) prev.label = ev.label;
        else last.nodes.push({ id: ev.id, label: ev.label });
      }
    } else if (ev.kind === "tool") {
      const last = chat[chat.length - 1];
      if (last && last.role === "assistant") last.tools.push(ev.name);
    } else if (ev.kind === "done") {
      busy = false;
    } else if (ev.kind === "reset") {
      chat = [];
      busy = false;
    } else if (ev.kind === "reload") {
      return loadChat();
    }
    renderChat();
  });
  es.addEventListener("engine", (e) => {
    renderEngine(JSON.parse(e.data));
    if (!$("#settings-modal").classList.contains("hidden")) renderEngineInfo();
  });
  es.addEventListener("games", () => { if (!$("#games-modal").classList.contains("hidden")) refreshGames(); });
  es.addEventListener("shutdown", () => { stopped = true; es.close(); showShutdown(); });
  es.onerror = () => { if (!stopped) { $("#engine").textContent = "serveur déconnecté…"; $("#engine").classList.remove("ok"); } };
  es.onopen = loadChat;
}

let stopped = false;
let chatInfo = { enabled: true, provider: "" };
async function loadChat() {
  try {
    chatInfo = await (await fetch("/api/chat")).json();
    chat = chatInfo.history;
    busy = chatInfo.busy;
    renderChat();
  } catch {}
}

loadConfig().catch(() => {});
connect();

// Ouverture directe d'un écran via l'adresse (#parties, #reglages)
if (location.hash === "#parties") openGames();
else if (location.hash.startsWith("#reglages")) openSettings(location.hash.split("-")[1] || "ai");
