// Local test server: serves index.html, the voice samples and the /api functions exactly like Vercel does.
//   LOCAL_DEV=1 GH_TOKEN=... USERS=... SESSION_SECRET=... node web/dev-server.js   -> http://localhost:3000
const http = require("http"), fs = require("fs"), path = require("path");
const PORT = process.env.PORT || 3000;
const TYPES = { ".json": "application/json", ".mp3": "audio/mpeg", ".html": "text/html; charset=utf-8" };
http.createServer(async (req, res) => {
  const url = new URL(req.url, "http://x");
  const m = url.pathname.match(/^\/api\/([a-z]+)$/);
  if (m && fs.existsSync(path.join(__dirname, "api", m[1] + ".js"))) {
    try { await require("./api/" + m[1] + ".js")(req, res); }
    catch (e) { res.statusCode = 500; res.end(JSON.stringify({ error: e.message })); }
    return;
  }
  const v = url.pathname.match(/^\/voices\/([\w.\-]+)$/);
  if (v && fs.existsSync(path.join(__dirname, "voices", v[1]))) {
    res.setHeader("Content-Type", TYPES[path.extname(v[1])] || "application/octet-stream");
    return fs.createReadStream(path.join(__dirname, "voices", v[1])).pipe(res);
  }
  res.setHeader("Content-Type", "text/html; charset=utf-8");
  res.end(fs.readFileSync(path.join(__dirname, "index.html")));
}).listen(PORT, () => console.log(`Video Studio web on http://localhost:${PORT}`));
