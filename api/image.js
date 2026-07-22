const ALLOWED = [
  ".rdcpix.com",
  ".realtor.com",
  ".zillowstatic.com",
  ".zillow.com",
  ".redfin.com",
  ".brightspotcdn.com",
  ".imgix.net",
  ".cloudfront.net",
  ".akamaized.net",
  ".amazonaws.com"
];

function allowed(hostname) {
  const host = String(hostname || "").toLowerCase();
  return ALLOWED.some(
    suffix => host === suffix.slice(1) || host.endsWith(suffix)
  );
}

module.exports = async function handler(req, res) {
  if (!["GET", "HEAD"].includes(req.method || "GET")) {
    res.setHeader("Allow", "GET, HEAD");
    return res.status(405).json({ error: "method not allowed" });
  }

  const raw = Array.isArray(req.query.url) ? req.query.url[0] : req.query.url;
  let target;

  try {
    target = new URL(String(raw || ""));
  } catch {
    return res.status(400).json({ error: "invalid image URL" });
  }

  if (target.protocol === "http:") target.protocol = "https:";

  if (target.protocol !== "https:" || !allowed(target.hostname)) {
    return res.status(403).json({ error: "image host not allowed" });
  }

  try {
    const upstream = await fetch(target, {
      method: req.method,
      redirect: "follow",
      headers: {
        accept: "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
        referer: "https://www.realtor.com/",
        "user-agent":
          "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) " +
          "AppleWebKit/537.36 Chrome/150 Safari/537.36"
      },
      signal: AbortSignal.timeout(25000)
    });

    if (!upstream.ok) {
      return res.status(upstream.status).json({
        error: "upstream image failed"
      });
    }

    const type = upstream.headers.get("content-type") || "";

    if (!type.toLowerCase().startsWith("image/")) {
      return res.status(415).json({
        error: "upstream did not return an image"
      });
    }

    res.status(200);
    res.setHeader("Content-Type", type);
    res.setHeader(
      "Cache-Control",
      "public, s-maxage=86400, stale-while-revalidate=604800"
    );

    if (req.method === "HEAD") return res.end();

    const body = Buffer.from(await upstream.arrayBuffer());

    if (body.length > 10 * 1024 * 1024) {
      return res.status(413).json({ error: "image too large" });
    }

    return res.send(body);
  } catch (error) {
    return res.status(502).json({
      error: "image fetch failed",
      detail: error instanceof Error ? error.message : String(error)
    });
  }
};
