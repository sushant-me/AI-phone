"use client";

import { useCallback, useEffect, useState } from "react";
import { api, formatPrice, type Order } from "@/lib/api";

const STATUSES = [
  "New",
  "Confirmed",
  "Cooking",
  "Ready",
  "Out for Delivery",
  "Delivered",
  "Cancelled",
];

type Stats = { total: number; today: number; revenue: number; new: number };

export default function OrdersPage() {
  const [orders, setOrders] = useState<Order[]>([]);
  const [stats, setStats] = useState<Stats>({
    total: 0,
    today: 0,
    revenue: 0,
    new: 0,
  });
  const [logs, setLogs] = useState<
    { id: number; phone?: string; summary?: string; started_at: string }[]
  >([]);
  const [loaded, setLoaded] = useState(false);

  const refresh = useCallback(() => {
    api
      .orders()
      .then((r) => setOrders(r.orders))
      .catch(() => {});
    api
      .stats()
      .then((s) => setStats(s))
      .catch(() => {});
    api
      .calllogs()
      .then((r) => setLogs(r.logs))
      .catch(() => {})
      .finally(() => setLoaded(true));
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const changeStatus = async (id: number, status: string) => {
    setOrders((prev) =>
      prev.map((o) => (o.id === id ? { ...o, status } : o)),
    );
    try {
      await api.updateOrderStatus(id, status);
    } catch {
      refresh();
    }
  };

  return (
    <div className="p-6">
      <header className="mb-5">
        <h1 className="text-2xl font-bold tracking-tight">📦 Orders & calls</h1>
        <p className="text-sm text-muted">Live orders placed through Maya.</p>
      </header>

      <div className="mb-6 grid grid-cols-2 gap-4 md:grid-cols-4">
        <StatCard label="Orders today" value={String(stats.today)} />
        <StatCard label="Total orders" value={String(stats.total)} />
        <StatCard label="New orders" value={String(stats.new)} />
        <StatCard
          label="Revenue"
          value={formatPrice(stats.revenue)}
          accent
        />
      </div>

      <h2 className="mb-3 text-lg font-semibold">Orders</h2>
      {!loaded ? (
        <p className="text-sm text-muted">Loading…</p>
      ) : orders.length === 0 ? (
        <div className="rounded-2xl border border-line bg-card p-8 text-center text-sm text-muted">
          No orders yet. Go to <span className="font-medium">Talk to Maya</span>,
          place an order, and confirm it.
        </div>
      ) : (
        <div className="flex flex-col gap-3">
          {orders.map((o) => (
            <div
              key={o.id}
              className="flex flex-wrap items-center gap-4 rounded-2xl border border-line bg-card px-5 py-4 shadow-sm"
            >
              <div className="min-w-0 flex-1">
                <div className="text-sm font-semibold">
                  Order #{o.id}
                  <span className="ml-2 font-normal text-muted">
                    {o.items
                      .map((i) => `${i.qty}× ${i.item_name}`)
                      .join(", ")}
                  </span>
                </div>
                <div className="mt-1 text-xs text-muted">
                  {o.phone && <>📞 {o.phone} · </>}
                  {o.address ? <>📍 {o.address} · </> : null}
                  🕐 {o.created_at.replace("T", " ")}
                </div>
              </div>
              <div className="text-lg font-bold text-brand">
                {formatPrice(o.total)}
              </div>
              <select
                value={o.status}
                onChange={(e) => changeStatus(o.id, e.target.value)}
                className="rounded-lg border border-line bg-white px-3 py-2 text-sm outline-none focus:border-brand"
              >
                {STATUSES.map((s) => (
                  <option key={s} value={s}>
                    {s}
                  </option>
                ))}
              </select>
            </div>
          ))}
        </div>
      )}

      <h2 className="mb-3 mt-8 text-lg font-semibold">Call logs</h2>
      {logs.length === 0 ? (
        <p className="text-sm text-muted">No calls yet.</p>
      ) : (
        <div className="overflow-hidden rounded-2xl border border-line bg-card shadow-sm">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-line bg-cream text-left text-xs uppercase tracking-wide text-muted">
                <th className="px-4 py-3 font-semibold">ID</th>
                <th className="px-4 py-3 font-semibold">Phone</th>
                <th className="px-4 py-3 font-semibold">Summary</th>
                <th className="px-4 py-3 font-semibold">Started</th>
              </tr>
            </thead>
            <tbody>
              {logs.map((l) => (
                <tr key={l.id} className="border-b border-line last:border-0">
                  <td className="px-4 py-2.5">{l.id}</td>
                  <td className="px-4 py-2.5">{l.phone || "—"}</td>
                  <td className="px-4 py-2.5">{l.summary || "—"}</td>
                  <td className="px-4 py-2.5">
                    {l.started_at.replace("T", " ")}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function StatCard({
  label,
  value,
  accent,
}: {
  label: string;
  value: string;
  accent?: boolean;
}) {
  return (
    <div className="rounded-2xl border border-line bg-card p-5 shadow-sm">
      <div className="text-xs font-medium uppercase tracking-wide text-muted">
        {label}
      </div>
      <div
        className={`mt-1 text-2xl font-bold ${accent ? "text-brand" : "text-ink"}`}
      >
        {value}
      </div>
    </div>
  );
}
