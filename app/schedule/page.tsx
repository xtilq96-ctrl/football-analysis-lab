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
        <MappingStatus diagnostic={match.fundamentals?.mappingDiagnostic} confidence={match.fundamentals?.mappingConfidence} />
        <p className="mt-4 border-t border-white/7 pt-3 text-sm leading-6 text-white/45">{match.note}</p>
      </article>)}
      {!data.matches.length && <SectionCard title="暂无赛程"><p className="text-sm text-white/45">官方接口当前没有返回该业务日的比赛。</p></SectionCard>}
    </div>
    <p className="mt-5 text-sm text-white/40"><a href="/" className="text-lime-300 hover:underline">返回今日分析</a></p>
  </DashboardSectionShell>;
}

function MappingStatus({ diagnostic, confidence }: {
  diagnostic?: { status: 'matched' | 'date_unavailable' | 'team_name_mismatch' | 'time_or_coverage_mismatch'; reason: string; confidence: number };
  confidence?: number;
}) {
  if (!diagnostic) return <p className="mt-3 text-xs text-white/35">专业数据：等待服务器诊断</p>;
  const labels = {
    matched: `已匹配${confidence == null ? '' : ` · 置信度 ${Math.round(confidence * 100)}%`}`,
    date_unavailable: '该比赛日专业赛程不可用',
    team_name_mismatch: '球队名称待安全匹配',
    time_or_coverage_mismatch: '未找到时间相符比赛',
  };
  const tone = diagnostic.status === 'matched'
    ? 'border-emerald-300/20 bg-emerald-300/10 text-emerald-200'
    : diagnostic.status === 'date_unavailable'
      ? 'border-amber-300/20 bg-amber-300/10 text-amber-100'
      : 'border-orange-300/20 bg-orange-300/10 text-orange-100';
  return <div className="mt-3 flex flex-wrap items-center gap-2 text-xs">
    <span className={`rounded-full border px-2.5 py-1 ${tone}`}>专业数据：{labels[diagnostic.status]}</span>
    <span className="text-white/35">{diagnostic.reason}</span>
  </div>;
}

function Value({ label, value }: { label: string; value: string }) {
  return <div className="rounded-xl border border-white/7 bg-black/10 px-2 py-3"><p className="text-xs text-white/35">{label}</p><p className="mt-1 font-medium text-white/75">{value}</p></div>;
}
