import DashboardShell from "@/components/layout/DashboardShell";

export default function FoodIntelligenceLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <DashboardShell dashboardType="foodIntelligence" userRole="ADMIN">{children}</DashboardShell>;
}
