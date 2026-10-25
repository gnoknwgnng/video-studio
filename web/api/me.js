const { send, currentUser, OWNER, REPO } = require("../lib/core");
module.exports = async (req, res) => {
  let user = null; try { user = currentUser(req); } catch {}
  send(res, 200, { user, repo: `${OWNER}/${REPO}` });
};
