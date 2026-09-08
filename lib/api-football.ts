import { env } from 'cloudflare:workers';

const API_BASE = 'https://v3.football.api-sports.io';
const LEAGUE_PRIORITY = new Map([
  [2, 1], [3, 2], [39, 3], [140, 4], [135, 5], [78, 6], [61, 7],
  [307, 8], [1, 9], [4, 10], [5, 11], [169, 12], [848, 13],
]);

type ApiEnvelope<T> = { response: T; errors?: Record<string, string> | string[] };

type ApiFixture = {
  fixture: { id: number; date: string; status: { short: string } };
  league: { id: number; name: string; country: string };
  teams: { home: { name: string }; away: { name: string } };
};

type ApiPrediction = {
  predictions?: {
    percent?: { home?: string; draw?: string; away?: string };
    under_over?: string | null;
  };
};

export type DashboardMatch = {
  id: number;
  league: string;
  time: string;
  dateLabel: string;
  home: string;
  away: string;
  probabilities: [number, number, number] | null;
  goals: string;
  confidence: number | null;
  risk: '低风险' | '中风险' | '高风险' | '待评估';
  riskTone: 'green' | 'amber' | 'red';
  note: string;
};

export type DashboardData = {
  matches: DashboardMatch[];
  updatedAt: string;
  error?: string;
};

function shanghaiDate(offsetDays: number) {
  return new Intl.DateTimeFormat('en-CA', {
    timeZone: 'Asia/Shanghai', year: 'numeric', month: '2-digit', day: '2-digit',
  }).format(new Date(Date.now() + offsetDays * 86_400_000));
}

async function cachedRequest<T>(path: string, ttlMs: number): Promise<T> {
  const cacheKey = `api-football:${path}`;
  const now = Date.now();
  let stalePayload: string | undefined;

  try {
    const row = await env.DB.prepare(
      'SELECT payload, expires_at AS expiresAt FROM api_cache WHERE cache_key = ?1',
    ).bind(cacheKey).first<{ payload: string; expiresAt: number }>();
    if (row) {
      stalePayload = row.payload;
      if (row.expiresAt > now) return (JSON.parse(row.payload) as ApiEnvelope<T>).response;
    }
  } catch {
    // The network request below still gives a useful result during a fresh migration.
  }

  if (!env.API_FOOTBALL_KEY) throw new Error('API-Football 密钥尚未配置');

  try {
    const response = await fetch(`${API_BASE}${path}`, {
      headers: { 'x-apisports-key': env.API_FOOTBALL_KEY },
    });
    if (!response.ok) throw new Error(`API-Football 返回 ${response.status}`);
    const payload = await response.text();
    const parsed = JSON.parse(payload) as ApiEnvelope<T>;
    if (parsed.errors && Object.keys(parsed.errors).length > 0) {
      throw new Error('API-Football 返回数据错误');
    }
    await env.DB.prepare(
      `INSERT INTO api_cache (cache_key, payload, expires_at, updated_at)
       VALUES (?1, ?2, ?3, ?4)
       ON CONFLICT(cache_key) DO UPDATE SET payload = excluded.payload,
       expires_at = excluded.expires_at, updated_at = excluded.updated_at`,
    ).bind(cacheKey, payload, now + ttlMs, now).run();
    return parsed.response;
  } catch (error) {
    if (stalePayload) return (JSON.parse(stalePayload) as ApiEnvelope<T>).response;
    throw error;
  }
}

function percentage(value?: string) {
  const parsed = Number.parseInt(value ?? '', 10);
  return Number.isFinite(parsed) ? parsed : 0;
}

function analyzeRisk(probabilities: [number, number, number] | null) {
  if (!probabilities) return { risk: '待评估' as const, riskTone: 'amber' as const };
  const sorted = [...probabilities].sort((a, b) => b - a);
  const gap = sorted[0] - sorted[1];
  if (gap >= 25) return { risk: '低风险' as const, riskTone: 'green' as const };
  if (gap >= 12) return { risk: '中风险' as const, riskTone: 'amber' as const };
  return { risk: '高风险' as const, riskTone: 'red' as const };
}

function buildNote(probabilities: [number, number, number] | null) {
  if (!probabilities) return '真实赛程已导入，供应商基础预测尚未返回，系统会在下一次刷新时重试。';
  const labels = ['主队', '平局', '客队'];
  const strongest = probabilities.indexOf(Math.max(...probabilities));
  return `API-Football 基础概率当前偏向${labels[strongest]}。这是第一阶段供应商基线，后续将叠加球队状态、伤停与市场数据。`;
}

export async function getDashboardData(): Promise<DashboardData> {
  try {
    const dates = [shanghaiDate(0), shanghaiDate(1)];
    const fixtureGroups = await Promise.all(dates.map((date) =>
      cachedRequest<ApiFixture[]>(`/fixtures?date=${date}&timezone=Asia%2FShanghai`, 30 * 60_000),
    ));

    const now = Date.now();
    const fixtures = fixtureGroups.flat()
      .filter((item) => item.fixture.status.short === 'NS')
      .filter((item) => new Date(item.fixture.date).getTime() > now - 15 * 60_000)
      .sort((a, b) => {
        const league = (LEAGUE_PRIORITY.get(a.league.id) ?? 99) - (LEAGUE_PRIORITY.get(b.league.id) ?? 99);
        return league || new Date(a.fixture.date).getTime() - new Date(b.fixture.date).getTime();
      });

    const preferred = fixtures.filter((item) => LEAGUE_PRIORITY.has(item.league.id));
    const selected = (preferred.length ? preferred : fixtures).slice(0, 6);
    const predictions = await Promise.all(selected.map(async (fixture) => {
      try {
        const result = await cachedRequest<ApiPrediction[]>(`/predictions?fixture=${fixture.fixture.id}`, 60 * 60_000);
        return result[0] ?? null;
      } catch {
        return null;
      }
    }));

    const matches = selected.map((fixture, index): DashboardMatch => {
      const prediction = predictions[index]?.predictions;
      const values: [number, number, number] = [
        percentage(prediction?.percent?.home),
        percentage(prediction?.percent?.draw),
        percentage(prediction?.percent?.away),
      ];
      const probabilities = values.some(Boolean) ? values : null;
      const risk = analyzeRisk(probabilities);
      const date = new Date(fixture.fixture.date);
      return {
        id: fixture.fixture.id,
        league: fixture.league.name,
        time: new Intl.DateTimeFormat('zh-CN', { timeZone: 'Asia/Shanghai', hour: '2-digit', minute: '2-digit', hour12: false }).format(date),
        dateLabel: new Intl.DateTimeFormat('zh-CN', { timeZone: 'Asia/Shanghai', month: 'numeric', day: 'numeric' }).format(date),
        home: fixture.teams.home.name,
        away: fixture.teams.away.name,
        probabilities,
        goals: prediction?.under_over ? `${prediction.under_over} 球线` : '待评估',
        confidence: probabilities ? Math.max(...probabilities) : null,
        ...risk,
        note: buildNote(probabilities),
      };
    });

    return { matches, updatedAt: new Date().toISOString() };
  } catch (error) {
    return {
      matches: [], updatedAt: new Date().toISOString(),
      error: error instanceof Error ? error.message : '真实数据暂时不可用',
    };
  }
}
