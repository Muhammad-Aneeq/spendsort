/**
 * Records the SpendSort demo video (Playwright + Chromium).
 *
 *   node demo/record-demo.mjs   (from frontend/)                 # against http://127.0.0.1:8123
 *   BASE_URL=http://localhost:5173 node demo/record-demo.mjs   (from frontend/)
 *
 * Prerequisites: the API running with the built SPA mounted, and the database already holding
 * two completed runs (see demo/README.md). It uploads a small third month and runs it live, so
 * the categorization on screen is real rather than staged.
 *
 * Design notes, because a LinkedIn video has constraints a UI does not:
 *   • **It autoplays muted.** Every beat therefore carries a burnt-in caption; nothing relies
 *     on narration.
 *   • **It plays small.** Captions are large, and the camera zooms into the one element that
 *     matters rather than showing a whole page of 12px type.
 *   • **Playwright renders no cursor.** A synthetic pointer is injected so clicks read as
 *     deliberate actions instead of things that just happen.
 */

import { existsSync, mkdirSync, readdirSync, renameSync, rmSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { chromium } from "@playwright/test";

const HERE = dirname(fileURLToPath(import.meta.url));
const ROOT = resolve(HERE, "..", "..");
const BASE_URL = process.env.BASE_URL ?? "http://127.0.0.1:8123";
const OUT_DIR = join(ROOT, "demo", "output");
const RAW_DIR = join(OUT_DIR, "raw");
const CSV = join(ROOT, "examples", "month_03_demo_small_seed44.csv");

const WIDTH = 1280;
const HEIGHT = 720;

// ---------------------------------------------------------------- utilities

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

/** Caption + cursor chrome, injected once per page load. */
const OVERLAY_CSS = `
#demo-caption {
  position: fixed; left: 0; right: 0; bottom: 0; z-index: 2147483646;
  display: flex; flex-direction: column; gap: 4px; align-items: center;
  padding: 18px 32px 26px;
  background: linear-gradient(to top, rgba(26,22,20,.93) 55%, rgba(26,22,20,0));
  font-family: "Space Grotesk", Inter, system-ui, sans-serif;
  opacity: 0; transition: opacity .35s ease; pointer-events: none;
}
#demo-caption.on { opacity: 1; }
#demo-caption b { font-size: 30px; font-weight: 700; color: #fff; letter-spacing: -.02em;
  text-align: center; line-height: 1.15; }
#demo-caption i { font-size: 17px; font-style: normal; color: #ffd9a8; text-align: center; }
#demo-cursor {
  position: fixed; z-index: 2147483647; width: 22px; height: 22px; margin: -11px 0 0 -11px;
  border-radius: 50%; background: rgba(13,148,136,.32); border: 2px solid #0d9488;
  pointer-events: none; transition: transform .45s cubic-bezier(.22,1,.36,1), opacity .2s;
  opacity: 0;
}
#demo-cursor.on { opacity: 1; }
#demo-cursor.tap { background: rgba(234,88,12,.55); border-color: #ea580c; }
#demo-title {
  position: fixed; inset: 0; z-index: 2147483645; display: flex; flex-direction: column;
  align-items: center; justify-content: center; gap: 18px; background: #14100e;
  font-family: "Space Grotesk", Inter, system-ui, sans-serif; text-align: center;
  opacity: 0; transition: opacity .5s ease; pointer-events: none; padding: 0 80px;
}
#demo-title.on { opacity: 1; }
#demo-title .h { font-size: 58px; font-weight: 700; color: #fff; letter-spacing: -.03em; }
#demo-title .s { font-size: 25px; color: #5eead4; font-weight: 500; }
#demo-title .t { font-size: 17px; color: #a8a29e; margin-top: 10px; }
`;

const OVERLAY_JS = `
(() => {
  if (document.getElementById('demo-caption')) return;
  const style = document.createElement('style');
  style.textContent = ${JSON.stringify(OVERLAY_CSS)};
  document.head.appendChild(style);

  const cap = document.createElement('div');
  cap.id = 'demo-caption';
  cap.innerHTML = '<b></b><i></i>';
  document.body.appendChild(cap);

  const cur = document.createElement('div');
  cur.id = 'demo-cursor';
  document.body.appendChild(cur);

  const title = document.createElement('div');
  title.id = 'demo-title';
  title.innerHTML = '<div class="h"></div><div class="s"></div><div class="t"></div>';
  document.body.appendChild(title);

  window.__demo = {
    caption(main, sub) {
      cap.querySelector('b').textContent = main || '';
      cap.querySelector('i').textContent = sub || '';
      cap.classList.toggle('on', Boolean(main));
    },
    cursor(x, y, tap) {
      cur.classList.add('on');
      cur.classList.toggle('tap', Boolean(tap));
      cur.style.transform = 'translate(' + x + 'px,' + y + 'px)';
    },
    hideCursor() { cur.classList.remove('on'); },
    title(h, s, t) {
      title.querySelector('.h').textContent = h || '';
      title.querySelector('.s').textContent = s || '';
      title.querySelector('.t').textContent = t || '';
      title.classList.toggle('on', Boolean(h));
    },
  };
})();
`;

async function install(page) {
  await page.evaluate(OVERLAY_JS);
}

async function caption(page, main, sub = "") {
  await page.evaluate(([m, s]) => window.__demo?.caption(m, s), [main, sub]);
}

async function titleCard(page, h, s = "", t = "") {
  await page.evaluate(([a, b, c]) => window.__demo?.title(a, b, c), [h, s, t]);
}

/** Move the synthetic pointer to an element, then click it. */
async function point(page, locator, { tap = true, settle = 650 } = {}) {
  await locator.scrollIntoViewIfNeeded();
  await sleep(250);
  const box = await locator.boundingBox();
  if (!box) throw new Error("element has no box; cannot point at it");
  const x = Math.round(box.x + box.width / 2);
  const y = Math.round(box.y + box.height / 2);
  await page.evaluate(([px, py]) => window.__demo?.cursor(px, py, false), [x, y]);
  await sleep(settle);
  if (tap) {
    await page.evaluate(([px, py]) => window.__demo?.cursor(px, py, true), [x, y]);
    await sleep(220);
  }
  return { x, y };
}

async function clickIt(page, locator, opts) {
  await point(page, locator, opts);
  await locator.click();
  await sleep(200);
  await page.evaluate(() => window.__demo?.cursor(-99, -99, false));
}

async function scrollTo(page, y) {
  await page.evaluate((top) => window.scrollTo({ top, behavior: "smooth" }), y);
  await sleep(900);
}

/** Wait until Recharts has actually painted, so the camera never lands on an empty panel. */
async function waitForCharts(page, count = 1) {
  await page
    .waitForFunction(
      (n) => document.querySelectorAll(".recharts-surface").length >= n,
      count,
      { timeout: 15000 },
    )
    .catch(() => {});
  await sleep(700); // let the line/bar transitions settle
}

/** Briefly ring an element so the eye lands on it. */
async function spotlight(page, locator, ms = 1800) {
  await locator.scrollIntoViewIfNeeded();
  await sleep(300);
  await locator.evaluate((el) => {
    el.dataset.demoPrev = el.style.cssText;
    el.style.outline = "3px solid #0d9488";
    el.style.outlineOffset = "5px";
    el.style.borderRadius = "12px";
    el.style.transition = "outline-color .3s";
  });
  await sleep(ms);
  await locator.evaluate((el) => {
    el.style.cssText = el.dataset.demoPrev ?? "";
  });
}

// ---------------------------------------------------------------- the script

async function main() {
  if (!existsSync(CSV)) throw new Error(`missing demo CSV: ${CSV}\nRun: make seed`);

  rmSync(RAW_DIR, { recursive: true, force: true });
  mkdirSync(RAW_DIR, { recursive: true });

  const browser = await chromium.launch({ args: ["--force-color-profile=srgb"] });
  const context = await browser.newContext({
    viewport: { width: WIDTH, height: HEIGHT },
    recordVideo: { dir: RAW_DIR, size: { width: WIDTH, height: HEIGHT } },
    deviceScaleFactor: 1,
    reducedMotion: "no-preference",
  });
  const page = await context.newPage();

  // Re-inject the overlay after any client-side navigation that remounts the body.
  page.on("framenavigated", async () => {
    try {
      await install(page);
    } catch {
      /* page may be mid-navigation */
    }
  });

  await page.goto(BASE_URL, { waitUntil: "networkidle" });
  await install(page);

  // ---- 1 · title card -----------------------------------------------------
  await titleCard(
    page,
    "SpendSort",
    "An expense agent that knows when it isn’t sure",
    "LangGraph · 4 nodes · gpt-5.6-luna · all data synthetic",
  );
  await sleep(3800);
  await titleCard(page, "");
  await sleep(700);

  // ---- 2 · the chart of accounts -----------------------------------------
  await caption(page, "Every transaction lands in a real chart of accounts", "20 expense accounts, editable YAML");
  await scrollTo(page, 420);
  await sleep(1800);
  await scrollTo(page, 0);

  // ---- 3 · upload ---------------------------------------------------------
  await caption(page, "Upload a month of card transactions", "Messy bank descriptors, mixed date formats");
  await sleep(1400);
  await page.setInputFiles('input[type="file"]', CSV);
  await page.waitForSelector("text=accepted", { timeout: 20000 });
  await sleep(1500);

  const acceptedRow = page.locator("text=/\\d+ awaiting categorization/").first();
  if (await acceptedRow.count()) await spotlight(page, acceptedRow, 1500);

  // ---- 4 · run it, live ---------------------------------------------------
  const runBtn = page.getByRole("button", { name: /Categorize \d+ transactions/ });
  await caption(page, "Now categorize them", "A live model call per unseen vendor — nothing staged");
  await clickIt(page, runBtn);
  await caption(page, "Running against gpt-5.6-luna…", "Vendors it already knows cost nothing at all");

  // The run is genuinely live; wait for the queue badge or navigate when it settles.
  await sleep(1000);
  await page.waitForFunction(
    () => !document.body.innerText.includes("Categorizing…"),
    null,
    { timeout: 180000 },
  );
  await sleep(1200);

  // ---- 5 · the confidence gate -------------------------------------------
  await caption(page, "");
  await clickIt(page, page.getByRole("link", { name: /^Run$/ }));
  await waitForCharts(page, 1);
  await caption(page, "Every decision carries a confidence", "At or above 0.85 it posts with no human");
  await scrollTo(page, 520);
  await sleep(3200);
  await caption(page, "The dashed line is the gate", "Bars to its right were applied unattended");
  await sleep(2600);

  // ---- 6 · the review queue ----------------------------------------------
  await scrollTo(page, 0);
  await caption(page, "");
  await clickIt(page, page.getByRole("link", { name: /Review queue/ }));
  await page.waitForSelector("ul > li", { timeout: 15000 }).catch(() => {});
  await sleep(900);
  await caption(page, "Everything else waits for a human", "Sorted least-confident first");
  await sleep(2400);

  const firstRow = page.locator("ul > li").first();
  if (await firstRow.count()) {
    await caption(page, "It says what it thought, and why", "Vendor, amount, account, confidence, reason");
    await spotlight(page, firstRow, 3000);
  }

  // ---- 7 · override → learned --------------------------------------------
  const overrideBtn = page.getByRole("button", { name: /^Override$/ }).first();
  if (await overrideBtn.count()) {
    await caption(page, "Correct it once", "");
    await clickIt(page, overrideBtn);
    await sleep(800);

    const picker = page.locator("select").first();
    await point(page, picker, { tap: true });
    await picker.selectOption({ index: 3 });
    await sleep(1600);

    await caption(page, "…and it never asks again", "The override is written to vendor memory as ‘human’");
    const flash = page.locator("text=/Learned:/").first();
    if (await flash.count()) await spotlight(page, flash, 3000);
    else await sleep(2600);
  }

  // ---- 8 · memory ---------------------------------------------------------
  await caption(page, "");
  await clickIt(page, page.getByRole("link", { name: /^Memory$/ }));
  await page.waitForSelector("table", { timeout: 15000 }).catch(() => {});
  await sleep(900);
  await caption(page, "That correction is permanent", "Next month this vendor costs nothing");
  await sleep(2800);
  await scrollTo(page, 300);
  await sleep(2200);

  // ---- 9 · THE BEND -------------------------------------------------------
  await scrollTo(page, 0);
  await caption(page, "");
  await clickIt(page, page.getByRole("link", { name: /^Metrics$/ }));
  await waitForCharts(page, 2);
  await caption(page, "And here is the whole point", "");
  await sleep(1600);

  await scrollTo(page, 330);
  await waitForCharts(page, 2);
  await caption(page, "The agent gets cheaper every month", "Memory covers more of each run, so the model is called less");
  await sleep(4200);

  const bendNote = page.locator("text=/cheaper/").first();
  if (await bendNote.count()) await spotlight(page, bendNote, 3600);

  await caption(page, "Memory-hit rate up. Cost per run down.", "Two panels, not one dual-axis chart — no invented crossover");
  await sleep(3000);

  // ---- 10 · export --------------------------------------------------------
  // Spotlight the button itself rather than scrolling to a guessed offset: the first take
  // captioned "export" over a table whose Export button had already scrolled off screen.
  await caption(page, "Export the categorized ledger", "Per line: account, confidence, source, reason");
  const exportBtn = page.getByRole("button", { name: /Export CSV/ }).first();
  if (await exportBtn.count()) {
    await point(page, exportBtn, { tap: false, settle: 900 });
    await spotlight(page, exportBtn, 2600);
  } else {
    await sleep(2600);
  }
  await page.evaluate(() => window.__demo?.hideCursor());
  await sleep(600);

  // ---- 11 · close ---------------------------------------------------------
  await caption(page, "");
  await titleCard(
    page,
    "Confidence → gate → learn",
    "The simplest honest finance agent",
    "100% auto-precision on 100 eval cases · every wrong answer queued, not posted",
  );
  await sleep(4200);
  await titleCard(page, "");
  await sleep(600);

  // ---- save ---------------------------------------------------------------
  await context.close();
  await browser.close();

  const files = readdirSync(RAW_DIR).filter((f) => f.endsWith(".webm"));
  if (!files.length) throw new Error("Playwright produced no video file");
  const finalPath = join(OUT_DIR, "spendsort-demo.webm");
  rmSync(finalPath, { force: true });
  renameSync(join(RAW_DIR, files[0]), finalPath);
  rmSync(RAW_DIR, { recursive: true, force: true });

  console.log(`\n  video: ${finalPath}`);
}

main().catch((err) => {
  console.error("\nRECORDING FAILED:", err.message);
  process.exit(1);
});
