const backend = () =>
  String(process.env.RESONANT_BACKEND_URL || "")
    .trim()
    .replace(/\/+$/, "");

module.exports = async function handler(req, res) {
  if (req.method !== "POST") {
    res.setHeader("Allow", "POST");
    return res.status(405).json({ error: "method not allowed" });
  }

  const base = backend();
  if (!base) {
    return res.status(503).json({
      error: "RESONANT_BACKEND_URL is not configured"
    });
  }

  let payload = req.body;
  if (typeof payload === "string") {
    try {
      payload = JSON.parse(payload);
    } catch {
      return res.status(400).json({ error: "invalid JSON body" });
    }
  }

  const text = String(payload?.text || "").trim();
  const k = Math.max(1, Math.min(128, Number(payload?.k || 24)));

  if (!text) {
    return res.status(400).json({ error: "text is required" });
  }

  try {
    const upstream = await fetch(`${base}/field/v1/search`, {
      method: "POST",
      headers: {
        accept: "application/json",
        "content-type": "application/json",
        "ngrok-skip-browser-warning": "1",
        "user-agent": "RESONANT/1.0"
      },
      body: JSON.stringify({ text, k }),
      redirect: "follow",
      signal: AbortSignal.timeout(55000)
    });

    const body = Buffer.from(await upstream.arrayBuffer());
    res.status(upstream.status);
    res.setHeader(
      "Content-Type",
      upstream.headers.get("content-type") ||
        "application/json; charset=utf-8"
    );
    res.setHeader("Cache-Control", "no-store");
    return res.send(body);
  } catch (error) {
    return res.status(502).json({
      error: "RESONANT property search is unreachable",
      detail: error instanceof Error ? error.message : String(error)
    });
  }
};
