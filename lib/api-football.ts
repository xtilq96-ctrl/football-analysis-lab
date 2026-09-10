import { env } from 'cloudflare:workers';

const SPORTTERY_URL = 'https://webapi.sporttery.cn/gateway/uniform/football/getMatchCalculatorV1.qry?channel=c&poolCode=had,hhad';

type Odds = { h?: string; d?: string; a?: string; goalLine?: string; updateDate?: string; updateTime?: string };
type ModelAnalysis = {
  modelVersion?: string;
  probabilities?: { home: number; draw: number; away: number };
  marketProbabilities?: { home: number; draw: number; away: number };
  predictedScore?: string;
  scoreProbabilities?: Array<{ score: string; probability: number }>;
  predictedTotalGoals?: string;
  totalGoalsProbabilities?: Record<string, number>;
  under25Probability?: number;
  over25Probability?: number;
  expectedGoals?: { home: number; away: number; total: number };
};
type TeamForm = {
  matches: number; wins: number; draws: number; losses: number;
  pointsPerGame: number | null; goalsForPerGame: number | null;
  goalsAgainstPerGame: number | null; cleanSheetRate: number | null;
  form: string; restDays: number | null; matchesLast14Days: number;
  venue: { matches: number; pointsPerGame: number | null; goalsForPerGame: number | null; goalsAgainstPerGame: number | null };
};
type TeamFundamentals = {
  apiName: string;
  form: TeamForm;
  absences: { total: number; injuries: number; suspensions: number; players: Array<{ name: string; reason: string }>; available?: boolean };
  lineup: { confirmed: boolean; formation?: string | null; startingCount: number; available?: boolean };
};
type Fundamentals = {
  status: 'ready' | 'partial' | 'unmatched' | 'not_configured' | 'api_error';
  coverage: number;
  source?: 'sporttery_history' | 'api_football';
  sourceLabel?: string;
  mappingConfidence?: number;
  message?: string;
  home?: TeamFundamentals;
  away?: TeamFundamentals;
  probabilityAdjustmentPoints?: { home: number; draw: number; away: number };
};
type AnalysisSchedule = {
  phase: string; isLocked: boolean; isEarlyMatch: boolean;
  finalAnalysisAt: string; lockAt: string; minutesToKickoff: number | null;
};
type MatchResult = {
  fullTimeScore: string;
  halfTimeScore?: string;
  actualOutcome: string;
  settledAt: string;
};
type MatchSettlement = {
  outcomeHit: boolean | null;
  scoreHit: boolean | null;
  totalGoalsHit: boolean | null;
  overUnderHit: boolean | null;
};
export type PerformanceSummary = {
  settledMatches: number;
  outcomeHits: number;
  outcomeHitRate: number | null;
  exactScoreHits: number;
  exactScoreHitRate: number | null;
  totalGoalsHits: number;
  totalGoalsHitRate: number | null;
  overUnderHits: number;
  overUnderHitRate: number | null;
  settledTwoLegs: number;
  twoLegHits: number;
  twoLegHitRate: number | null;
  settledCombinations?: number;
  combinationHits?: number;
  combinationHitRate?: number | null;
  combinationStats?: Array<{ legCount: number; settled: number; hits: number; hitRate: number | null }>;
  probabilityEvaluation?: ProbabilityMetrics;
  recent30?: ProbabilityMetrics;
  calibration?: Array<{ label: string; sampleSize: number; averageConfidence: number; actualHitRate: number; gap: number }>;
  calibrationError?: number | null;
};
type ProbabilityMetrics = { sampleSize: number; outcomeHitRate: number | null; brierScore: number | null; logLoss: number | null };
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
  analysis?: ModelAnalysis;
  result?: MatchResult;
  settlement?: MatchSettlement;
  fundamentals?: Fundamentals;
  analysisSchedule?: AnalysisSchedule;
};
type SportteryEnvelope = { success: boolean; errorCode: string; value?: { matchInfoList?: Array<{ businessDate: string; subMatchList: SportteryMatch[] }> } };
type RelayMatch = {
  matchId: string;
  businessDate: string;
  officialNumber: string;
  matchNumber: number;
  league: string;
  home: string;
  away: string;
  kickoffDate: string;
  kickoffTime: string;
  saleStatus: string;
  had?: Odds;
  hhad?: Odds;
  analysis?: ModelAnalysis;
  result?: MatchResult;
  settlement?: MatchSettlement;
  fundamentals?: Fundamentals;
  analysisSchedule?: AnalysisSchedule;
};
export type DashboardRecommendation = {
  type?: string;
  legCount?: number;
  level: string;
  combinedProbability: number;
  combinedOdds: number;
  averageEdge?: number;
  isLocked?: boolean;
  basis?: string;
  legs: Array<{
    matchId: string;
    officialNumber: string;
    league: string;
    home: string;
    away: string;
    pick: string;
    probability: number;
    odds: number;
  }>;
};
export type RecommendationDecision = {
  status: 'recommended' | 'no_pick';
  legCount: number;
  candidateCount: number;
  reason: string;
  rulesVersion: string;
};
type RelayPayload = {
  source: string;
  businessDate: string;
  businessDates?: string[];
  updatedAt: string;
  count: number;
  matches: RelayMatch[];
  recommendations?: Record<string, DashboardRecommendation[]>;
  recommendationDecisions?: Record<string, RecommendationDecision>;
  performance?: PerformanceSummary;
};

const VERIFIED_SNAPSHOT_2026_09_08: SportteryMatch[] = [
  { matchId: 2041345, matchNum: 2001, matchNumStr: '周二001', matchWeek: '周二', businessDate: '2026-09-08', matchDate: '2026-09-08', matchTime: '18:30:00', leagueAllName: '韩国职业联赛', homeTeamAllName: '蔚山现代', awayTeamAllName: '首尔FC', sellStatus: '1', had: { h: '3.29', d: '3.58', a: '1.83', updateDate: '2026-09-08', updateTime: '15:49:37' }, hhad: { h: '1.74', d: '3.80', a: '3.43', goalLine: '+1' } },
  { matchId: 2041346, matchNum: 2002, matchNumStr: '周二002', matchWeek: '周二', businessDate: '2026-09-08', matchDate: '2026-09-09', matchTime: '00:45:00', leagueAllName: '欧洲冠军联赛', homeTeamAllName: '雅典AEK', awayTeamAllName: 'LASK林茨', sellStatus: '1', had: { h: '1.59', d: '3.85', a: '4.15', updateDate: '2026-09-08', updateTime: '12:46:01' }, hhad: { h: '2.73', d: '3.70', a: '2.03', goalLine: '-1' } },
  { matchId: 2041347, matchNum: 2003, matchNumStr: '周二003', matchWeek: '周二', businessDate: '2026-09-08', matchDate: '2026-09-09', matchTime: '00:45:00', leagueAllName: '欧洲冠军联赛', homeTeamAllName: '布鲁日', awayTeamAllName: '阿斯顿维拉', sellStatus: '1', had: { h: '2.41', d: '3.35', a: '2.41', updateDate: '2026-09-08', updateTime: '13:19:26' }, hhad: { h: '1.42', d: '4.30', a: '5.20', goalLine: '+1' } },
  { matchId: 2041348, matchNum: 2004, matchNumStr: '周二004', matchWeek: '周二', businessDate: '2026-09-08', matchDate: '2026-09-09', matchTime: '00:45:00', leagueAllName: '荷兰甲级联赛', homeTeamAllName: '奈梅亨', awayTeamAllName: 'SBV精英', sellStatus: '1', had: { h: '1.48', d: '4.30', a: '4.55', updateDate: '2026-09-08', updateTime: '09:45:44' }, hhad: { h: '2.35', d: '3.90', a: '2.24', goalLine: '-1' } },
  { matchId: 2041349, matchNum: 2005, matchNumStr: '周二005', matchWeek: '周二', businessDate: '2026-09-08', matchDate: '2026-09-09', matchTime: '02:00:00', leagueAllName: '沙特职业联赛', homeTeamAllName: '胡巴尔卡德西亚', awayTeamAllName: '吉达国民', sellStatus: '1', had: { h: '1.80', d: '3.75', a: '3.25', updateDate: '2026-09-08', updateTime: '15:30:07' }, hhad: { h: '3.25', d: '3.85', a: '1.78', goalLine: '-1' } },
  { matchId: 2041350, matchNum: 2006, matchNumStr: '周二006', matchWeek: '周二', businessDate: '2026-09-08', matchDate: '2026-09-09', matchTime: '02:45:00', leagueAllName: '英格兰冠军联赛', homeTeamAllName: '南安普敦', awayTeamAllName: '斯旺西', sellStatus: '1', had: { h: '1.67', d: '3.60', a: '3.95', updateDate: '2026-09-08', updateTime: '13:24:20' }, hhad: { h: '3.05', d: '3.56', a: '1.92', goalLine: '-1' } },
  { matchId: 2041351, matchNum: 2007, matchNumStr: '周二007', matchWeek: '周二', businessDate: '2026-09-08', matchDate: '2026-09-09', matchTime: '02:45:00', leagueAllName: '英格兰联赛杯', homeTeamAllName: '桑德兰', awayTeamAllName: '赫尔城', sellStatus: '1', had: { h: '1.56', d: '3.60', a: '4.75', updateDate: '2026-09-08', updateTime: '15:31:20' }, hhad: { h: '2.90', d: '3.25', a: '2.10', goalLine: '-1' } },
  { matchId: 2041352, matchNum: 2008, matchNumStr: '周二008', matchWeek: '周二', businessDate: '2026-09-08', matchDate: '2026-09-09', matchTime: '03:00:00', leagueAllName: '欧洲冠军联赛', homeTeamAllName: '皇家马德里', awayTeamAllName: '国际米兰', sellStatus: '1', had: { h: '1.42', d: '4.40', a: '5.05', updateDate: '2026-09-08', updateTime: '12:33:36' }, hhad: { h: '2.25', d: '3.75', a: '2.40', goalLine: '-1' } },
  { matchId: 2041353, matchNum: 2009, matchNumStr: '周二009', matchWeek: '周二', businessDate: '2026-09-08', matchDate: '2026-09-09', matchTime: '03:00:00', leagueAllName: '欧洲冠军联赛', homeTeamAllName: '多特蒙德', awayTeamAllName: '比利亚雷亚尔', sellStatus: '1', had: { h: '1.61', d: '3.95', a: '3.92', updateDate: '2026-09-08', updateTime: '14:05:44' }, hhad: { h: '2.65', d: '3.85', a: '2.03', goalLine: '-1' } },
  { matchId: 2041376, matchNum: 2010, matchNumStr: '周二010', matchWeek: '周二', businessDate: '2026-09-08', matchDate: '2026-09-09', matchTime: '03:00:00', leagueAllName: '欧洲冠军联赛', homeTeamAllName: '里尔', awayTeamAllName: '皇家贝蒂斯', sellStatus: '1', had: { h: '1.90', d: '3.30', a: '3.33', updateDate: '2026-09-07', updateTime: '13:58:26' }, hhad: { h: '3.75', d: '3.70', a: '1.69', goalLine: '-1' } },
  { matchId: 2041354, matchNum: 2011, matchNumStr: '周二011', matchWeek: '周二', businessDate: '2026-09-08', matchDate: '2026-09-09', matchTime: '03:00:00', leagueAllName: '欧洲冠军联赛', homeTeamAllName: '波尔图', awayTeamAllName: '曼彻斯特城', sellStatus: '1', had: { h: '4.85', d: '4.05', a: '1.48', updateDate: '2026-09-07', updateTime: '13:58:26' }, hhad: { h: '2.26', d: '3.65', a: '2.42', goalLine: '+1' } },
  { matchId: 2041355, matchNum: 2012, matchNumStr: '周二012', matchWeek: '周二', businessDate: '2026-09-08', matchDate: '2026-09-09', matchTime: '06:00:00', leagueAllName: '南美解放者杯', homeTeamAllName: '弗鲁米嫩塞', awayTeamAllName: '普拉滕斯', sellStatus: '1', had: { h: '1.53', d: '3.20', a: '6.15', updateDate: '2026-09-08', updateTime: '14:31:54' }, hhad: { h: '2.90', d: '3.18', a: '2.13', goalLine: '-1' } },
];

const EMPTY_PERFORMANCE: PerformanceSummary = {
  settledMatches: 0, outcomeHits: 0, outcomeHitRate: null, exactScoreHits: 0,
  exactScoreHitRate: null, totalGoalsHits: 0, totalGoalsHitRate: null,
  overUnderHits: 0, overUnderHitRate: null, settledTwoLegs: 0,
  twoLegHits: 0, twoLegHitRate: null,
};

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
  predictedScore: string | null;
  scoreProbabilities: Array<{ score: string; probability: number }>;
  predictedTotalGoals: string | null;
  totalGoalsProbabilities: Record<string, number> | null;
  over25Probability: number | null;
  under25Probability: number | null;
  expectedGoals: { home: number; away: number; total: number } | null;
  fundamentals: Fundamentals | null;
  analysisSchedule: AnalysisSchedule | null;
  result: MatchResult | null;
  settlement: MatchSettlement | null;
};

export type DashboardData = { matches: DashboardMatch[]; recommendations: DashboardRecommendation[]; recommendationDecision: RecommendationDecision | null; performance: PerformanceSummary; updatedAt: string; businessDate: string; sourceMode: 'mainland_relay' | 'live' | 'verified_snapshot'; error?: string };

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

function fromHex(value: string) {
  if (!/^[0-9a-f]{64}$/i.test(value)) return null;
  return Uint8Array.from(value.match(/.{2}/g) ?? [], (byte) => Number.parseInt(byte, 16));
}

async function verifyRelayBody(body: string, signatureValue: string, relaySecret: string): Promise<RelayPayload> {
  const signature = fromHex(signatureValue);
  if (!signature) throw new Error('大陆采集节点签名缺失');
  const key = await crypto.subtle.importKey(
    'raw', new TextEncoder().encode(relaySecret), { name: 'HMAC', hash: 'SHA-256' }, false, ['verify'],
  );
  const valid = await crypto.subtle.verify('HMAC', key, signature, new TextEncoder().encode(body));
  if (!valid) throw new Error('大陆采集节点签名校验失败');
  const payload = JSON.parse(body) as RelayPayload;
  if (!payload.updatedAt || !payload.businessDate || !Array.isArray(payload.matches) || payload.count !== payload.matches.length) {
    throw new Error('大陆采集节点数据结构异常');
  }
  const age = Date.now() - Date.parse(payload.updatedAt);
  if (!Number.isFinite(age) || age < -5 * 60_000 || age > 20 * 60_000) throw new Error('大陆采集节点数据已过期');
  return payload;
}

async function verifiedRelayData(): Promise<RelayPayload> {
  const relayUrl = env.FOOTBALL_AI_RELAY_URL;
  const relaySecret = env.FOOTBALL_AI_RELAY_SECRET;
  if (!relaySecret) throw new Error('大陆采集节点尚未配置');
  try {
    const cached = await env.DB.prepare(
      'SELECT payload FROM api_cache WHERE cache_key = ?1 AND expires_at > ?2',
    ).bind('football-ai:relay-push', Date.now()).first<{ payload: string }>();
    if (cached?.payload) {
      const envelope = JSON.parse(cached.payload) as { body?: string; signature?: string };
      if (envelope.body && envelope.signature) return await verifyRelayBody(envelope.body, envelope.signature, relaySecret);
    }
  } catch (cacheError) {
    console.warn('pushed relay cache unavailable', cacheError instanceof Error ? cacheError.message : 'unknown cache error');
  }
  if (!relayUrl) throw new Error('大陆采集节点尚未配置');
  const response = await fetch(relayUrl, { headers: { Accept: 'application/json' }, cache: 'no-store' });
  if (!response.ok) throw new Error(`大陆采集节点返回 ${response.status}`);
  const body = await response.text();
  return verifyRelayBody(body, response.headers.get('X-Football-Signature') ?? '', relaySecret);
}

function relayMatch(item: RelayMatch): SportteryMatch {
  const suffix = item.officialNumber.slice(-3);
  return {
    matchId: Number(item.matchId),
    matchNum: item.matchNumber || Number(suffix),
    matchNumStr: item.officialNumber,
    matchWeek: item.officialNumber.slice(0, -3),
    businessDate: item.businessDate,
    matchDate: item.kickoffDate,
    matchTime: item.kickoffTime,
    leagueAllName: item.league,
    homeTeamAllName: item.home,
    awayTeamAllName: item.away,
    sellStatus: item.saleStatus,
    had: item.had,
    hhad: item.hhad,
    analysis: item.analysis,
    result: item.result,
    settlement: item.settlement,
    fundamentals: item.fundamentals,
    analysisSchedule: item.analysisSchedule,
  };
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
  let businessDate = shanghaiDate();
  let updatedAt = new Date().toISOString();
  let sourceMode: DashboardData['sourceMode'] = 'mainland_relay';
  let recommendations: DashboardRecommendation[] = [];
  let recommendationDecision: RecommendationDecision | null = null;
  let performance = EMPTY_PERFORMANCE;
  try {
    let source: SportteryMatch[] = [];
    try {
      const relay = await verifiedRelayData();
      businessDate = relay.businessDate;
      updatedAt = relay.updatedAt;
      source = relay.matches.filter((item) => item.businessDate === businessDate).map(relayMatch);
      recommendations = relay.recommendations?.[businessDate] ?? [];
      recommendationDecision = relay.recommendationDecisions?.[businessDate] ?? null;
      performance = relay.performance ?? EMPTY_PERFORMANCE;
      if (businessDate === '2026-09-08') {
        const merged = new Map(VERIFIED_SNAPSHOT_2026_09_08.map((item) => [item.matchId, item]));
        source.forEach((item) => merged.set(item.matchId, item));
        source = [...merged.values()];
      }
    } catch (relayError) {
      console.warn('mainland relay unavailable', relayError instanceof Error ? relayError.message : 'unknown relay error');
      try {
        const payload = await getSportteryData();
        const group = payload.value?.matchInfoList?.find((item) => item.businessDate === businessDate);
        source = group?.subMatchList ?? [];
        if (!source.length) throw new Error('体彩官方直连未返回当前业务日');
        sourceMode = 'live';
      } catch {
        if (businessDate !== '2026-09-08') throw new Error('大陆体彩采集节点暂时不可用');
        source = VERIFIED_SNAPSHOT_2026_09_08;
        sourceMode = 'verified_snapshot';
      }
    }
    const matches = source.sort((a, b) => a.matchNum - b.matchNum).map((item): DashboardMatch => {
      const had = parseOdds(item.had);
      const hhad = parseOdds(item.hhad);
      const market = deVig(had);
      const modelProbabilities = item.analysis?.probabilities;
      const probabilities = modelProbabilities
        ? [modelProbabilities.home, modelProbabilities.draw, modelProbabilities.away] as [number, number, number]
        : market?.probabilities ?? null;
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
        marketProbabilities: market?.probabilities ?? null,
        averageOdds: had,
        handicapOdds: hhad,
        handicapLine: item.hhad?.goalLine || null,
        bookmakerCount: had ? 1 : 0,
        marketMargin: market?.margin ?? null,
        goals: hhad?.length ? `让球 ${item.hhad?.goalLine || '0'}` : '让球待公布',
        confidence: probabilities ? Math.max(...probabilities) : null,
        ...riskFor(probabilities),
        note: probabilities ? `${item.analysis?.modelVersion === 'v2-market-fundamentals' ? 'V2 已综合近期状态、主客场、攻防、赛程与人员信息' : item.analysis?.modelVersion === 'v2-market-official-history' ? 'V2 已综合体彩官方历史状态、主客场攻防和赛程' : '当前使用体彩市场概率'}，结果偏向${labels[strongest]}，${updateAt}。概率分析不代表结果保证。` : '体彩官方赛程已导入，胜平负固定奖尚未公布或暂停售。',
        saleStatus: item.sellStatus,
        predictedScore: item.analysis?.predictedScore ?? null,
        scoreProbabilities: item.analysis?.scoreProbabilities ?? [],
        predictedTotalGoals: item.analysis?.predictedTotalGoals ?? null,
        totalGoalsProbabilities: item.analysis?.totalGoalsProbabilities ?? null,
        over25Probability: item.analysis?.over25Probability ?? null,
        under25Probability: item.analysis?.under25Probability ?? null,
        expectedGoals: item.analysis?.expectedGoals ?? null,
        fundamentals: item.fundamentals ?? null,
        analysisSchedule: item.analysisSchedule ?? null,
        result: item.result ?? null,
        settlement: item.settlement ?? null,
      };
    });
    return { matches, recommendations, recommendationDecision, performance, updatedAt, businessDate, sourceMode };
  } catch (error) {
    return { matches: [], recommendations: [], recommendationDecision, performance, updatedAt, businessDate, sourceMode, error: error instanceof Error ? error.message : '体彩官方数据暂时不可用' };
  }
}
