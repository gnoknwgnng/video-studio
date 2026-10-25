const { send, sessionCookie } = require("../lib/core");
module.exports = async (req, res) => send(res, 200, { ok: true }, { "Set-Cookie": sessionCookie("", 0) });
