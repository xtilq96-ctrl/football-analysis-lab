import { DashboardSectionShell, SectionCard } from '@/components/dashboard-section-shell';
import { getDashboardData } from '@/lib/api-football';

export default async function SystemPage() {
  const data = await getDashboardData();
  const updatedAt = new Intl.DateTimeFormat('zh-CN', { timeZone: 'Asia/Shanghai', dateStyle: 'medium', timeStyle: 'short' }).format(new Date(data.updatedAt));
  const historyReady = data.matches.filter((match) => (match.fundamentals?.coverage ?? 0) >= 4).length;
  const lineups = data.matches.filter((match) => match.fundamentals?.home?.lineup.confirmed && match.fundamentals?.away?.lineup.confirmed).length;
  const operations = data.operations;
  const watchdog = operations?.watchdog;
  const report = data.dailyReports[0];
  const nextAnalysis = operations?.analysis.nextFinalAnalysisAt ? formatTime(operations.analysis.nextFinalAnalysisAt) : '今日已完成';
  const backupAt = operations?.backup.latestAt ? formatTime(operations.backup.latestAt) : '首次备份执行中';
  const apiUsage = operations?.apiFootball;
  const usagePercent = apiUsage ? Math.min(100, Math.round(apiUsage.used / apiUsage.dailyLimit * 100)) : 0;
  const apiTone = apiUsage?.mode === 'stopped' || apiUsage?.mode === 'lineups_only'
    ? 'border-amber-300/20 bg-amber-300/[.055]'
    : 'border-sky-300/20 bg-sky-300/[.055]';
  return <DashboardSectionShell active="/system" title="数据与任务" description="查看云端采集、历史回填、模型生成和赛果核对是否正常。">
    <section className={`mb-4 rounded-2xl border p-5 sm:p-6 ${watchdog?.status === 'warning' || data.error ? 'border-amber-300/20 bg-amber-300/[.055]' : 'border-emerald-300/20 bg-emerald-300/[.055]'}`}>
      <div className="flex flex-wrap items-center justify-between gap-3"><div><p className="text-sm text-white/45">无人值守守护</p><h2 className="mt-1 text-xl font-semibold text-white/85">{watchdog?.status === 'warning' || data.error ? '发现异常，正在自动重试' : '系统运行正常'}</h2></div><span className="rounded-full border border-white/10 bg-black/10 px-3 py-1 text-xs text-white/60">每5分钟检查</span></div>
      <p className="mt-3 text-sm leading-6 text-white/50">{watchdog?.errors?.length ? watchdog.errors.join('；') : '采集、网站快照和关键服务均在监控范围内；状态发生变化时会记录并通知。'}</p>
    </section>
    <section className={`mb-4 rounded-2xl border p-5 sm:p-6 ${apiTone}`}>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div><p className="text-sm text-white/45">API-Football 用量管家</p><h2 className="mt-1 text-xl font-semibold text-white/85">{apiUsage ? `${apiUsage.used} / ${apiUsage.dailyLimit} 次` : '等待服务器上报'}</h2></div>
        <span className="rounded-full border border-white/10 bg-black/10 px-3 py-1 text-xs text-white/65">{apiUsage?.modeLabel ?? '尚未启用'}</span>
      </div>
      <div className="mt-4 h-2 overflow-hidden rounded-full bg-black/25"><div className={`h-full rounded-full ${usagePercent >= 80 ? 'bg-amber-300' : 'bg-sky-300'}`} style={{ width: `${usagePercent}%` }} /></div>
      <div className="mt-4 grid gap-3 text-sm sm:grid-cols-4">
        <Metric label="正常可用" value={apiUsage ? `${apiUsage.safeRemaining}次` : '—'} />
        <Metric label="应急预留" value={apiUsage ? `${apiUsage.reserve}次` : '15次'} />
        <Metric label="最后调用" value={apiUsage?.lastRequestAt ? formatTime(apiUsage.lastRequestAt) : '今日尚未调用'} />
        <Metric label="预计重置" value={apiUsage?.nextResetAt ? formatTime(apiUsage.nextResetAt) : '等待上报'} />
      </div>
      <p className="mt-4 text-sm leading-6 text-white/50">达到60次后停止非必要查询；达到80次后只保留临场首发；达到85次自动停止并保留15次应急额度。</p>
    </section>
    <div className="grid gap-4 md:grid-cols-2">
      <SectionCard title="中国体彩官方数据"><Rows rows={[["当日业务日", data.businessDate],["今日场次", `${data.matches.length}场`],["最近同步", updatedAt],["运行方式", "南京节点每5分钟"]]} /></SectionCard>
      <SectionCard title="同步与自动恢复"><Rows rows={[["本地数据延迟", watchdog?.localDataAgeMinutes == null ? "等待首轮检查" : `${watchdog.localDataAgeMinutes}分钟`],["网站快照延迟", watchdog?.mirrorAgeMinutes == null ? "等待首轮检查" : `${watchdog.mirrorAgeMinutes}分钟`],["超时标准", `${operations?.collector.staleAfterMinutes ?? 15}分钟`],["自动重试", watchdog?.autoRetry === false ? "关闭" : "已开启"]]} /></SectionCard>
      <SectionCard title="分析时限"><Rows rows={[["分析已生成", `${operations?.analysis.readyMatches ?? data.matches.length}/${operations?.analysis.totalMatches ?? data.matches.length}场`],["已经锁定", `${operations?.analysis.lockedMatches ?? 0}场`],["下一次最终分析", nextAnalysis],["锁定规则", "开赛前60分钟或21:00"]]} /></SectionCard>
      <SectionCard title="球队历史基本面"><Rows rows={[["已生成", `${historyReady}/${data.matches.length}场`],["历史范围", "近120天体彩官方赛果"],["完整回填", "每天1次"],["增量更新", "每5分钟"]]} /></SectionCard>
      <SectionCard title="伤停与首发"><Rows rows={[["双方首发确认", `${lineups}场`],["当前状态", lineups ? "部分已取得" : "等待专业数据源"],["缺失处理", "不猜测、不修正"],["临场检查", "开赛前3小时"]]} /></SectionCard>
      <SectionCard title="分时刷新调度"><Rows rows={[["赛程匹配", apiUsage?.schedule.fixtures ?? "每6小时按日期批量刷新"],["伤停停赛", apiUsage?.schedule.injuries ?? "每4小时按日期批量刷新"],["临场首发", apiUsage?.schedule.lineups ?? "赛前180/90/45/20分钟"],["已确认首发", "停止重复查询"]]} /></SectionCard>
      <SectionCard title="今日接口明细"><Rows rows={apiUsage && Object.keys(apiUsage.byPurpose).length ? Object.entries(apiUsage.byPurpose).map(([label, value]) => [label, `${value}次`]) : [["状态", "今日尚无真实调用"],["计数规则", "只计算实际访问接口"]]} /></SectionCard>
      <SectionCard title="自动复盘"><Rows rows={[["已核对赛果", `${data.performance.settledMatches}场`],["已核对组合", `${data.performance.settledCombinations ?? data.performance.settledTwoLegs}组`],["动态串数", "不推荐 / 2 / 3 / 4串1"],["预测锁定", "开赛前60分钟或21:00"],["运行状态", data.error ? "数据重试中" : "正常"]]} /></SectionCard>
      <SectionCard title="最近一份每日复盘"><Rows rows={report ? [["体彩业务日", report.businessDate],["已结算", `${report.settledMatches}场`],["胜平负命中", rate(report.outcomeHitRate)],["总进球命中", rate(report.totalGoalsHitRate)]] : [["状态", "等待首批比赛完赛"],["生成方式", "赛果更新后自动生成"]]} /></SectionCard>
      <SectionCard title="数据库备份"><Rows rows={[["状态", operations?.backup.status === 'ok' ? "正常" : "准备中"],["最近备份", backupAt],["执行时间", "每天03:30"],["保留期限", `${operations?.backup.retentionDays ?? 30}天`]]} /></SectionCard>
    </div>
  </DashboardSectionShell>;
}

function Rows({ rows }: { rows: string[][] }) { return <div className="divide-y divide-white/7">{rows.map(([label,value]) => <div key={label} className="flex items-center justify-between gap-4 py-3 text-sm"><span className="text-white/45">{label}</span><b className="text-right font-medium text-white/75">{value}</b></div>)}</div>; }
function Metric({ label, value }: { label: string; value: string }) { return <div className="rounded-xl border border-white/8 bg-black/10 px-4 py-3"><p className="text-xs text-white/40">{label}</p><p className="mt-1 font-medium text-white/75">{value}</p></div>; }
function formatTime(value: string) { return new Intl.DateTimeFormat('zh-CN', { timeZone: 'Asia/Shanghai', dateStyle: 'short', timeStyle: 'short' }).format(new Date(value)); }
function rate(value: number | null) { return value == null ? '样本不足' : `${value}%`; }
