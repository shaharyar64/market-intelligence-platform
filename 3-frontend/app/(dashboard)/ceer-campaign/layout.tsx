import DashboardShell from "@/components/layout/DashboardShell";

export default function CeerCampaignLayout({ children }: { children: React.ReactNode }) {
  return <DashboardShell dashboardType="ceerCampaign" userRole="ADMIN">{children}</DashboardShell>;
}
