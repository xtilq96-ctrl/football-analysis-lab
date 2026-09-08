import {
  Activity, BarChart3, Bell, CalendarDays, ChevronRight, CircleAlert, Clock3,
  Database, Gauge, ShieldCheck, Sparkles, Trophy,
} from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Progress } from '@/components/ui/progress';
import { getDashboardData, type DashboardMatch, type DashboardRecommendation } from '@/lib/api-football';

const riskStyles = {
  green: 'border-emerald-400/25 bg-emerald-400/10 text-emerald-300',
  amber: 'border-amber-400/25 bg-amber-400/10 text-amber-300',
  red: 'border-rose-400/25 bg-rose-400/10 text-rose-300',
};

export default async function Home() {
  const data = await getDashboardData();
  const updatedAt = new Intl.DateTimeFormat('zh-CN', {
    timeZone: 'Asia/Shanghai', hour: '2-digit', minute: '2-digit', hour12: false,
  }).format(new Date(data.updatedAt));
  const predicted = data.matches.filter((match) => match.probabilities).length;
  const withOdds = data.matches.filter((match) => match.marketProbabilities).length;
  const completeness = data.matches.length ? Math.round((predicted / data.matches.length) * 100) : 0;
  const numberRange = data.matches.length
    ? `${data.matches[0].officialNumber}–${data.matches[data.matches.length - 1].officialNumber.slice(-3)}`
    : '暂无场次';

  return (
    <main className="min-h-screen bg-background pb-20 text-foreground lg:pb-0">
      <header className="sticky top-0 z-20 border-b border-white/8 bg-[#07110d]/90 backdrop-blur-xl">
        <div className="mx-auto flex h-16 max-w-[1440px] items-center justify-between px-4 sm:px-6 lg:px-8">
          <div className="flex items-center gap-3">
            <div className="grid h-9 w-9 place-items-center rounded-xl bg-lime-300 text-[#07110d] shadow-[0_0_24px_rgba(190,242,100,.16)]"><Trophy className="h-[19px] w-[19px]" /></div>
            <div><p className="text-[15px] font-semibold leading-tight tracking-tight">足球 AI 分析台</p><p className="text-xs text-white/45">中国竞彩足球</p></div>
          </div>
          <div className="flex items-center gap-2">
            <Badge className={`hidden sm:inline-flex ${data.error ? 'border-amber-400/20 bg-amber-400/10 text-amber-300' : 'border-emerald-400/20 bg-emerald-400/10 text-emerald-300'}`}><span className={`mr-1.5 h-1.5 w-1.5 rounded-full ${data.error ? 'bg-amber-300' : 'bg-emerald-300'}`} />{data.error ? '等待数据' : '接口已连接'}</Badge>
            <Button aria-label="查看通知" size="icon" variant="ghost" className="text-white/65 hover:bg-white/7 hover:text-white"><Bell className="h-[18px] w-[18px]" /></Button>
          </div>
        </div>
      </header>

      <div className="mx-auto grid max-w-[1440px] gap-6 px-4 py-6 sm:px-6 lg:grid-cols-[220px_minmax(0,1fr)_300px] lg:px-8 lg:py-8">
        <aside className="hidden lg:block">
          <nav className="sticky top-24 space-y-1" aria-label="主要导航">
            <NavItem icon={<Sparkles />} label="今日分析" active />
            <NavItem icon={<CalendarDays />} label="赛程中心" />
            <NavItem icon={<BarChart3 />} label="模型评估" />
            <NavItem icon={<Gauge />} label="策略实验室" />
            <NavItem icon={<Database />} label="数据与任务" />
          </nav>
          <div className="mt-8 rounded-2xl border border-white/8 bg-white/[.025] p-4">
            <div className="flex items-center gap-2 text-sm font-medium text-white/80"><ShieldCheck className="h-4 w-4 text-lime-300" />研究模式</div>
            <p className="mt-2 text-xs leading-5 text-white/40">仅做概率分析与模拟回测，不连接真实资金。</p>
          </div>
        </aside>

        <section className="min-w-0">
          <div className="mb-5 flex flex-col justify-between gap-4 sm:flex-row sm:items-end">
            <div>
              <div className="mb-2 flex items-center gap-2 text-sm text-lime-300"><Activity className="h-4 w-4" />中国体彩官方竞彩赛程</div>
              <h1 className="text-2xl font-semibold tracking-[-0.035em] sm:text-[2rem]">今日竞彩足球</h1>
              <p className="mt-1.5 text-sm text-white/45">{data.businessDate} · {numberRange} · 共 {data.matches.length} 场 · 最近同步 {updatedAt}</p>
            </div>
            <div className="flex items-center gap-2 rounded-xl border border-white/8 bg-white/[.035] px-3 py-2 text-sm text-white/65"><CalendarDays className="h-4 w-4 text-white/40" />体彩业务日</div>
          </div>

          <div className={`mb-5 flex items-start gap-3 rounded-2xl p-4 text-sm ${data.error ? 'border border-amber-400/15 bg-amber-400/[.065] text-amber-100/75' : 'border border-sky-400/15 bg-sky-400/[.065] text-sky-100/75'}`}>
            <CircleAlert className={`mt-0.5 h-4 w-4 shrink-0 ${data.error ? 'text-amber-300' : 'text-sky-300'}`} />
            <p>{data.error ? <><span className="font-medium">官方数据暂时未返回：</span>{data.error}。系统会在下次访问时重试。</> : data.sourceMode === 'verified_snapshot' ? <><span className="font-medium text-sky-200">已显示官方核验快照。</span> 自动采集数据暂时不可用，页面会继续重试。</> : data.sourceMode === 'mainland_relay' ? <><span className="font-medium text-sky-200">南京采集节点运行正常。</span> 每5分钟读取中国体育彩票官方数据并校验签名，已开赛场次与赔率变化持续留存。</> : <><span className="font-medium text-sky-200">官方数据已连接。</span> 场次、时间和固定奖来自中国体育彩票公开接口；概率由官方固定奖去水换算。</>}</p>
          </div>

          <RecommendationPanel recommendations={data.recommendations} />

          {data.matches.length ? (
            <div className="space-y-4">{data.matches.map((match) => <MatchCard key={match.id} match={match} />)}</div>
          ) : (
            <Card className="border-white/8 bg-white/[.035] shadow-none"><CardContent className="py-14 text-center"><p className="text-white/70">当前没有可展示的未开赛重点比赛</p><p className="mt-2 text-sm text-white/35">数据源恢复或产生新赛程后会自动出现。</p></CardContent></Card>
          )}
        </section>

        <aside className="space-y-4">
          <Card className="border-white/8 bg-white/[.035] shadow-none">
            <CardHeader className="pb-3"><CardTitle className="flex items-center justify-between text-base font-medium">数据运行状态<span className={`h-2 w-2 rounded-full ${data.error ? 'bg-amber-300' : 'bg-emerald-300 shadow-[0_0_12px_rgba(110,231,183,.65)]'}`} /></CardTitle></CardHeader>
            <CardContent className="space-y-4">
              <StatusRow label="体彩官方赛程" value={data.error ? '重试中' : '已导入'} meta={`${data.matches.length} 场 · ${updatedAt}`} muted={Boolean(data.error)} />
              <StatusRow label="官方固定奖" value={withOdds ? '已接入' : '等待中'} meta={`${withOdds}/${data.matches.length} 场`} muted={!withOdds} />
              <StatusRow label="去水概率" value={predicted ? '已生成' : '等待中'} meta={`${predicted}/${data.matches.length} 场`} muted={!predicted} />
              <StatusRow label="赛果自动结算" value={data.performance.settledMatches ? '已运行' : '等待完赛'} meta={`${data.performance.settledMatches} 场已核对`} muted={!data.performance.settledMatches} />
              <StatusRow label="数据模式" value={data.sourceMode === 'mainland_relay' ? '大陆自动采集' : data.sourceMode === 'live' ? '官方直连' : '官方快照'} meta={data.sourceMode === 'mainland_relay' ? '每 5 分钟更新' : data.sourceMode === 'live' ? '实时读取' : '自动恢复中'} muted={data.sourceMode === 'verified_snapshot'} />
            </CardContent>
          </Card>
          <Card className="overflow-hidden border-lime-300/12 bg-[linear-gradient(145deg,rgba(190,242,100,.09),rgba(255,255,255,.025))] shadow-none">
            <CardContent className="p-5">
              <div className="flex items-center justify-between"><p className="text-sm font-medium text-white/75">预测数据覆盖</p><span className="text-xl font-semibold text-lime-300">{completeness}</span></div>
              <Progress value={completeness} className="mt-3 h-1.5 bg-white/8 [&_[data-slot=progress-indicator]]:bg-lime-300" />
              <p className="mt-3 text-xs leading-5 text-white/40">体彩固定奖去水概率已上线；API-Football 后续仅作为球队状态、伤停和比赛统计的辅助源。</p>
            </CardContent>
          </Card>
          <Card className="border-white/8 bg-white/[.035] shadow-none">
            <CardHeader className="pb-3"><CardTitle className="text-base font-medium">历史验证</CardTitle></CardHeader>
            <CardContent className="grid grid-cols-2 gap-3 text-sm">
              <Metric label="胜平负命中" value={data.performance.outcomeHitRate === null ? '—' : String(data.performance.outcomeHitRate)} unit={data.performance.outcomeHitRate === null ? '' : '%'} />
              <Metric label="大小2.5命中" value={data.performance.overUnderHitRate === null ? '—' : String(data.performance.overUnderHitRate)} unit={data.performance.overUnderHitRate === null ? '' : '%'} />
              <Metric label="精确比分命中" value={data.performance.exactScoreHitRate === null ? '—' : String(data.performance.exactScoreHitRate)} unit={data.performance.exactScoreHitRate === null ? '' : '%'} />
              <Metric label="2串1命中" value={data.performance.twoLegHitRate === null ? '—' : String(data.performance.twoLegHitRate)} unit={data.performance.twoLegHitRate === null ? '' : '%'} />
            </CardContent>
          </Card>
          <div className="grid grid-cols-2 gap-3 lg:grid-cols-1 xl:grid-cols-2"><Metric label="今日竞彩" value={String(data.matches.length)} unit="场" /><Metric label="固定奖覆盖" value={String(completeness)} unit="%" /></div>
        </aside>
      </div>

      <nav className="fixed inset-x-0 bottom-0 z-30 grid grid-cols-4 border-t border-white/8 bg-[#07110d]/95 px-2 pb-[max(.5rem,env(safe-area-inset-bottom))] pt-2 backdrop-blur-xl lg:hidden" aria-label="移动端导航">
        <MobileNav icon={<Sparkles />} label="今日" active /><MobileNav icon={<CalendarDays />} label="赛程" /><MobileNav icon={<BarChart3 />} label="评估" /><MobileNav icon={<Database />} label="系统" />
      </nav>
    </main>
  );
}

function MatchCard({ match }: { match: DashboardMatch }) {
  const [home, draw, away] = match.probabilities ?? [0, 0, 0];
  return (
    <Card className="group border-white/8 bg-white/[.035] py-0 shadow-none transition-colors hover:border-white/15 hover:bg-white/[.05]">
      <CardContent className="p-5 sm:p-6">
        <div className="flex items-center justify-between gap-3">
          <div className="flex min-w-0 items-center gap-2 text-xs text-white/42"><Badge className="border-lime-300/20 bg-lime-300/10 text-lime-200">{match.officialNumber}</Badge><span className="truncate">{match.league}</span><span>·</span><span>{match.dateLabel}</span><Clock3 className="h-3.5 w-3.5" /><span>{match.time}</span></div>
          <Badge variant="outline" className={riskStyles[match.riskTone]}>{match.risk}</Badge>
        </div>
        <div className="mt-5 grid items-center gap-5 sm:grid-cols-[minmax(170px,.8fr)_minmax(280px,1.2fr)_auto]">
          <div><div className="flex items-center gap-3 text-lg font-semibold tracking-tight"><span>{match.home}</span><span className="text-sm font-normal text-white/25">vs</span><span>{match.away}</span></div><p className="mt-1 text-xs text-white/35">{match.goals} · {match.confidence === null ? '等待固定奖' : `官方去水最高概率 ${match.confidence}%`}</p></div>
          <div>
            {match.probabilities ? <><div className="mb-2 flex justify-between text-xs text-white/45"><span>主胜 <b className="ml-1 font-semibold text-white/85">{home}%</b></span><span>平局 <b className="ml-1 font-semibold text-white/85">{draw}%</b></span><span>客胜 <b className="ml-1 font-semibold text-white/85">{away}%</b></span></div><div className="flex h-2 overflow-hidden rounded-full bg-white/5"><span className="bg-lime-300" style={{ width: `${home}%` }} /><span className="bg-sky-400" style={{ width: `${draw}%` }} /><span className="bg-violet-400" style={{ width: `${away}%` }} /></div></> : <p className="text-sm text-white/35">预测数据等待下一次同步</p>}
          </div>
          <Button variant="ghost" size="sm" className="justify-self-start text-white/60 hover:bg-white/7 hover:text-white sm:justify-self-end">分析摘要 <ChevronRight className="h-4 w-4" /></Button>
        </div>
        {match.averageOdds && match.marketProbabilities && <div className="mt-4 grid gap-2 rounded-xl border border-white/7 bg-black/10 p-3 text-xs text-white/45 sm:grid-cols-3"><span>体彩胜平负 <b className="ml-1 text-white/75">{match.averageOdds.join(' / ')}</b></span><span>官方去水概率 <b className="ml-1 text-white/75">{match.marketProbabilities.join('% / ')}%</b></span><span>{match.handicapLine ? `让球 ${match.handicapLine}` : '让球'} <b className="ml-1 text-white/75">{match.handicapOdds?.join(' / ') ?? '待公布'}</b>{match.marketMargin !== null && ` · 理论返还前利润 ${match.marketMargin}%`}</span></div>}
        {match.predictedScore && <div className="mt-3 rounded-xl border border-violet-400/12 bg-violet-400/[.055] p-3">
          <div className="flex flex-wrap items-center gap-x-5 gap-y-2 text-xs text-white/55">
            <span>模型比分 <b className="ml-1 text-violet-200">{match.predictedScore}</b></span>
            <span>总进球 <b className="ml-1 text-violet-200">{match.predictedTotalGoals} 球</b></span>
            <span>期望进球 <b className="ml-1 text-violet-200">{match.expectedGoals?.home}–{match.expectedGoals?.away}</b></span>
            <span>大 2.5 <b className="ml-1 text-violet-200">{match.over25Probability}%</b></span>
          </div>
          <div className="mt-2 flex flex-wrap gap-1.5">{match.scoreProbabilities.slice(0, 3).map((score) => <Badge key={score.score} variant="outline" className="border-white/10 text-white/55">{score.score} · {score.probability}%</Badge>)}</div>
        </div>}
        {match.result && <div className="mt-3 flex flex-wrap items-center justify-between gap-2 rounded-xl border border-emerald-400/15 bg-emerald-400/[.06] p-3 text-sm"><span className="text-white/65">官方赛果 <b className="ml-1 text-emerald-200">{match.result.fullTimeScore} · {match.result.actualOutcome}</b></span><span className={match.settlement?.outcomeHit ? 'text-emerald-300' : 'text-rose-300'}>{match.settlement?.outcomeHit ? '胜平负命中' : '胜平负未命中'}</span></div>}
        <p className="mt-4 border-t border-white/7 pt-4 text-sm leading-6 text-white/48">{match.note}</p>
      </CardContent>
    </Card>
  );
}

function RecommendationPanel({ recommendations }: { recommendations: DashboardRecommendation[] }) {
  return (
    <Card className="mb-5 border-lime-300/15 bg-[linear-gradient(135deg,rgba(190,242,100,.08),rgba(255,255,255,.025))] shadow-none">
      <CardHeader className="pb-3">
        <CardTitle className="flex flex-wrap items-center justify-between gap-2 text-base font-medium">
          <span className="flex items-center gap-2"><Sparkles className="h-4 w-4 text-lime-300" />自动 2 串 1</span>
          <span className="text-xs font-normal text-white/35">V1 市场概率 + 泊松比分模型</span>
        </CardTitle>
      </CardHeader>
      <CardContent>
        {recommendations.length ? <div className="grid gap-3 xl:grid-cols-3">{recommendations.map((recommendation, index) => (
          <div key={recommendation.legs.map((leg) => leg.matchId).join('-')} className="rounded-xl border border-white/8 bg-black/10 p-3">
            <div className="mb-2 flex items-center justify-between"><Badge className={index === 0 ? 'border-lime-300/20 bg-lime-300/10 text-lime-200' : 'border-white/10 bg-white/5 text-white/55'}>{index === 0 ? '首选' : `备选 ${index}`}</Badge><span className="text-xs text-white/38">{recommendation.level}</span></div>
            <div className="space-y-2">{recommendation.legs.map((leg) => <div key={leg.matchId} className="text-sm"><p className="text-white/75">{leg.officialNumber} · {leg.pick} <span className="text-xs text-white/35">@ {leg.odds}</span></p><p className="truncate text-xs text-white/35">{leg.home} vs {leg.away} · {leg.probability}%</p></div>)}</div>
            <div className="mt-3 flex justify-between border-t border-white/7 pt-2 text-xs text-white/40"><span>组合概率 {recommendation.combinedProbability}%</span><span>参考倍数 {recommendation.combinedOdds}</span></div>
          </div>
        ))}</div> : <p className="text-sm text-white/45">当前没有同时达到最低概率要求的两场组合，系统选择不推荐。</p>}
        <p className="mt-3 text-xs leading-5 text-white/35">只在模型概率达到门槛时生成组合；概率与参考倍数用于研究和回测，不代表收益保证。</p>
      </CardContent>
    </Card>
  );
}

function NavItem({ icon, label, active = false }: { icon: React.ReactNode; label: string; active?: boolean }) {
  return <button className={`flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-left text-sm transition ${active ? 'bg-lime-300 font-medium text-[#07110d]' : 'text-white/50 hover:bg-white/5 hover:text-white/85'}`}><span className="[&>svg]:h-[17px] [&>svg]:w-[17px]">{icon}</span>{label}</button>;
}

function MobileNav({ icon, label, active = false }: { icon: React.ReactNode; label: string; active?: boolean }) {
  return <button className={`flex flex-col items-center gap-1 text-[11px] ${active ? 'text-lime-300' : 'text-white/40'}`}><span className="[&>svg]:h-5 [&>svg]:w-5">{icon}</span>{label}</button>;
}

function StatusRow({ label, value, meta, muted = false }: { label: string; value: string; meta: string; muted?: boolean }) {
  return <div className="flex items-center justify-between gap-3"><div><p className="text-sm text-white/65">{label}</p><p className="mt-0.5 text-xs text-white/30">{meta}</p></div><span className={`text-xs ${muted ? 'text-amber-300' : 'text-emerald-300'}`}>{value}</span></div>;
}

function Metric({ label, value, unit }: { label: string; value: string; unit: string }) {
  return <div className="rounded-2xl border border-white/8 bg-white/[.03] p-4"><p className="text-xs text-white/38">{label}</p><p className="mt-1 text-2xl font-semibold tracking-tight">{value}<span className="ml-1 text-sm font-normal text-white/35">{unit}</span></p></div>;
}
