// Phone-size, full-page screenshot of a website, used by the "website" scrolling scene.
//   node engine/capture_site.cjs https://vcfriend.online out.png [chromePath]
// Prints one JSON line: {"ok":true,"width":780,"height":8400} or {"ok":false,"error":"..."}
const puppeteer = require("puppeteer-core");
const { execSync } = require("child_process");

const [url, out, chromeArg] = process.argv.slice(2);
const MAX_CSS_HEIGHT = 4200;            // about 5 phone screens: enough for a scroll, keeps the file small
const done = (o) => { console.log(JSON.stringify(o)); process.exit(o.ok ? 0 : 1); };
if (!url || !out) done({ ok: false, error: "usage: capture_site.cjs URL OUT.png [chromePath]" });

(async () => {
  let browser;
  const timer = setTimeout(() => done({ ok: false, error: "timed out" }), 75000);
  try {
    const exe = chromeArg || execSync("npx hyperframes browser path", { encoding: "utf8" }).trim().split("\n").pop();
    browser = await puppeteer.launch({ executablePath: exe, headless: true, args: ["--no-sandbox", "--disable-dev-shm-usage", "--hide-scrollbars"] });
    const page = await browser.newPage();
    await page.setUserAgent("Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1");
    await page.setViewport({ width: 390, height: 844, deviceScaleFactor: 2, isMobile: true, hasTouch: true });
    const resp = await page.goto(url, { waitUntil: "networkidle2", timeout: 40000 }).catch(() => null);
    if (resp && resp.status() >= 400) done({ ok: false, error: `site answered ${resp.status()}` });
    await new Promise((r) => setTimeout(r, 1500));

    // close common cookie / consent / newsletter popups
    await page.evaluate(() => {
      const words = /^(accept( all)?|agree|i agree|allow( all)?|got it|ok(ay)?|continue|close|no thanks|dismiss|×|✕)$/i;
      for (const el of document.querySelectorAll("button, a, [role=button]")) {
        const t = (el.innerText || el.getAttribute("aria-label") || "").trim();
        if (t.length < 20 && words.test(t)) { try { el.click(); } catch {} }
      }
    }).catch(() => {});
    await new Promise((r) => setTimeout(r, 600));

    // scroll down slowly so lazy-loaded images appear, then back to the top
    await page.evaluate(async (max) => {
      for (let y = 0; y < Math.min(document.body.scrollHeight, max); y += 400) { window.scrollTo(0, y); await new Promise((r) => setTimeout(r, 180)); }
      window.scrollTo(0, 0);
    }, MAX_CSS_HEIGHT).catch(() => {});
    await new Promise((r) => setTimeout(r, 1200));

    const text = await page.evaluate(() => (document.body.innerText || "").trim()).catch(() => "");
    if (text.length < 80) done({ ok: false, error: "page looks empty, blocked or behind a login" });
    if (/captcha|are you a robot|verify you are (a )?human|continue shopping|access denied|unusual traffic|enable javascript|checking your browser/i.test(text.slice(0, 600)))
      done({ ok: false, error: "the site showed a bot check instead of its page" });
    const h = await page.evaluate(() => Math.max(document.body.scrollHeight, document.documentElement.scrollHeight)).catch(() => 844);
    if (h < 1200) done({ ok: false, error: "page is too short to scroll" });
    const height = Math.min(h, MAX_CSS_HEIGHT);
    await page.screenshot({ path: out, clip: { x: 0, y: 0, width: 390, height }, captureBeyondViewport: true });
    clearTimeout(timer);
    await browser.close();
    done({ ok: true, width: 780, height: height * 2 });
  } catch (e) {
    try { if (browser) await browser.close(); } catch {}
    done({ ok: false, error: String(e.message || e).slice(0, 200) });
  }
})();
