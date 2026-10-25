// Local test server: serves index.html and the /api functions exactly like Vercel does.
//   LOCAL_DEV=1 GH_TOKEN=... USERS=... SESSION_SECRET=... node web/dev-server.js   -> http://localhost:3000
const http = require("http"), fs = require("fs"), path = require("path");
const PORT = process.env.PORT || 3000;
http.createServer(async (req, res) => {
  const url = new URL(req.url, "http://x");
  const m = url.pathname.match(/^\/api\/([a-z]+)$/);
  if (m && fs.existsSync(path.join(__dirname, "api", m[1] + ".js"))) {
    try { await require("./api/" + m[1] + ".js")(req, res); }
    catch (e) { res.statusCode = 500; res.end(JSON.stringify({ error: e.message })); }
    return;
  }
  res.setHeader("Content-Type", "text/html; charset=utf-8");
  res.end(fs.readFileSync(path.join(__dirname, "index.html")));
}).listen(PORT, () => console.log(`Video Studio web on http://localhost:${PORT}`));
