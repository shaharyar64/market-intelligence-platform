import DashboardShell from "@/components/layout/DashboardShell";

export default function PricingLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <DashboardShell dashboardType="pricing" userRole="ADMIN">{children}</DashboardShell>;
}
