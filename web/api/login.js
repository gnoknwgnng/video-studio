const { send, readBody, checkPassword, makeSession, sessionCookie } = require("../lib/core");

module.exports = async (req, res) => {
  if (req.method !== "POST") return send(res, 405, { error: "Use POST" });
  const { username, password } = await readBody(req);
  if (!username || !password || String(username).length > 64 || String(password).length > 200)
    return send(res, 400, { error: "Enter your username and password." });
  try {
    if (!checkPassword(username, password)) {
      await new Promise((r) => setTimeout(r, 600));   // slow down password guessing
      return send(res, 401, { error: "Wrong username or password." });
    }
    const name = String(username).toLowerCase();
    send(res, 200, { user: name }, { "Set-Cookie": sessionCookie(makeSession(name), 7 * 86400) });
  } catch (e) {
    send(res, 500, { error: "Login is not configured: " + e.message });
  }
};
