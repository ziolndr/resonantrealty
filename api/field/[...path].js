const HOP_BY_HOP = new Set([
  'connection','keep-alive','proxy-authenticate','proxy-authorization','te',
  'trailers','transfer-encoding','upgrade','content-length'
]);

function backendBase() {
  return String(process.env.RESONANT_BACKEND_URL || '').trim().replace(/\/+$/, '');
}

module.exports = async function handler(req, res) {
  const base = backendBase();
  if (!base) return res.status(503).json({ error: 'RESONANT_BACKEND_URL is not configured' });

  const rawPath = req.query.path;
  const route = Array.isArray(rawPath) ? rawPath.join('/') : String(rawPath || '');
  const query = new URLSearchParams();
  for (const [key, value] of Object.entries(req.query || {})) {
    if (key === 'path') continue;
    if (Array.isArray(value)) value.forEach(item => query.append(key, String(item)));
    else if (value != null) query.set(key, String(value));
  }
  const target = `${base}/field/${route}${query.size ? `?${query}` : ''}`;

  const headers = {};
  for (const [key, value] of Object.entries(req.headers || {})) {
    const lower = key.toLowerCase();
    if (HOP_BY_HOP.has(lower) || lower === 'host') continue;
    if (value != null) headers[key] = value;
  }

  const method = req.method || 'GET';
  let body;
  if (!['GET','HEAD'].includes(method)) {
    if (Buffer.isBuffer(req.body) || typeof req.body === 'string') body = req.body;
    else if (req.body != null) {
      body = JSON.stringify(req.body);
      headers['content-type'] = headers['content-type'] || 'application/json';
    }
  }

  try {
    const upstream = await fetch(target, {
      method, headers, body, redirect: 'manual', signal: AbortSignal.timeout(55000)
    });
    res.status(upstream.status);
    upstream.headers.forEach((value, key) => {
      if (!HOP_BY_HOP.has(key.toLowerCase())) res.setHeader(key, value);
    });
    res.send(Buffer.from(await upstream.arrayBuffer()));
  } catch (error) {
    res.status(502).json({
      error: 'RESONANT property field is unreachable',
      detail: error instanceof Error ? error.message : String(error)
    });
  }
};
