"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

export function Shell({ children }) {
  const path = usePathname();
  return (
    <div className="shell">
      <aside className="nav">
        <h1>Medi-Shield</h1>
        <p>Claims document intake</p>
        <Link className={path === "/" ? "active" : ""} href="/">Cases</Link>
        <Link className={path.startsWith("/review") ? "active" : ""} href="/review">Review queue</Link>
      </aside>
      <main className="main">{children}</main>
    </div>
  );
}

export function Badge({ value }) {
  if (!value) return <span className="badge RECEIVED">Pending</span>;
  return <span className={`badge ${value}`}>{value}</span>;
}
