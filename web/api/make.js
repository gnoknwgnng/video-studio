// Start a new video: validates the form, then triggers the "Make video" GitHub workflow.
const { send, readBody, requireUser, gh, OWNER, REPO, WORKFLOW } = require("../lib/core");

module.exports = async (req, res) => {
  if (req.method !== "POST") return send(res, 405, { error: "Use POST" });
  const user = requireUser(req, res); if (!user) return;
  const b = await readBody(req);
  const topic = String(b.topic || "").trim(), notes = String(b.notes || "").trim(), logo = String(b.logo || "").trim();
  if (topic.length < 4 || topic.length > 140) return send(res, 400, { error: "The topic must be 4–140 characters." });
  if (notes.length > 300) return send(res, 400, { error: "Notes must be 300 characters or less." });
  if (logo && !/^https:\/\/[^\s"'<>]+$/i.test(logo)) return send(res, 400, { error: "The logo must be an https:// image link." });
  try {
    const out = await gh(`/repos/${OWNER}/${REPO}/actions/workflows/${WORKFLOW}/dispatches`, {
      method: "POST",
      body: JSON.stringify({
        ref: "main",
        inputs: { topic, notes, logo, site_photos: b.site_photos ? "true" : "false", video: "", requested_by: user },
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
