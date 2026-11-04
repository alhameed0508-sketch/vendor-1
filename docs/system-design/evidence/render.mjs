// Render a sketch-style design page and check it.
//
//   node render.mjs <page.html> [--out DIR] [--name NAME] [--review DIR] [--pw PATH]
//
// Writes  <NAME>-overview.png  (the #ov diagram at 2x, if the page has one)
//         <NAME>.pdf           (whole page, A4 landscape from the page's print CSS)
// Checks  - labels that overlap, sit within 6 px of their box edge, or have a line running through them
//           (lines marked data-cross="1" are exempt, e.g. a deliberate red X)
//         - horizontal overflow at 390 px phone width
//         - JavaScript errors
// Exits 1 if any check fails, so it can be used as a gate.
//
// Needs playwright-core and an installed Chrome or Edge (no browser download). --pw may point to any
// folder whose node_modules contains playwright-core (or to a package.json in such a folder).
import { createRequire } from "node:module";
import { fileURLToPath, pathToFileURL } from "node:url";
import path from "node:path";
import fs from "node:fs";

const args = process.argv.slice(2);
const opt = (k, d) => { const i = args.indexOf(k); return i >= 0 ? args[i + 1] : d; };
const html = path.resolve(args.find((a) => !a.startsWith("--") && !args[args.indexOf(a) - 1]?.startsWith("--")) ?? "");
if (!html.endsWith(".html") || !fs.existsSync(html)) { console.error("usage: node render.mjs <page.html> [--out DIR] [--name NAME] [--review DIR] [--pw PATH]"); process.exit(2); }
const outDir = path.resolve(opt("--out", path.dirname(html)));
const name = opt("--name", path.basename(html, ".html"));
const reviewDir = opt("--review", null);

function loadPlaywright() {
  const tries = [opt("--pw", null), process.cwd(), path.dirname(html), path.dirname(fileURLToPath(import.meta.url))]
    .filter(Boolean).map((p) => (p.endsWith(".json") ? p : path.join(p, "package.json")));
  for (const t of tries) {
    try { return createRequire(t)("playwright-core"); } catch { /* try next */ }
  }
  console.error("playwright-core not found. Pass --pw <folder with node_modules/playwright-core>, or run `npm i -D playwright-core` in a scratch folder and point --pw at it.");
  process.exit(2);
}
const { chromium } = loadPlaywright();
let browser;
for (const channel of ["chrome", "msedge", undefined]) {
  try { browser = await chromium.launch(channel ? { channel } : {}); break; } catch { /* try next */ }
}
if (!browser) { console.error("No Chrome/Edge found for playwright-core."); process.exit(2); }

const url = pathToFileURL(html).href;
const errors = [];
let failed = false;
try {
  const ctx = await browser.newContext({ viewport: { width: 1600, height: 1000 }, deviceScaleFactor: 2 });
  const page = await ctx.newPage();
  page.on("pageerror", (e) => errors.push(String(e)));
  page.on("console", (m) => { if (m.type() === "error") errors.push(m.text()); });
  await page.goto(url);
  await page.waitForSelector("html[data-sketched='1']", { timeout: 15000 }).catch(() => errors.push("sketch script did not run (no html[data-sketched])"));
  await page.evaluate(() => document.fonts.ready);

  const issues = await page.evaluate(() => {
    const out = [];
    const band = (b) => ({ x: b.x + 1, y: b.y + b.height * 0.3, width: b.width - 2, height: b.height * 0.5 });
    const hit = (a, b) => a.x < b.x + b.width && b.x < a.x + a.width && a.y < b.y + b.height && b.y < a.y + a.height;
    document.querySelectorAll("svg.sketch").forEach((svg, si) => {
      const label = svg.querySelector("title")?.textContent?.slice(0, 30) || `svg${si}`;
      const texts = [...svg.querySelectorAll("text")].map((t) => ({ t, b: t.getBBox() })).filter((x) => x.b.width > 0);
      const shapes = [...svg.querySelectorAll("rect.sk")].map((r) => r.getBBox()).filter((b) => b.width > 40 && b.height > 30 && b.width < 1000);
      const nm = (t) => `"${t.textContent.trim().slice(0, 40)}"`;
      for (let i = 0; i < texts.length; i++)
        for (let j = i + 1; j < texts.length; j++)
          if (hit(band(texts[i].b), band(texts[j].b))) out.push(`[${label}] labels overlap ${nm(texts[i].t)} / ${nm(texts[j].t)}`);
      for (const { t, b } of texts) {
        const cx = b.x + 4, cy = b.y + b.height / 2;
        for (const r of shapes) {
          const inside = cx > r.x && cx < r.x + r.width && cy > r.y && cy < r.y + r.height;
          if (inside && (b.x + b.width > r.x + r.width - 6 || b.x < r.x + 2))
            out.push(`[${label}] ${nm(t)} too close to its box edge (${Math.round(b.x + b.width - (r.x + r.width - 6))}px over)`);
        }
      }
      const lines = [...svg.querySelectorAll("line.sk, path.sk")].filter((e) => !e.getAttribute("data-closed") && !e.getAttribute("data-cross") && !/[AZ]/.test(e.getAttribute("d") || ""));
      for (const c of lines) {
        const len = c.getTotalLength();
        for (const { t, b } of texts) {
          const g = band(b);
          for (let s = 0; s <= len; s += 3) {
            const p = c.getPointAtLength(s);
            if (p.x > g.x && p.x < g.x + g.width && p.y > g.y && p.y < g.y + g.height) { out.push(`[${label}] a line runs through ${nm(t)}`); break; }
          }
        }
      }
    });
    return out;
  });

  const hasOverview = (await page.locator("#ov").count()) > 0;
  if (hasOverview) {
    await page.addStyleTag({ content: ".layout{display:block;max-width:none;padding:0} nav.toc{display:none} #ov{width:1760px!important;min-width:1760px}" });
    await page.setViewportSize({ width: 1800, height: 1100 });
    await page.locator("#ov").screenshot({ path: path.join(outDir, `${name}-overview.png`) });
  }
  if (reviewDir) {
    fs.mkdirSync(reviewDir, { recursive: true });
    const boards = page.locator("svg.sketch");
    for (let i = 0; i < await boards.count(); i++) await boards.nth(i).screenshot({ path: path.join(reviewDir, `board-${i}.png`) });
  }

  const pdfPage = await ctx.newPage();
  await pdfPage.goto(url);
  await pdfPage.waitForSelector("html[data-sketched='1']", { timeout: 15000 }).catch(() => {});
  await pdfPage.evaluate(() => document.fonts.ready);
  await pdfPage.pdf({ path: path.join(outDir, `${name}.pdf`), preferCSSPageSize: true, printBackground: true });

  const mobile = await browser.newContext({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 2 });
  const m = await mobile.newPage();
  await m.goto(url);
  await m.waitForSelector("html[data-sketched='1']", { timeout: 15000 }).catch(() => {});
  const overflow = await m.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
  if (reviewDir) {
    await m.screenshot({ path: path.join(reviewDir, "mobile-top.png") });
    const desk = await ctx.newPage();
    await desk.setViewportSize({ width: 1440, height: 900 });
    await desk.goto(url);
    await desk.waitForSelector("html[data-sketched='1']", { timeout: 15000 }).catch(() => {});
    for (const id of await desk.evaluate(() => [...document.querySelectorAll("main > section[id]")].map((s) => s.id)))
      await desk.locator("#" + id).screenshot({ path: path.join(reviewDir, `section-${id}.png`) });
  }

  console.log(`layout issues: ${issues.length}`); issues.forEach((s) => console.log("  " + s));
  console.log(`phone-width horizontal overflow: ${overflow}px`);
  console.log(`page errors: ${errors.length}`); errors.forEach((s) => console.log("  " + s));
  for (const f of [hasOverview ? `${name}-overview.png` : null, `${name}.pdf`].filter(Boolean))
    console.log(`${f}: ${fs.statSync(path.join(outDir, f)).size} bytes`);
  failed = issues.length > 0 || overflow > 0 || errors.length > 0;
} finally {
  await browser.close();
}
process.exit(failed ? 1 : 0);
