import { DashboardSectionShell, SectionCard } from '@/components/dashboard-section-shell';
import { getDashboardData } from '@/lib/api-football';

export default async function EvaluationPage() {
  const data = await getDashboardData();
  const performance = data.performance;
  const probability = performance.probabilityEvaluation;
  const recent = performance.recent30;
  return <DashboardSectionShell active="/evaluation" title="模型评估" description="每场预测在截止时间锁定，完赛后自动核对胜平负、比分、总进球和概率质量；样本不足时不会据此升级模型。">
    <section className="rounded-2xl border border-lime-300/15 bg-lime-300/[.055] p-5 sm:p-6">
      <div className="flex flex-wrap items-end justify-between gap-3"><div><h2 className="text-base font-medium">真实赛果验证</h2><p className="mt-1 text-sm text-white/45">累计结果与最近30场同时展示，防止历史平均掩盖近期退化。</p></div><span className="text-xs text-white/35">概率误差越低越好</span></div>
      <div className="mt-4 grid grid-cols-2 gap-3 md:grid-cols-4"><Metric label="已核对比赛" value={`${performance.settledMatches}场`} /><Metric label="胜平负命中" value={rate(performance.outcomeHitRate)} /><Metric label="大小2.5命中" value={rate(performance.overUnderHitRate)} /><Metric label="总进球命中" value={rate(performance.totalGoalsHitRate)} /><Metric label="概率样本" value={`${probability?.sampleSize ?? 0}场`} /><Metric label="Brier误差" value={score(probability?.brierScore)} /><Metric label="最近30场命中" value={rate(recent?.outcomeHitRate ?? null)} /><Metric label="校准偏差" value={performance.calibrationError == null ? '样本不足' : `${performance.calibrationError}点`} /></div>
    </section>

    <div className="mt-4 grid gap-4 xl:grid-cols-[1.2fr_.8fr]">
      <SectionCard title="概率校准">
        {performance.calibration?.length ? <div className="overflow-x-auto"><table className="w-full min-w-[520px] text-left text-sm"><thead className="text-white/35"><tr className="border-b border-white/8"><th className="pb-3 font-normal">模型置信度</th><th className="pb-3 font-normal">样本</th><th className="pb-3 font-normal">平均预测</th><th className="pb-3 font-normal">实际命中</th><th className="pb-3 font-normal">偏差</th></tr></thead><tbody>{performance.calibration.map((item) => <tr key={item.label} className="border-b border-white/6 last:border-0"><td className="py-3 text-white/70">{item.label}</td><td className="py-3 text-white/45">{item.sampleSize}场</td><td className="py-3 text-white/60">{item.averageConfidence}%</td><td className="py-3 text-white/60">{item.actualHitRate}%</td><td className={`py-3 ${Math.abs(item.gap) <= 8 ? 'text-emerald-300' : 'text-amber-300'}`}>{signed(item.gap)}点</td></tr>)}</tbody></table></div> : <p className="text-sm text-white/45">新评估字段已启用，等待后续完赛样本形成校准分组。</p>}
      </SectionCard>
      <SectionCard title="组合回测">
        <div className="space-y-3">{(performance.combinationStats ?? []).map((item) => <div key={item.legCount} className="flex items-center justify-between rounded-xl border border-white/8 bg-black/10 p-4"><div><p className="text-sm text-white/70">{item.legCount}串1</p><p className="mt-1 text-xs text-white/35">已核对 {item.settled} 组 · 命中 {item.hits} 组</p></div><b className="text-lg text-white/80">{rate(item.hitRate)}</b></div>)}</div>
        <p className="mt-3 text-xs leading-5 text-white/35">不同串数分开统计。组合只有在最早场锁定后才进入正式回测，避免把临时方案混入成绩。</p>
      </SectionCard>
    </div>

    <div className="mt-4 grid gap-4 xl:grid-cols-2">
      <SectionCard title="算法口径"><p className="text-sm leading-7 text-white/55">胜平负先由体彩固定奖去水，再用近期状态、主客场攻防和赛程做有限修正。比分与总进球来自和胜平负概率相匹配的泊松分布。</p><p className="mt-3 text-sm leading-7 text-white/55">Brier误差和对数损失用于衡量概率本身是否可靠，不只判断最高概率选项有没有猜中。</p></SectionCard>
      <SectionCard title="升级纪律"><p className="text-sm leading-7 text-white/55">当前数据只用于持续观察。达到足够样本后，候选模型必须同时通过命中率、概率校准和近期稳定性测试，才允许升级；否则继续保留现有模型。</p><p className="mt-3 text-xs text-white/35">历史表现不代表未来结果，系统不作收益承诺。</p></SectionCard>
    </div>
  </DashboardSectionShell>;
}

function rate(value: number | null | undefined) { return value == null ? '样本不足' : `${value}%`; }
function score(value: number | null | undefined) { return value == null ? '样本不足' : value.toFixed(4); }
function signed(value: number) { return `${value > 0 ? '+' : ''}${value}`; }
function Metric({ label, value }: { label: string; value: string }) { return <div className="rounded-xl border border-white/8 bg-black/10 p-4"><p className="text-xs text-white/38">{label}</p><p className="mt-1 text-xl font-semibold text-white/80">{value}</p></div>; }
