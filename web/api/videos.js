// Finished videos = GitHub Releases that contain an MP4.
const { send, requireUser, gh, OWNER, REPO } = require("../lib/core");

module.exports = async (req, res) => {
  if (!requireUser(req, res)) return;
  try {
    const rel = await gh(`/repos/${OWNER}/${REPO}/releases?per_page=50`);
    const videos = (rel || []).map((r) => {
      const mp4s = (r.assets || []).filter((x) => x.name.endsWith(".mp4"));
      const a = mp4s.find((x) => !/-(16x9|1x1|4x5)\.mp4$/.test(x.name)) || mp4s[0];
      if (!a) return null;
      const srt = (r.assets || []).find((x) => x.name.endsWith(".srt"));
      const jpg = (r.assets || []).find((x) => x.name.endsWith(".jpg") && !x.name.endsWith("-youtube.jpg"));
      const yt = (r.assets || []).find((x) => x.name.endsWith("-youtube.jpg"));
      const extra = mp4s.filter((x) => x !== a).map((x) => ({ label: (x.name.match(/-(16x9|1x1|4x5)\.mp4$/) || [, "other"])[1].replace("x", ":"), url: x.browser_download_url }));
      const credits = String(r.body || "").split("Image credits:")[1] || "";
      return { title: r.name || r.tag_name, tag: r.tag_name, date: r.published_at, url: a.browser_download_url,
               size: a.size, page: r.html_url, srt: srt ? srt.browser_download_url : null, poster: jpg ? jpg.browser_download_url : null, youtube: yt ? yt.browser_download_url : null, extra, credits: credits.trim().split("\n").filter(Boolean).slice(0, 12) };
    }).filter(Boolean);
    send(res, 200, { videos });
  } catch (e) { send(res, 502, { error: e.message }); }
};
