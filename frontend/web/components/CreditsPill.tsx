"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";

/** The one place a balance is shown in the header — deliberately the only
 * place (product feedback: a separate wallet card on Home duplicated this
 * and got cut). */
export function CreditsPill() {
  const [balance, setBalance] = useState<number | null>(null);

  useEffect(() => {
    api.me().then((me) => setBalance(me.balance)).catch(() => setBalance(null));
  }, []);

  return (
    <Link
      href="/me"
      className="flex items-center gap-1.5 rounded-full bg-surface border border-border-soft px-2.5 py-1.5"
    >
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="var(--a3)" strokeWidth="2">
        <circle cx="12" cy="12" r="9" />
        <path d="M12 7v5l3 2" />
      </svg>
      <span className="text-xs text-text-2 tabular-nums">
        {balance === null ? "…" : balance.toLocaleString()}
      </span>
    </Link>
  );
}
