import { DashboardSectionShell, SectionCard } from '@/components/dashboard-section-shell';
import { getDashboardData } from '@/lib/api-football';

export default async function SystemPage() {
  const data = await getDashboardData();
  const updatedAt = new Intl.DateTimeFormat('zh-CN', { timeZone: 'Asia/Shanghai', dateStyle: 'medium', timeStyle: 'short' }).format(new Date(data.updatedAt));
  const historyReady = data.matches.filter((match) => (match.fundamentals?.coverage ?? 0) >= 4).length;
  const lineups = data.matches.filter((match) => match.fundamentals?.home?.lineup.confirmed && match.fundamentals?.away?.lineup.confirmed).length;
  return <DashboardSectionShell active="/system" title="数据与任务" description="查看云端采集、历史回填、模型生成和赛果核对是否正常。">
    <div className="grid gap-4 md:grid-cols-2">
      <SectionCard title="中国体彩官方数据"><Rows rows={[["当日业务日", data.businessDate],["今日场次", `${data.matches.length}场`],["最近同步", updatedAt],["运行方式", "南京节点每5分钟"]]} /></SectionCard>
      <SectionCard title="球队历史基本面"><Rows rows={[["已生成", `${historyReady}/${data.matches.length}场`],["历史范围", "近120天体彩官方赛果"],["完整回填", "每天1次"],["增量更新", "每5分钟"]]} /></SectionCard>
      <SectionCard title="伤停与首发"><Rows rows={[["双方首发确认", `${lineups}场`],["当前状态", lineups ? "部分已取得" : "等待专业数据源"],["缺失处理", "不猜测、不修正"],["临场检查", "开赛前3小时"]]} /></SectionCard>
      <SectionCard title="自动复盘"><Rows rows={[["已核对赛果", `${data.performance.settledMatches}场`],["已核对组合", `${data.performance.settledCombinations ?? data.performance.settledTwoLegs}组`],["动态串数", "不推荐 / 2 / 3 / 4串1"],["预测锁定", "开赛前60分钟或21:00"],["运行状态", data.error ? "数据重试中" : "正常"]]} /></SectionCard>
    </div>
  </DashboardSectionShell>;
}

function Rows({ rows }: { rows: string[][] }) { return <div className="divide-y divide-white/7">{rows.map(([label,value]) => <div key={label} className="flex items-center justify-between gap-4 py-3 text-sm"><span className="text-white/45">{label}</span><b className="text-right font-medium text-white/75">{value}</b></div>)}</div>; }
