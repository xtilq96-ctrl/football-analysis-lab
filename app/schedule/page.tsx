import Link from 'next/link';
import { Badge } from '@/components/ui/badge';
import { DashboardSectionShell, SectionCard } from '@/components/dashboard-section-shell';
import { getDashboardData } from '@/lib/api-football';

export default async function SchedulePage() {
  const data = await getDashboardData();
  return <DashboardSectionShell active="/schedule" title="赛程中心" description={`${data.businessDate} 体彩业务日 · 官方编号只按当天业务日展示，共 ${data.matches.length} 场。`}>
    <div className="space-y-3">
      {data.matches.map((match) => <article id={`match-${match.id}`} key={match.id} className="scroll-mt-24 rounded-2xl border border-white/8 bg-white/[.035] p-4 sm:p-5">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-2"><Badge className="border-lime-300/20 bg-lime-300/10 text-lime-200">{match.officialNumber}</Badge><span className="text-sm text-white/45">{match.league} · {match.dateLabel} {match.time}</span></div>
          <span className="text-sm text-white/55">{match.analysisSchedule?.phase ?? '等待时间判断'}</span>
        </div>
        <div className="mt-4 grid gap-4 lg:grid-cols-[1fr_1.3fr] lg:items-center">
          <div><p className="text-lg font-semibold">{match.home} <span className="mx-2 text-sm font-normal text-white/25">vs</span> {match.away}</p><p className="mt-1 text-sm text-white/40">体彩胜平负：{match.averageOdds?.join(' / ') ?? '待公布'} · {match.handicapLine ? `让球 ${match.handicapLine}` : '让球待公布'}</p></div>
          <div className="grid grid-cols-4 gap-2 text-center text-sm"><Value label="推荐" value={match.probabilities ? ['主胜','平局','客胜'][match.probabilities.indexOf(Math.max(...match.probabilities))] : '等待'} /><Value label="比分" value={match.predictedScore ?? '—'} /><Value label="总进球" value={match.predictedTotalGoals ? `${match.predictedTotalGoals}球` : '—'} /><Value label="置信度" value={match.confidence === null ? '—' : `${match.confidence}%`} /></div>
        </div>
        <p className="mt-4 border-t border-white/7 pt-3 text-sm leading-6 text-white/45">{match.note}</p>
      </article>)}
      {!data.matches.length && <SectionCard title="暂无赛程"><p className="text-sm text-white/45">官方接口当前没有返回该业务日的比赛。</p></SectionCard>}
    </div>
    <p className="mt-5 text-sm text-white/40"><Link href="/" className="text-lime-300 hover:underline">返回今日分析</Link></p>
  </DashboardSectionShell>;
}

function Value({ label, value }: { label: string; value: string }) {
  return <div className="rounded-xl border border-white/7 bg-black/10 px-2 py-3"><p className="text-xs text-white/35">{label}</p><p className="mt-1 font-medium text-white/75">{value}</p></div>;
}
