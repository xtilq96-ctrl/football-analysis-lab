import { DashboardSectionShell, SectionCard } from '@/components/dashboard-section-shell';
import { getDashboardData } from '@/lib/api-football';

export default async function EvaluationPage() {
  const data = await getDashboardData();
  const performance = data.performance;
  return <DashboardSectionShell active="/evaluation" title="模型评估" description="公开展示系统怎样从体彩固定奖得到胜平负概率，再计算比分和总进球；历史命中率只统计已经完赛并自动核对的样本。">
    <div className="grid gap-4 xl:grid-cols-2">
      <SectionCard title="1. 胜平负概率">
        <p className="text-sm leading-7 text-white/55">先把体彩胜、平、负固定奖分别转换成隐含概率：<b className="text-white/80">1 ÷ 固定奖</b>。三项相加通常超过100%，系统再除以三项总和完成“去水”，得到市场基准概率。</p>
        <p className="mt-3 text-sm leading-7 text-white/55">有历史样本时，再结合近10场积分、进失球、零封率、主客场表现、休息天数和14天赛程密度进行有限修正。修正幅度设有上限，避免少量历史数据压过体彩市场信息。</p>
      </SectionCard>
      <SectionCard title="2. 比分概率">
        <p className="text-sm leading-7 text-white/55">系统寻找一组主队与客队期望进球，使泊松模型计算出的主胜、平局、客胜概率尽量接近修正后的胜平负概率。然后计算0～10球的联合概率，例如“主队进1球概率 × 客队进0球概率”得到1-0概率。</p>
        <p className="mt-3 text-sm leading-7 text-white/55">页面的模型比分是与预测赛果方向一致的最高概率比分，同时保存概率最高的前5个比分。它不是确定结果。</p>
      </SectionCard>
      <SectionCard title="3. 总进球数">
        <p className="text-sm leading-7 text-white/55">主队期望进球与客队期望进球相加，得到全场总期望进球。再用泊松分布计算0、1、2、3……球各自概率，概率最高的一档作为总进球参考；3球及以上的概率合计为“大2.5”。</p>
      </SectionCard>
      <SectionCard title="4. 数据边界">
        <p className="text-sm leading-7 text-white/55">免费基本面来自近120天中国体彩已收录比赛，不代表球队全部正式比赛。伤停和首发没有可靠专业源时不会参与修正，并在页面明确显示“等待专业源”。</p>
      </SectionCard>
    </div>
    <section className="mt-4 rounded-2xl border border-lime-300/15 bg-lime-300/[.055] p-5 sm:p-6"><h2 className="text-base font-medium">当前历史验证</h2><div className="mt-4 grid grid-cols-2 gap-3 md:grid-cols-4"><Metric label="已核对比赛" value={`${performance.settledMatches}场`} /><Metric label="胜平负命中" value={rate(performance.outcomeHitRate)} /><Metric label="总进球命中" value={rate(performance.totalGoalsHitRate)} /><Metric label="2串1命中" value={rate(performance.twoLegHitRate)} /></div><p className="mt-4 text-xs leading-5 text-white/40">样本越少，命中率波动越大。系统不会用命中率承诺未来结果。</p></section>
  </DashboardSectionShell>;
}

function rate(value: number | null) { return value === null ? '样本不足' : `${value}%`; }
function Metric({ label, value }: { label: string; value: string }) { return <div className="rounded-xl border border-white/8 bg-black/10 p-4"><p className="text-xs text-white/38">{label}</p><p className="mt-1 text-xl font-semibold text-white/80">{value}</p></div>; }
