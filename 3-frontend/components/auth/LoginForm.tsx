"use client";

import { useState } from "react";
import Image from "next/image";
import { ArrowRight, Eye, EyeOff, LockKeyhole, AlertCircle, XCircle } from "lucide-react";
import { useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";
import { loginUser, completeNewPassword } from "@/lib/auth";
import { setAccessToken } from "@/lib/authSession";

export default function LoginForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const successMessage = searchParams.get("success");

  // common
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // new password flow
  const [isNewPasswordRequired, setIsNewPasswordRequired] = useState(false);
  const [session, setSession] = useState<string | null>(null);
  const [newPassword, setNewPassword] = useState("");

  async function handleLogin(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);

    try {
      const res = await loginUser(email, password);

      // 🔴 FIRST TIME LOGIN
      if (res.challenge === "NEW_PASSWORD_REQUIRED") {
        setIsNewPasswordRequired(true);
        setSession(res.session);
        return;
      }

      // ✅ NORMAL LOGIN
      saveTokens(res);
      router.push("/");
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : "Login failed";
      if (message.includes("unauthorized") || message.includes("inactive")) {
        setError("Your account is inactive or not found. Please contact your administrator.");
      } else {
        setError(message);
      }
    } finally {
      setLoading(false);
    }
  }

  async function handleSetNewPassword(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);

    try {
      if (!session) throw new Error("Session missing");

      const res = await completeNewPassword(
        email,
        newPassword,
        session
      );

      saveTokens(res);
      router.push("/");
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Password update failed");
    } finally {
      setLoading(false);
    }
  }

  function saveTokens(data: { access_token: string }) {
    setAccessToken(data.access_token);
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
        Secure workspace
      </div>

      {!isNewPasswordRequired ? (
        <>
          <h1 className="text-3xl font-semibold tracking-tight text-slate-950 2xl:text-4xl">
            Welcome back
          </h1>

          <p className="mt-2 text-sm leading-6 text-slate-500 2xl:text-base">
            Sign in to access your market intelligence workspace.
          </p>

          {successMessage && (
            <p className="mt-5 rounded-2xl border border-green-100 bg-green-50 px-4 py-3 text-sm font-medium text-green-700">
              {successMessage}
            </p>
          )}

          <form onSubmit={handleLogin} className="mt-8 space-y-5 2xl:mt-10 2xl:space-y-6">
            <div>
              <label htmlFor="email" className="text-sm font-semibold text-slate-700">
                Email
              </label>
              <input
                type="email"
                id="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="name@company.com"
                className="mt-2 h-12 w-full rounded-2xl border border-slate-200 bg-slate-50/80 px-4 text-slate-800 outline-none transition placeholder:text-slate-400 focus:border-blue-400 focus:bg-white focus:ring-4 focus:ring-blue-100 2xl:h-14 2xl:text-base"
              />
            </div>

            <div>
              <PasswordField
                id="password"
                value={password}
                onChange={setPassword}
                show={showPassword}
                toggle={() => setShowPassword(!showPassword)}
              />
              <div className="mt-2 text-right">
                <Link href="/forgot-password" className="text-xs font-medium text-blue-600 hover:underline">
                  Forgot password?
                </Link>
              </div>
            </div>

            {error && (
              <div className="rounded-2xl border border-red-200 bg-red-50 px-4 py-3 flex items-start gap-3">
                {error.includes("inactive") || error.includes("not found") ? (
                  <XCircle className="h-5 w-5 text-red-600 flex-shrink-0 mt-0.5" />
                ) : (
                  <AlertCircle className="h-5 w-5 text-red-600 flex-shrink-0 mt-0.5" />
                )}
                <p className="text-sm font-medium text-red-700">{error}</p>
              </div>
            )}

            <button
              type="submit"
              disabled={loading}
              className="group flex h-12 w-full items-center justify-center gap-2 rounded-2xl bg-[#0b2a7a] text-sm font-semibold text-white shadow-[0_12px_24px_rgba(37,99,235,0.22)] transition hover:-translate-y-0.5 hover:bg-[#0f3a9c] disabled:translate-y-0 disabled:cursor-not-allowed disabled:opacity-60 2xl:h-14 2xl:text-base"
            >
              {loading ? "Signing in..." : "Continue"}
              {!loading && <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-0.5" />}
            </button>
          </form>
        </>
      ) : (
        <>
          <h1 className="text-3xl font-semibold tracking-tight text-slate-950 2xl:text-4xl">
            Set New Password
          </h1>

          <p className="mt-2 text-sm leading-6 text-slate-500 2xl:text-base">
            This is your first login. Please set a new password.
          </p>

          <form
            onSubmit={handleSetNewPassword}
            className="mt-8 space-y-5 2xl:mt-10 2xl:space-y-6"
          >
            <PasswordField
              id="new-password"
              value={newPassword}
              onChange={setNewPassword}
              show={showPassword}
              toggle={() => setShowPassword(!showPassword)}
            />

            {error && (
              <div className="rounded-2xl border border-red-200 bg-red-50 px-4 py-3 flex items-start gap-3">
                <AlertCircle className="h-5 w-5 text-red-600 flex-shrink-0 mt-0.5" />
                <p className="text-sm font-medium text-red-700">{error}</p>
              </div>
            )}

            <button
              type="submit"
              disabled={loading}
              className="group flex h-12 w-full items-center justify-center gap-2 rounded-2xl bg-[#0b2a7a] text-sm font-semibold text-white shadow-[0_12px_24px_rgba(37,99,235,0.22)] transition hover:-translate-y-0.5 hover:bg-[#0f3a9c] disabled:translate-y-0 disabled:cursor-not-allowed disabled:opacity-60 2xl:h-14 2xl:text-base"
            >
              {loading ? "Updating..." : "Update Password"}
              {!loading && <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-0.5" />}
            </button>
          </form>
        </>
      )}

      <div className="mt-8 border-t border-slate-100 pt-6 text-center text-xs font-medium text-slate-500 2xl:mt-10 2xl:pt-8 2xl:text-sm">
        Analytics Platform Intelligence Platform
      </div>
    </div>
  );
}

/* ---------------- PASSWORD FIELD ---------------- */

function PasswordField({
  id,
  value,
  onChange,
  show,
  toggle,
}: {
  id: string;
  value: string;
  onChange: (v: string) => void;
  show: boolean;
  toggle: () => void;
}) {
  return (
    <div>
      <label htmlFor={id} className="text-sm font-semibold text-slate-700">
        Password
      </label>

      <div className="relative mt-2">
        <input
          type={show ? "text" : "password"}
          id={id}
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
          {show ? (
            <EyeOff className="h-5 w-5" />
          ) : (
            <Eye className="h-5 w-5" />
          )}
        </button>
      </div>
    </div>
  );
}
