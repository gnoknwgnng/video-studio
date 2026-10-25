// Shared server code for the Video Studio web app (runs on Vercel serverless functions).
// Secrets come only from environment variables set in Vercel: GH_TOKEN, USERS, SESSION_SECRET.
const crypto = require("crypto");

const OWNER = process.env.GH_OWNER || "gnoknwgnng";
const REPO = process.env.GH_REPO || "video-studio";
const WORKFLOW = "make-video.yml";
const GH_API = process.env.GH_API || "https://api.github.com";
const SESSION_DAYS = 7;

// ---------- HTTP helpers (plain Node, so the same code runs on Vercel and locally) ----------
function send(res, status, data, headers = {}) {
  res.statusCode = status;
  res.setHeader("Content-Type", "application/json; charset=utf-8");
  res.setHeader("Cache-Control", "no-store");
  for (const [k, v] of Object.entries(headers)) res.setHeader(k, v);
  res.end(JSON.stringify(data));
}

async function readBody(req) {
  if (req.body && typeof req.body === "object") return req.body;          // Vercel already parsed it
  if (typeof req.body === "string") { try { return JSON.parse(req.body); } catch { return {}; } }
  const chunks = []; let size = 0;
  for await (const c of req) { size += c.length; if (size > 20000) break; chunks.push(c); }
  try { return JSON.parse(Buffer.concat(chunks).toString("utf8") || "{}"); } catch { return {}; }
}

function cookies(req) {
  const out = {};
  for (const part of String(req.headers.cookie || "").split(";")) {
    const i = part.indexOf("="); if (i > 0) out[part.slice(0, i).trim()] = decodeURIComponent(part.slice(i + 1).trim());
  }
  return out;
}

// ---------- passwords: scrypt hashes stored in the USERS env var ----------
// USERS = "aviral:SALT:HASH,friend:SALT:HASH"   (make entries with: node web/tools/add-user.js NAME PASSWORD)
function users() {
  const map = {};
  for (const entry of String(process.env.USERS || "").split(/[,\n]/)) {
    const [name, salt, hash] = entry.trim().split(":");
    if (name && salt && hash) map[name.toLowerCase()] = { salt, hash };
  }
  return map;
}

function hashPassword(password, salt = crypto.randomBytes(16).toString("hex")) {
  const hash = crypto.scryptSync(String(password), salt, 32).toString("hex");
  return { salt, hash };
}

function checkPassword(username, password) {
  const u = users()[String(username || "").toLowerCase()];
  // always run scrypt so a wrong username takes as long as a wrong password
  const { hash } = hashPassword(password, u ? u.salt : "0".repeat(32));
  if (!u) return false;
  const a = Buffer.from(hash, "hex"), b = Buffer.from(u.hash, "hex");
  return a.length === b.length && crypto.timingSafeEqual(a, b);
}

// ---------- sessions: signed cookie (no database needed) ----------
function secret() {
  const s = process.env.SESSION_SECRET;
  if (!s || s.length < 32) throw new Error("SESSION_SECRET is missing or shorter than 32 characters");
  return s;
}
const b64 = (s) => Buffer.from(s).toString("base64url");
const sign = (data) => crypto.createHmac("sha256", secret()).update(data).digest("base64url");

function makeSession(username) {
  const payload = b64(JSON.stringify({ u: username, exp: Date.now() + SESSION_DAYS * 864e5 }));
  return `${payload}.${sign(payload)}`;
}

function sessionCookie(value, maxAgeSec) {
  const secure = process.env.LOCAL_DEV ? "" : " Secure;";
  return `vs_session=${value}; Path=/; HttpOnly;${secure} SameSite=Lax; Max-Age=${maxAgeSec}`;
}

function currentUser(req) {
  const raw = cookies(req).vs_session; if (!raw) return null;
  const [payload, sig] = raw.split(".");
  if (!payload || !sig) return null;
  const good = sign(payload);
  if (sig.length !== good.length || !crypto.timingSafeEqual(Buffer.from(sig), Buffer.from(good))) return null;
  try {
    const data = JSON.parse(Buffer.from(payload, "base64url").toString("utf8"));
    if (!data.u || data.exp < Date.now() || !users()[String(data.u).toLowerCase()]) return null;
    return data.u;
  } catch { return null; }
}

function requireUser(req, res) {
  const u = currentUser(req);
  if (!u) { send(res, 401, { error: "Please log in." }); return null; }
  return u;
}

// ---------- GitHub ----------
async function gh(path, opts = {}) {
  if (!process.env.GH_TOKEN) throw new Error("GH_TOKEN is not set in Vercel environment variables");
  const r = await fetch(GH_API + path, {
    ...opts,
    headers: { Authorization: `Bearer ${process.env.GH_TOKEN}`, Accept: "application/vnd.github+json",
               "X-GitHub-Api-Version": "2022-11-28", "User-Agent": "video-studio-web", ...(opts.headers || {}) },
  });
  const text = await r.text();
  let data = null; try { data = text ? JSON.parse(text) : null; } catch { data = text; }
  if (!r.ok) {
    const msg = (data && data.message) || text || r.statusText;
    const err = new Error(`GitHub ${r.status}: ${msg}`); err.status = r.status; throw err;
  }
  return data;
}

module.exports = { OWNER, REPO, WORKFLOW, send, readBody, hashPassword, checkPassword, makeSession,
                   sessionCookie, currentUser, requireUser, gh };
