import { env } from 'cloudflare:workers';

const SPORTTERY_URL = 'https://webapi.sporttery.cn/gateway/uniform/football/getMatchCalculatorV1.qry?channel=c&poolCode=had,hhad';

type Odds = { h?: string; d?: string; a?: string; goalLine?: string; updateDate?: string; updateTime?: string };
type SportteryMatch = {
  matchId: number;
  matchNum: number;
  matchNumStr?: string;
  matchWeek: string;
  businessDate: string;
  matchDate: string;
  matchTime: string;
  leagueAllName: string;
  homeTeamAllName: string;
  awayTeamAllName: string;
  sellStatus: string;
  had?: Odds;
  hhad?: Odds;
};
type SportteryEnvelope = { success: boolean; errorCode: string; value?: { matchInfoList?: Array<{ businessDate: string; subMatchList: SportteryMatch[] }> } };

export type DashboardMatch = {
  id: number;
  officialNumber: string;
  league: string;
  time: string;
  dateLabel: string;
  home: string;
  away: string;
  probabilities: [number, number, number] | null;
  providerProbabilities: [number, number, number] | null;
  marketProbabilities: [number, number, number] | null;
  averageOdds: [number, number, number] | null;
  handicapOdds: [number, number, number] | null;
  handicapLine: string | null;
  bookmakerCount: number;
  marketMargin: number | null;
  goals: string;
  confidence: number | null;
  risk: '低风险' | '中风险' | '高风险' | '待评估';
  riskTone: 'green' | 'amber' | 'red';
  note: string;
  saleStatus: string;
};

export type DashboardData = { matches: DashboardMatch[]; updatedAt: string; businessDate: string; error?: string };

function shanghaiDate() {
  return new Intl.DateTimeFormat('en-CA', { timeZone: 'Asia/Shanghai', year: 'numeric', month: '2-digit', day: '2-digit' }).format(new Date());
}

async function getSportteryData(): Promise<SportteryEnvelope> {
  const cacheKey = 'sporttery:football:had-hhad';
  const now = Date.now();
  let stale: string | undefined;
  try {
    const row = await env.DB.prepare('SELECT payload, expires_at AS expiresAt FROM api_cache WHERE cache_key = ?1')
      .bind(cacheKey).first<{ payload: string; expiresAt: number }>();
    if (row) {
      stale = row.payload;
      if (row.expiresAt > now) return JSON.parse(row.payload) as SportteryEnvelope;
    }
  } catch { /* A fresh migration may not have the cache table yet. */ }

  try {
    const response = await fetch(SPORTTERY_URL, {
      headers: {
        'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 Version/17.5 Mobile/15E148 Safari/604.1',
        Accept: 'application/json, text/javascript, */*; q=0.01',
        Referer: 'https://m.sporttery.cn/mjc/jsq/zqspf/',
        Origin: 'https://m.sporttery.cn',
        'X-Requested-With': 'XMLHttpRequest',
      },
    });
    if (!response.ok) throw new Error(`体彩官方接口返回 ${response.status}`);
    const payload = await response.text();
    const parsed = JSON.parse(payload) as SportteryEnvelope;
    if (!parsed.success || parsed.errorCode !== '0') throw new Error('体彩官方接口返回数据错误');
    await env.DB.prepare(
      `INSERT INTO api_cache (cache_key, payload, expires_at, updated_at) VALUES (?1, ?2, ?3, ?4)
       ON CONFLICT(cache_key) DO UPDATE SET payload=excluded.payload, expires_at=excluded.expires_at, updated_at=excluded.updated_at`,
    ).bind(cacheKey, payload, now + 5 * 60_000, now).run();
    return parsed;
  } catch (error) {
    if (stale) return JSON.parse(stale) as SportteryEnvelope;
    throw error;
  }
}

function parseOdds(odds?: Odds): [number, number, number] | null {
  const values = [Number(odds?.h), Number(odds?.d), Number(odds?.a)] as [number, number, number];
  return values.every((value) => Number.isFinite(value) && value > 1) ? values : null;
}

function deVig(odds: [number, number, number] | null) {
  if (!odds) return null;
  const implied = odds.map((value) => 1 / value) as [number, number, number];
  const total = implied.reduce((sum, value) => sum + value, 0);
  const home = Math.round((implied[0] / total) * 100);
  const draw = Math.round((implied[1] / total) * 100);
  return { probabilities: [home, draw, 100 - home - draw] as [number, number, number], margin: Number(((total - 1) * 100).toFixed(1)) };
}

function riskFor(probabilities: [number, number, number] | null) {
  if (!probabilities) return { risk: '待评估' as const, riskTone: 'amber' as const };
  const sorted = [...probabilities].sort((a, b) => b - a);
  const gap = sorted[0] - sorted[1];
  if (gap >= 25) return { risk: '低风险' as const, riskTone: 'green' as const };
  if (gap >= 12) return { risk: '中风险' as const, riskTone: 'amber' as const };
  return { risk: '高风险' as const, riskTone: 'red' as const };
}

function officialNumber(match: SportteryMatch) {
  if (match.matchNumStr) return match.matchNumStr;
  return `${match.matchWeek}${String(match.matchNum % 1000).padStart(3, '0')}`;
}

export async function getDashboardData(): Promise<DashboardData> {
  const businessDate = shanghaiDate();
  try {
    const payload = await getSportteryData();
    const group = payload.value?.matchInfoList?.find((item) => item.businessDate === businessDate);
    const source = group?.subMatchList ?? [];
    const matches = source.sort((a, b) => a.matchNum - b.matchNum).map((item): DashboardMatch => {
      const had = parseOdds(item.had);
      const hhad = parseOdds(item.hhad);
      const market = deVig(had);
      const probabilities = market?.probabilities ?? null;
      const labels = ['主胜', '平局', '客胜'];
      const strongest = probabilities ? probabilities.indexOf(Math.max(...probabilities)) : -1;
      const updateAt = item.had?.updateTime ? `${item.had.updateTime.slice(0, 5)} 更新` : '等待更新';
      return {
        id: item.matchId || item.matchNum,
        officialNumber: officialNumber(item),
        league: item.leagueAllName,
        time: item.matchTime.slice(0, 5),
        dateLabel: item.matchDate.slice(5).replace('-', '/'),
        home: item.homeTeamAllName,
        away: item.awayTeamAllName,
        probabilities,
        providerProbabilities: null,
        marketProbabilities: probabilities,
        averageOdds: had,
        handicapOdds: hhad,
        handicapLine: item.hhad?.goalLine || null,
        bookmakerCount: had ? 1 : 0,
        marketMargin: market?.margin ?? null,
        goals: hhad?.length ? `让球 ${item.hhad?.goalLine || '0'}` : '让球待公布',
        confidence: probabilities ? Math.max(...probabilities) : null,
        ...riskFor(probabilities),
        note: probabilities ? `体彩官方胜平负固定奖去水后偏向${labels[strongest]}，${updateAt}。当前仅表示市场概率，不是投注保证。` : '体彩官方赛程已导入，胜平负固定奖尚未公布或暂停售。',
        saleStatus: item.sellStatus,
      };
    });
    return { matches, updatedAt: new Date().toISOString(), businessDate };
  } catch (error) {
    return { matches: [], updatedAt: new Date().toISOString(), businessDate, error: error instanceof Error ? error.message : '体彩官方数据暂时不可用' };
  }
}
