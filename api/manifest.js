const backend = () =>
  String(process.env.RESONANT_BACKEND_URL || "")
    .trim()
    .replace(/\/+$/, "");

module.exports = async function handler(req, res) {
  if (!["GET", "HEAD"].includes(req.method || "GET")) {
    res.setHeader("Allow", "GET, HEAD");
    return res.status(405).json({ error: "method not allowed" });
  }

  const base = backend();
  if (!base) {
    return res.status(503).json({
      error: "RESONANT_BACKEND_URL is not configured"
    });
  }

  try {
    const upstream = await fetch(`${base}/field/v1/manifest`, {
      method: req.method,
      headers: {
        accept: "application/json",
        "ngrok-skip-browser-warning": "1",
        "user-agent": "RESONANT/1.0"
      },
      redirect: "follow",
      signal: AbortSignal.timeout(20000)
    });

    const body = Buffer.from(await upstream.arrayBuffer());
    res.status(upstream.status);
    res.setHeader(
      "Content-Type",
      upstream.headers.get("content-type") ||
        "application/json; charset=utf-8"
    );
    res.setHeader("Cache-Control", "no-store");

    if (req.method === "HEAD") return res.end();
    return res.send(body);
  } catch (error) {
    return res.status(502).json({
      error: "RESONANT property manifest is unreachable",
      detail: error instanceof Error ? error.message : String(error)
    });
  }
};
