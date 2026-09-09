import {
  BarChart3, CalendarDays, Database, Gauge, ShieldCheck, Sparkles, Trophy,
} from 'lucide-react';

const navigation = [
  { href: '/', label: '今日分析', icon: Sparkles },
  { href: '/schedule', label: '赛程中心', icon: CalendarDays },
  { href: '/evaluation', label: '模型评估', icon: BarChart3 },
  { href: '/lab', label: '策略实验室', icon: Gauge },
  { href: '/system', label: '数据与任务', icon: Database },
];

export function DashboardSectionShell({
  active,
  title,
  description,
  children,
}: {
  active: string;
  title: string;
  description: string;
  children: React.ReactNode;
}) {
  return (
    <main className="min-h-screen bg-background pb-20 text-foreground lg:pb-0">
      <header className="sticky top-0 z-20 border-b border-white/8 bg-[#07110d]/90 backdrop-blur-xl">
        <div className="mx-auto flex h-16 max-w-[1440px] items-center justify-between px-4 sm:px-6 lg:px-8">
          <a href="/" className="flex items-center gap-3">
            <span className="grid h-9 w-9 place-items-center rounded-xl bg-lime-300 text-[#07110d]"><Trophy className="h-[19px] w-[19px]" /></span>
            <span><b className="block text-[15px] leading-tight">足球 AI 分析台</b><span className="text-xs text-white/45">中国竞彩足球</span></span>
          </a>
          <span className="rounded-full border border-emerald-400/20 bg-emerald-400/10 px-3 py-1.5 text-xs text-emerald-300">自动运行中</span>
        </div>
      </header>

      <div className="mx-auto grid max-w-[1440px] gap-6 px-4 py-6 sm:px-6 lg:grid-cols-[220px_minmax(0,1fr)] lg:px-8 lg:py-8">
        <aside className="hidden lg:block">
          <nav className="sticky top-24 space-y-1" aria-label="主要导航">
            {navigation.map(({ href, label, icon: Icon }) => <a key={href} href={href} className={`flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm transition ${active === href ? 'bg-lime-300 font-medium text-[#07110d]' : 'text-white/50 hover:bg-white/5 hover:text-white/85'}`}><Icon className="h-[17px] w-[17px]" />{label}</a>)}
          </nav>
          <div className="mt-8 rounded-2xl border border-white/8 bg-white/[.025] p-4">
            <div className="flex items-center gap-2 text-sm font-medium text-white/80"><ShieldCheck className="h-4 w-4 text-lime-300" />研究模式</div>
            <p className="mt-2 text-xs leading-5 text-white/40">概率分析与长期回测，不连接真实资金。</p>
          </div>
        </aside>

        <section className="min-w-0">
          <div className="mb-6"><h1 className="text-2xl font-semibold tracking-[-0.035em] sm:text-[2rem]">{title}</h1><p className="mt-2 text-sm leading-6 text-white/45">{description}</p></div>
          {children}
        </section>
      </div>

      <nav className="fixed inset-x-0 bottom-0 z-30 grid grid-cols-5 border-t border-white/8 bg-[#07110d]/95 px-1 pb-[max(.5rem,env(safe-area-inset-bottom))] pt-2 backdrop-blur-xl lg:hidden" aria-label="移动端导航">
        {navigation.map(({ href, label, icon: Icon }) => <a key={href} href={href} className={`flex flex-col items-center gap-1 text-[11px] ${active === href ? 'text-lime-300' : 'text-white/40'}`}><Icon className="h-5 w-5" />{label.replace('中心', '').replace('模型', '')}</a>)}
      </nav>
    </main>
  );
}

export function SectionCard({ title, children }: { title: string; children: React.ReactNode }) {
  return <section className="rounded-2xl border border-white/8 bg-white/[.035] p-5 sm:p-6"><h2 className="text-base font-medium text-white/85">{title}</h2><div className="mt-4">{children}</div></section>;
}
