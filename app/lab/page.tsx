import { Badge } from '@/components/ui/badge';
import { DashboardSectionShell, SectionCard } from '@/components/dashboard-section-shell';
import { getDashboardData } from '@/lib/api-football';

export default async function LabPage() {
  const data = await getDashboardData();
  return <DashboardSectionShell active="/lab" title="策略实验室" description="查看系统当前自动筛选的2串1组合和筛选规则。没有达到门槛时，系统宁可不推荐。">
    <div className="grid gap-4 xl:grid-cols-[1.4fr_.8fr]">
      <SectionCard title="今日自动2串1">
        {data.recommendations.length ? <div className="space-y-3">{data.recommendations.map((item, index) => <div key={item.legs.map((leg) => leg.matchId).join('-')} className="rounded-xl border border-white/8 bg-black/10 p-4"><div className="flex items-center justify-between"><Badge className={index === 0 ? 'border-lime-300/20 bg-lime-300/10 text-lime-200' : 'border-white/10 bg-white/5 text-white/55'}>{index === 0 ? '首选' : `备选${index}`}</Badge><span className="text-sm text-white/45">{item.level}</span></div>{item.legs.map((leg) => <p key={leg.matchId} className="mt-3 text-sm text-white/70">{leg.officialNumber} · {leg.home} vs {leg.away} · <b>{leg.pick}</b> · {leg.probability}%</p>)}<p className="mt-3 border-t border-white/7 pt-3 text-xs text-white/40">组合概率 {item.combinedProbability}% · 参考倍数 {item.combinedOdds}</p></div>)}</div> : <p className="text-sm text-white/45">当前没有两场同时达到最低概率要求，系统暂不生成组合。</p>}
      </SectionCard>
      <SectionCard title="筛选规则">
        <ol className="space-y-3 text-sm leading-6 text-white/55"><li>1. 单场最高概率至少42%。</li><li>2. 已开赛比赛自动排除。</li><li>3. 优先组合不同联赛，降低同类风险集中。</li><li>4. 每个业务日最多保留3组。</li><li>5. 按早场截止时间锁定，锁定后不追改结果。</li></ol>
      </SectionCard>
    </div>
  </DashboardSectionShell>;
}
