import DashboardShell from "@/components/layout/DashboardShell";

export default function BankBrandHealthLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <DashboardShell dashboardType="bankBrandHealth" userRole="ADMIN">{children}</DashboardShell>;
}
