// Screenshot an HTML file at an exact size (used for the designed cover images).
//   node engine/cover.cjs page.html out.jpg 1080 1920 [chromePath]
const puppeteer = require("puppeteer-core");
const { execSync } = require("child_process");
const path = require("path");

const [html, out, w, h, chromeArg] = process.argv.slice(2);
(async () => {
  const exe = chromeArg || process.env.HYPERFRAMES_BROWSER_PATH ||
    execSync("npx hyperframes browser path", { encoding: "utf8" }).trim().split("\n").pop();
  const browser = await puppeteer.launch({ executablePath: exe, headless: true, args: ["--no-sandbox", "--disable-dev-shm-usage", "--allow-file-access-from-files"] });
  try {
    const page = await browser.newPage();
    await page.setViewport({ width: +w, height: +h, deviceScaleFactor: 1 });
    await page.goto("file://" + path.resolve(html), { waitUntil: "networkidle0", timeout: 60000 });
    await page.evaluate(async () => { if (document.fonts) await document.fonts.ready; if (window.fitAll) window.fitAll(); });
    await new Promise((r) => setTimeout(r, 300));
    await page.screenshot({ path: out, type: out.endsWith(".png") ? "png" : "jpeg", quality: out.endsWith(".png") ? undefined : 90 });
    console.log(JSON.stringify({ ok: true }));
  } catch (e) {
    console.log(JSON.stringify({ ok: false, error: String(e.message || e) }));
    process.exitCode = 1;
  } finally { await browser.close(); }
})();
