"use client";

import { useEffect, useState } from "react";
import { api, type MenuItem } from "@/lib/api";

const CATEGORIES = ["Momo", "Main", "Newari", "Fast Food", "Snacks", "Drinks"];

export default function MenuPage() {
  const [rows, setRows] = useState<MenuItem[]>([]);
  const [loaded, setLoaded] = useState(false);
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);

  useEffect(() => {
    api
      .menu()
      .then((r) => setRows(r.items))
      .catch(() => setMsg("Backend not reachable on :8000"))
      .finally(() => setLoaded(true));
  }, []);

  const update = (i: number, patch: Partial<MenuItem>) =>
    setRows((prev) => prev.map((r, idx) => (idx === i ? { ...r, ...patch } : r)));

  const addRow = () =>
    setRows((prev) => [
      ...prev,
      { name: "", category: "Main", price: 0, description: "", available: true },
    ]);

  const removeRow = (i: number) =>
    setRows((prev) => prev.filter((_, idx) => idx !== i));

  const save = async () => {
    setSaving(true);
    setMsg(null);
    try {
      await api.saveMenu(rows);
      setMsg("Menu saved — Maya now knows the latest items and prices ✅");
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "Save failed");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="p-6">
      <header className="mb-5 flex items-end justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">🍽️ Menu</h1>
          <p className="text-sm text-muted">
            Changes update Maya&apos;s knowledge instantly (menu grounding / RAG).
          </p>
        </div>
        <button
          onClick={save}
          disabled={saving || !loaded}
          className="rounded-xl bg-brand px-4 py-2.5 text-sm font-semibold text-white hover:bg-brand-600 disabled:opacity-40"
        >
          {saving ? "Saving…" : "Save menu"}
        </button>
      </header>

      {msg && (
        <div className="mb-4 rounded-xl bg-brand-50 px-4 py-3 text-sm text-brand-700">
          {msg}
        </div>
      )}

      <div className="overflow-hidden rounded-2xl border border-line bg-card shadow-sm">
        <table className="w-full border-collapse text-sm">
          <thead>
            <tr className="border-b border-line bg-cream text-left text-xs uppercase tracking-wide text-muted">
              <th className="px-4 py-3 font-semibold">Name</th>
              <th className="px-4 py-3 font-semibold">Category</th>
              <th className="px-4 py-3 font-semibold">Price (Rs)</th>
              <th className="px-4 py-3 font-semibold">Description</th>
              <th className="px-4 py-3 font-semibold">Available</th>
              <th className="px-2 py-3" />
            </tr>
          </thead>
          <tbody>
            {rows.map((r, i) => (
              <tr key={i} className="border-b border-line last:border-0">
                <td className="px-4 py-2">
                  <input
                    value={r.name}
                    onChange={(e) => update(i, { name: e.target.value })}
                    placeholder="Item name"
                    className="w-full rounded-md border border-line px-2 py-1.5 outline-none focus:border-brand"
                  />
                </td>
                <td className="px-4 py-2">
                  <select
                    value={r.category}
                    onChange={(e) => update(i, { category: e.target.value })}
                    className="w-full rounded-md border border-line bg-white px-2 py-1.5 outline-none focus:border-brand"
                  >
                    {CATEGORIES.map((c) => (
                      <option key={c} value={c}>
                        {c}
                      </option>
                    ))}
                  </select>
                </td>
                <td className="px-4 py-2">
                  <input
                    type="number"
                    min={0}
                    step={5}
                    value={r.price}
                    onChange={(e) => update(i, { price: Number(e.target.value) })}
                    className="w-28 rounded-md border border-line px-2 py-1.5 outline-none focus:border-brand"
                  />
                </td>
                <td className="px-4 py-2">
                  <input
                    value={r.description ?? ""}
                    onChange={(e) => update(i, { description: e.target.value })}
                    placeholder="Short description"
                    className="w-full rounded-md border border-line px-2 py-1.5 outline-none focus:border-brand"
                  />
                </td>
                <td className="px-4 py-2 text-center">
                  <input
                    type="checkbox"
                    checked={Boolean(r.available)}
                    onChange={(e) => update(i, { available: e.target.checked })}
                    className="h-4 w-4 accent-brand"
                  />
                </td>
                <td className="px-2 py-2">
                  <button
                    onClick={() => removeRow(i)}
                    className="rounded-md px-2 py-1 text-muted hover:bg-brand-50 hover:text-brand"
                    aria-label="Remove row"
                  >
                    ✕
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <button
        onClick={addRow}
        className="mt-4 rounded-xl border border-dashed border-line bg-card px-4 py-2.5 text-sm font-medium text-muted hover:border-brand hover:text-brand"
      >
        + Add item
      </button>
    </div>
  );
}
