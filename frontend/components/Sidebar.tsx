"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const NAV = [
  { href: "/", label: "Talk to Maya", icon: "📞" },
  { href: "/menu", label: "Menu", icon: "🍽️" },
  { href: "/orders", label: "Orders & calls", icon: "📦" },
  { href: "/settings", label: "Settings", icon: "⚙️" },
];

export function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="flex w-60 shrink-0 flex-col gap-1 bg-sidebar p-4 text-[#f5ede4]">
      <div className="px-2 pb-5 pt-3">
        <div className="text-xl font-bold tracking-tight">📞 Maya</div>
        <div className="text-sm text-[#cbb9a8]">
          AI receptionist · Nepal
        </div>
      </div>

      <nav className="flex flex-col gap-1">
        {NAV.map((it) => {
          const active =
            it.href === "/" ? pathname === "/" : pathname.startsWith(it.href);
          return (
            <Link
              key={it.href}
              href={it.href}
              className={`flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors ${
                active
                  ? "bg-brand text-white shadow-sm"
                  : "text-[#e8dcd0] hover:bg-sidebar-2"
              }`}
            >
              <span className="text-base leading-none">{it.icon}</span>
              {it.label}
            </Link>
          );
        })}
      </nav>

      <div className="mt-auto rounded-lg bg-sidebar-2 px-3 py-2.5 text-[11px] leading-relaxed text-[#b39e8c]">
        100% local · zero cloud cost
        <br />
        Nepanglish + humanized voice
      </div>
    </aside>
  );
}
