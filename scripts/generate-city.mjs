#!/usr/bin/env node
/**
 * Contribution City — an animated isometric skyline for a GitHub profile README.
 *
 * Composition, back to front: full-canvas sky, sun and clouds, distant skyline
 * sitting on the horizon, a horizontal water band, then the city on its own
 * finite ground diamond, then foreground atmosphere. The ground is never wider
 * than the city: its edges fade into the bay instead of cutting a polygon
 * across the sky.
 *
 * Data: the last twelve months become twelve districts on a 4x3 grid, newest
 * month downtown. Every lot is built — a quiet day is a one-to-three floor
 * building, not a tile — and height is base + k*sqrt(count), capped so the
 * tallest tower is roughly seven lot-widths.
 *
 * Output is a self-contained SVG: CSS keyframes and SMIL only, no JavaScript,
 * no external CSS, fonts or images. Under 400 KB per theme.
 *
 *   node scripts/generate-city.mjs                 # live (GH_PAT or GITHUB_TOKEN)
 *   node scripts/generate-city.mjs --sample        # synthetic year, no network
 */
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";

const LOGIN = process.env.CITY_LOGIN || "mgkvibez";
const TOKEN = process.env.GH_PAT || process.env.GITHUB_TOKEN || "";
const OUT = process.env.CITY_OUT || "assets";
const SAMPLE = process.argv.includes("--sample");

const VIEW_W = 1200;
const VIEW_H = 800;
const HORIZON_FALLBACK = 352;   // replaced per-render once the fit is known
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

function hexToRgb(hex) {
  const h = hex.replace("#", "");
  return [0, 2, 4].map((i) => parseInt(h.slice(i, i + 2), 16));
}
function mix(a, b, t) {
  const [a1, a2, a3] = hexToRgb(a);
  const [b1, b2, b3] = hexToRgb(b);
  return `#${[
    Math.round(a1 + (b1 - a1) * t),
    Math.round(a2 + (b2 - a2) * t),
    Math.round(a3 + (b3 - a3) * t),
  ]
    .map((v) => v.toString(16).padStart(2, "0"))
    .join("")}`;
}

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
  const rnd = mulberry32(fnv1a("sample-city-v3"));
  const out = [];
  const today = new Date();
  for (let i = 369; i >= 0; i -= 1) {
    const d = new Date(today.getTime() - i * 86400000);
    const weekday = d.getUTCDay();
    const weekend = weekday === 0 || weekday === 6 ? 0.3 : 1;
    const burst = i % 43 < 5 ? 5 : 1;
    out.push({
      date: d.toISOString().slice(0, 10),
      count: Math.max(0, Math.round(rnd() * 12 * weekend * burst)),
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
const DIST_Z = LOT_ROWS * LOT_Z;      // 132
const CITY_X = 4 * DIST_X + 3 * STREET;   // 894
const CITY_Z = 3 * DIST_Z + 2 * STREET;   // 448

const BASE_FLOOR = 8;                 // one storey, in world units
const MAX_FLOORS = 20;                // tallest tower ≈ 6-8 lot widths

/**
 * Downtown must read centre-right in the rendered frame, so the anchor slot is
 * chosen by projected screen position, not by grid index: the slot nearest 62%
 * of the way across the city gets the newest month.
 */
const DOWNTOWN = (() => {
  const slots = [];
  for (let row = 0; row < 3; row += 1) {
    for (let col = 0; col < 4; col += 1) {
      const x = col * (DIST_X + STREET) + DIST_X / 2;
      const z = row * (DIST_Z + STREET) + DIST_Z / 2;
      slots.push({ col, row, sx: (x - z) * 0.5 });
    }
  }
  const xs = slots.map((s) => s.sx);
  const lo = Math.min(...xs);
  const hi = Math.max(...xs);
  return slots
    .map((s) => ({ ...s, at: (s.sx - lo) / (hi - lo) }))
    .sort((a, b) => Math.abs(a.at - 0.62) - Math.abs(b.at - 0.62))[0];
})();

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

function assignSlots(months) {
  const slots = [];
  for (let row = 0; row < 3; row += 1) {
    for (let col = 0; col < 4; col += 1) {
      slots.push({ col, row, d: Math.hypot(col - DOWNTOWN.col, (row - DOWNTOWN.row) * 1.5) });
    }
  }
  slots.sort((a, b) => a.d - b.d);
  return [...months].reverse().map((month, i) => ({ ...month, ...slots[i % slots.length] }));
}

/** Height in world units: floors, so a quiet day still has a body. */
function floorsFor(count, peak) {
  if (count <= 0) return 1;
  const share = Math.sqrt(count / Math.max(1, peak));
  return clamp(Math.round(1 + share * (MAX_FLOORS - 1)), 1, MAX_FLOORS);
}

/* ------------------------------------------------------------------- themes */

const THEMES = {
  gold: {
    key: "gold",
    label: "Contribution City — dusk",
    sky: [["0%", "#120f2c"], ["30%", "#2c1a44"], ["56%", "#672b45"], ["78%", "#b8492a"], ["100%", "#f6a95f"]],
    sun: { colour: "#ffeec2", halo: "#ff9a45", r: 46, x: 852, dy: -18 },
    cloud: "#ffc993",
    water: ["#231630", "#3d2133", "#57283a"],
    ground: ["#3b2a1e", "#241a16"],
    street: "#4a3527",
    lane: "#7a5734",
    faces: { left: "#2a1d15", right: "#452f1f", top: "#7b5732" },
    trim: "#f0cd8c",
    win: "#ffd08a",
    winDim: "#6d4a24",
    spire: "#ffedb8",
    ring: ["#4a3a56", "#3a2d47", "#2c2238"],
    park: "#3c5a3d",
    tree: "#51724a",
    hazeColour: "#ff9d5a",
    hud: { bg: "rgba(12,9,22,0.76)", line: "#f0cd8c", text: "#f8e9c6", dim: "#bd9a68" },
    neonMode: false,
  },
  neon: {
    key: "neon",
    label: "Contribution City — fog",
    sky: [["0%", "#03060f"], ["34%", "#06101f"], ["64%", "#0a1c33"], ["86%", "#123a52"], ["100%", "#1c5a6b"]],
    sun: { colour: "#d8fbff", halo: "#22d3ee", r: 26, x: 296, dy: -84 },
    cloud: "#78d5ea",
    water: ["#04121c", "#062331", "#0a3346"],
    ground: ["#132436", "#0a1521"],
    street: "#17303f",
    lane: "#2b6076",
    faces: { left: "#0d1a2a", right: "#17314a", top: "#264c68" },
    trim: "#22d3ee",
    win: "#8ff2ff",
    winDim: "#1a4a5a",
    spire: "#a6ffbb",
    ring: ["#0b1b2c", "#0d2136", "#102a42"],
    park: "#12372c",
    tree: "#1d6b4a",
    hazeColour: "#3fa9c4",
    hud: { bg: "rgba(3,10,17,0.78)", line: "#22d3ee", text: "#ddfbff", dim: "#5fa3b6" },
    neonMode: true,
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

  trackBox(x, y, w, h) {
    this.track([[x, y], [x + w, y + h]]);
  }

  poly(points, fill, extra = "") {
    this.track(points);
    this.parts.push(
      `<polygon points="${points.map(([x, y]) => `${Math.round(x)},${Math.round(y)}`).join(" ")}" fill="${fill}"${extra}/>`,
    );
  }

  raw(fragment) {
    this.parts.push(fragment);
  }

  toString() {
    return this.parts.join("");
  }
}

const iso = (x, z, h = 0) => [(x - z) * 0.5, (x + z) * 0.25 - h];
const isoPoly = (corners, h = 0) => corners.map(([x, z]) => iso(x, z, h));

function insetFace(points, factor) {
  const cx = points.reduce((s, p) => s + p[0], 0) / points.length;
  const cy = points.reduce((s, p) => s + p[1], 0) / points.length;
  return points.map(([x, y]) => [cx + (x - cx) * factor, cy + (y - cy) * factor]);
}

/** Bilinear point inside a face quad: how signage gets glued to a facade. */
function facePoint(quad, u, v) {
  const [tl, tr, br, bl] = quad;
  const top = [tl[0] + (tr[0] - tl[0]) * u, tl[1] + (tr[1] - tl[1]) * u];
  const bot = [bl[0] + (br[0] - bl[0]) * u, bl[1] + (br[1] - bl[1]) * u];
  return [top[0] + (bot[0] - top[0]) * v, top[1] + (bot[1] - top[1]) * v];
}

function faceQuad(quad, u0, v0, u1, v1) {
  return [facePoint(quad, u0, v0), facePoint(quad, u1, v0), facePoint(quad, u1, v1), facePoint(quad, u0, v1)];
}

/** One prism with the lighting the brief asks for: left dark, right mid, top light. */
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

  const shade = opts.shade || 0;
  const faceColour = (base) => (shade ? mix(base, theme.hazeColour, shade) : base);

  scene.poly(leftFace, faceColour(theme.faces.left));
  const glass = opts.dim ? `url(#wd-${theme.key})` : `url(#w-${theme.key})`;
  if (opts.windows !== false && opts.small !== true) {
    scene.poly(insetFace(leftFace, 0.84), glass, ' opacity="0.45"');
  }

  scene.poly(rightFace, faceColour(theme.faces.right));
  if (opts.windows !== false) {
    scene.poly(insetFace(rightFace, 0.84), glass, opts.dim ? ' opacity="0.5"' : "");
  }

  scene.poly(roof, faceColour(theme.faces.top), ` stroke="${theme.trim}" stroke-width="0.6" stroke-opacity="0.45"`);

  if (theme.neonMode && opts.neonEdges !== false) {
    // 1.5px neon tubing on the silhouette, plus a soft bloom pass underneath
    const col = opts.neonColour || theme.neon[0];
    scene.raw(
      `<polyline points="${leftFace.concat([leftFace[0]]).map(([x, y]) => `${Math.round(x)},${Math.round(y)}`).join(" ")}" fill="none" stroke="${col}" stroke-width="3.6" stroke-opacity="0.35" filter="url(#blur-${theme.key})"/>`,
    );
    scene.raw(
      `<polyline points="${[bTop, cTop, cBot].map(([x, y]) => `${Math.round(x)},${Math.round(y)}`).join(" ")}" fill="none" stroke="${col}" stroke-width="1.5" stroke-opacity="0.95"/>`,
    );
    scene.raw(
      `<polyline points="${[cTop, dTop, dBot, cBot].map(([x, y]) => `${Math.round(x)},${Math.round(y)}`).join(" ")}" fill="none" stroke="${col}" stroke-width="1.5" stroke-opacity="0.7"/>`,
    );
  } else if (opts.rim) {
    scene.raw(
      `<polyline points="${[bTop, cTop, dTop].map(([x, y]) => `${Math.round(x)},${Math.round(y)}`).join(" ")}" fill="none" stroke="${theme.trim}" stroke-width="1.2" stroke-opacity="0.5" filter="url(#blur-${theme.key})"/>`,
    );
  }

  return { roof, rightFace, leftFace };
}

/** Stepped tower: returns the group string and the canvas-space top point. */
function tower(scene, lot, h, theme, rnd, opts = {}) {
  const footprintX = opts.fx;
  const footprintZ = opts.fz;
  const tiers = h > BASE_FLOOR * 14 ? 3 : h > BASE_FLOOR * 7 ? 2 : 1;
  const tierHeights = tiers === 3 ? [0.5, 0.3, 0.2] : tiers === 2 ? [0.62, 0.38] : [1];
  const shrink = tiers === 3 ? [1, 0.78, 0.56] : tiers === 2 ? [1, 0.74] : [1];

  let y = 0;
  let last = null;
  for (let t = 0; t < tiers; t += 1) {
    const segH = h * tierHeights[t];
    const fx = footprintX * shrink[t];
    const fz = footprintZ * shrink[t];
    last = prism(scene, lot.x, lot.z, fx, fz, y, y + segH, theme, {
      windows: true,
      small: h < BASE_FLOOR * 4,
      dim: opts.dim,
      shade: opts.shade || 0,
      neonColour: opts.neonColour,
      neonEdges: opts.neonEdges,
      rim: theme.neonMode ? false : true,
    });

    // gold vertical light strips climbing each tier
    if (!theme.neonMode && h > BASE_FLOOR * 8) {
      for (const u of [0.24, 0.52, 0.8]) {
        const p0 = facePoint(last.rightFace, u, 0.06);
        const p1 = facePoint(last.rightFace, u, 0.96);
        scene.raw(
          `<line x1="${Math.round(p0[0])}" y1="${Math.round(p0[1])}" x2="${Math.round(p1[0])}" y2="${Math.round(p1[1])}" stroke="${theme.win}" stroke-width="1.4" stroke-opacity="0.75"/>`,
        );
      }
    }

    // neon holographic panel, skewed onto the facade it belongs to
    if (theme.neonMode && h > BASE_FLOOR * 5 && rnd() > 0.55) {
      const colour = pick(rnd, theme.neon);
      const u0 = 0.18;
      const u1 = 0.82;
      const v0 = 0.3 + rnd() * 0.25;
      const v1 = Math.min(0.92, v0 + 0.26);
      const panel = faceQuad(last.rightFace, u0, v0, u1, v1);
      scene.raw(
        `<polygon points="${panel.map(([x, yy]) => `${Math.round(x)},${Math.round(yy)}`).join(" ")}" fill="${colour}" opacity="0.55" filter="url(#glow-${theme.key})"/>` +
          `<polygon points="${panel.map(([x, yy]) => `${Math.round(x)},${Math.round(yy)}`).join(" ")}" fill="url(#holo-${theme.key})" opacity="0.85" class="shim" style="animation-delay:${n1(rnd() * 6)}s"/>`,
      );
    }
    y += segH;
  }

  return { top: iso(lot.x, lot.z, h), body: last, tiers };
}

/* ------------------------------------------------------------------- cities */

function buildCity(days, themeKey) {
  const theme = THEMES[themeKey];
  const st = statsOf(days);
  const peak = Math.max(1, ...days.map((d) => d.count));
  const months = assignSlots(monthsOf(days));
  const rnd = mulberry32(fnv1a(`${days[days.length - 1].date}|${themeKey}|v3`));

  const groundScene = new Scene();
  const cityScene = new Scene();
  const ringScene = new Scene();
  const fxScene = new Scene();

  const pad = LOT_X;
  const waterStart = CITY_Z + LOT_Z * 1.2;
  const lots = [];

  /* --- districts: every lot gets a building ----------------------------- */
  for (const district of months) {
    const dx = district.col * (DIST_X + STREET);
    const dz = district.row * (DIST_Z + STREET);
    const fill = (i, day) => {
      const col = i % LOT_COLS;
      const row = Math.floor(i / LOT_COLS);
      lots.push({
        day,
        x: dx + col * LOT_X + LOT_X / 2,
        z: dz + row * LOT_Z + LOT_Z / 2,
        district: district.ym,
      });
    };
    district.days.slice(0, LOT_COLS * LOT_ROWS).forEach((day, i) => fill(i, day));
    for (let i = district.days.length; i < LOT_COLS * LOT_ROWS; i += 1) {
      fill(i, { date: district.ym, count: 0 });
    }
  }

  /* --- ground: one finite diamond, one lot of margin, faded edges ------- */
  const groundCorners = [
    [-pad, -pad],
    [CITY_X + pad, -pad],
    [CITY_X + pad, waterStart],
    [-pad, waterStart],
  ].map(([x, z]) => iso(x, z));
  groundScene.raw(
    `<polygon points="${groundCorners.map(([x, y]) => `${n1(x)},${n1(y)}`).join(" ")}" fill="url(#ground-${theme.key})" mask="url(#groundFade-${theme.key})"/>`,
  );
  groundScene.track(groundCorners);

  // streets between the districts, lighter than the block surface
  const streets = [];
  for (let c = 1; c < 4; c += 1) {
    const sx = c * DIST_X + (c - 1) * STREET;
    streets.push([[sx, -pad], [sx + STREET * 0.8, -pad], [sx + STREET * 0.8, waterStart], [sx, waterStart]]);
  }
  for (let r = 1; r < 3; r += 1) {
    const sz = r * DIST_Z + (r - 1) * STREET;
    streets.push([[-pad, sz], [CITY_X + pad, sz], [CITY_X + pad, sz + STREET * 0.8], [-pad, sz + STREET * 0.8]]);
  }
  streets.push([[-pad, waterStart - 16], [CITY_X + pad, waterStart - 16], [CITY_X + pad, waterStart - 5], [-pad, waterStart - 5]]);
  for (const s of streets) {
    groundScene.poly(isoPoly(s), theme.street, ' opacity="0.9"');
  }
  // wet sheen: coloured streaks on the asphalt, strongest in neon
  for (let i = 0; i < (theme.neonMode ? 26 : 12); i += 1) {
    const sx2 = -pad + rnd() * (CITY_X + pad * 2);
    const sz2 = rnd() * waterStart;
    const a = iso(sx2, sz2);
    const len = 8 + rnd() * 26;
    groundScene.raw(
      `<rect x="${n1(a[0])}" y="${n1(a[1])}" width="${n1(len)}" height="1.6" fill="${theme.neonMode ? pick(rnd, theme.neon) : theme.win}" opacity="${n1(0.14 + rnd() * 0.22)}"/>`,
    );
  }

  /* --- decorative ring: three depth layers with real windows ------------ */
  const ringLayers = [
    { z: -LOT_Z * 1.6, spread: 150, hMin: 60, hMax: 150, haze: 0.42 },
    { z: -LOT_Z * 4.4, spread: 230, hMin: 44, hMax: 118, haze: 0.58 },
    { z: -LOT_Z * 7.6, spread: 320, hMin: 30, hMax: 86, haze: 0.74 },
  ];
  ringLayers.forEach((layer, li) => {
    const rows = [-pad - layer.spread, CITY_X + pad + layer.spread];
    const xs = [];
    for (let x = -pad - layer.spread; x < CITY_X + pad + layer.spread; x += 64 + rnd() * 30) xs.push(x);
    // a full row behind the city plus flanking towers either side
    for (const x of xs) {
      const h = layer.hMin + rnd() * (layer.hMax - layer.hMin);
      const w = 22 + rnd() * 16;
      ringScene.parts.push(
        "",
      );
      const local = new Scene();
      prism(local, x, layer.z + (rnd() - 0.5) * 40, w, w * 0.66, 0, h, theme, {
        windows: true,
        shade: layer.haze,
        neonEdges: theme.neonMode,
        neonColour: theme.neon ? pick(rnd, theme.neon) : null,
      });
      ringScene.track([[local.minX, local.minY], [local.maxX, local.maxY]]);
      ringScene.raw(`<g opacity="${layer.haze > 0.6 ? 0.6 : 0.8}">${local.toString()}</g>`);
    }
    for (const z of [DIST_Z * 0.6, DIST_Z * 2.2]) {
      for (const edge of rows) {
        const h = layer.hMin * 0.7 + rnd() * (layer.hMax - layer.hMin) * 0.8;
        const w = 20 + rnd() * 14;
        const local = new Scene();
        prism(local, edge, z + rnd() * DIST_Z, w, w * 0.7, 0, h, theme, {
          windows: true,
          shade: layer.haze,
          neonEdges: theme.neonMode,
          neonColour: theme.neon ? pick(rnd, theme.neon) : null,
        });
        ringScene.track([[local.minX, local.minY], [local.maxX, local.maxY]]);
        ringScene.raw(`<g opacity="${layer.haze > 0.6 ? 0.55 : 0.75}">${local.toString()}</g>`);
      }
    }
    void li;
  });

  /* --- the data city ---------------------------------------------------- */
  const fx = 29;      // footprint fills ~85% of the 34-unit lot
  const fz = 19;
  const order = [...lots].sort((a, b) => a.x + a.z - (b.x + b.z));
  const spireCut = (() => {
    const heights = order.map((l) => floorsFor(l.day.count, peak) * BASE_FLOOR).sort((a, b) => a - b);
    return heights[Math.floor(heights.length * 0.95)];
  })();

  let tallest = { x: 0, y: 0, h: 0 };
  for (const lot of order) {
    const quiet = lot.day.count === 0;
    const floors = quiet ? 1 + Math.floor(rnd() * 3) : floorsFor(lot.day.count, peak);
    const h = floors * BASE_FLOOR;

    // short contact shadow, hugging the footprint
    cityScene.poly(
      isoPoly([
        [lot.x - fx / 2 - 2, lot.z - fz / 2 - 2],
        [lot.x + fx / 2, lot.z - fz / 2 - 2],
        [lot.x + fx / 2, lot.z + fz / 2],
        [lot.x - fx / 2 - 2, lot.z + fz / 2],
      ]),
      "#000000",
      ' opacity="0.3"',
    );

    const neonColour = theme.neonMode ? pick(rnd, theme.neon) : null;
    const { top } = tower(cityScene, lot, h, theme, rnd, { fx, fz, neonColour, dim: quiet });
    if (h > tallest.h) tallest = { x: top[0], y: top[1], h };

    // gold spires on the top 5% only
    if (!quiet && h >= spireCut && h > BASE_FLOOR * 8) {
      const spireH = 14 + rnd() * 10;
      cityScene.raw(
        `<line x1="${n1(top[0])}" y1="${n1(top[1])}" x2="${n1(top[0])}" y2="${n1(top[1] - spireH)}" stroke="${theme.spire}" stroke-width="1.6" opacity="0.95"/>` +
          `<circle cx="${n1(top[0])}" cy="${n1(top[1] - spireH)}" r="2.6" fill="${theme.spire}" filter="url(#glow-${theme.key})"/>`,
      );
      cityScene.track([[top[0], top[1] - spireH - 4]]);
    }
    // the busiest day gets the crown
    if (lot.day.date === st.busiest.date) {
      cityScene.raw(
        `<line x1="${n1(top[0])}" y1="${n1(top[1])}" x2="${n1(top[0])}" y2="${n1(top[1] - 30)}" stroke="${theme.spire}" stroke-width="2.2"/>` +
          `<circle cx="${n1(top[0])}" cy="${n1(top[1] - 32)}" r="5" fill="${theme.spire}" filter="url(#glow-${theme.key})"/>` +
          `<circle cx="${n1(top[0])}" cy="${n1(top[1] - 32)}" r="16" fill="${theme.spire}" opacity="0.18" filter="url(#blur-${theme.key})"/>`,
      );
      cityScene.track([[top[0] - 18, top[1] - 50]]);
    }

    // car lights, riding the streets
    if (lot.day.count > 4 && rnd() > 0.86) {
      const a = iso(lot.x - 30, lot.z + fz, 1.2);
      const b = iso(lot.x + 30, lot.z + fz, 1.2);
      cityScene.raw(
        `<rect x="-2.4" y="-1.1" width="4.8" height="2.2" rx="1.1" fill="#fff4d6" opacity="0.9" filter="url(#glow-${theme.key})">` +
          `<animateMotion dur="${n1(6 + rnd() * 6)}s" repeatCount="indefinite" begin="${n1(-rnd() * 8)}s" path="M ${n1(a[0])} ${n1(a[1])} L ${n1(b[0])} ${n1(b[1])}"/></rect>`,
      );
    }
  }

  /* --- fit: 80% of the frame, centred, nothing clipped ------------------ */
  const box = {
    minX: Math.min(groundScene.minX, cityScene.minX, ringScene.minX),
    minY: Math.min(groundScene.minY, cityScene.minY, ringScene.minY),
    maxX: Math.max(groundScene.maxX, cityScene.maxX, ringScene.maxX),
    maxY: Math.max(groundScene.maxY, cityScene.maxY, ringScene.maxY),
  };
  const bw = box.maxX - box.minX;
  const bh = box.maxY - box.minY;
  const scale = Math.min((VIEW_W * 0.8) / bw, (VIEW_H * 0.66) / bh);
  const frontY = VIEW_H - 26;                       // waterfront sits near the bottom
  const tx = VIEW_W / 2 - ((box.minX + box.maxX) / 2) * scale;
  const ty = frontY - box.maxY * scale;
  const toCanvas = (wx, wz, h = 0) => {
    const [sx, sy] = iso(wx, wz, h);
    return [sx * scale + tx, sy * scale + ty];
  };
  const waterY = toCanvas(0, waterStart)[1];
  const HORIZON = clamp(Math.round(box.minY * scale + ty - 64), 170, 430);
  // the waterfront runs along z = waterStart, which projects to a 1:2 slope;
  // mirroring across that line is what keeps reflections under their buildings
  const shoreP = toCanvas(CITY_X / 2, waterStart);
  const shoreQ = toCanvas(CITY_X / 2 + 400, waterStart);
  const shoreAngle = (Math.atan2(shoreQ[1] - shoreP[1], shoreQ[0] - shoreP[0]) * 180) / Math.PI;
  const bayPoly = [
    toCanvas(-1400, waterStart),
    toCanvas(CITY_X + 1400, waterStart),
    [VIEW_W + 400, VIEW_H + 400],
    [-400, VIEW_H + 400],
  ];

  /* --- sky, sun, clouds: full canvas ----------------------------------- */
  const skyStops = theme.sky.map(([o, c]) => `<stop offset="${o}" stop-color="${c}"/>`).join("");
  const sun = { x: theme.sun.x, y: HORIZON + theme.sun.dy, r: theme.sun.r };

  const clouds = [];
  const crnd = mulberry32(fnv1a(`cloud-${themeKey}`));
  for (let i = 0; i < 6; i += 1) {
    const cx2 = 60 + crnd() * (VIEW_W - 120);
    const cy2 = 50 + crnd() * (HORIZON - 130);
    clouds.push(
      `<g class="${i % 2 ? "drift2" : "drift"}" opacity="${n1(0.1 + crnd() * 0.12)}" style="animation-delay:${n1(-i * 4)}s">` +
        `<ellipse cx="${n1(cx2)}" cy="${n1(cy2)}" rx="${n1(80 + crnd() * 130)}" ry="${n1(11 + crnd() * 9)}" fill="${theme.cloud}" filter="url(#blur-${theme.key})"/></g>`,
    );
  }

  /* --- distant skyline sitting on the horizon --------------------------- */
  const far = new Scene();
  const frnd = mulberry32(fnv1a(`far-${themeKey}`));
  for (let row = 0; row < 3; row += 1) {
    const base = HORIZON - row * 7;
    const hMax = 62 - row * 14;
    const fade = 0.72 - row * 0.16;
    for (let x = -20; x < VIEW_W + 20; x += 16 + frnd() * 26) {
      const h = 14 + frnd() * hMax;
      const w = 10 + frnd() * 16;
      const colour = mix(theme.faces.right, theme.sky[1][1], 0.55 + row * 0.15);
      far.raw(
        `<rect x="${n1(x)}" y="${n1(base - h)}" width="${n1(w)}" height="${n1(h)}" fill="${colour}" opacity="${fade}"/>` +
          `<rect x="${n1(x)}" y="${n1(base - h)}" width="${n1(w)}" height="${n1(h)}" fill="url(#w-far-${theme.key})" opacity="${n1(fade * 0.8)}"/>`,
      );
    }
  }
  const farLayer = `<g>${far.toString()}</g>`;

  /* --- searchlights: sky-wide, behind everything ------------------------ */
  const beams = [];
  if (!theme.neonMode) {
    for (let i = 0; i < 4; i += 1) {
      const bx = 150 + i * 300;
      beams.push(
        `<g class="beam" style="animation-delay:${n1(-i * 4)}s;transform-origin:${bx}px ${HORIZON}px">` +
          `<polygon points="${bx},${HORIZON} ${bx - 120},-80 ${bx + 120},-80" fill="url(#beam-${themeKey})" opacity="0.5"/></g>`,
      );
    }
  }

  /* --- water: a horizontal band at the horizon -------------------------- */
  const waterLines = [];
  const wrnd = mulberry32(fnv1a(`water-${themeKey}`));
  for (let i = 0; i < 40; i += 1) {
    const y = HORIZON + 8 + wrnd() * (VIEW_H - HORIZON - 20);
    waterLines.push(
      `<rect x="${n1(wrnd() * VIEW_W)}" y="${n1(y)}" width="${n1(20 + wrnd() * 90)}" height="1.3" fill="${theme.neonMode ? pick(wrnd, theme.neon) : theme.win}" opacity="${n1(0.06 + wrnd() * 0.12)}"/>`,
    );
  }

  /* --- foreground fog (neon) / warm haze (gold) ------------------------- */
  const fog = [];
  const frnd2 = mulberry32(fnv1a(`fog-${themeKey}`));
  for (let i = 0; i < (theme.neonMode ? 3 : 2); i += 1) {
    const y = 470 + i * 90;
    fog.push(
      `<g class="${i % 2 ? "drift2" : "drift"}" style="animation-delay:${n1(-i * 5)}s" opacity="${n1(theme.neonMode ? 0.2 : 0.14)}">` +
        `<rect x="-260" y="${y}" width="${VIEW_W + 520}" height="${70 + i * 24}" fill="url(#fog-${themeKey})" filter="url(#blur-${theme.key})"/></g>`,
    );
  }
  const rain = theme.neonMode
    ? `<rect width="${VIEW_W}" height="${VIEW_H}" fill="url(#rain-${themeKey})" opacity="0.22"/>`
    : "";

  /* --- HUD -------------------------------------------------------------- */
  const hudLines = [
    ["@" + LOGIN, theme.hud.text],
    [`${st.total.toLocaleString("en-US")} contributions`, theme.hud.text],
    [`${st.active} active days · ${st.current}d streak`, theme.hud.dim],
    [`longest ${st.longest}d · busiest ${st.busiest.count}`, theme.hud.dim],
  ];

  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="${VIEW_W}" height="${VIEW_H}" viewBox="0 0 ${VIEW_W} ${VIEW_H}" role="img" aria-label="${esc(theme.label)}: ${st.total} contributions drawn as an isometric city">
<title>${esc(theme.label)}</title>
<defs>
  <linearGradient id="sky-${themeKey}" x1="0" y1="0" x2="0" y2="1">${skyStops}</linearGradient>
  <radialGradient id="sunG-${themeKey}">
    <stop offset="0%" stop-color="${theme.sun.colour}" stop-opacity="0.95"/>
    <stop offset="32%" stop-color="${theme.sun.halo}" stop-opacity="0.55"/>
    <stop offset="100%" stop-color="${theme.sun.halo}" stop-opacity="0"/>
  </radialGradient>
  <linearGradient id="water-${themeKey}" gradientUnits="userSpaceOnUse" x1="0" y1="${HORIZON}" x2="0" y2="${VIEW_H}">
    <stop offset="0%" stop-color="${theme.water[0]}" stop-opacity="0.55"/>
    <stop offset="18%" stop-color="${theme.water[1]}"/>
    <stop offset="100%" stop-color="${theme.water[2]}"/>
  </linearGradient>
  <linearGradient id="shore-${themeKey}" gradientUnits="userSpaceOnUse" x1="0" y1="${HORIZON - 10}" x2="0" y2="${HORIZON + 26}">
    <stop offset="0%" stop-color="${theme.sun.halo}" stop-opacity="0"/>
    <stop offset="55%" stop-color="${theme.sun.halo}" stop-opacity="0.35"/>
    <stop offset="100%" stop-color="${theme.sun.halo}" stop-opacity="0"/>
  </linearGradient>
  <radialGradient id="ground-${themeKey}">
    <stop offset="0%" stop-color="${theme.ground[0]}"/>
    <stop offset="70%" stop-color="${theme.ground[0]}"/>
    <stop offset="100%" stop-color="${theme.ground[1]}"/>
  </radialGradient>
  <linearGradient id="beam-${themeKey}" x1="0" y1="1" x2="0" y2="0">
    <stop offset="0%" stop-color="${theme.sun.colour}" stop-opacity="0.5"/>
    <stop offset="70%" stop-color="${theme.sun.colour}" stop-opacity="0.1"/>
    <stop offset="100%" stop-color="${theme.sun.colour}" stop-opacity="0"/>
  </linearGradient>
  <linearGradient id="fog-${themeKey}" x1="0" y1="0" x2="0" y2="1">
    <stop offset="0%" stop-color="${theme.hazeColour}" stop-opacity="0"/>
    <stop offset="45%" stop-color="${theme.hazeColour}" stop-opacity="0.7"/>
    <stop offset="100%" stop-color="${theme.hazeColour}" stop-opacity="0"/>
  </linearGradient>
  <linearGradient id="holo-${themeKey}" x1="0" y1="0" x2="1" y2="1">
    <stop offset="0%" stop-color="#ffffff" stop-opacity="0.55"/>
    <stop offset="45%" stop-color="${theme.neon ? theme.neon[0] : "#fff"}" stop-opacity="0.15"/>
    <stop offset="100%" stop-color="#ffffff" stop-opacity="0.4"/>
  </linearGradient>
  <linearGradient id="reflFade-${themeKey}" gradientUnits="userSpaceOnUse" x1="0" y1="${n1(waterY)}" x2="0" y2="${n1(waterY + 260)}">
    <stop offset="0%" stop-color="#fff" stop-opacity="0.55"/>
    <stop offset="60%" stop-color="#fff" stop-opacity="0.12"/>
    <stop offset="100%" stop-color="#fff" stop-opacity="0"/>
  </linearGradient>
  <radialGradient id="groundFadeG-${themeKey}">
    <stop offset="60%" stop-color="#fff" stop-opacity="1"/>
    <stop offset="100%" stop-color="#fff" stop-opacity="0"/>
  </radialGradient>
  <mask id="groundFade-${themeKey}" maskUnits="userSpaceOnUse" x="-1200" y="-1200" width="3600" height="3600">
    <ellipse cx="${n1((groundScene.minX + groundScene.maxX) / 2)}" cy="${n1((groundScene.minY + groundScene.maxY) / 2)}" rx="${n1((groundScene.maxX - groundScene.minX) * 0.62)}" ry="${n1((groundScene.maxY - groundScene.minY) * 0.66)}" fill="url(#groundFadeG-${themeKey})"/>
  </mask>
  <mask id="reflMask-${themeKey}" maskUnits="userSpaceOnUse" x="0" y="${n1(waterY)}" width="${VIEW_W}" height="${VIEW_H}">
    <rect x="0" y="${n1(waterY)}" width="${VIEW_W}" height="${VIEW_H - waterY}" fill="url(#reflFade-${themeKey})"/>
  </mask>
  <clipPath id="reflClip-${themeKey}"><polygon points="${bayPoly.map(([x, y]) => `${n1(x)},${n1(y)}`).join(" ")}"/></clipPath>
  <g id="cityBody-${themeKey}"><g transform="translate(${n1(tx)} ${n1(ty)}) scale(${n1(scale * 1000) / 1000})">${cityScene.toString()}</g></g>
  <pattern id="w-${themeKey}" patternUnits="userSpaceOnUse" width="6.5" height="8">
    <rect x="1" y="1.8" width="3" height="3.6" fill="${theme.win}"/>
  </pattern>
  <pattern id="wd-${themeKey}" patternUnits="userSpaceOnUse" width="6.5" height="8">
    <rect x="1.6" y="2.4" width="2.4" height="3" fill="${theme.winDim}"/>
  </pattern>
  <pattern id="w-far-${themeKey}" patternUnits="userSpaceOnUse" width="7" height="9">
    <rect x="2" y="3" width="2.4" height="3" fill="${theme.win}" opacity="0.5"/>
  </pattern>
  <pattern id="rain-${themeKey}" patternUnits="userSpaceOnUse" width="26" height="26" patternTransform="rotate(14)">
    <line x1="0" y1="0" x2="0" y2="10" stroke="${theme.cloud}" stroke-width="0.8" opacity="0.5"/>
  </pattern>
  <filter id="blur-${themeKey}" x="-60%" y="-60%" width="220%" height="220%"><feGaussianBlur stdDeviation="5"/></filter>
  <filter id="glow-${themeKey}" x="-80%" y="-80%" width="260%" height="260%">
    <feGaussianBlur stdDeviation="2.4" result="b"/>
    <feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge>
  </filter>
  <style>
    .drift{animation:drift 34s linear infinite}
    .drift2{animation:drift 47s linear infinite}
    .beam{animation:sweep 22s ease-in-out infinite}
    .shim{animation:shim 6s ease-in-out infinite}
    @keyframes drift{0%{transform:translateX(0)}100%{transform:translateX(120px)}}
    @keyframes sweep{0%,100%{transform:rotate(-7deg)}50%{transform:rotate(7deg)}}
    @keyframes shim{0%,100%{opacity:.7}50%{opacity:1}}
    @media (prefers-reduced-motion: reduce){.drift,.drift2,.beam,.shim{animation:none}}
  </style>
</defs>

<rect width="${VIEW_W}" height="${VIEW_H}" fill="url(#sky-${themeKey})"/>
<circle cx="${n1(sun.x)}" cy="${n1(sun.y)}" r="${n1(sun.r * 3.4)}" fill="url(#sunG-${themeKey})"/>
<circle cx="${n1(sun.x)}" cy="${n1(sun.y)}" r="${sun.r}" fill="${theme.sun.colour}" opacity="0.92"/>
${clouds.join("")}
${farLayer}
${beams.join("")}
<rect x="0" y="${HORIZON}" width="${VIEW_W}" height="${VIEW_H - HORIZON}" fill="url(#water-${themeKey})"/>
<rect x="0" y="${HORIZON - 12}" width="${VIEW_W}" height="40" fill="url(#shore-${themeKey})"/>
${waterLines.join("")}

<g clip-path="url(#reflClip-${themeKey})" mask="url(#reflMask-${themeKey})" opacity="0.25">
  <g transform="translate(${n1(shoreP[0])} ${n1(shoreP[1])}) rotate(${n1(shoreAngle * 100) / 100}) scale(1 -1) rotate(${n1(-shoreAngle * 100) / 100}) translate(${n1(-shoreP[0])} ${n1(-shoreP[1])})">
    <use href="#cityBody-${themeKey}"/>
  </g>
</g>

<g transform="translate(${n1(tx)} ${n1(ty)}) scale(${n1(scale * 1000) / 1000})">
  ${ringScene.toString()}
  ${groundScene.toString()}
</g>
<use href="#cityBody-${themeKey}"/>

${fog.join("")}
${rain}

<g>
  <rect x="24" y="22" width="286" height="${18 + hudLines.length * 19}" rx="9" fill="${theme.hud.bg}" stroke="${theme.hud.line}" stroke-opacity="0.38"/>
  ${hudLines
    .map(
      ([text, colour], i) =>
        `<text x="42" y="${45 + i * 19}" fill="${colour}" font-family="ui-monospace,SFMono-Regular,Menlo,Consolas,monospace" font-size="${i === 0 ? 13.5 : 11.5}">${esc(text)}</text>`,
    )
    .join("\n  ")}
</g>
</svg>`;

  const tallestCanvas = [tallest.x * scale + tx, tallest.y * scale + ty];
  return {
    svg,
    stats: st,
    check: {
      scale: Math.round(scale * 1000) / 1000,
      cityW: Math.round(bw * scale),
      cityH: Math.round(bh * scale),
      waterY: Math.round(waterY),
      tallestAt: `${Math.round(tallestCanvas[0])},${Math.round(tallestCanvas[1])}`,
      tallestShareX: Math.round((tallestCanvas[0] / VIEW_W) * 100),
      tallestInLotWidths: Math.round(((MAX_FLOORS * BASE_FLOOR) / (34 * 0.83)) * 10) / 10,
      inside:
        box.minX * scale + tx >= -1 &&
        box.maxX * scale + tx <= VIEW_W + 1 &&
        box.minY * scale + ty >= -1 &&
        box.maxY * scale + ty <= VIEW_H + 1,
    },
  };
}

/* ---------------------------------------------------------------------- run */

async function main() {
  const days = await loadDays();
  const stats = statsOf(days);
  mkdirSync(OUT, { recursive: true });

  for (const key of THEME_KEYS) {
    const { svg, check } = buildCity(days, key);
    writeFileSync(`${OUT}/city-${key}.svg`, svg);
    console.log(
      `${OUT}/city-${key}.svg  ${(Buffer.byteLength(svg) / 1024).toFixed(0)} KB  ` +
        `city ${check.cityW}x${check.cityH}  scale ${check.scale}  ` +
        `waterline y=${check.waterY}  tallest at x=${check.tallestShareX}%  ` +
        `tallest ${check.tallestInLotWidths} lot widths  ` +
        `inside=${check.inside ? "yes" : "NO"}`,
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
