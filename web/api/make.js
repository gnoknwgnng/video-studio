// Start a new video: validates the form, then triggers the "Make video" GitHub workflow.
const { send, readBody, requireUser, gh, OWNER, REPO, WORKFLOW } = require("../lib/core");

// allowed values for each option (anything else is ignored)
const CHOICES = {
  format: ["auto", "explainer", "listicle", "news", "story", "tutorial", "product", "comparison", "hiring", "pitch", "announcement", "motivational"],
  duration: ["short", "standard", "long"],
  tone: ["energetic", "friendly", "professional", "dramatic", "funny", "calm", "inspirational", "authoritative", "casual"],
  theme: ["light", "dark"],
  music: ["upbeat", "calm", "dramatic", "tech", "news", "none"],
  music_volume: ["low", "medium", "high"],
  voice_quality: ["natural", "fast"],
  subtitles: ["kinetic", "bold", "karaoke", "classic", "none"],
  pace: ["fast", "normal", "relaxed"],
};

module.exports = async (req, res) => {
  if (req.method !== "POST") return send(res, 405, { error: "Use POST" });
  const user = requireUser(req, res); if (!user) return;
  const b = await readBody(req);
  const topic = String(b.topic || "").trim(), notes = String(b.notes || "").trim(), logo = String(b.logo || "").trim();
  if (topic.length < 4 || topic.length > 4000) return send(res, 400, { error: "Please enter at least 4 characters." });
  if (notes.length > 4000) return send(res, 400, { error: "Notes must be 4000 characters or less." });
  if (logo && !/^https:\/\/[^\s"'<>]+$/i.test(logo)) return send(res, 400, { error: "The logo must be an https:// image link." });
  const language = String(b.language || "").trim().toLowerCase();
  if (language && !/^[a-z]{2,8}(-[a-z0-9]{2,8})?$/.test(language)) return send(res, 400, { error: "Unknown language code." });
  const voice = String(b.voice || "auto").trim();
  if (!/^(auto|female|male|[a-z]+:[A-Za-z0-9_\-]+|[A-Za-z0-9_\-]+)$/.test(voice) || voice.length > 80) return send(res, 400, { error: "Unknown voice." });
  const opts = [];
  for (const [k, allowed] of Object.entries(CHOICES)) {
    const v = String(b[k] || "").trim().toLowerCase();
    if (v && allowed.includes(v)) opts.push(`${k}=${v}`);
  }
  if (b.research === false) opts.push("research=no");
  if (b.visual === false) opts.push("visual=no");
  if (logo) opts.push(`logo=${logo}`);
  try {
    const out = await gh(`/repos/${OWNER}/${REPO}/actions/workflows/${WORKFLOW}/dispatches`, {
      method: "POST",
      body: JSON.stringify({
        ref: "main",
        inputs: { topic, notes, language, voice, options: opts.join("; "),
                  background_music: String(b.music) === "none" ? "off" : ({ low: "soft", medium: "medium", high: "loud" }[String(b.music_volume)] || "soft"),
                  site_photos: b.site_photos ? "true" : "false", video: "", requested_by: user },
        return_run_details: true,
      }),
    });
    send(res, 200, { ok: true, run_id: out && out.workflow_run_id ? out.workflow_run_id : null });
  } catch (e) {
    const hint = e.status === 401 || e.status === 403 ? " Check that GH_TOKEN is valid and has Actions: Read and write."
               : e.status === 404 ? " Check GH_OWNER/GH_REPO and that GH_TOKEN can access this repository." : "";
    send(res, 502, { error: e.message + hint });
  }
};
