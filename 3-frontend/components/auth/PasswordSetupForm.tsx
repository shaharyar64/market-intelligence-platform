"use client";

import { useState } from "react";
import Image from "next/image";
import { ArrowRight, Eye, EyeOff, LockKeyhole } from "lucide-react";
import { useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";
import { resetPassword, setupPassword } from "@/lib/auth";

type Variant = "reset" | "setup";

const COPY = {
  reset: {
    badge: "Password reset",
    heading: "Reset your password",
    subheading: "Enter a new password for your account.",
    buttonIdle: "Reset password",
    buttonLoading: "Resetting...",
    invalidToken: "This reset link is invalid or has expired.",
    successParam: "Password reset successfully. Please log in.",
  },
  setup: {
    badge: "Account setup",
    heading: "Set your password",
    subheading: "Welcome! Create a password to activate your account.",
    buttonIdle: "Set password",
    buttonLoading: "Setting...",
    invalidToken: "This invite link is invalid or has expired.",
    successParam: "Password set. Welcome!",
  },
} satisfies Record<Variant, object>;

function validatePassword(pw: string): string | null {
  if (pw.length < 8) return "Password must be at least 8 characters.";
  if (!/[A-Z]/.test(pw)) return "Password must contain at least one uppercase letter.";
  if (!/[0-9]/.test(pw)) return "Password must contain at least one number.";
  if (!/[^A-Za-z0-9]/.test(pw)) return "Password must contain at least one special character.";
  return null;
}

export default function PasswordSetupForm({ variant }: { variant: Variant }) {
  const router = useRouter();
  const searchParams = useSearchParams();
  const token = searchParams.get("token") ?? "";

  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirm, setShowConfirm] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const copy = COPY[variant];

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);

    const validationError = validatePassword(password);
    if (validationError) { setError(validationError); return; }
    if (password !== confirm) { setError("Passwords do not match."); return; }

    setLoading(true);
    try {
      const fn = variant === "reset" ? resetPassword : setupPassword;
      await fn(token, password);
      router.push(`/login?success=${encodeURIComponent(copy.successParam)}`);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "";
      const isTokenError =
        msg.toLowerCase().includes("invalid") ||
        msg.toLowerCase().includes("expired") ||
        msg.toLowerCase().includes("not found");
      setError(isTokenError || !msg ? copy.invalidToken : msg);
    } finally {
      setLoading(false);
    }
  }

  if (!token) {
    return (
      <div className="w-full max-w-[470px] rounded-[30px] border border-slate-200/80 bg-white/95 px-7 py-8 shadow-[0_24px_70px_rgba(15,23,42,0.13)] backdrop-blur sm:px-10 sm:py-10 2xl:max-w-[560px]">
        <p className="rounded-2xl border border-red-100 bg-red-50 px-4 py-3 text-sm font-medium text-red-600">
          {copy.invalidToken}
        </p>
        <div className="mt-6 text-center text-xs font-medium text-slate-400">
          <Link href="/login" className="text-blue-600 hover:underline">Back to sign in</Link>
        </div>
      </div>
    );
  }

  return (
    <div className="w-full max-w-[470px] rounded-[30px] border border-slate-200/80 bg-white/95 px-7 py-8 shadow-[0_24px_70px_rgba(15,23,42,0.13)] backdrop-blur sm:px-10 sm:py-10 2xl:max-w-[560px] 2xl:px-12 2xl:py-12">
      <div className="mb-8 inline-flex rounded-2xl bg-[#06164a] px-4 py-3 shadow-[0_12px_30px_rgba(6,22,74,0.18)]">
        <Image
          src="/logo.svg"
          alt="Analytics Platform"
          width={170}
          height={32}
          priority
          className="2xl:w-[210px]"
        />
      </div>

      <div className="mb-7 inline-flex items-center gap-2 rounded-full border border-blue-100 bg-blue-50 px-3 py-1.5 text-xs font-semibold text-blue-700 2xl:px-4 2xl:py-2 2xl:text-sm">
        <LockKeyhole className="h-3.5 w-3.5" />
        {copy.badge}
      </div>

      <h2 className="text-3xl font-semibold tracking-tight text-slate-950 2xl:text-4xl">
        {copy.heading}
      </h2>
      <p className="mt-2 text-sm leading-6 text-slate-500 2xl:text-base">
        {copy.subheading}
      </p>

      <form onSubmit={handleSubmit} className="mt-8 space-y-5 2xl:mt-10 2xl:space-y-6">
        <PasswordField
          label="New password"
          value={password}
          onChange={setPassword}
          show={showPassword}
          toggle={() => setShowPassword((p) => !p)}
        />
        <PasswordField
          label="Confirm password"
          value={confirm}
          onChange={setConfirm}
          show={showConfirm}
          toggle={() => setShowConfirm((p) => !p)}
        />

        <ul className="space-y-1 text-xs text-slate-400">
          <PasswordRule met={password.length >= 8} text="At least 8 characters" />
          <PasswordRule met={/[A-Z]/.test(password)} text="One uppercase letter" />
          <PasswordRule met={/[0-9]/.test(password)} text="One number" />
          <PasswordRule met={/[^A-Za-z0-9]/.test(password)} text="One special character" />
        </ul>

        {error && (
          <p className="rounded-2xl border border-red-100 bg-red-50 px-4 py-3 text-sm font-medium text-red-600">
            {error}
          </p>
        )}

        <button
          type="submit"
          disabled={loading}
          className="group flex h-12 w-full items-center justify-center gap-2 rounded-2xl bg-[#0b2a7a] text-sm font-semibold text-white shadow-[0_12px_24px_rgba(37,99,235,0.22)] transition hover:-translate-y-0.5 hover:bg-[#0f3a9c] disabled:translate-y-0 disabled:cursor-not-allowed disabled:opacity-60 2xl:h-14 2xl:text-base"
        >
          {loading ? copy.buttonLoading : copy.buttonIdle}
          {!loading && <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-0.5" />}
        </button>
      </form>

      <div className="mt-8 border-t border-slate-100 pt-6 text-center text-xs font-medium text-slate-500 2xl:mt-10 2xl:pt-8 2xl:text-sm">
        <Link href="/login" className="text-blue-600 hover:underline">Back to sign in</Link>
      </div>
    </div>
  );
}

function PasswordField({
  label,
  value,
  onChange,
  show,
  toggle,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  show: boolean;
  toggle: () => void;
}) {
  return (
    <div>
      <label className="text-sm font-semibold text-slate-700">{label}</label>
      <div className="relative mt-2">
        <input
          type={show ? "text" : "password"}
          required
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder="••••••••"
          className="h-12 w-full rounded-2xl border border-slate-200 bg-slate-50/80 px-4 pr-11 text-slate-800 outline-none transition placeholder:text-slate-400 focus:border-blue-400 focus:bg-white focus:ring-4 focus:ring-blue-100 2xl:h-14 2xl:text-base"
        />
        <button
          type="button"
          onClick={toggle}
          aria-label={show ? "Hide password" : "Show password"}
          aria-pressed={show}
          className="absolute inset-y-0 right-3 flex items-center text-slate-400 transition hover:text-slate-700"
        >
          {show ? <EyeOff className="h-5 w-5" /> : <Eye className="h-5 w-5" />}
        </button>
      </div>
    </div>
  );
}

function PasswordRule({ met, text }: { met: boolean; text: string }) {
  return (
    <li className={`flex items-center gap-1.5 transition-colors ${met ? "text-green-600" : "text-slate-400"}`}>
      <span className={`h-1.5 w-1.5 rounded-full ${met ? "bg-green-500" : "bg-slate-300"}`} />
      {text}
    </li>
  );
}
