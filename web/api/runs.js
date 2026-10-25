// Recent video runs with live step-by-step progress for the ones still running.
const { send, requireUser, gh, OWNER, REPO, WORKFLOW } = require("../lib/core");

const FRIENDLY = [
  [/write the script/i, "Writing the script with AI"], [/make the video/i, "Recording voice & rendering"],
  [/install|restore|cache|set up|checkout|use /i, "Preparing the machine"], [/save script/i, "Saving"],
  [/upload/i, "Uploading"], [/publish/i, "Publishing"],
];
const friendly = (name) => (FRIENDLY.find(([re]) => re.test(name)) || [null, name])[1];

module.exports = async (req, res) => {
  if (!requireUser(req, res)) return;
  try {
    const data = await gh(`/repos/${OWNER}/${REPO}/actions/workflows/${WORKFLOW}/runs?per_page=12`);
    const runs = await Promise.all((data.workflow_runs || []).map(async (r, i) => {
      const run = { id: r.id, title: r.display_title, status: r.status, conclusion: r.conclusion,
                    created: r.created_at, updated: r.updated_at, url: r.html_url, event: r.event };
      if (r.status !== "completed" && i < 4) {
        try {
          const jobs = await gh(`/repos/${OWNER}/${REPO}/actions/runs/${r.id}/jobs`);
          const job = (jobs.jobs || []).find((j) => j.name.startsWith("render")) || (jobs.jobs || [])[0];
          const steps = (job && job.steps) || [];
          const done = steps.filter((s) => s.status === "completed").length;
          const cur = steps.find((s) => s.status === "in_progress");
          run.progress = steps.length ? Math.round((done / steps.length) * 100) : 3;
          run.step = cur ? friendly(cur.name) : (job ? "Starting…" : "Waiting for a machine…");
        } catch { run.step = "Starting…"; run.progress = 3; }
      }
      return run;
    }));
    send(res, 200, { runs });
  } catch (e) { send(res, 502, { error: e.message }); }
};
