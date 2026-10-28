import DashboardShell from "@/components/layout/DashboardShell";

export default function TrendsRealEstateLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <DashboardShell dashboardType="trendsRealEstate" userRole="ADMIN">{children}</DashboardShell>;
}
