"use client";

import { useEffect, useState } from "react";
import { useTheme } from "next-themes";
import { Sun, Moon } from "lucide-react";

export default function ThemeToggle() {
  const { resolvedTheme, setTheme } = useTheme();

  // The server cannot know the persisted theme, so resolvedTheme differs
  // between SSR and the first client render — reading it before mount causes
  // a hydration mismatch. Render a neutral toggle until mounted; the real
  // active state applies in a client-only re-render right after.
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);

  const isDark = mounted ? resolvedTheme !== "light" : false;
  const lightActive = mounted && !isDark;
  const darkActive = mounted && isDark;

  const buttonStyle = (active: boolean) => ({
    background: active ? "var(--card-bg)" : "transparent",
    color: active ? "var(--title-tx)" : "var(--muted-tx)",
    boxShadow: active ? "0 4px 12px rgba(15, 23, 42, 0.12)" : "none",
  });

  return (
    <div
      role="group"
      aria-label="Theme"
      style={{
        background: "rgba(148, 163, 184, 0.12)",
        border: "1px solid var(--card-bd)",
        boxShadow: "0 8px 22px rgba(15, 23, 42, 0.08)",
      }}
      className="flex h-10 items-center gap-1 rounded-xl p-1"
    >
      <button
        type="button"
        onClick={() => setTheme("light")}
        aria-pressed={mounted ? !isDark : undefined}
        title="Light mode"
        style={buttonStyle(lightActive)}
        className="flex h-8 w-8 items-center justify-center rounded-lg transition"
      >
        <Sun className="h-4 w-4" />
      </button>
      <button
        type="button"
        onClick={() => setTheme("dark")}
        aria-pressed={mounted ? isDark : undefined}
        title="Dark mode"
        style={buttonStyle(darkActive)}
        className="flex h-8 w-8 items-center justify-center rounded-lg transition"
      >
        <Moon className="h-4 w-4" />
      </button>
    </div>
  );
}
