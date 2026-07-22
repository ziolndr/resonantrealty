const {
  RESONANT_BACKEND
} = require("../lib/resonant-backend");

module.exports = async function handler(req, res) {
  if (!["GET", "HEAD"].includes(req.method || "GET")) {
    res.setHeader("Allow", "GET, HEAD");
    return res.status(405).json({
      error: "method not allowed"
    });
  }

  try {
    const upstream = await fetch(
      `${RESONANT_BACKEND}/field/v1/manifest`,
      {
        method: req.method,
        headers: {
          accept: "application/json",
          "user-agent": "RESONANT/1.0"
        },
        redirect: "follow",
        signal: AbortSignal.timeout(20000)
      }
    );

    const body = Buffer.from(await upstream.arrayBuffer());

    res.status(upstream.status);
    res.setHeader(
      "Content-Type",
      upstream.headers.get("content-type") ||
        "application/json; charset=utf-8"
    );
    res.setHeader("Cache-Control", "no-store");
    res.setHeader(
      "X-Resonant-Backend",
      RESONANT_BACKEND
    );

    if (req.method === "HEAD") {
      return res.end();
    }

    return res.send(body);
  } catch (error) {
    return res.status(503).json({
      error: "property field unavailable",
      backend: RESONANT_BACKEND,
      detail: error instanceof Error
        ? error.message
        : String(error)
    });
  }
};
