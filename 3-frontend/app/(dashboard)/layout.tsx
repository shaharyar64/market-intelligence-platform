export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div style={{ background: "transparent" }} className="flex min-h-screen overflow-x-clip">
      <main className="flex-1 min-w-0">
        {children}
      </main>
    </div>
  );
}