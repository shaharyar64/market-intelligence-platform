import DashboardShell from "@/components/layout/DashboardShell";

export default function BankingLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <DashboardShell dashboardType="banking" userRole="ADMIN">{children}</DashboardShell>;
}
