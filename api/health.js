module.exports = async function handler(req, res) {
  const base = String(process.env.RESONANT_BACKEND_URL || "")
    .trim()
    .replace(/\/+$/, "");

  if (!base) {
    return res.status(503).json({
      ok: false,
      routes: true,
      error: "RESONANT_BACKEND_URL is not configured"
    });
  }

  try {
    const upstream = await fetch(`${base}/field/v1/manifest`, {
      headers: {
        accept: "application/json",
        "ngrok-skip-browser-warning": "1",
        "user-agent": "RESONANT/1.0"
      },
      signal: AbortSignal.timeout(20000)
    });

    const body = await upstream.json();

    return res.status(upstream.ok ? 200 : 502).json({
      ok: upstream.ok,
      routes: true,
      backend: upstream.ok,
      backend_url: base,
      count: Number(body.count || body.total_records || 0),
      build: "github-push-and-env-deploy-20260721"
    });
  } catch (error) {
    return res.status(502).json({
      ok: false,
      routes: true,
      backend: false,
      backend_url: base,
      error: error instanceof Error ? error.message : String(error)
    });
  }
};
