async function dispatch(env) {
  const url = `https://api.github.com/repos/${env.GITHUB_REPO}/actions/workflows/${env.WORKFLOW_FILE}/dispatches`;
  const res = await fetch(url, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${env.GITHUB_TOKEN}`,
      Accept: "application/vnd.github+json",
      "Content-Type": "application/json",
      // GitHub rejects API requests without a User-Agent.
      "User-Agent": "jobhunt-trigger",
      "X-GitHub-Api-Version": "2022-11-28",
    },
    body: JSON.stringify({ ref: env.GITHUB_REF }),
  });
  if (res.status !== 204) {
    throw new Error(`Workflow dispatch failed: ${res.status} ${await res.text()}`);
  }
}

export default {
  async scheduled(controller, env, ctx) {
    await dispatch(env);
  },
};
