export default function AskAssistantPage() {
  return (
    <div className="flex flex-col items-center justify-center min-h-[70vh] gap-6 text-center px-4">
      <div className="flex items-center justify-center w-20 h-20 rounded-2xl bg-gradient-to-br from-blue-500 to-violet-600 shadow-lg">
        <svg width="36" height="36" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
          <path d="M12 2a10 10 0 1 0 10 10" />
          <path d="M12 6v6l4 2" />
          <circle cx="19" cy="5" r="3" fill="white" stroke="none" />
        </svg>
      </div>

      <div>
        <h1 className="text-3xl font-bold text-slate-800 mb-2">Analytics Platform is Coming Soon</h1>
        <p className="text-slate-500 text-base max-w-sm">
          We're working hard to bring Analytics Platform to Bank Spatial. Stay tuned — it'll be worth the wait.
        </p>
      </div>

      <span
        className="inline-flex items-center gap-2 px-4 py-2 rounded-full text-sm font-semibold"
        style={{ background: "#ede9fe", color: "#6d28d9" }}
      >
        <span className="w-2 h-2 rounded-full bg-violet-500 animate-pulse" />
        In Development
      </span>
    </div>
  );
}
