"use client";

import Image from "next/image";
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
      href="/app/me"
      className="flex items-center gap-1.5 rounded-full bg-surface border border-border-soft px-2.5 py-1.5"
    >
      <Image src="/brand/credits-token.png" alt="" width={16} height={16} />
      <span className="text-xs text-text-2 tabular-nums">
        {balance === null ? "…" : balance.toLocaleString()}
      </span>
    </Link>
  );
}
