import { Badge } from '@/components/ui/badge';
import { DashboardSectionShell, SectionCard } from '@/components/dashboard-section-shell';
import { getDashboardData } from '@/lib/api-football';

export default async function LabPage() {
  const data = await getDashboardData();
  const decision = data.recommendationDecision;
  const selectedType = data.recommendations[0]?.type ?? (decision?.legCount ? `${decision.legCount}串1` : '今日不推荐');
  return <DashboardSectionShell active="/lab" title="策略实验室" description="系统按当日场次质量自动决定不推荐、2串1、3串1或4串1，不再固定生成某一种组合。">
    <div className="grid gap-4 xl:grid-cols-[1.4fr_.8fr]">
      <SectionCard title={`今日决策 · ${selectedType}`}>
        <div className={`mb-4 rounded-xl border p-4 ${decision?.status === 'no_pick' ? 'border-amber-400/15 bg-amber-400/[.055]' : 'border-lime-300/15 bg-lime-300/[.055]'}`}>
          <p className="text-sm font-medium text-white/80">{decision?.reason ?? '正在等待南京采集节点生成今日组合决策。'}</p>
          <p className="mt-1 text-xs text-white/40">符合单场初筛 {decision?.candidateCount ?? 0} 场 · 规则版本 {decision?.rulesVersion ?? '等待同步'}</p>
        </div>
        {data.recommendations.length ? <div className="space-y-3">{data.recommendations.map((item, index) => <div key={item.legs.map((leg) => leg.matchId).join('-')} className="rounded-xl border border-white/8 bg-black/10 p-4">
          <div className="flex items-center justify-between"><Badge className={index === 0 ? 'border-lime-300/20 bg-lime-300/10 text-lime-200' : 'border-white/10 bg-white/5 text-white/55'}>{index === 0 ? `首选 ${item.type ?? ''}` : `备选${index} ${item.type ?? ''}`}</Badge><span className="text-sm text-white/45">{item.level}{item.isLocked ? ' · 已锁定' : ' · 持续更新'}</span></div>
          {item.legs.map((leg) => <p key={leg.matchId} className="mt-3 text-sm text-white/70">{leg.officialNumber} · {leg.home} vs {leg.away} · <b>{leg.pick}</b> · {leg.probability}%</p>)}
          <p className="mt-3 border-t border-white/7 pt-3 text-xs text-white/40">组合概率 {item.combinedProbability}% · 参考倍数 {item.combinedOdds}{item.averageEdge !== undefined ? ` · 平均概率优势 ${signed(item.averageEdge)}%` : ''}</p>
          {item.basis && <p className="mt-2 text-xs leading-5 text-white/35">依据：{item.basis}</p>}
        </div>)}</div> : <p className="text-sm text-white/45">今日没有达到完整门槛的组合。系统会继续监测赔率和基本面，但不会为了凑数强行给出结果。</p>}
      </SectionCard>
      <SectionCard title="自动选择规则">
        <ol className="space-y-3 text-sm leading-6 text-white/55"><li>1. 排除已开赛、无固定奖和高风险场次。</li><li>2. 单场概率至少45%，且模型概率必须高于市场基准并覆盖固定奖成本。</li><li>3. 进入2串1需达到50%，三场或四场组合要求更高。</li><li>4. 同联赛过度集中会被降权或排除。</li><li>5. 最多展示3组，最早场锁定后不追改。</li><li>6. 所有组合只用于模型研究与回测。</li></ol>
      </SectionCard>
    </div>
  </DashboardSectionShell>;
}

function signed(value: number) { return `${value > 0 ? '+' : ''}${value}`; }
