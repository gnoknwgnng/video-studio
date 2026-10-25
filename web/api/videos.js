// Finished videos = GitHub Releases that contain an MP4.
const { send, requireUser, gh, OWNER, REPO } = require("../lib/core");

module.exports = async (req, res) => {
  if (!requireUser(req, res)) return;
  try {
    const rel = await gh(`/repos/${OWNER}/${REPO}/releases?per_page=50`);
    const videos = (rel || []).map((r) => {
      const a = (r.assets || []).find((x) => x.name.endsWith(".mp4"));
      if (!a) return null;
      const credits = String(r.body || "").split("Image credits:")[1] || "";
      return { title: r.name || r.tag_name, tag: r.tag_name, date: r.published_at, url: a.browser_download_url,
               size: a.size, page: r.html_url, credits: credits.trim().split("\n").filter(Boolean).slice(0, 12) };
    }).filter(Boolean);
    send(res, 200, { videos });
  } catch (e) { send(res, 502, { error: e.message }); }
};
