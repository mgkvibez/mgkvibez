#!/usr/bin/env node
/**
 * Contribution City — an animated isometric skyline for a GitHub profile README.
 *
 * Every day of the last year becomes one building. Height is that day's
 * contribution count, so the busiest day is the tower you cannot miss. The whole
 * city is a self-contained SVG: no JavaScript, no external CSS, no fonts, no
 * images — GitHub serves it through camo as an <img>, so the only things that
 * survive are SMIL and CSS keyframes written inside the file.
 *
 *   node scripts/generate-city.mjs                 # live, needs GH_PAT or GITHUB_TOKEN
 *   node scripts/generate-city.mjs --sample        # synthetic year, no network
 *   CITY_LOGIN=someone node scripts/generate-city.mjs
 */
import { mkdirSync, writeFileSync } from "node:fs";
import { dirname } from "node:path";

const LOGIN = process.env.CITY_LOGIN || "mgkvibez";
const TOKEN = process.env.GH_PAT || process.env.GITHUB_TOKEN || "";
const OUT = process.env.CITY_OUT || "assets";
const SAMPLE = process.argv.includes("--sample");

/* ------------------------------------------------------------------ helpers */

const TILE_X = 10;          // half-width of one isometric tile
const TILE_Y = 5;           // half-depth of one isometric tile
const PAD_TOP = 172;        // sky above the back row
const WATER_H = 168;        // river / waterfront band at the front

/** Deterministic PRNG: the city must be identical for identical data. */
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

const r1 = (n) => Math.round(n * 10) / 10;
const clamp = (n, lo, hi) => Math.min(hi, Math.max(lo, n));

/* --------------------------------------------------------------------- data */

const QUERY = `
query($login: String!) {
  user(login: $login) {
    login
    name
    contributionsCollection {
      contributionCalendar {
        totalContributions
        weeks { contributionDays { date contributionCount } }
      }
    }
  }
}`;

async function graphql(query, variables, attempts = 3) {
  let last;
  for (let attempt = 0; attempt < attempts; attempt += 1) {
    if (attempt) await new Promise((r) => setTimeout(r, 2500 * attempt));
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
  const rnd = mulberry32(fnv1a("sample-city"));
  const days = [];
  const today = new Date();
  for (let i = 369; i >= 0; i -= 1) {
    const d = new Date(today.getTime() - i * 86400000);
    const weekend = [0, 6].includes(d.getUTCDay());
    const burst = i % 37 < 3 ? 4 : 1;
    const count = Math.max(0, Math.round((rnd() * 14 * burst) - (weekend ? 3 : 0)));
    days.push({ date: d.toISOString().slice(0, 10), count });
  }
  return days;
}

async function loadDays() {
  if (SAMPLE) return sampleDays();
  if (!TOKEN) {
    console.warn("no GH_PAT or GITHUB_TOKEN set — rendering the synthetic year");
    return sampleDays();
  }
  const user = await graphql(QUERY, { login: LOGIN });
  const cal = user.contributionsCollection.contributionCalendar;
  return cal.weeks.flatMap((w) =>
    w.contributionDays.map((d) => ({ date: d.date, count: d.contributionCount })),
  );
}

/* -------------------------------------------------------------------- stats */

function statsOf(days) {
  const total = days.reduce((sum, d) => sum + d.count, 0);
  let longest = 0;
  let run = 0;
  let current = 0;
  let busiest = days[0];

  for (const day of days) {
    run = day.count > 0 ? run + 1 : 0;
    longest = Math.max(longest, run);
    if (day.count > busiest.count) busiest = day;
  }
  for (let i = days.length - 1; i >= 0; i -= 1) {
    if (days[i].count > 0) current += 1;
    else break;
  }
  return { total, active: days.filter((d) => d.count > 0).length, current, longest, busiest };
}

/* --------------------------------------------------------------- iso layout */

function layout(days) {
  const start = new Date(`${days[0].date}T00:00:00Z`);
  const mondayIndex = (start.getUTCDay() + 6) % 7;
  const cells = [];
  days.forEach((day, i) => {
    const slot = i + mondayIndex;
    const week = Math.floor(slot / 7);
    const weekday = slot % 7;
    const month = day.date.slice(5, 7);
    cells.push({ ...day, week, weekday, month });
  });

  // real streets: every week column is a gap, every month boundary a wider one
  const xOfWeek = [];
  let x = 0;
  cells.forEach((c) => {
    if (xOfWeek[c.week] === undefined) xOfWeek[c.week] = 0;
  });
  let cursor = 0;
  let seenMonth = null;
  for (let w = 0; w <= Math.max(...cells.map((c) => c.week)); w += 1) {
    const first = cells.find((c) => c.week === w);
    if (first && first.month !== seenMonth) {
      if (seenMonth !== null) cursor += 9;   // street at the month boundary
      seenMonth = first.month;
    }
    xOfWeek[w] = cursor;
    cursor += 19;                             // one week column + its gap
  }
  return { cells, xOfWeek, weeks: xOfWeek.length };
}

/* ------------------------------------------------------------------ drawing */

const esc = (s) => String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");

function poly(points, fill, extra = "") {
  const d = points.map(([x, y]) => `${r1(x)},${r1(y)}`).join(" ");
  return `<polygon points="${d}" fill="${fill}"${extra}/>`;
}

/** Height in pixels for a day's count. Zero days are plazas, never nothing. */
function heightFor(count, peak) {
  if (count === 0) return 3;
  const ratio = Math.min(1, count / Math.max(12, peak));
  return 10 + Math.pow(ratio, 0.62) * 148;
}

function buildingFaces(cx, cy, h, w, theme, rnd, tall) {
  const halfW = w;             // half width along the iso axis
  const halfD = w * 0.5;
  const ax = cx;
  const ay = cy;
  const top = ay - h;

  // three visible faces of the prism, in painter's order
  const left = [[ax - halfW, ay], [ax, ay + halfD], [ax, top + halfD], [ax - halfW, top]];
  const right = [[ax, ay + halfD], [ax + halfW, ay], [ax + halfW, top], [ax, top + halfD]];
  const roof = [[ax, top + halfD], [ax + halfW, top], [ax, top - halfD], [ax - halfW, top]];

  const out = [];
  const glass = [];
  out.push(poly(left, theme.faces.left));
  out.push(poly(right, theme.faces.right));
  out.push(poly(roof, theme.faces.top, ` stroke="${theme.edge}" stroke-width="0.9" stroke-opacity="0.85"`));

  // a lit edge where the two facades meet: the strongest depth cue there is
  out.push(
    `<line x1="${r1(ax)}" y1="${r1(top + halfD)}" x2="${r1(ax)}" y2="${r1(ay + halfD)}" stroke="${theme.edge}" stroke-width="1.1" opacity="0.9"/>`,
  );

  // windows: deterministic per building, fewer on small ones
  const cols = clamp(Math.round(w * 1.1), 2, 4);
  const rows = clamp(Math.floor((h - 8) / 12), 1, 9);
  if (rows >= 1) {
    for (let c = 0; c < cols; c += 1) {
      for (let rr = 0; rr < rows; rr += 1) {
        if (rnd() > 0.72) continue;
        const fx = 0.14 + (c / cols) * 0.72;
        const fy = 0.12 + (rr / rows) * 0.76;
        const ww = 2.1;
        const hh = 3.1;
        // left face: dark, windows barely lit
        if (rnd() > 0.45) {
          glass.push(
            `<rect x="${r1(ax - halfW + fx * halfW + 1.4)}" y="${r1(top + fy * h + halfD * (1 - fx) + 2)}" width="${ww}" height="${hh}" fill="${theme.window}" opacity="${r1(0.45 + rnd() * 0.3)}"/>`,
          );
        }
        // right face: lit
        glass.push(
          `<rect x="${r1(ax + fx * halfW + 0.8)}" y="${r1(top + fy * h + halfD * fx + 2)}" width="${ww}" height="${hh}" fill="${theme.windowBright}" opacity="${r1(0.55 + rnd() * 0.45)}"/>`,
        );
      }
    }
  }

  if (tall) {
    // art-deco vertical strips / neon edge tubing up the corner
    out.push(
      `<line x1="${r1(ax)}" y1="${r1(top + halfD)}" x2="${r1(ax)}" y2="${r1(ay + halfD)}" stroke="${theme.stripe}" stroke-width="2" opacity="0.55"/>`,
    );
  }
  return { faces: out.join(""), glass: glass.join("") };
}

function themeStyles(theme) {
  return `
  .tw{animation:twinkle ${theme.twinkleSec}s ease-in-out infinite}
  .fog{animation:drift 18s ease-in-out infinite}
  .fog2{animation:drift 24s ease-in-out infinite reverse}
  .beam{animation:sweep 16s ease-in-out infinite}
  .glow{animation:breathe 9s ease-in-out infinite}
  .car{animation:drive ${theme.carSec}s linear infinite}
  .shimmer{animation:shimmer 8s ease-in-out infinite}
  @keyframes twinkle{0%,100%{opacity:.55}50%{opacity:1}}
  @keyframes drift{0%,100%{transform:translateX(0)}50%{transform:translateX(26px)}}
  @keyframes sweep{0%,100%{transform:rotate(-13deg)}50%{transform:rotate(13deg)}}
  @keyframes breathe{0%,100%{opacity:.55}50%{opacity:.9}}
  @keyframes drive{0%{transform:translateX(-40px)}100%{transform:translateX(1100px)}}
  @keyframes shimmer{0%,100%{opacity:.75}45%{opacity:1}60%{opacity:.6}}
  @media (prefers-reduced-motion: reduce){
    .tw,.fog,.fog2,.beam,.glow,.car,.shimmer{animation:none}
  }`;
}

/* -------------------------------------------------------------------- cities */

const THEMES = {
  gold: {
    key: "gold",
    title: "Contribution City — dusk",
    twinkleSec: 6.5,
    carSec: 22,
    sky: [
      ["0%", "#0d0a24"],
      ["38%", "#2a1346"],
      ["62%", "#6b2350"],
      ["82%", "#b8452f"],
      ["100%", "#f0903c"],
    ],
    sun: { x: 905, y: 268, r: 46, core: "#ffe6a8", halo: "#ff9a4d" },
    faces: { left: "#33241b", right: "#553c29", top: "#8a6740" },
    edge: "#f4d79b",
    window: "#c9964a",
    windowBright: "#ffd98a",
    stripe: "#f0c987",
    ground: "#1b1420",
    groundAlt: "#221725",
    street: "#0f0a14",
    water: [["0%", "#120d1e"], ["55%", "#2a1730"], ["100%", "#3d2033"]],
    reflection: "#ffbf6b",
    prop: "#2f4a3a",
    hud: { bg: "rgba(12,8,20,0.72)", stroke: "#e8c477", text: "#f6e2b8", dim: "#b99a6b" },
    accent: "#f0c987",
    spire: "#ffe7a6",
  },
  neon: {
    key: "neon",
    title: "Contribution City — fog",
    twinkleSec: 4.2,
    carSec: 14,
    sky: [
      ["0%", "#04060d"],
      ["45%", "#080f1e"],
      ["78%", "#11203a"],
      ["100%", "#16324f"],
    ],
    sun: { x: 250, y: 210, r: 30, core: "#bff6ff", halo: "#22d3ee" },
    faces: { left: "#1a3a55", right: "#26516f", top: "#3a7290" },
    edge: "#5ceaff",
    window: "#1f7f96",
    windowBright: "#d8fdff",
    stripe: "#f472b6",
    ground: "#0b1626",
    groundAlt: "#132437",
    street: "#03060c",
    water: [["0%", "#04101a"], ["55%", "#062231"], ["100%", "#0a3140"]],
    reflection: "#22d3ee",
    prop: "#123a2c",
    hud: { bg: "rgba(4,10,18,0.74)", stroke: "#22d3ee", text: "#d9fbff", dim: "#4f8fa6" },
    accent: "#00ff41",
    spire: "#9dffb4",
  },
};

function buildCity(days, themeKey) {
  const theme = THEMES[themeKey];
  const st = statsOf(days);
  const { cells, xOfWeek, weeks } = layout(days);
  const seed = fnv1a(`${days[days.length - 1].date}|${themeKey}|${st.total}`);
  const rnd = mulberry32(seed);

  const W = 1200;
  const DEPTH = 470;                 // vertical room for the plane itself
  const H = PAD_TOP + DEPTH + WATER_H;
  const cx = W / 2;
  const backY = PAD_TOP + 14;
  const groundEnd = PAD_TOP + DEPTH;
  const maxGx = xOfWeek[xOfWeek.length - 1];

  // project: week axis runs right-back, weekday axis right-front
  const spanMin = -6 * 19;           // last weekday of the first week
  const spanMax = maxGx;             // first weekday of the last week
  const spanMid = (spanMin + spanMax) / 2;
  const yMax = maxGx * 0.26 + 6 * TILE_Y * 1.55;
  const ySquash = (DEPTH - 46) / Math.max(1, yMax);

  const pos = (cell) => {
    const gx = xOfWeek[cell.week];
    const along = gx - cell.weekday * 19;
    const x = cx + (along - spanMid) * 0.5;
    const y = backY + (gx * 0.26 + cell.weekday * TILE_Y * 1.55) * ySquash;
    return { x, y };
  };

  const peak = Math.max(1, ...cells.map((c) => c.count));
  const busiest = st.busiest.date;

  // ---- sky
  const skyStops = theme.sky
    .map(([offset, colour]) => `<stop offset="${offset}" stop-color="${colour}"/>`)
    .join("");
  const parts = [];
  parts.push(
    `<svg xmlns="http://www.w3.org/2000/svg" width="${W}" height="${H}" viewBox="0 0 ${W} ${H}" role="img" aria-label="${esc(theme.title)}: ${st.total} contributions as an isometric skyline">`,
    `<title>${esc(theme.title)} — ${st.total} contributions</title>`,
    `<defs>
      <linearGradient id="sky-${theme.key}" x1="0" y1="0" x2="0" y2="1">${skyStops}</linearGradient>
      <linearGradient id="water-${theme.key}" x1="0" y1="0" x2="0" y2="1">${theme.water
        .map(([o, c]) => `<stop offset="${o}" stop-color="${c}"/>`)
        .join("")}</linearGradient>
      <radialGradient id="halo-${theme.key}">
        <stop offset="0%" stop-color="${theme.sun.halo}" stop-opacity="0.85"/>
        <stop offset="60%" stop-color="${theme.sun.halo}" stop-opacity="0.12"/>
        <stop offset="100%" stop-color="${theme.sun.halo}" stop-opacity="0"/>
      </radialGradient>
      <linearGradient id="haze-${theme.key}" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0%" stop-color="${theme.sky[1][1]}" stop-opacity="0"/>
        <stop offset="100%" stop-color="${theme.sky[1][1]}" stop-opacity="0.75"/>
      </linearGradient>
      <filter id="soft-${theme.key}" x="-40%" y="-40%" width="180%" height="180%">
        <feGaussianBlur stdDeviation="9"/>
      </filter>
      <filter id="glow-${theme.key}" x="-60%" y="-60%" width="220%" height="220%">
        <feGaussianBlur stdDeviation="4.5" result="b"/>
        <feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge>
      </filter>
      <style>${themeStyles(theme)}</style>
    </defs>`,
    `<rect width="${W}" height="${H}" fill="url(#sky-${theme.key})"/>`,
  );

  // ---- sun / moon and its glow
  const { sun } = theme;
  parts.push(
    `<g class="glow"><circle cx="${sun.x}" cy="${sun.y}" r="${sun.r * 3.4}" fill="url(#halo-${theme.key})"/>`,
    `<circle cx="${sun.x}" cy="${sun.y}" r="${sun.r}" fill="${sun.core}" opacity="0.95"/></g>`,
  );

  // ---- clouds (gold) / haze bands (neon)
  if (themeKey === "gold") {
    for (let i = 0; i < 4; i += 1) {
      const cy2 = 90 + i * 34;
      const w2 = 190 + i * 70;
      parts.push(
        `<g class="fog" opacity="${0.16 + i * 0.03}"><ellipse cx="${180 + i * 250}" cy="${cy2}" rx="${w2}" ry="${13 + i * 3}" fill="#f7c08a" filter="url(#soft-${theme.key})"/></g>`,
      );
    }
  } else {
    for (let i = 0; i < 3; i += 1) {
      parts.push(
        `<g class="${i % 2 ? "fog2" : "fog"}" opacity="0.3"><ellipse cx="${200 + i * 380}" cy="${groundEnd - 40 - i * 30}" rx="${420 - i * 60}" ry="26" fill="#0e3550" filter="url(#soft-${theme.key})"/></g>`,
      );
    }
  }

  // ---- ground plate
  const plateMidY = backY + yMax * ySquash * 0.52;
  const plate = [
    [cx - 566, plateMidY],
    [cx, plateMidY + 172],
    [cx + 566, plateMidY],
    [cx, plateMidY - 172],
  ];
  parts.push(poly(plate, theme.ground, ' opacity="0.92"'));

  // ---- street grid under the blocks
  const streets = [];
  for (let w = 0; w < weeks; w += 1) {
    if (w % 4 !== 0) continue;
    const a = { x: cx + (xOfWeek[w]) * 0.5 - 40, y: backY + xOfWeek[w] * 0.26 };
    streets.push(
      `<line x1="${r1(a.x - 250)}" y1="${r1(a.y + 120)}" x2="${r1(a.x + 250)}" y2="${r1(a.y - 40)}" stroke="${theme.street}" stroke-width="5" opacity="0.55"/>`,
    );
  }
  parts.push(...streets);

  // ---- buildings, far to near
  const ordered = [...cells].sort((a, b) => {
    const da = xOfWeek[a.week] + a.weekday * 19;
    const db = xOfWeek[b.week] + b.weekday * 19;
    return da - db;
  });

  const cars = [];
  let tallestDrawn = false;

  for (const cell of ordered) {
    const { x, y } = pos(cell);
    const h = heightFor(cell.count, peak);
    const w = cell.count === 0 ? 6.4 : 6.2 + Math.min(1.6, cell.count / 40);
    const isTallest = cell.date === busiest && !tallestDrawn;

    if (cell.count === 0) {
      // empty lot: a low plaza slab with a tree or two
      const slab = [
        [x - w, y],
        [x, y + w * 0.5],
        [x + w, y],
        [x, y - w * 0.5],
      ];
      parts.push(poly(slab, theme.groundAlt, ` opacity="0.95" stroke="${theme.edge}" stroke-width="0.4" stroke-opacity="0.18"`));
      if (rnd() > 0.55) {
        const tx = x + (rnd() - 0.5) * 6;
        parts.push(
          `<rect x="${r1(tx - 0.7)}" y="${r1(y - 7)}" width="1.4" height="6" fill="${theme.prop}"/>`,
          `<circle cx="${r1(tx)}" cy="${r1(y - 9)}" r="${r1(2.6 + rnd())}" fill="${theme.prop}" opacity="0.9"/>`,
        );
      }
      continue;
    }

    parts.push(`<ellipse cx="${r1(x + 1.5)}" cy="${r1(y + w * 0.5)}" rx="${r1(w * 1.15)}" ry="${r1(w * 0.34)}" fill="#000000" opacity="0.28"/>`);
    const { faces, glass } = buildingFaces(x, y, h, w, theme, rnd, h > 78);
    parts.push(faces);
    if (glass) {
      parts.push(`<g class="tw" style="animation-delay:${r1(rnd() * theme.twinkleSec)}s">${glass}</g>`);
    }

    // rooftop detail: crown spire on the busiest day, aerial on the next tallest
    if (isTallest) {
      tallestDrawn = true;
      const top = y - h;
      parts.push(
        `<g class="glow">`,
        `<line x1="${r1(x)}" y1="${r1(top + w * 0.5)}" x2="${r1(x)}" y2="${r1(top - 34)}" stroke="${theme.spire}" stroke-width="2.4"/>`,
        `<circle cx="${r1(x)}" cy="${r1(top - 38)}" r="4.2" fill="${theme.spire}" filter="url(#glow-${theme.key})"/>`,
        `</g>`,
      );
    } else if (h > 110 && rnd() > 0.6) {
      const top = y - h;
      parts.push(
        `<line x1="${r1(x)}" y1="${r1(top + w * 0.4)}" x2="${r1(x)}" y2="${r1(top - 14)}" stroke="${theme.edge}" stroke-width="1" opacity="0.8"/>`,
      );
    }

    // a few billboards on the front face (neon) / lit signage (gold)
    if (h > 96 && rnd() > 0.72) {
      const top = y - h;
      const by = top + h * (0.22 + rnd() * 0.2);
      const colour = themeKey === "neon" ? (rnd() > 0.5 ? "#f472b6" : "#00ff41") : theme.windowBright;
      parts.push(
        `<rect class="shimmer" x="${r1(x + 1.5)}" y="${r1(by)}" width="4.6" height="12" fill="${colour}" opacity="0.9" filter="url(#glow-${theme.key})"/>`,
      );
    }

    // cars on the near streets
    if (rnd() > 0.82) {
      const lane = y + w * 0.62;
      cars.push({ y: lane, delay: -r1(rnd() * theme.carSec), light: rnd() > 0.5 ? "#ffffff" : "#ff5f57" });
    }
  }

  // ---- traffic: light dots sliding along the avenues
  for (const car of cars.slice(0, 14)) {
    parts.push(
      `<g class="car" style="animation-delay:${car.delay}s"><rect x="0" y="${r1(car.y)}" width="5" height="2.2" rx="1" fill="${car.light}" opacity="0.9" filter="url(#glow-${theme.key})"/></g>`,
    );
  }

  // ---- river / waterfront with reflections
  parts.push(
    `<rect x="0" y="${groundEnd}" width="${W}" height="${WATER_H}" fill="url(#water-${theme.key})"/>`,
    `<line x1="0" y1="${groundEnd}" x2="${W}" y2="${groundEnd}" stroke="${theme.accent}" stroke-width="1" opacity="0.35"/>`,
  );
  for (let i = 0; i < 26; i += 1) {
    const rx = 40 + rnd() * (W - 80);
    const ry = groundEnd + 8 + rnd() * (WATER_H - 26);
    const rw = 4 + rnd() * 22;
    parts.push(
      `<rect x="${r1(rx)}" y="${r1(ry)}" width="${r1(rw)}" height="1.6" fill="${theme.reflection}" opacity="${r1(0.1 + rnd() * 0.3)}"/>`,
    );
  }

  // ---- searchlights (gold) / sky glow bands (neon)
  if (themeKey === "gold") {
    for (let i = 0; i < 3; i += 1) {
      const bx = 240 + i * 320;
      const by = groundEnd - 150;
      const delay = -i * 4;
      parts.push(
        `<g class="beam" style="animation-delay:${delay}s;transform-origin:${r1(bx)}px ${r1(by)}px">`,
        `<polygon points="${r1(bx)},${r1(by)} ${r1(bx - 26)},${r1(by - 300)} ${r1(bx + 26)},${r1(by - 300)}" fill="#ffe9b0" opacity="0.09" filter="url(#soft-${theme.key})"/>`,
        `</g>`,
      );
    }
  } else {
    parts.push(
      `<rect x="0" y="${groundEnd - 60}" width="${W}" height="60" fill="#22d3ee" opacity="0.05" filter="url(#soft-${theme.key})"/>`,
      `<rect x="0" y="${groundEnd - 120}" width="${W}" height="50" fill="#f472b6" opacity="0.045" filter="url(#soft-${theme.key})"/>`,
    );
  }

  // ---- haze over the back of the city so depth reads
  parts.push(
    `<rect x="0" y="${backY - 20}" width="${W}" height="150" fill="url(#haze-${theme.key})" opacity="0.5"/>`,
  );

  // ---- HUD
  const hud = theme.hud;
  const lines = [
    ["@" + LOGIN, hud.text],
    [`${st.total.toLocaleString("en-US")} contributions`, hud.text],
    [`${st.current}d streak · ${st.longest}d longest`, hud.dim],
    [`busiest ${st.busiest.count} · ${st.busiest.date}`, hud.dim],
  ];
  const hudText = lines
    .map(
      ([text, colour], i) =>
        `<text x="44" y="${48 + i * 20}" fill="${colour}" font-family="ui-monospace,SFMono-Regular,Menlo,Consolas,monospace" font-size="${i === 0 ? 13 : 11.5}" letter-spacing="0.5">${esc(text)}</text>`,
    )
    .join("");
  parts.push(
    `<g><rect x="26" y="26" width="290" height="94" rx="8" fill="${hud.bg}" stroke="${hud.stroke}" stroke-opacity="0.45"/>${hudText}</g>`,
  );

  parts.push("</svg>");
  return { svg: parts.join("\n"), stats: st };
}

/* ---------------------------------------------------------------------- run */

async function main() {
  const days = await loadDays();
  const stats = statsOf(days);
  mkdirSync(OUT, { recursive: true });

  for (const key of ["gold", "neon"]) {
    const { svg } = buildCity(days, key);
    const path = `${OUT}/city-${key}.svg`;
    mkdirSync(dirname(path), { recursive: true });
    writeFileSync(path, svg);
    const kb = (Buffer.byteLength(svg) / 1024).toFixed(0);
    console.log(`${path}  ${kb} KB`);
  }

  // keep the README caption honest: it is the one number a reader trusts,
  // so the same run that redraws the city rewrites it between the markers.
  try {
    const readmePath = "README.md";
    const readme = await import("node:fs").then((m) => m.readFileSync(readmePath, "utf8"));
    const caption =
      `**${stats.total.toLocaleString("en-US")} contributions** · ` +
      `${stats.current}-day current streak · ${stats.longest}-day longest · ` +
      `busiest day ${stats.busiest.count} on ${stats.busiest.date}`;
    const updated = readme.replace(
      /<!-- city:stats:start -->[\s\S]*?<!-- city:stats:end -->/,
      `<!-- city:stats:start -->${caption}<!-- city:stats:end -->`,
    );
    if (updated !== readme) {
      await import("node:fs").then((m) => m.writeFileSync(readmePath, updated));
      console.log("README caption updated");
    }
  } catch (error) {
    console.log("no README to update:", error.message);
  }

  const s = stats;
  console.log(
    `total ${s.total} · active ${s.active} · current ${s.current}d · longest ${s.longest}d · busiest ${s.busiest.count} on ${s.busiest.date}`,
  );
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
