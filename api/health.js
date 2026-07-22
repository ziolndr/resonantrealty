const {
  RESONANT_BACKEND
} = require("../lib/resonant-backend");

module.exports = async function handler(req, res) {
  try {
    const upstream = await fetch(
      `${RESONANT_BACKEND}/field/v1/manifest`,
      {
        headers: {
          accept: "application/json",
          "user-agent": "RESONANT/1.0"
        },
        redirect: "follow",
        signal: AbortSignal.timeout(20000)
      }
    );

    const body = await upstream.json();

    return res.status(upstream.ok ? 200 : 502).json({
      ok: upstream.ok,
      count: Number(
        body.count ||
        body.total_records ||
        body.embedded_records ||
        0
      ),
      backend: RESONANT_BACKEND,
      source: "committed-zrok-v2"
    });
  } catch (error) {
    return res.status(503).json({
      ok: false,
      backend: RESONANT_BACKEND,
      source: "committed-zrok-v2",
      detail: error instanceof Error
        ? error.message
        : String(error)
    });
  }
};
