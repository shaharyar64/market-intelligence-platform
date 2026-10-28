import DashboardShell from "@/components/layout/DashboardShell";

export default function SaudiRealEstateLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <DashboardShell dashboardType="saudiRealEstate" userRole="ADMIN">{children}</DashboardShell>;
}
