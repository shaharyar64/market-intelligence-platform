import DashboardTopbar from "@/components/layout/DashboardTopbar";
import type { LucideIcon } from "lucide-react";

type StarterPageProps = {
  title: string;
  eyebrow: string;
  description: string;
  icon: LucideIcon;
  sections: string[];
};

export default function StarterPage({
  title,
  eyebrow,
  description,
  icon: Icon,
  sections,
}: StarterPageProps) {
  return (
    <div className="min-h-screen">
      <DashboardTopbar title="BrandIQ" />

      <main className="p-8">
        <section className="chart-card rounded-xl p-6">
          <div className="flex flex-col gap-6 lg:flex-row lg:items-start lg:justify-between">
            <div className="max-w-3xl">
              <div className="mb-4 flex items-center gap-3">
                <div className="flex h-11 w-11 items-center justify-center rounded-xl border border-[var(--card-bd)] bg-[var(--card-bg-2)]">
                  <Icon className="h-5 w-5 text-blue-500" />
                </div>
                <span className="text-xs font-semibold uppercase tracking-[0.18em] text-[var(--muted-tx)]">
                  {eyebrow}
                </span>
              </div>

              <h2 className="text-2xl font-semibold text-[var(--title-tx)]">{title}</h2>
              <p className="mt-3 max-w-2xl text-sm leading-6 text-[var(--body-tx)]">
                {description}
              </p>
            </div>

            <div className="rounded-lg border border-[var(--card-bd)] bg-[var(--card-bg-2)] px-4 py-3 text-sm font-medium text-[var(--muted-tx)]">
              Build area ready
            </div>
          </div>
        </section>

        <section className="mt-6 grid gap-4 md:grid-cols-3">
          {sections.map((section) => (
            <div key={section} className="chart-card rounded-xl p-5">
              <div className="h-2 w-14 rounded-full bg-blue-500/70" />
              <h3 className="mt-4 text-sm font-semibold text-[var(--title-tx)]">{section}</h3>
              <p className="mt-2 text-xs leading-5 text-[var(--muted-tx)]">
                Placeholder for the first implementation pass.
              </p>
            </div>
          ))}
        </section>
      </main>
    </div>
  );
}
