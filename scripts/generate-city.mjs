#!/usr/bin/env node
/**
 * Contribution City — an animated isometric skyline for a GitHub profile README.
 *
 * Layout: the last twelve months become twelve districts on a 4x3 grid, newest
 * month downtown. Each district holds a month of days as lots. Nothing is empty:
 * a zero-contribution day is a low-rise with dim windows, and a handful of lots
 * are parks. Height is baseHeight + k*sqrt(count), capped, so one commit still
 * reads as a building while a ninety-four day becomes the tower with the crown.
 *
 * Rendering: one ground plane in the same isometric projection as the towers,
 * streets as lighter strips between districts, a bay beyond the city edge with
 * faded reflections, three layers of non-data skyline behind it, and a single
 * fit transform computed from the drawing's own bounding box so nothing clips.
 *
 * Output is a self-contained SVG: no JavaScript, no external CSS, no fonts, no
 * images. Only CSS keyframes and SMIL, which survive GitHub's camo proxy.
 *
 *   node scripts/generate-city.mjs                 # live (GH_PAT or GITHUB_TOKEN)
 *   node scripts/generate-city.mjs --sample        # synthetic year, no network
 *   CITY_LOGIN=someone node scripts/generate-city.mjs
 */
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";

const LOGIN = process.env.CITY_LOGIN || "mgkvibez";
const TOKEN = process.env.GH_PAT || process.env.GITHUB_TOKEN || "";
const OUT = process.env.CITY_OUT || "assets";
const SAMPLE = process.argv.includes("--sample");

const VIEW_W = 1200;
const VIEW_H = 800;
const FILL = 0.85;            // the drawing fills 85% of the viewBox
const THEME_KEYS = ["gold", "neon"];

/* ------------------------------------------------------------ small helpers */

function mulberry32(seed) {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

function fnv1a(text) {
  let h = 2166136261;
  for (let i = 0; i < text.length; i += 1) {
    h ^= text.charCodeAt(i);
    h = Math.imul(h, 16777619);
  }
  return h >>> 0;
}

const n1 = (v) => Math.round(v * 10) / 10;
const clamp = (v, lo, hi) => Math.min(hi, Math.max(lo, v));
const pick = (rnd, list) => list[Math.floor(rnd() * list.length) % list.length];
const esc = (s) => String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");

/* --------------------------------------------------------------------- data */

const QUERY = `
query($login: String!) {
  user(login: $login) {
    contributionsCollection {
      contributionCalendar {
        weeks { contributionDays { date contributionCount } }
      }
    }
  }
}`;

async function graphql(query, variables, attempts = 4) {
  let last;
  for (let attempt = 0; attempt < attempts; attempt += 1) {
    if (attempt) await new Promise((r) => setTimeout(r, 2000 * attempt));
    try {
      const res = await fetch("https://api.github.com/graphql", {
        method: "POST",
        headers: {
          Authorization: `bearer ${TOKEN}`,
          "Content-Type": "application/json",
          "User-Agent": "contribution-city",
        },
        body: JSON.stringify({ query, variables }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const body = await res.json();
      if (body.errors) throw new Error(JSON.stringify(body.errors));
      return body.data.user;
    } catch (error) {
      last = error;
    }
  }
  throw new Error(`GraphQL failed after ${attempts} attempts: ${last}`);
}

function sampleDays() {
  const rnd = mulberry32(fnv1a("sample-city-v2"));
  const out = [];
  const today = new Date();
  for (let i = 369; i >= 0; i -= 1) {
    const d = new Date(today.getTime() - i * 86400000);
    const weekday = d.getUTCDay();
    const burst = i % 41 < 4 ? 5 : 1;
    const weekend = weekday === 0 || weekday === 6 ? 0.35 : 1;
    out.push({
      date: d.toISOString().slice(0, 10),
      count: Math.max(0, Math.round(rnd() * 13 * burst * weekend)),
    });
  }
  return out;
}

async function loadDays() {
  if (SAMPLE) return sampleDays();
  if (!TOKEN) {
    console.warn("no GH_PAT or GITHUB_TOKEN — rendering the synthetic year");
    return sampleDays();
  }
  const user = await graphql(QUERY, { login: LOGIN });
  return user.contributionsCollection.contributionCalendar.weeks.flatMap((w) =>
    w.contributionDays.map((d) => ({ date: d.date, count: d.contributionCount })),
  );
}

function statsOf(days) {
  const total = days.reduce((sum, d) => sum + d.count, 0);
  let longest = 0;
  let run = 0;
  let busiest = days[0];
  for (const day of days) {
    run = day.count > 0 ? run + 1 : 0;
    longest = Math.max(longest, run);
    if (day.count > busiest.count) busiest = day;
  }
  let current = 0;
  for (let i = days.length - 1; i >= 0; i -= 1) {
    if (days[i].count > 0) current += 1;
    else break;
  }
  return { total, current, longest, busiest, active: days.filter((d) => d.count > 0).length };
}

/* ------------------------------------------------------------------- layout */

const LOT_X = 34;
const LOT_Z = 22;
const LOT_COLS = 6;
const LOT_ROWS = 6;
const STREET = 26;
const DIST_X = LOT_COLS * LOT_X;      // 204
const DIST_Z = LOT_ROWS * LOT_Z;      // 110
const CITY_X = 4 * DIST_X + 3 * STREET;
const CITY_Z = 3 * DIST_Z + 2 * STREET;

const HEIGHT_BASE = 11;
const HEIGHT_K = 20.5;
const HEIGHT_CAP = 198;

/** Newest month downtown: front row, middle columns. */
const DOWNTOWN = { col: 1, row: 2 };

function monthsOf(days) {
  const map = new Map();
  for (const day of days) {
    const ym = day.date.slice(0, 7);
    if (!map.has(ym)) map.set(ym, []);
    map.get(ym).push(day);
  }
  return [...map.entries()]
    .sort((a, b) => (a[0] < b[0] ? -1 : 1))
    .slice(-12)
    .map(([ym, list]) => ({ ym, days: list }));
}

/** Assign months to a 4x3 grid, nearest the downtown slot gets the newest. */
function assignSlots(months) {
  const slots = [];
  for (let row = 0; row < 3; row += 1) {
    for (let col = 0; col < 4; col += 1) {
      const d = Math.hypot(col - DOWNTOWN.col, (row - DOWNTOWN.row) * 1.4);
      slots.push({ col, row, d });
    }
  }
  slots.sort((a, b) => a.d - b.d);
  const newestFirst = [...months].reverse();
  return newestFirst.map((month, i) => ({ ...month, ...slots[i % slots.length] }));
}

function heightFor(count, peak) {
  const scaled = HEIGHT_BASE + HEIGHT_K * Math.sqrt(Math.max(0, count));
  const eased = peak > 0 ? Math.min(1, Math.sqrt(count / Math.max(1, peak))) : 0;
  return Math.min(HEIGHT_CAP, scaled * (0.55 + 0.45 * eased));
}

/* ------------------------------------------------------------------- themes */

const THEMES = {
  gold: {
    key: "gold",
    label: "Contribution City — dusk",
    sky: [["0%", "#141033"], ["34%", "#33204f"], ["58%", "#6d2f4e"], ["78%", "#b64a2c"], ["100%", "#f2a05a"]],
    sun: { colour: "#ffe3a6", halo: "#ff9c4a" },
    ground: "#2a1d18",
    groundEdge: "#1a110e",
    street: "#4b3527",
    lane: "#6b4a30",
    water: ["#231428", "#3a1f2c", "#4d2733"],
    faces: { left: "#241811", right: "#3d2a1c", top: "#7a5632" },
    trim: "#e6c07b",
    win: "#ffcf87",
    winDim: "#7a5327",
    spire: "#ffe9b0",
    park: "#33503a",
    tree: "#486b46",
    skyline: ["#2b2140", "#241b36", "#1d162c"],
    hudBg: "rgba(14,10,24,0.78)",
    hudLine: "#e6c07b",
    hudText: "#f7e6c2",
    hudDim: "#b99a6b",
    accent: "#e6c07b",
  },
  neon: {
    key: "neon",
    label: "Contribution City — fog",
    sky: [["0%", "#03060f"], ["40%", "#071127"], ["70%", "#0d1f3c"], ["88%", "#14304f"], ["100%", "#1c4463"]],
    sun: { colour: "#c9fbff", halo: "#22d3ee" },
    ground: "#0a1524",
    groundEdge: "#050a12",
    street: "#132639",
    lane: "#1d3d55",
    water: ["#04121d", "#062636", "#0b3a4a"],
    faces: { left: "#0c1726", right: "#16283e", top: "#24425e" },
    trim: "#22d3ee",
    win: "#7ff0ff",
    winDim: "#1b5a6e",
    spire: "#9dffb4",
    park: "#123a2c",
    tree: "#1d6b4a",
    skyline: ["#0a1626", "#0b1a2c", "#0d2034"],
    hudBg: "rgba(4,12,20,0.8)",
    hudLine: "#22d3ee",
    hudText: "#dcfaff",
    hudDim: "#5d9cb0",
    accent: "#00ff41",
    neon: ["#22d3ee", "#f472b6", "#00ff41"],
  },
};

/* ------------------------------------------------------------------ drawing */

class Scene {
  constructor() {
    this.parts = [];
    this.minX = Infinity;
    this.minY = Infinity;
    this.maxX = -Infinity;
    this.maxY = -Infinity;
  }

  track(points) {
    for (const [x, y] of points) {
      if (!Number.isFinite(x) || !Number.isFinite(y)) continue;
      this.minX = Math.min(this.minX, x);
      this.minY = Math.min(this.minY, y);
      this.maxX = Math.max(this.maxX, x);
      this.maxY = Math.max(this.maxY, y);
    }
  }

  push(...items) {
    this.parts.push(...items);
  }

  poly(points, fill, extra = "") {
    this.track(points);
    const d = points.map(([x, y]) => `${n1(x)},${n1(y)}`).join(" ");
    this.parts.push(`<polygon points="${d}" fill="${fill}"${extra}/>`);
  }

  rect(x, y, w, h, fill, extra = "") {
    this.track([[x, y], [x + w, y + h]]);
    this.parts.push(
      `<rect x="${n1(x)}" y="${n1(y)}" width="${n1(w)}" height="${n1(h)}" fill="${fill}"${extra}/>`,
    );
  }

  line(x1, y1, x2, y2, stroke, width, opacity = 1) {
    this.track([[x1, y1], [x2, y2]]);
    this.parts.push(
      `<line x1="${n1(x1)}" y1="${n1(y1)}" x2="${n1(x2)}" y2="${n1(y2)}" stroke="${stroke}" stroke-width="${width}" opacity="${opacity}"/>`,
    );
  }

  toString() {
    return this.parts.join("");
  }
}

/** Isometric projection: world (X, Z) ground, H height above it. */
const iso = (x, z, h = 0) => [(x - z) * 0.5, (x + z) * 0.25 - h];
const isoPoly = (corners, h = 0) => corners.map(([x, z]) => iso(x, z, h));

/** Shrink a face toward its own centroid so windows do not touch the edges. */
function insetFace(points, factor) {
  const cx = points.reduce((s, p) => s + p[0], 0) / points.length;
  const cy = points.reduce((s, p) => s + p[1], 0) / points.length;
  return points.map(([x, y]) => [cx + (x - cx) * factor, cy + (y - cy) * factor]);
}

/** One prism: left face darkest, right face mid, top lightest. */
function prism(scene, cx, cz, sx, sz, y0, y1, theme, opts = {}) {
  const x0 = cx - sx / 2;
  const x1 = cx + sx / 2;
  const z0 = cz - sz / 2;
  const z1 = cz + sz / 2;

  const aTop = iso(x0, z0, y1);
  const bTop = iso(x1, z0, y1);
  const cTop = iso(x1, z1, y1);
  const dTop = iso(x0, z1, y1);
  const bBot = iso(x1, z0, y0);
  const cBot = iso(x1, z1, y0);
  const dBot = iso(x0, z1, y0);

  const rightFace = [bTop, cTop, cBot, bBot];
  const leftFace = [cTop, dTop, dBot, cBot];
  const roof = [aTop, bTop, cTop, dTop];

  scene.poly(leftFace, theme.faces.left);
  scene.poly(rightFace, theme.faces.right);
  if (opts.windows !== false) {
    scene.poly(insetFace(leftFace, 0.82), `url(#w-${theme.key})`, ' opacity="0.5"');
    scene.poly(insetFace(rightFace, 0.82), `url(#w-${theme.key})`);
  }
  scene.poly(roof, theme.faces.top, ` stroke="${theme.trim}" stroke-width="0.6" stroke-opacity="0.5"`);

  if (opts.trim) {
    // vertical light strip on the corner nearest the viewer
    scene.line(cTop[0], cTop[1], cBot[0], cBot[1], opts.trim, opts.trimWidth || 1.2, 0.95);
  }
  return { roof, rightFace, leftFace, corners: { aTop, bTop, cTop, dTop } };
}

/* ------------------------------------------------------------------- cities */

function buildCity(days, themeKey) {
  const theme = THEMES[themeKey];
  const st = statsOf(days);
  const peak = Math.max(1, ...days.map((d) => d.count));
  const months = assignSlots(monthsOf(days));
  const rnd = mulberry32(fnv1a(`${days[days.length - 1].date}|${themeKey}|v2`));
  const scene = new Scene();
  const flicker = [[], [], []];
  const cars = [];
  const spireLayer = [];
  const billboards = [];
  const beams = [];

  const x0 = 0;
  const z0 = 0;
  const waterStart = CITY_Z + 34;
  const pad = 46;
  const bandBays = [];

  /* --- background skyline: three hazy layers, no data, pure depth --------- */
  const backLayers = [
    { z: -150, hMax: 150, alpha: 0.30, step: 58 },
    { z: -96, hMax: 196, alpha: 0.45, step: 66 },
    { z: -52, hMax: 236, alpha: 0.6, step: 78 },
  ];
  const backObj = new Scene();
  backLayers.forEach((layer, li) => {
    const colour = theme.skyline[li];
    const hazy = {
      ...theme,
      faces: { left: colour, right: colour, top: theme.skyline[Math.min(2, li + 1)] },
      trim: colour,
    };
    for (let x = -190; x < CITY_X + 220; x += layer.step) {
      const jitter = (rnd() - 0.5) * layer.step * 0.5;
      const w = layer.step * (0.45 + rnd() * 0.4);
      const h = layer.hMax * (0.35 + rnd() * 0.65);
      prism(backObj, x + jitter, layer.z + (rnd() - 0.5) * 30, w, w * 0.62, 0, h, hazy, {
        windows: false,
      });
    }
  });
  scene.parts.push(`<g opacity="0.85">${backObj.toString()}</g>`);
  scene.minX = Math.min(scene.minX, backObj.minX);
  scene.minY = Math.min(scene.minY, backObj.minY);
  scene.maxX = Math.max(scene.maxX, backObj.maxX);
  scene.maxY = Math.max(scene.maxY, backObj.maxY);

  /* --- ground plane: one diamond, same projection as the towers ----------- */
  const groundPolys = {
    plate: [
      [x0 - pad, z0 - pad],
      [CITY_X + pad, z0 - pad],
      [CITY_X + pad, waterStart],
      [x0 - pad, waterStart],
    ],
  };
  scene.poly(isoPoly(groundPolys.plate), theme.ground, ` stroke="${theme.groundEdge}" stroke-width="1.5"`);

  /* --- streets: lighter strips in the gaps between districts -------------- */
  const streetRects = [];
  for (let c = 1; c < 4; c += 1) {
    const sx = c * DIST_X + (c - 1) * STREET;
    streetRects.push([
      [sx, z0 - pad * 0.7],
      [sx + STREET * 0.8, z0 - pad * 0.7],
      [sx + STREET * 0.8, waterStart - 12],
      [sx, waterStart - 12],
    ]);
  }
  for (let r = 1; r < 3; r += 1) {
    const sz = r * DIST_Z + (r - 1) * STREET;
    streetRects.push([
      [x0 - pad * 0.7, sz],
      [CITY_X + pad * 0.7, sz],
      [CITY_X + pad * 0.7, sz + STREET * 0.8],
      [x0 - pad * 0.7, sz + STREET * 0.8],
    ]);
  }
  // a coastal road so the bay has a shoreline to meet
  streetRects.push([
    [x0 - pad, waterStart - 13],
    [CITY_X + pad, waterStart - 13],
    [CITY_X + pad, waterStart - 2],
    [x0 - pad, waterStart - 2],
  ]);

  for (const rect of streetRects) {
    scene.poly(isoPoly(rect), theme.street, ' opacity="0.95"');
    // painted lane line, the only bright detail on the asphalt
    const mid = rect.map(([x, z]) => [x, z]);
    const a = iso((mid[0][0] + mid[2][0]) / 2, (mid[0][1] + mid[2][1]) / 2);
    const b = iso((mid[1][0] + mid[3][0]) / 2, (mid[1][1] + mid[3][1]) / 2);
    scene.line(a[0], a[1], b[0], b[1], theme.lane, 1, 0.45);
  }

  /* --- lots: every day becomes a building -------------------------------- */
  const lots = [];
  for (const district of months) {
    const dx = district.col * (DIST_X + STREET);
    const dz = district.row * (DIST_Z + STREET);
    district.days.forEach((day, i) => {
      const col = i % LOT_COLS;
      const row = Math.floor(i / LOT_COLS);
      lots.push({
        day,
        x: dx + col * LOT_X + LOT_X / 2,
        z: dz + row * LOT_Z + LOT_Z / 2,
        district: district.ym,
      });
    });
    // any lots a short month leaves over become low-rise fillers, never gaps
    const used = district.days.length;
    for (let i = used; i < LOT_COLS * LOT_ROWS; i += 1) {
      const col = i % LOT_COLS;
      const row = Math.floor(i / LOT_COLS);
      lots.push({
        day: { date: district.ym, count: 0 },
        x: dx + col * LOT_X + LOT_X / 2,
        z: dz + row * LOT_Z + LOT_Z / 2,
        district: district.ym,
        filler: true,
      });
    }
  }

  // parks: sparse decoration, always on a quiet or filler lot
  const parkLots = new Set();
  const candidates = lots.filter((l) => l.day.count === 0).map((_, i) => i);
  for (let i = 0; i < 7 && candidates.length; i += 1) {
    parkLots.add(candidates[Math.floor(rnd() * candidates.length)]);
  }

  const depthKey = (l) => l.x + l.z;
  lots.sort((a, b) => depthKey(a) - depthKey(b));

  let tallestPlaced = false;
  const busiestDate = st.busiest.date;

  lots.forEach((lot, index) => {
    const h = heightFor(lot.day.count, peak);
    const footprintX = 25;
    const footprintZ = 15;
    const isEmptyQuiet = lot.day.count === 0;

    if (!isEmptyQuiet && parkLots.has(index) && lot.day.count <= 1) {
      // plaza: pale square, a few trees, no tower
      const plaza = isoPoly([
        [lot.x - footprintX / 2, lot.z - footprintZ / 2],
        [lot.x + footprintX / 2, lot.z - footprintZ / 2],
        [lot.x + footprintX / 2, lot.z + footprintZ / 2],
        [lot.x - footprintX / 2, lot.z + footprintZ / 2],
      ]);
      scene.poly(plaza, theme.park, ' opacity="0.95"');
      for (let t = 0; t < 3; t += 1) {
        const tx = lot.x + (rnd() - 0.5) * 16;
        const tz = lot.z + (rnd() - 0.5) * 9;
        const base = iso(tx, tz, 0);
        const scl = 0.85 + rnd() * 0.4;
        scene.parts.push(
          `<use href="#tree-${theme.key}" x="${n1(base[0])}" y="${n1(base[1])}" transform="scale(${n1(scl * 100) / 100})"/>`,
        );
        scene.track([[base[0] - 5 * scl, base[1] - 13 * scl]]);
      }
      return;
    }

    const isBusiest = lot.day.date === busiestDate && !tallestPlaced;
    if (isBusiest) tallestPlaced = true;

    // contact shadow: short, soft, hugging the footprint
    const shadow = isoPoly([
      [lot.x - footprintX / 2 - 3, lot.z - footprintZ / 2 - 3],
      [lot.x + footprintX / 2 - 1, lot.z - footprintZ / 2 - 3],
      [lot.x + footprintX / 2 - 1, lot.z + footprintZ / 2 - 1],
      [lot.x - footprintX / 2 - 3, lot.z + footprintZ / 2 - 1],
    ]);
    scene.poly(shadow, "#000000", ' opacity="0.26"');

    // Art Deco / glass towers stack 1-3 setbacks
    const tiers = h > 132 ? 3 : h > 74 ? 2 : 1;
    let remaining = h;
    let fx = footprintX;
    let fz = footprintZ;
    for (let t = 0; t < tiers; t += 1) {
      const isTop = t === tiers - 1;
      const segH = isTop ? remaining : remaining * (tiers === 3 ? 0.52 : 0.64);
      const y0 = h - remaining;
      const y1 = y0 + segH;
      const trimColour =
        themeKey === "neon" && h > 70 ? pick(rnd, theme.neon) : theme.trim;
      const { roof, rightFace, leftFace } = prism(
        scene,
        lot.x,
        lot.z,
        fx,
        fz,
        y0,
        y1,
        theme,
        {
          windows: !isEmptyQuiet,
          trim: h > 46 || themeKey === "neon" ? trimColour : null,
          trimWidth: themeKey === "neon" ? 1.3 : 1.1,
        },
      );

      // flicker overlay: shared groups, never per-window animation
      if (!isEmptyQuiet && h > 30) {
        const bucket = flicker[index % 3];
        bucket.push(
          `<polygon points="${insetFace(rightFace, 0.62).map(([x, y]) => `${n1(x)},${n1(y)}`).join(" ")}" fill="url(#wf-${theme.key})" opacity="0.85"/>`,
        );
      }
      remaining -= segH;
      fx *= 0.7;
      fz *= 0.7;
    }

    const roofPoint = iso(lot.x, lot.z, h);

    // neon signage / gold lit crown band
    if (themeKey === "neon" && h > 80 && rnd() > 0.42) {
      const colour = pick(rnd, theme.neon);
      const bx = roofPoint[0] - 6;
      const by = roofPoint[1] + 14;
      billboards.push(
        `<g class="shim" style="animation-delay:${n1(rnd() * 7)}s"><rect x="${n1(bx)}" y="${n1(by)}" width="7" height="16" fill="${colour}" opacity="0.92" filter="url(#glow-${theme.key})"/>`,
        `<rect x="${n1(bx + 1.2)}" y="${n1(by + 2)}" width="4.6" height="12" fill="#ffffff" opacity="0.35"/></g>`,
      );
    }
    if (themeKey === "gold" && h > 96 && rnd() > 0.5) {
      billboards.push(
        `<rect x="${n1(roofPoint[0] - 5)}" y="${n1(roofPoint[1] + 16)}" width="10" height="3" fill="${theme.win}" opacity="0.5"/>`,
      );
    }

    // gold spires on the tallest tenth, crown on the busiest day
    if (isBusiest || h > HEIGHT_CAP * 0.82) {
      const spireH = isBusiest ? 44 : 22 + rnd() * 8;
      spireLayer.push(
        `<line x1="${n1(roofPoint[0])}" y1="${n1(roofPoint[1])}" x2="${n1(roofPoint[0])}" y2="${n1(roofPoint[1] - spireH)}" stroke="${theme.spire}" stroke-width="${isBusiest ? 2.4 : 1.4}" opacity="0.95"/>`,
        `<circle cx="${n1(roofPoint[0])}" cy="${n1(roofPoint[1] - spireH)}" r="${isBusiest ? 5 : 3}" fill="${theme.spire}" filter="url(#glow-${theme.key})"/>`,
      );
      if (isBusiest) {
        spireLayer.push(
          `<circle cx="${n1(roofPoint[0])}" cy="${n1(roofPoint[1] - spireH)}" r="16" fill="${theme.spire}" opacity="0.16" filter="url(#blur-${theme.key})"/>`,
        );
      }
      scene.track([[roofPoint[0], roofPoint[1] - spireH - 8]]);
    }

    // searchlight on the top of a few tall gold towers
    if (themeKey === "gold" && h > 110 && beams.length < 4 && rnd() > 0.45) {
      beams.push({ x: roofPoint[0], y: roofPoint[1], delay: -rnd() * 14 });
    }
    if (themeKey === "neon" && h > 120 && bandBays.length < 3 && rnd() > 0.5) {
      bandBays.push({ x: roofPoint[0], y: roofPoint[1], colour: pick(rnd, theme.neon) });
    }

    // traffic: only on the streets, so cars stay inside the asphalt
    if (lot.day.count > 6 && rnd() > 0.72 && cars.length < 12) {
      cars.push({
        x: lot.x + (rnd() - 0.5) * 10,
        z: lot.z + footprintZ * 0.85,
        dir: rnd() > 0.5 ? 1 : -1,
        delay: -rnd() * 12,
      });
    }
  });

  /* --- bay: at ground level, along the city's front edge ------------------ */
  const waterQuad = [
    [x0 - pad - 60, waterStart],
    [CITY_X + pad + 60, waterStart],
    [CITY_X + pad + 60, waterStart + 470],
    [x0 - pad - 60, waterStart + 470],
  ];
  const waterPoly = isoPoly(waterQuad);
  scene.poly(waterPoly, `url(#water-${theme.key})`);
  // shoreline
  scene.line(
    iso(x0 - pad - 60, waterStart)[0],
    iso(x0 - pad - 60, waterStart)[1],
    iso(CITY_X + pad + 60, waterStart)[0],
    iso(CITY_X + pad + 60, waterStart)[1],
    theme.accent,
    1.2,
    0.5,
  );

  // reflections: front-row towers mirrored into the bay, faded and blurred
  const nearEdge = lots
    .filter((l) => l.z > CITY_Z - DIST_Z)
    .sort((a, b) => b.day.count - a.day.count)
    .slice(0, 16);
  for (const lot of nearEdge) {
    const h = heightFor(lot.day.count, peak);
    if (h < 24) continue;
    const base = iso(lot.x, waterStart + 20);
    const w = 9 + Math.min(12, h / 14);
    scene.parts.push(
      `<rect x="${n1(base[0] - w / 2)}" y="${n1(base[1])}" width="${n1(w)}" height="${n1(h * 0.55)}" fill="${theme.faces.top}" opacity="0.22" filter="url(#blur-${theme.key})"/>`,
      `<rect x="${n1(base[0] - w / 6)}" y="${n1(base[1])}" width="${n1(w / 3)}" height="${n1(h * 0.7)}" fill="${theme.win}" opacity="0.14" filter="url(#blur-${theme.key})"/>`,
    );
    scene.track([[base[0] - w, base[1] + h * 0.7]]);
  }

  /* --- overlays that belong to the city --------------------------------- */
  scene.push(...billboards, ...spireLayer);

  // neon fog drifting between the blocks
  if (themeKey === "neon") {
    for (let i = 0; i < 4; i += 1) {
      const fg = iso(180 + i * 230, 120 + i * 80, 26 + i * 10);
      scene.parts.push(
        `<g class="${i % 2 ? "fog2" : "fog"}" style="animation-delay:${n1(-i * 3)}s"><ellipse cx="${n1(fg[0])}" cy="${n1(fg[1])}" rx="${220 - i * 20}" ry="${26 + i * 4}" fill="#2a6f8f" opacity="0.16" filter="url(#blur-${theme.key})"/></g>`,
      );
      scene.track([[fg[0] - 220, fg[1] - 30], [fg[0] + 220, fg[1] + 30]]);
    }
  } else {
    // gold: warm haze pooling between the blocks at roof height
    for (let i = 0; i < 3; i += 1) {
      const fg = iso(140 + i * 300, 150 + i * 70, 40 + i * 12);
      scene.parts.push(
        `<g class="fog" style="animation-delay:${n1(-i * 4)}s"><ellipse cx="${n1(fg[0])}" cy="${n1(fg[1])}" rx="${260 - i * 30}" ry="${22 + i * 4}" fill="#ffb466" opacity="0.13" filter="url(#blur-${theme.key})"/></g>`,
      );
      scene.track([[fg[0] - 260, fg[1] - 26], [fg[0] + 260, fg[1] + 26]]);
    }
  }

  // flicker layers, shared by many windows
  scene.push(
    flicker
      .map(
        (bucket, i) =>
          `<g class="flk" style="animation-delay:${n1(i * 1.7)}s">${bucket.join("")}</g>`,
      )
      .join(""),
  );

  // car lights
  for (const car of cars) {
    const a = iso(car.x - 26 * car.dir, car.z, 1.4);
    const b = iso(car.x + 26 * car.dir, car.z, 1.4);
    scene.parts.push(
      `<g><rect x="-2.6" y="-1.2" width="5.2" height="2.4" rx="1.2" fill="#fff6dc" opacity="0.95" filter="url(#glow-${theme.key})"><animateMotion dur="${n1(7 + rnd() * 5)}s" repeatCount="indefinite" begin="${n1(car.delay)}s" path="M ${n1(a[0])} ${n1(a[1])} L ${n1(b[0])} ${n1(b[1])}"/></rect></g>`,
    );
  }

  // searchlights: rotating, gradient-faded cones
  for (const beam of beams) {
    scene.parts.push(
      `<g class="beam" style="animation-delay:${n1(beam.delay)}s;transform-origin:${n1(beam.x)}px ${n1(beam.y)}px"><polygon points="${n1(beam.x)},${n1(beam.y)} ${n1(beam.x - 30)},${n1(beam.y - 330)} ${n1(beam.x + 30)},${n1(beam.y - 330)}" fill="url(#beam-${theme.key})" opacity="0.5"/></g>`,
    );
    scene.track([[beam.x - 120, beam.y - 340], [beam.x + 120, beam.y - 300]]);
  }

  /* --- fit: scale and centre the drawing into the viewBox ---------------- */
  const bw = scene.maxX - scene.minX;
  const bh = scene.maxY - scene.minY;
  const scale = Math.min((VIEW_W * FILL) / bw, (VIEW_H * FILL) / bh);
  const tx = (VIEW_W - bw * scale) / 2 - scene.minX * scale;
  const ty = (VIEW_H - bh * scale) / 2 - scene.minY * scale;

  const horizonY = ty + (iso(0, -70, 0)[1] - scene.minY) * scale;

  /* --- sky, sun, clouds: canvas coords, above the fitted city ------------ */
  const skyStops = theme.sky.map(([o, c]) => `<stop offset="${o}" stop-color="${c}"/>`).join("");
  const skylineTop = horizonY;
  const sun = { x: VIEW_W * 0.74, y: skylineTop - 14, r: 34 };

  const clouds = [];
  const cloudRnd = mulberry32(fnv1a(`clouds-${themeKey}`));
  for (let i = 0; i < 5; i += 1) {
    const cx2 = 430 + cloudRnd() * 720;
    const cy2 = 60 + cloudRnd() * Math.max(90, horizonY - 190);
    const rx = 90 + cloudRnd() * 120;
    clouds.push(
      `<g class="${i % 2 ? "fog2" : "fog"}" opacity="${n1(0.10 + cloudRnd() * 0.10)}" style="animation-delay:${n1(-i * 5)}s">`,
      `<ellipse cx="${n1(cx2)}" cy="${n1(cy2)}" rx="${n1(rx)}" ry="${n1(13 + cloudRnd() * 9)}" fill="${themeKey === "gold" ? "#ffcf9a" : "#7fd8ee"}" filter="url(#blur-${theme.key})"/>`,
      `</g>`,
    );
  }

  const hud = [
    ["@" + LOGIN, theme.hudText],
    [`${st.total.toLocaleString("en-US")} contributions`, theme.hudText],
    [`${st.active} active days`, theme.hudDim],
    [`${st.current}d streak · ${st.longest}d longest`, theme.hudDim],
    [`busiest ${st.busiest.count} · ${st.busiest.date}`, theme.hudDim],
  ];
  const hudWidth = 300;
  const hudHeight = 22 + hud.length * 19;

  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="${VIEW_W}" height="${VIEW_H}" viewBox="0 0 ${VIEW_W} ${VIEW_H}" role="img" aria-label="${esc(theme.label)}: ${st.total} contributions drawn as a dense isometric city">
<title>${esc(theme.label)}</title>
<defs>
  <linearGradient id="sky-${theme.key}" x1="0" y1="0" x2="0" y2="1">${skyStops}</linearGradient>
  <radialGradient id="sun-${theme.key}">
    <stop offset="0%" stop-color="${theme.sun.colour}" stop-opacity="0.95"/>
    <stop offset="45%" stop-color="${theme.sun.halo}" stop-opacity="0.55"/>
    <stop offset="100%" stop-color="${theme.sun.halo}" stop-opacity="0"/>
  </radialGradient>
  <linearGradient id="water-${theme.key}" x1="0" y1="0" x2="0.35" y2="1">
    <stop offset="0%" stop-color="${theme.water[0]}"/>
    <stop offset="45%" stop-color="${theme.water[1]}"/>
    <stop offset="100%" stop-color="${theme.water[2]}"/>
  </linearGradient>
  <linearGradient id="beam-${theme.key}" x1="0" y1="1" x2="0" y2="0">
    <stop offset="0%" stop-color="${themeKey === "gold" ? "#ffe9b8" : "#9dfcff"}" stop-opacity="0.55"/>
    <stop offset="100%" stop-color="${themeKey === "gold" ? "#ffe9b8" : "#9dfcff"}" stop-opacity="0"/>
  </linearGradient>
  <linearGradient id="hud-${theme.key}" x1="0" y1="0" x2="1" y2="1">
    <stop offset="0%" stop-color="${theme.hudBg}"/>
    <stop offset="100%" stop-color="${theme.hudBg}"/>
  </linearGradient>
  <g id="tree-${theme.key}">
    <line x1="0" y1="0" x2="0" y2="-5" stroke="${theme.tree}" stroke-width="1.2"/>
    <circle cx="0" cy="-7.5" r="3.6" fill="${theme.tree}" opacity="0.92"/>
    <circle cx="1" cy="-9" r="1.7" fill="${theme.park}" opacity="0.75"/>
  </g>
  <pattern id="w-${theme.key}" patternUnits="userSpaceOnUse" width="7" height="9">
    <rect width="7" height="9" fill="none"/>
    <rect x="1" y="2" width="3.4" height="4" fill="${theme.win}" opacity="0.55"/>
  </pattern>
  <pattern id="wf-${theme.key}" patternUnits="userSpaceOnUse" width="7" height="9">
    <rect x="1" y="2" width="3.4" height="4" fill="${theme.win}"/>
  </pattern>
  <filter id="blur-${theme.key}" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="6"/></filter>
  <filter id="glow-${theme.key}" x="-70%" y="-70%" width="240%" height="240%">
    <feGaussianBlur stdDeviation="2.6" result="b"/>
    <feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge>
  </filter>
  <style>
    .flk{animation:flick 5.5s ease-in-out infinite}
    .shim{animation:shimmer 7s ease-in-out infinite}
    .fog{animation:drift 19s ease-in-out infinite}
    .fog2{animation:drift 27s ease-in-out infinite reverse}
    .beam{animation:sweep 17s ease-in-out infinite}
    @keyframes flick{0%,100%{opacity:.42}40%{opacity:.95}70%{opacity:.6}}
    @keyframes shimmer{0%,100%{opacity:.72}45%{opacity:1}62%{opacity:.55}}
    @keyframes drift{0%,100%{transform:translateX(0)}50%{transform:translateX(30px)}}
    @keyframes sweep{0%,100%{transform:rotate(-11deg)}50%{transform:rotate(11deg)}}
    @media (prefers-reduced-motion: reduce){.flk,.shim,.fog,.fog2,.beam{animation:none}}
  </style>
</defs>
<rect width="${VIEW_W}" height="${VIEW_H}" fill="url(#sky-${theme.key})"/>
<circle cx="${n1(sun.x)}" cy="${n1(sun.y)}" r="${sun.r * 3.2}" fill="url(#sun-${theme.key})"/>
<circle cx="${n1(sun.x)}" cy="${n1(sun.y)}" r="${sun.r}" fill="${theme.sun.colour}" opacity="0.92"/>
${clouds.join("")}
<g transform="translate(${n1(tx)} ${n1(ty)}) scale(${n1(scale * 100) / 100})">
${scene.toString()}
</g>
<g>
  <rect x="24" y="22" width="${hudWidth}" height="${hudHeight}" rx="9" fill="${theme.hudBg}" stroke="${theme.hudLine}" stroke-opacity="0.4"/>
  ${hud
    .map(
      ([text, colour], i) =>
        `<text x="42" y="${45 + i * 19}" fill="${colour}" font-family="ui-monospace,SFMono-Regular,Menlo,Consolas,monospace" font-size="${i === 0 ? 13.5 : 11.5}" letter-spacing="0.4">${esc(text)}</text>`,
    )
    .join("\n  ")}
</g>
</svg>`;

  const coverage = (lots.length * 25 * 15) / ((CITY_X + 2 * pad) * (waterStart + 2 * pad));
  const fitsX = scene.minX * scale + tx >= -1 && scene.maxX * scale + tx <= VIEW_W + 1;
  const fitsY = scene.minY * scale + ty >= -1 && scene.maxY * scale + ty <= VIEW_H + 1;
  return {
    svg,
    stats: st,
    scale,
    box: { bw, bh },
    check: {
      lots: lots.length,
      coverage: Math.round(coverage * 100),
      fitsX,
      fitsY,
      footprint: `${Math.round(bw * scale)}x${Math.round(bh * scale)}`,
    },
  };
}

/* ---------------------------------------------------------------------- run */

async function main() {
  const days = await loadDays();
  const stats = statsOf(days);
  mkdirSync(OUT, { recursive: true });

  for (const key of THEME_KEYS) {
    const { svg, box, check } = buildCity(days, key);
    writeFileSync(`${OUT}/city-${key}.svg`, svg);
    console.log(
      `${OUT}/city-${key}.svg  ${(Buffer.byteLength(svg) / 1024).toFixed(0)} KB  ` +
        `lots ${check.lots} (${check.coverage}% of ground built)  ` +
        `fitted ${check.footprint} of ${VIEW_W}x${VIEW_H}  ` +
        `inside=${check.fitsX && check.fitsY ? "yes" : "NO"}`,
    );
  }

  try {
    const readme = readFileSync("README.md", "utf8");
    const caption =
      `**${stats.total.toLocaleString("en-US")} contributions** · ` +
      `${stats.current}-day current streak · ${stats.longest}-day longest · ` +
      `busiest day ${stats.busiest.count} on ${stats.busiest.date}`;
    const updated = readme.replace(
      /<!-- city:stats:start -->[\s\S]*?<!-- city:stats:end -->/,
      `<!-- city:stats:start -->${caption}<!-- city:stats:end -->`,
    );
    if (updated !== readme) {
      writeFileSync("README.md", updated);
      console.log("README caption updated");
    }
  } catch {
    console.log("no README here, skipping caption");
  }

  console.log(
    `total ${stats.total} · active ${stats.active} · current ${stats.current}d · longest ${stats.longest}d · busiest ${stats.busiest.count} on ${stats.busiest.date}`,
  );
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
