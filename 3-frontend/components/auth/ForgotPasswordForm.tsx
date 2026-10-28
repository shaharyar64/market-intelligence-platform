"use client";

import { useState } from "react";
import Image from "next/image";
import { ArrowRight, LockKeyhole, MailCheck } from "lucide-react";
import Link from "next/link";
import { forgotPassword } from "@/lib/auth";

export default function ForgotPasswordForm() {
  const [email, setEmail] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [sent, setSent] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      await forgotPassword(email);
      setSent(true);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Unable to send the reset link. Please try again.");
    } finally {
      setLoading(false);
    }
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
        Password recovery
      </div>

      {!sent ? (
        <>
          <h2 className="text-3xl font-semibold tracking-tight text-slate-950 2xl:text-4xl">
            Forgot password?
          </h2>
          <p className="mt-2 text-sm leading-6 text-slate-500 2xl:text-base">
            Enter your email and we&apos;ll send you a reset link.
          </p>

          <form onSubmit={handleSubmit} className="mt-8 space-y-5 2xl:mt-10 2xl:space-y-6">
            <div>
              <label className="text-sm font-semibold text-slate-700">Email</label>
              <input
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="name@company.com"
                className="mt-2 h-12 w-full rounded-2xl border border-slate-200 bg-slate-50/80 px-4 text-slate-800 outline-none transition placeholder:text-slate-400 focus:border-blue-400 focus:bg-white focus:ring-4 focus:ring-blue-100 2xl:h-14 2xl:text-base"
              />
            </div>

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
              {loading ? "Sending..." : "Send reset link"}
              {!loading && <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-0.5" />}
            </button>
          </form>
        </>
      ) : (
        <>
          <div className="flex h-14 w-14 items-center justify-center rounded-2xl border border-green-100 bg-green-50 2xl:h-16 2xl:w-16">
            <MailCheck className="h-7 w-7 text-green-600 2xl:h-8 2xl:w-8" />
          </div>
          <h2 className="mt-5 text-3xl font-semibold tracking-tight text-slate-950 2xl:text-4xl">
            Check your email
          </h2>
          <p className="mt-2 text-sm leading-6 text-slate-500 2xl:text-base">
            Password reset link sent to <span className="font-semibold text-slate-700">{email}</span>. The link expires in 1 hour.
          </p>
        </>
      )}

      <div className="mt-8 border-t border-slate-100 pt-6 text-center text-xs font-medium text-slate-400 2xl:mt-10 2xl:pt-8 2xl:text-sm">
        <Link href="/login" className="text-blue-600 hover:underline">
          Back to sign in
        </Link>
      </div>
    </div>
  );
}
