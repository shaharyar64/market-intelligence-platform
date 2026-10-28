import DashboardShell from "@/components/layout/DashboardShell";

export default function RealEstateLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <DashboardShell dashboardType="realEstate" userRole="ADMIN">{children}</DashboardShell>;
}
