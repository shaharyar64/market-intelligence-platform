"use client";

import Image from "next/image";
import { useRouter } from "next/navigation";
import { LogOut } from "lucide-react";
import { logoutUser } from "@/lib/authSession";

export default function TopNavbar() {
  const router = useRouter();

  return (
    <header className="w-full border-b border-slate-200 bg-white">
      <div className="max-w-6xl mx-auto px-8 h-16 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="h-9 w-52 rounded-xl bg-[#0f172a] border-r border-slate-800 flex items-center justify-center text-white shadow-md">
            <Image
              src="/logo.svg"
              alt="Logo"
              width={182}
              height={32}
            />
          </div>
        </div>

        <button
          onClick={async () => {
            try {
              await logoutUser();
            } finally {
              router.push("/login");
            }
          }}
          className="flex items-center gap-2 px-4 py-2 rounded-lg
            bg-violet-600 text-white text-sm font-medium
            hover:bg-violet-700 transition shadow-md"
        >
          <LogOut className="h-4 w-4" />
          Logout
        </button>
      </div>
    </header>
  );
}
