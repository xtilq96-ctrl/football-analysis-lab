import {
  Activity,
  BarChart3,
  Bell,
  CalendarDays,
  ChevronRight,
  CircleAlert,
  Clock3,
  Database,
  Gauge,
  ShieldCheck,
  Sparkles,
  Trophy,
} from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Progress } from '@/components/ui/progress';

const matches = [
  { league: '英格兰超级联赛', time: '20:30', home: '曼城', away: '利物浦', probabilities: [44, 27, 29], goals: '2–4 球', confidence: 78, risk: '中风险', riskTone: 'amber', note: '双方近期进攻效率较高，成员模型对主胜判断存在分歧。' },
  { league: '英格兰超级联赛', time: '23:00', home: '阿森纳', away: '布莱顿', probabilities: [61, 23, 16], goals: '2–3 球', confidence: 86, risk: '低风险', riskTone: 'green', note: '球队强度与市场基线方向一致，当前数据覆盖较完整。' },
  { league: '英格兰超级联赛', time: '01:30', home: '切尔西', away: '纽卡斯尔联', probabilities: [39, 29, 32], goals: '1–3 球', confidence: 64, risk: '高风险', riskTone: 'red', note: '胜负概率接近，建议等待临场阵容和最后赔率快照。' },
];

const riskStyles = {
  green: 'border-emerald-400/25 bg-emerald-400/10 text-emerald-300',
  amber: 'border-amber-400/25 bg-amber-400/10 text-amber-300',
  red: 'border-rose-400/25 bg-rose-400/10 text-rose-300',
};

export default function Home() {
  return (
    <main className="min-h-screen bg-background text-foreground">
      <header className="sticky top-0 z-20 border-b border-white/8 bg-[#07110d]/90 backdrop-blur-xl">
        <div className="mx-auto flex h-16 max-w-[1440px] items-center justify-between px-4 sm:px-6 lg:px-8">
          <div className="flex items-center gap-3">
            <div className="grid h-9 w-9 place-items-center rounded-xl bg-lime-300 text-[#07110d] shadow-[0_0_24px_rgba(190,242,100,.16)]"><Trophy className="h-[19px] w-[19px]" /></div>
            <div><p className="text-[15px] font-semibold leading-tight tracking-tight">足球 AI 分析台</p><p className="text-xs text-white/45">云端运行中</p></div>
          </div>
          <div className="flex items-center gap-2">
            <Badge className="hidden border-emerald-400/20 bg-emerald-400/10 text-emerald-300 sm:inline-flex"><span className="mr-1.5 h-1.5 w-1.5 rounded-full bg-emerald-300" />系统正常</Badge>
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
              <div className="mb-2 flex items-center gap-2 text-sm text-lime-300"><Activity className="h-4 w-4" />今日首版已生成</div>
              <h1 className="text-2xl font-semibold tracking-[-0.035em] sm:text-[2rem]">今日比赛分析</h1>
              <p className="mt-1.5 text-sm text-white/45">3 场重点观察 · 下次更新 18:30 · 开赛前 15 分钟冻结</p>
            </div>
            <div className="flex items-center gap-2 rounded-xl border border-white/8 bg-white/[.035] px-3 py-2 text-sm text-white/65"><CalendarDays className="h-4 w-4 text-white/40" />今日<span className="text-white/25">·</span>北京时间</div>
          </div>

          <div className="mb-5 flex items-start gap-3 rounded-2xl border border-sky-400/15 bg-sky-400/[.065] p-4 text-sm text-sky-100/75">
            <CircleAlert className="mt-0.5 h-4 w-4 shrink-0 text-sky-300" />
            <p><span className="font-medium text-sky-200">当前为界面演示数据。</span> 正式数据供应商接入并通过质量检查后，才会展示真实分析结果。</p>
          </div>

          <div className="space-y-4">{matches.map((match) => <MatchCard key={`${match.home}-${match.away}`} match={match} />)}</div>
        </section>

        <aside className="space-y-4">
          <Card className="border-white/8 bg-white/[.035] shadow-none">
            <CardHeader className="pb-3"><CardTitle className="flex items-center justify-between text-base font-medium">数据运行状态<span className="h-2 w-2 rounded-full bg-emerald-300 shadow-[0_0_12px_rgba(110,231,183,.65)]" /></CardTitle></CardHeader>
            <CardContent className="space-y-4">
              <StatusRow label="赛程数据" value="已更新" meta="2 分钟前" />
              <StatusRow label="赔率快照" value="正常" meta="5 分钟前" />
              <StatusRow label="伤停信息" value="待接入" meta="未配置" muted />
              <StatusRow label="赛后复盘" value="已完成" meta="昨日 23 场" />
            </CardContent>
          </Card>
          <Card className="overflow-hidden border-lime-300/12 bg-[linear-gradient(145deg,rgba(190,242,100,.09),rgba(255,255,255,.025))] shadow-none">
            <CardContent className="p-5">
              <div className="flex items-center justify-between"><p className="text-sm font-medium text-white/75">模型健康度</p><span className="text-xl font-semibold text-lime-300">82</span></div>
              <Progress value={82} className="mt-3 h-1.5 bg-white/8 [&_[data-slot=progress-indicator]]:bg-lime-300" />
              <p className="mt-3 text-xs leading-5 text-white/40">统计基线、球队强度与市场模型运行正常。机器学习模型尚未进入正式融合。</p>
            </CardContent>
          </Card>
          <div className="grid grid-cols-2 gap-3 lg:grid-cols-1 xl:grid-cols-2"><Metric label="今日覆盖" value="3" unit="场" /><Metric label="数据完整度" value="91" unit="%" /></div>
        </aside>
      </div>

      <nav className="fixed inset-x-0 bottom-0 z-30 grid grid-cols-4 border-t border-white/8 bg-[#07110d]/95 px-2 pb-[max(.5rem,env(safe-area-inset-bottom))] pt-2 backdrop-blur-xl lg:hidden" aria-label="移动端导航">
        <MobileNav icon={<Sparkles />} label="今日" active /><MobileNav icon={<CalendarDays />} label="赛程" /><MobileNav icon={<BarChart3 />} label="评估" /><MobileNav icon={<Database />} label="系统" />
      </nav>
    </main>
  );
}

function MatchCard({ match }: { match: (typeof matches)[number] }) {
  const [home, draw, away] = match.probabilities;
  return (
    <Card className="group border-white/8 bg-white/[.035] py-0 shadow-none transition-colors hover:border-white/15 hover:bg-white/[.05]">
      <CardContent className="p-5 sm:p-6">
        <div className="flex items-center justify-between gap-3">
          <div className="flex min-w-0 items-center gap-2 text-xs text-white/42"><span className="truncate">{match.league}</span><span>·</span><Clock3 className="h-3.5 w-3.5" /><span>{match.time}</span></div>
          <Badge variant="outline" className={riskStyles[match.riskTone as keyof typeof riskStyles]}>{match.risk}</Badge>
        </div>
        <div className="mt-5 grid items-center gap-5 sm:grid-cols-[minmax(170px,.8fr)_minmax(280px,1.2fr)_auto]">
          <div><div className="flex items-center gap-3 text-lg font-semibold tracking-tight"><span>{match.home}</span><span className="text-sm font-normal text-white/25">vs</span><span>{match.away}</span></div><p className="mt-1 text-xs text-white/35">预计总进球 {match.goals} · 可信度 {match.confidence}%</p></div>
          <div>
            <div className="mb-2 flex justify-between text-xs text-white/45"><span>主胜 <b className="ml-1 font-semibold text-white/85">{home}%</b></span><span>平局 <b className="ml-1 font-semibold text-white/85">{draw}%</b></span><span>客胜 <b className="ml-1 font-semibold text-white/85">{away}%</b></span></div>
            <div className="flex h-2 overflow-hidden rounded-full bg-white/5"><span className="bg-lime-300" style={{ width: `${home}%` }} /><span className="bg-sky-400" style={{ width: `${draw}%` }} /><span className="bg-violet-400" style={{ width: `${away}%` }} /></div>
          </div>
          <Button variant="ghost" size="sm" className="justify-self-start text-white/60 hover:bg-white/7 hover:text-white sm:justify-self-end">查看分析 <ChevronRight className="h-4 w-4" /></Button>
        </div>
        <p className="mt-4 border-t border-white/7 pt-4 text-sm leading-6 text-white/48">{match.note}</p>
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
