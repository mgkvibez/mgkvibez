#!/usr/bin/env node
/**
 * Re-themes the arcade contribution graphs into this profile's own terminal
 * language, and frames them.
 *
 * The games themselves stay abozanona/pacman-contribution-graph output: cell
 * reveal timing, ghosts, lasers and sprites are the engine's. What changes here
 * is everything around it — the contribution cells are repainted from GitHub's
 * stock greens onto this profile's phosphor ramp, and the whole scene is set
 * inside a CRT window with a live score line drawn from the same contribution
 * calendar the cards read.
 *
 * Zero dependencies. Reads the action's dist/ output, writes assets/images.
 *
 *   node scripts/arcade-retheme.mjs --in dist --out assets/images --sample
 */
import { mkdirSync, readFileSync, writeFileSync, existsSync } from "node:fs";
import { join } from "node:path";

const LOGIN = process.env.CITY_LOGIN || process.env.ARCADE_LOGIN || "mgkvibez";
const TOKEN = process.env.GH_PAT || process.env.CARDS_TOKEN || process.env.GITHUB_TOKEN || "";
const argOf = (name, fallback) => {
  const i = process.argv.indexOf(`--${name}`);
  return i > -1 ? process.argv[i + 1] : fallback;
};
const SAMPLE = process.argv.includes("--sample");
const IN = argOf("in", "dist");
const OUT = argOf("out", "assets/images");

/* ---------------------------------------------------------------- palettes */

// GitHub's stock ramp, both schemes, mapped onto phosphor. Keyed by source hex.
const MAP_DARK = {
  "#0d1117": "#04070a", // page behind the grid
  "#161b22": "#0b1a13", // an uneaten cell
  "#0e4429": "#0a3d21", // eaten, quiet day
  "#006d32": "#0d7a33",
  "#26a641": "#14c24c",
  "#39d353": "#00ff41", // eaten, busiest day
  "#8b949e": "#79b891", // month labels
  "#aaaaaa": "#8fd6a8",
  "#808080": "#5f9b74",
  "#000000": "#03070a", // galaga's void
  "#ffffff": "KEEP",    // sprites and stars: the game's own colours stay
  white: "KEEP",
  black: "#03070a",
};

const MAP_LIGHT = {
  "#ffffff": "#f4fff8",
  "#ebedf0": "#d6ecdd",
  "#9be9a8": "#8be5a8",
  "#40c463": "#27b95a",
  "#30a14e": "#12a144",
  "#216e39": "#0a7a2c",
  "#24292f": "#0c1a12",
  "#57606a": "#4a6b57",
  "#8b949e": "#5f8a70",
  "#aaaaaa": "#7fb894",
  "#000000": "#0a0f0c",
  "#ffffff ": "#f4fff8",
  white: "KEEP",
  black: "#0a0f0c",
};

const rack = (raw, map) => {
  const used = new Set();
  const out = raw.replace(/#[0-9a-fA-F]{6}\b|\bwhite\b|\bblack\b/g, (hex) => {
    const key = hex.toLowerCase();
    const to = map[key];
    if (!to || to === "KEEP") return hex;
    used.add(`${key}->${to}`);
    return to;
  });
  return { svg: out, used: [...used].length };
};

/* ------------------------------------------------------------------- stats */

const QUERY = `
query($login: String!) {
  user(login: $login) {
    contributionsCollection {
      contributionCalendar {
        totalContributions
        weeks { contributionDays { contributionCount } }
      }
    }
  }
}`;

async function liveStats(attempts = 3) {
  if (!TOKEN) return null;
  let last;
  for (let i = 0; i < attempts; i += 1) {
    if (i) await new Promise((r) => setTimeout(r, 1500 * i));
    try {
      const res = await fetch("https://api.github.com/graphql", {
        method: "POST",
        headers: { Authorization: `bearer ${TOKEN}`, "Content-Type": "application/json", "User-Agent": "arcade-retheme" },
        body: JSON.stringify({ query: QUERY, variables: { login: LOGIN } }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const body = await res.json();
      if (body.errors) throw new Error(JSON.stringify(body.errors));
      const cal = body.data.user.contributionsCollection.contributionCalendar;
      const days = cal.weeks.flatMap((w) => w.contributionDays.map((d) => d.contributionCount));
      let streak = 0;
      for (let i = days.length - 1; i >= 0; i -= 1) {
        if (days[i] > 0) streak += 1;
        else break;
      }
      return {
        total: cal.totalContributions,
        active: days.filter((c) => c > 0).length,
        best: Math.max(...days),
        streak,
      };
    } catch (error) {
      last = error;
    }
  }
  console.warn(`stats unavailable (${last && last.message}), reusing the cached line`);
  return null;
}

function cachedStats() {
  const file = join(OUT, "..", ".arcade-stats.json");
  try {
    return JSON.parse(readFileSync(file, "utf8"));
  } catch {
    return null;
  }
}

/* ------------------------------------------------------------------ chrome */

const esc = (s) => String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");

function frame({ game, label, innerW, innerH, stats, dark }) {
  const pad = 17;
  const bar = 34;
  const foot = 46;
  const W = innerW + pad * 2;
  const H = bar + innerH + foot;
  const bg = dark ? "#04070a" : "#f4fff8";
  const ink = dark ? "#00ff41" : "#0a7a2c";
  const dim = dark ? "#2f6b47" : "#4a6b57";
  const edge = dark ? "#123323" : "#bfe6cc";
  const hud = stats
    ? `SCORE ${stats.total.toLocaleString("en-US")}   ACTIVE ${stats.active}   BEST DAY ${stats.best}   STREAK ${stats.streak}d`
    : "SCORE ----   NO SIGNAL";
  const id = `ac-${game}-${dark ? "d" : "l"}`;

  return { W, H, svg: `<svg xmlns="http://www.w3.org/2000/svg" width="${W}" height="${H}" viewBox="0 0 ${W} ${H}" role="img" aria-label="Arcade contribution graph for ${esc(LOGIN)}, ${esc(label)}">
<title>${esc(LOGIN)} — ${esc(label)}</title>
<defs>
  <linearGradient id="${id}-bar" x1="0" y1="0" x2="0" y2="1">
    <stop offset="0%" stop-color="${dark ? "#0b1a13" : "#e7f7ec"}"/>
    <stop offset="100%" stop-color="${dark ? "#061009" : "#d9f0e1"}"/>
  </linearGradient>
  <pattern id="${id}-scan" width="4" height="4" patternUnits="userSpaceOnUse">
    <rect width="4" height="1" fill="${ink}" opacity="0.05"/>
  </pattern>
  <radialGradient id="${id}-vig" cx="0.5" cy="0.45" r="0.75">
    <stop offset="60%" stop-color="#000" stop-opacity="0"/>
    <stop offset="100%" stop-color="#000" stop-opacity="${dark ? 0.5 : 0.08}"/>
  </radialGradient>
</defs>
<rect x="0.5" y="0.5" width="${W - 1}" height="${H - 1}" rx="10" fill="${bg}" stroke="${edge}"/>
<path d="M10.5 0.5 H${W - 10.5} A10 10 0 0 1 ${W - 0.5} 10.5 V${bar} H0.5 V10.5 A10 10 0 0 1 10.5 0.5 Z" fill="url(#${id}-bar)"/>
<line x1="0.5" y1="${bar}" x2="${W - 0.5}" y2="${bar}" stroke="${edge}"/>
<circle cx="22" cy="17" r="4.2" fill="#ff5f57"/><circle cx="37" cy="17" r="4.2" fill="#febc2e"/><circle cx="52" cy="17" r="4.2" fill="#28c840"/>
<text x="${W / 2}" y="21.5" text-anchor="middle" font-family="ui-monospace,SFMono-Regular,Menlo,Consolas,monospace" font-size="12.5" fill="${dark ? "#79b891" : "#3f6b52"}">${esc(LOGIN)}@github:~$ arcade --${esc(game)}</text>
<text x="${W - 14}" y="21.5" text-anchor="end" font-family="ui-monospace,SFMono-Regular,Menlo,Consolas,monospace" font-size="10.5" fill="${dim}">${esc(label)}</text>
<!--GAME-->
<rect x="${pad}" y="${H - foot + 12}" width="${W - pad * 2}" height="1" fill="${edge}"/>
<text x="${pad + 4}" y="${H - foot + 32}" font-family="ui-monospace,SFMono-Regular,Menlo,Consolas,monospace" font-size="12" fill="${ink}" letter-spacing="0.6">${esc(hud)}</text>
</svg>` };
}

/* What the frame above lacks is the game inside it, so the game is spliced in
   place of that empty placeholder, keeping its own coordinate space. */

function compose({ source, game, label, dark, stats }) {
  const open = source.indexOf(">", source.indexOf("<svg")) + 1;
  const close = source.lastIndexOf("</svg>");
  let inner = source.slice(open, close);
  // drop the generator's own desc/metadata block: our title carries that
  inner = inner.replace(/<desc>[\s\S]*?<\/desc>/, "").replace(/<metadata>[\s\S]*?<\/metadata>/, "");

  const m = /<svg[^>]*width="(\d+)"[^>]*height="(\d+)"/.exec(source.slice(0, 400));
  const innerW = m ? Number(m[1]) : 1166;
  const innerH = m ? Number(m[2]) : 184;

  const shell = frame({ game, label, innerW, innerH, stats, dark });
  const placeholder = "<!--GAME-->";
  const body = `<svg x="17" y="34" width="${innerW}" height="${innerH}" overflow="visible">${inner}</svg>
<rect x="17" y="34" width="${innerW}" height="${innerH}" fill="url(#ac-${game}-${dark ? "d" : "l"}-scan)"/>
<rect x="0.5" y="0.5" width="${shell.W - 1}" height="${shell.H - 1}" rx="10" fill="url(#ac-${game}-${dark ? "d" : "l"}-vig)" pointer-events="none"/>`;

  return shell.svg.replace(placeholder, body);
}

/* -------------------------------------------------------------------- run */

const GAMES = [
  { key: "pacman", label: "PAC-MAN" },
];

const stats = SAMPLE
  ? { total: 2501, active: 88, best: 94, streak: 68 }
  : (await liveStats()) || cachedStats();

mkdirSync(OUT, { recursive: true });
let written = 0;

for (const { key, label } of GAMES) {
  for (const [suffix, dark, map] of [["", false, MAP_LIGHT], ["-dark", true, MAP_DARK]]) {
    const src = join(IN, `${key}-contribution-graph${suffix}.svg`);
    if (!existsSync(src)) {
      console.error(`missing ${src} — has the action changed its output paths?`);
      process.exit(1);
    }
    const raw = readFileSync(src, "utf8");
    const { svg: themed, used } = rack(raw, map);
    const composed = compose({ source: themed, game: key, label, dark, stats });

    if (!/<animate/.test(composed)) {
      console.error(`${src} lost its animation during retheme — aborting`);
      process.exit(1);
    }
    if (Buffer.byteLength(composed) < 20000) {
      console.error(`${src} produced ${Buffer.byteLength(composed)} bytes — too small, aborting`);
      process.exit(1);
    }

    const out = join(OUT, `arcade-${key}${suffix}.svg`);
    writeFileSync(out, composed);
    written += 1;
    console.log(`${out}  ${(Buffer.byteLength(composed) / 1024).toFixed(0)} KB  ${used} colours remapped`);
  }
}

if (stats && !SAMPLE) {
  writeFileSync(join(OUT, "..", ".arcade-stats.json"), JSON.stringify(stats, null, 2));
}
console.log(`wrote ${written} themed graphs`);
