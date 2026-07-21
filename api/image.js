const ALLOWED_SUFFIXES = [
  '.rdcpix.com', '.realtor.com', '.zillowstatic.com', '.redfin.com',
  '.brightspotcdn.com', '.imgix.net', '.cloudfront.net'
];
const EXACT_HOSTS = new Set(['rdcpix.com','realtor.com','zillowstatic.com','redfin.com']);

function allowedHost(hostname) {
  const host = String(hostname || '').toLowerCase();
  return EXACT_HOSTS.has(host) || ALLOWED_SUFFIXES.some(suffix => host.endsWith(suffix));
}

module.exports = async function handler(req, res) {
  if (req.method !== 'GET' && req.method !== 'HEAD') {
    res.setHeader('Allow', 'GET, HEAD');
    return res.status(405).json({ error: 'method not allowed' });
  }

  const raw = Array.isArray(req.query.url) ? req.query.url[0] : req.query.url;
  let target;
  try {
    target = new URL(String(raw || ''));
  } catch {
    return res.status(400).json({ error: 'invalid image URL' });
  }

  if (target.protocol !== 'https:' || !allowedHost(target.hostname)) {
    return res.status(403).json({ error: 'image host not allowed' });
  }

  try {
    const upstream = await fetch(target, {
      redirect: 'follow',
      headers: {
        'accept': 'image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8',
        'accept-language': 'en-US,en;q=0.9',
        'referer': 'https://www.realtor.com/',
        'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/150 Safari/537.36'
      },
      signal: AbortSignal.timeout(20000)
    });

    if (!upstream.ok) return res.status(upstream.status).json({ error: 'upstream image failed' });
    const type = upstream.headers.get('content-type') || '';
    if (!type.toLowerCase().startsWith('image/')) {
      return res.status(415).json({ error: 'upstream did not return an image' });
    }

    const declared = Number(upstream.headers.get('content-length') || 0);
    if (declared > 8 * 1024 * 1024) return res.status(413).json({ error: 'image too large' });
    const payload = Buffer.from(await upstream.arrayBuffer());
    if (payload.length > 8 * 1024 * 1024) return res.status(413).json({ error: 'image too large' });

    res.setHeader('Content-Type', type);
    res.setHeader('Cache-Control', 'public, s-maxage=86400, stale-while-revalidate=604800');
    res.setHeader('X-Resonant-Image-Proxy', '1');
    if (req.method === 'HEAD') return res.status(200).end();
    return res.status(200).send(payload);
  } catch (error) {
    return res.status(502).json({
      error: 'image fetch failed',
      detail: error instanceof Error ? error.message : String(error)
    });
  }
};
