#!/usr/bin/env node
/**
 * Terminal boot hero for the profile README.
 *
 * Draws one self-contained SVG: a CRT window that types a short ssh session,
 * then settles into a neofetch-style readout of the real account. No JS, no
 * web fonts, no images inside the file - GitHub renders it through camo, where
 * nothing but CSS keyframes and SMIL survives.
 *
 *   node scripts/generate-hero.mjs                     # live GraphQL
 *   node scripts/generate-hero.mjs --sample            # deterministic, offline
 *   node scripts/generate-hero.mjs --out assets/hero.svg
 *
 * Exits non-zero on fetch failure WITHOUT touching the existing file, so a bad
 * API day can never blank the top of the profile.
 */
import { writeFileSync, readFileSync, existsSync } from "node:fs";

const W = 1200;
const H = 420;
const LOGIN = process.env.HERO_LOGIN || "mgkvibez";
const TOKEN = process.env.CARDS_TOKEN || process.env.GITHUB_TOKEN || "";

// palette mirrors cards/theme.py
const BG = "#0a0e14";
const PANEL = "#0d1117";
const CHROME = "#161b22";
const BORDER = "#1f2730";
const FG = "#c9d1d9";
const DIM = "#8b949e";
const GREEN = "#00ff41";
const PHOSPHOR = "#39d353";
const AMBER = "#e3b341";
const CYAN = "#58a6ff";
const MONO =
  "ui-monospace, SFMono-Regular, 'SF Mono', Menlo, Consolas, 'Liberation Mono', monospace";

const LANG_COLOURS = {
  TypeScript: "#3178c6", Python: "#3572a5", JavaScript: "#f1e05a",
  Shell: "#89e051", HTML: "#e34c26", SCSS: "#c6538c", Go: "#00add8",
  Rust: "#dea584", Dockerfile: "#384d54", CSS: "#563d7c", Makefile: "#427819",
};

const esc = (s) =>
  String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");

function months(years) {
  const m = Math.round(years * 12);
  const y = Math.floor(m / 12);
  const r = m % 12;
  if (y && r) return `${y}y ${r}m`;
  if (y) return `${y}y`;
  return `${r}m`;
}

const SAMPLE = {
  login: "mgkvibez",
  createdAt: "2025-02-11T17:27:08Z",
  repos: 47,
  stars: 110,
  followers: 31,
  languages: [
    ["TypeScript", 15124686], ["Python", 1628350], ["JavaScript", 953321],
    ["Shell", 177410], ["HTML", 112977],
  ],
};

const QUERY = `
query($login: String!) {
  user(login: $login) {
    login
    createdAt
    followers { totalCount }
    repositories(first: 100, ownerAffiliations: OWNER, isFork: false, privacy: PUBLIC) {
      totalCount
      nodes {
        stargazerCount
        languages(first: 10, orderBy: {field: SIZE, direction: DESC}) {
          edges { size node { name } }
        }
      }
    }
  }
}`;

async function fetchLive() {
  if (!TOKEN) throw new Error("no CARDS_TOKEN/GITHUB_TOKEN in the environment");
  let last;
  for (let attempt = 0; attempt < 3; attempt += 1) {
    try {
      const res = await fetch("https://api.github.com/graphql", {
        method: "POST",
        headers: {
          Authorization: `bearer ${TOKEN}`,
          "Content-Type": "application/json",
          "User-Agent": "mgkvibez-hero",
        },
        body: JSON.stringify({ query: QUERY, variables: { login: LOGIN } }),
      });
      if (!res.ok) throw new Error(`GraphQL HTTP ${res.status}`);
      const body = await res.json();
      if (body.errors) throw new Error(body.errors[0].message);
      const user = body.data.user;
      const sizes = new Map();
      for (const repo of user.repositories.nodes) {
        for (const edge of repo.languages.edges) {
          sizes.set(edge.node.name, (sizes.get(edge.node.name) || 0) + edge.size);
        }
      }
      return {
        login: user.login,
        createdAt: user.createdAt,
        repos: user.repositories.totalCount,
        stars: user.repositories.nodes.reduce((n, r) => n + r.stargazerCount, 0),
        followers: user.followers.totalCount,
        languages: [...sizes.entries()].sort((a, b) => b[1] - a[1]).slice(0, 5),
      };
    } catch (error) {
      last = error;
      await new Promise((r) => setTimeout(r, 1500 * (attempt + 1)));
    }
  }
  throw last;
}

/** A shield, drawn rather than set in a font, so it renders anywhere. */
function emblem(cx, cy) {
  const w = 96;
  const h = 112;
  const left = cx - w / 2;
  const right = cx + w / 2;
  const top = cy - h / 2;
  const shoulder = top + h * 0.58;
  const bottom = top + h;
  const mid = cx;
  return `
    <g class="emblem">
      <path d="M ${left} ${top} L ${right} ${top} L ${right} ${shoulder}
               Q ${right} ${bottom - 18} ${mid} ${bottom}
               Q ${left} ${bottom - 18} ${left} ${shoulder} Z"
            fill="url(#shieldFill)" stroke="${GREEN}" stroke-width="2.5" stroke-opacity="0.9"/>
      <path d="M ${left + 10} ${top + 10} L ${right - 10} ${top + 10} L ${right - 10} ${shoulder}
               Q ${right - 10} ${bottom - 26} ${mid} ${bottom - 10}
               Q ${left + 10} ${bottom - 26} ${left + 10} ${shoulder} Z"
            fill="none" stroke="${PHOSPHOR}" stroke-width="1.2" stroke-opacity="0.45"/>
      <circle cx="${mid}" cy="${top + 46}" r="11" fill="${PANEL}" stroke="${PHOSPHOR}" stroke-width="2"/>
      <rect x="${mid - 4.5}" y="${top + 52}" width="9" height="24" rx="4.5" fill="${PANEL}" stroke="${PHOSPHOR}" stroke-width="2"/>
    </g>`;
}

function build(data) {
  const joined = new Date(data.createdAt);
  const now = Date.now();
  const years = Math.max(0, (now - joined.getTime()) / (365.25 * 24 * 3600 * 1000));
  const started = joined.toLocaleString("en-GB", { month: "short", year: "numeric", timeZone: "UTC" });

  const screenTop = 48;
  const promptOne = 84;
  const promptTwo = 112;
  const blockTop = 152;

  const rows = [
    ["HOST", `@${data.login}`, FG],
    ["UPTIME", `${months(years)}  since ${started}`, FG],
    ["REPOS", `${data.repos} public`, FG],
    ["STARS", `${data.stars}`, GREEN],
    ["FOLLOWERS", `${data.followers}`, FG],
  ];

  const rowGap = 27;
  const rowsSvg = rows
    .map(([label, value, colour], i) => {
      const y = blockTop + 26 + i * rowGap;
      return `<g class="row" style="--d:${(2.0 + i * 0.12).toFixed(2)}s">
        <text x="316" y="${y}" class="lbl">${label}</text>
        <text x="430" y="${y}" fill="${colour}">${esc(value)}</text>
      </g>`;
    })
    .join("");

  const focusY = blockTop + 26 + rows.length * rowGap + 10;
  const focus = `<g class="row" style="--d:2.8s">
      <text x="316" y="${focusY}" class="lbl">FOCUS</text>
      <text x="430" y="${focusY}" fill="${FG}">security tooling · CI/testing infra · AI agent tooling</text>
    </g>`;

  const langY = focusY + 32;
  let cursorX = 430;
  const langSvg = data.languages
    .map(([name], i) => {
      const x = cursorX;
      const label = name;
      const slot = `<g class="row" style="--d:${(3.2 + i * 0.14).toFixed(2)}s">
        <circle cx="${x + 5}" cy="${langY - 4}" r="5" fill="${LANG_COLOURS[name] || DIM}"/>
        <text x="${x + 18}" y="${langY}" fill="${FG}">${esc(label)}</text>
      </g>`;
      cursorX += 26 + label.length * 7.6;
      return slot;
    })
    .join("");

  return `<svg xmlns="http://www.w3.org/2000/svg" width="${W}" height="${H}" viewBox="0 0 ${W} ${H}" role="img" aria-labelledby="heroTitle heroDesc">
  <title id="heroTitle">Terminal boot sequence for ${esc(data.login)}</title>
  <desc id="heroDesc">A CRT terminal types an ssh session, then prints ${data.repos} public repositories, ${data.stars} stars, ${data.followers} followers and the top languages.</desc>
  <defs>
    <linearGradient id="shieldFill" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0" stop-color="${GREEN}" stop-opacity="0.22"/>
      <stop offset="1" stop-color="${PHOSPHOR}" stop-opacity="0.05"/>
    </linearGradient>
    <linearGradient id="screenWash" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0" stop-color="${GREEN}" stop-opacity="0.05"/>
      <stop offset="0.5" stop-color="${GREEN}" stop-opacity="0"/>
      <stop offset="1" stop-color="${PHOSPHOR}" stop-opacity="0.04"/>
    </linearGradient>
    <pattern id="scanlines" width="4" height="4" patternUnits="userSpaceOnUse">
      <rect width="4" height="1.4" fill="#000000" opacity="0.16"/>
    </pattern>
    <filter id="glow" x="-40%" y="-40%" width="180%" height="180%">
      <feGaussianBlur stdDeviation="3" result="b"/>
      <feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge>
    </filter>
    <style>
      text { font-family: ${MONO}; font-size: 16px; fill: ${FG}; letter-spacing: 0.2px; }
      .lbl { fill: ${DIM}; font-size: 13.5px; letter-spacing: 1.2px; }
      .title { fill: ${DIM}; font-size: 12px; letter-spacing: 1px; }
      .big { fill: ${GREEN}; font-size: 15px; }
      /* Everything is visible by default: motion is an enhancement, never a
         precondition for reading the card. Reduced motion simply keeps the
         finished frame. */
      @media (prefers-reduced-motion: no-preference) {
        .typeline { animation: wipe 0.55s steps(28, end) var(--d) both; }
        .row { animation: fade 0.5s ease-out var(--d) both; }
        .cursor { animation: blink 1.1s steps(2, start) infinite; }
        .sweep { animation: sweep 9s linear infinite; }
        .flicker { animation: flicker 7s ease-in-out infinite; }
        .emblem { animation: fade 0.9s ease-out 1.5s both; }
      }
      @keyframes wipe { from { clip-path: inset(0 100% 0 0); } to { clip-path: inset(0 0 0 0); } }
      @keyframes fade { from { opacity: 0; transform: translateY(3px); } to { opacity: 1; transform: translateY(0); } }
      @keyframes blink { 0%, 49% { opacity: 1; } 50%, 100% { opacity: 0; } }
      @keyframes sweep { from { transform: translateY(0); } to { transform: translateY(364px); } }
      @keyframes flicker { 0%, 96%, 100% { opacity: 1; } 97% { opacity: 0.93; } 98.5% { opacity: 0.98; } }
    </style>
  </defs>

  <rect width="${W}" height="${H}" fill="${BG}"/>
  <g class="flicker">
    <rect x="8" y="8" width="${W - 16}" height="${H - 16}" rx="12" fill="${PANEL}" stroke="${BORDER}"/>
    <path d="M 8 48 H ${W - 8}" stroke="${BORDER}"/>
    <rect x="20" y="20" width="${W - 40}" height="20" fill="none"/>
    <circle cx="34" cy="28" r="5" fill="#f85149"/>
    <circle cx="52" cy="28" r="5" fill="${AMBER}"/>
    <circle cx="70" cy="28" r="5" fill="${PHOSPHOR}"/>
    <text x="92" y="33" class="title">visitor@github - ssh</text>
    <text x="${W - 28}" y="33" class="title" text-anchor="end">tty1 · 80x24</text>

    <rect x="9" y="${screenTop}" width="${W - 18}" height="${H - 56}" fill="url(#screenWash)"/>

    <text x="40" y="${promptOne}" class="typeline" style="--d:0.25s">$ ssh visitor@github</text>
    <text x="238" y="${promptOne}" class="typeline big" style="--d:0.85s; fill:${GREEN}">auth ok</text>
    <text x="40" y="${promptTwo}" class="typeline" style="--d:1.15s">$ ./whoami --verbose</text>
    <rect class="cursor" x="232" y="${promptTwo - 13}" width="9" height="15" fill="${GREEN}"/>

    ${emblem(180, blockTop + 96)}
    <text x="180" y="${blockTop + 178}" fill="${GREEN}" text-anchor="middle" font-size="14">@${esc(data.login)}</text>
    <text x="180" y="${blockTop + 198}" class="lbl" text-anchor="middle">github.com/${esc(data.login)}</text>

    ${rowsSvg}
    ${focus}
    ${langSvg}

    <path d="M 32 ${H - 42} H ${W - 32}" stroke="${BORDER}" stroke-opacity="0.8"/>
    <text x="40" y="${H - 20}" class="lbl" style="font-size:11.5px">read-only session · rendered from the live GitHub API · no credentials stored</text>
    <text x="${W - 40}" y="${H - 20}" class="lbl" style="font-size:11.5px" text-anchor="end">${new Date().toISOString().slice(0,10)}</text>

    <rect x="9" y="${screenTop}" width="${W - 18}" height="${H - 56}" fill="url(#scanlines)" pointer-events="none"/>
    <g clip-path="url(#sweepClip)">
      <rect class="sweep" x="9" y="${screenTop}" width="${W - 18}" height="26" fill="${GREEN}" opacity="0.045"/>
    </g>
    <clipPath id="sweepClip"><rect x="9" y="${screenTop}" width="${W - 18}" height="${H - 56}"/></clipPath>
  </g>
</svg>
`;
}

async function main() {
  const args = process.argv.slice(2);
  const sample = args.includes("--sample");
  const outIndex = args.indexOf("--out");
  const out = outIndex >= 0 ? args[outIndex + 1] : "assets/hero.svg";

  let data;
  try {
    data = sample ? SAMPLE : await fetchLive();
  } catch (error) {
    console.error(`hero: keeping the existing ${out} (${error.message})`);
    process.exit(1);
  }

  const svg = build(data);
  if (svg.length > 300 * 1024) {
    console.error("hero: refusing to write, over the 300 KB budget");
    process.exit(1);
  }
  if (existsSync(out) && readFileSync(out, "utf8") === svg) {
    console.log(`hero: unchanged (${Math.round(svg.length / 1024)} KB)`);
    return;
  }
  writeFileSync(out, svg);
  console.log(
    `hero: ${out} ${Math.round(svg.length / 1024)} KB · ${data.repos} repos · ` +
      `${data.stars} stars · ${data.followers} followers · ${data.languages.length} languages`,
  );
}

main();
