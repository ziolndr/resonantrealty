function backendBase() {
  return String(process.env.RESONANT_BACKEND_URL || '').trim().replace(/\/+$/, '');
}

module.exports = async function handler(req, res) {
  const base = backendBase();
  if (!base) return res.status(503).json({ ok: false, error: 'RESONANT_BACKEND_URL is not configured' });
  try {
    const manifestResponse = await fetch(`${base}/field/v1/manifest`, {
      headers: { accept: 'application/json' }, signal: AbortSignal.timeout(10000)
    });
    if (!manifestResponse.ok) return res.status(502).json({ ok: false, error: `manifest ${manifestResponse.status}` });
    const manifest = await manifestResponse.json();
    let imageCount = null;
    if (String(req.query.full || '') === '1') {
      const searchResponse = await fetch(`${base}/field/v1/search`, {
        method: 'POST',
        headers: { 'content-type': 'application/json', accept: 'application/json' },
        body: JSON.stringify({ text: 'home residence architecture natural light views', k: 24 }),
        signal: AbortSignal.timeout(30000)
      });
      if (!searchResponse.ok) return res.status(502).json({ ok: false, error: `search ${searchResponse.status}` });
      const data = await searchResponse.json();
      const rows = data.results || data.matches || data.items || [];
      imageCount = rows.filter(row => row.imageUrl || (Array.isArray(row.images) && row.images.length)).length;
    }
    res.setHeader('Cache-Control', 'no-store');
    return res.status(200).json({
      ok: true,
      build: '20260721-image-delivery-v3',
      count: Number(manifest.count || 0),
      imageResults: imageCount
    });
  } catch (error) {
    return res.status(502).json({ ok: false, error: error instanceof Error ? error.message : String(error) });
  }
};
