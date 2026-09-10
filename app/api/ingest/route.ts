import { env } from 'cloudflare:workers';

const MAX_BODY_SIZE = 2 * 1024 * 1024;

function fromHex(value: string) {
  if (!/^[0-9a-f]{64}$/i.test(value)) return null;
  return Uint8Array.from(value.match(/.{2}/g) ?? [], (byte) => Number.parseInt(byte, 16));
}

export async function POST(request: Request) {
  const secret = env.FOOTBALL_AI_RELAY_SECRET;
  if (!secret) return Response.json({ error: 'ingest not configured' }, { status: 503 });
  const body = await request.text();
  if (!body || body.length > MAX_BODY_SIZE) return Response.json({ error: 'invalid body' }, { status: 400 });
  const signature = fromHex(request.headers.get('X-Football-Signature') ?? '');
  if (!signature) return Response.json({ error: 'invalid signature' }, { status: 401 });
  const key = await crypto.subtle.importKey(
    'raw', new TextEncoder().encode(secret), { name: 'HMAC', hash: 'SHA-256' }, false, ['verify'],
  );
  const valid = await crypto.subtle.verify('HMAC', key, signature, new TextEncoder().encode(body));
  if (!valid) return Response.json({ error: 'invalid signature' }, { status: 401 });
  let payload: { updatedAt?: string; businessDate?: string; count?: number; matches?: unknown[] };
  try {
    payload = JSON.parse(body);
  } catch {
    return Response.json({ error: 'invalid json' }, { status: 400 });
  }
  if (!payload.updatedAt || !payload.businessDate || !Array.isArray(payload.matches) || payload.count !== payload.matches.length) {
    return Response.json({ error: 'invalid payload' }, { status: 400 });
  }
  const age = Date.now() - Date.parse(payload.updatedAt);
  if (!Number.isFinite(age) || age < -5 * 60_000 || age > 20 * 60_000) {
    return Response.json({ error: 'stale payload' }, { status: 400 });
  }
  const envelope = JSON.stringify({ body, signature: request.headers.get('X-Football-Signature') });
  const now = Date.now();
  await env.DB.prepare(
    `INSERT INTO api_cache (cache_key, payload, expires_at, updated_at) VALUES (?1, ?2, ?3, ?4)
     ON CONFLICT(cache_key) DO UPDATE SET payload=excluded.payload, expires_at=excluded.expires_at, updated_at=excluded.updated_at`,
  ).bind('football-ai:relay-push', envelope, now + 30 * 60_000, now).run();
  return Response.json({ ok: true, businessDate: payload.businessDate, count: payload.count });
}
