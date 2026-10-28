import Image from "next/image";
import { BarChart3, Brain, MessageSquareText, ShieldCheck, Sparkles } from "lucide-react";

export default function LoginLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="min-h-screen bg-[#f7f9fc] px-4 py-5 text-slate-900 lg:h-screen lg:overflow-hidden">
      <div
        className="pointer-events-none fixed inset-0 opacity-[0.035]"
        style={{
          backgroundImage:
            "linear-gradient(rgba(15,23,42,1) 1px,transparent 1px),linear-gradient(90deg,rgba(15,23,42,1) 1px,transparent 1px)",
          backgroundSize: "42px 42px",
        }}
      />

      <div className="relative mx-auto grid min-h-[calc(100vh-40px)] max-w-[1760px] grid-cols-1 items-center gap-8 lg:h-[calc(100vh-40px)] lg:min-h-0 lg:grid-cols-[1.02fr_0.98fr] 2xl:max-w-[2200px] 2xl:grid-cols-[1.08fr_0.92fr] 2xl:gap-14">

        {/* LEFT PANEL */}
        <aside
          className="hidden h-full overflow-hidden rounded-[34px] bg-[#06164a] px-12 py-10 text-white shadow-[0_28px_90px_rgba(15,23,42,0.18)] lg:flex lg:flex-col lg:justify-between xl:py-12 2xl:px-16 2xl:py-14"
          style={{
            backgroundImage:
              "linear-gradient(135deg, rgba(5,18,58,0.98), rgba(11,45,122,0.96)), linear-gradient(135deg, rgba(20,184,166,0.18), transparent 35%), linear-gradient(rgba(255,255,255,0.055) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.055) 1px, transparent 1px)",
            backgroundSize: "auto, auto, 46px 46px, 46px 46px",
          }}
        >
          <div>
            <div className="inline-flex items-center gap-2 rounded-full border border-white/14 bg-white/8 px-3 py-1.5 text-xs font-semibold tracking-[0.18em] text-cyan-100 2xl:px-4 2xl:py-2 2xl:text-sm">
              <Sparkles className="h-3.5 w-3.5 text-cyan-300" />
              AI-POWERED MARKET INTELLIGENCE
            </div>

            <div className="mt-7">
              <Image
                src="/logo.svg"
                alt="Analytics Platform"
                width={210}
                height={40}
                priority
                className="2xl:w-[260px]"
              />
            </div>

            <h2 className="mt-8 max-w-2xl text-4xl font-semibold leading-[1.05] tracking-tight xl:text-5xl 2xl:max-w-4xl 2xl:text-6xl">
              Research intelligence for fast-moving markets.
            </h2>

            <p className="mt-4 max-w-xl text-base leading-7 text-slate-300 2xl:max-w-3xl 2xl:text-lg 2xl:leading-8">
              Analytics Platform blends human research expertise with AI systems to turn market signals into clear decisions.
            </p>

            <div className="mt-8 grid max-w-2xl gap-3 xl:mt-10 xl:gap-4 2xl:mt-14 2xl:max-w-4xl 2xl:gap-5">

              <Feature
                icon={<BarChart3 className="h-5 w-5 text-cyan-300" />}
                title="Multi-domain intelligence"
                desc="Dashboards for banking, EV, real estate, pricing and more, built from social, web and market signals."
              />

              <Feature
                icon={<Brain className="h-5 w-5 text-fuchsia-300" />}
                title="ML-powered insight models"
                desc="Machine learning turns noisy internet data into trends, anomalies, sentiment and growth patterns."
              />

              <Feature
                icon={<MessageSquareText className="h-5 w-5 text-blue-300" />}
                title="LLM research assistant"
                desc="Ask Analytics Platform questions in natural language and move from raw data to decision-ready answers."
              />
            </div>
          </div>

          <div className="mt-5 flex items-center justify-between border-t border-white/10 pt-5 2xl:pt-6">
            <div className="flex items-center gap-2 text-xs font-medium text-slate-300">
              <ShieldCheck className="h-4 w-4 text-cyan-300" />
              Enterprise research workspace
            </div>
            <p className="text-xs text-slate-400">
              2026 Analytics Platform
            </p>
          </div>
        </aside>

        {/* RIGHT PANEL */}
        <main className="flex min-h-[calc(100vh-40px)] items-center justify-center py-8 lg:h-full lg:min-h-0 lg:py-0">
          {children}
        </main>
      </div>
    </div>
  );
}

function Feature({
  icon,
  title,
  desc,
}: {
  icon: React.ReactNode;
  title: string;
  desc: string;
}) {
  return (
    <div className="flex items-start gap-4 rounded-2xl border border-white/10 bg-white/[0.07] p-3.5 shadow-[inset_0_1px_0_rgba(255,255,255,0.08)] backdrop-blur xl:p-4 2xl:gap-5 2xl:p-5">
      <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl border border-white/10 bg-white/10 2xl:h-14 2xl:w-14">
        {icon}
      </div>

      <div>
        <h4 className="text-sm font-semibold text-white 2xl:text-base">
          {title}
        </h4>
        <p className="mt-1 text-sm leading-relaxed text-slate-300 2xl:text-base 2xl:leading-7">
          {desc}
        </p>
      </div>
    </div>
  );
}
