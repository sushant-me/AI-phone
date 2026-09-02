"use client";

import { formatPrice, type CartItem } from "@/lib/api";

type Props = {
  cart: CartItem[];
  phone: string;
  name: string;
  address: string;
  busy: boolean;
  onPhone: (v: string) => void;
  onName: (v: string) => void;
  onAddress: (v: string) => void;
  onIncrement: (name: string) => void;
  onDecrement: (name: string) => void;
  onConfirm: () => void;
  onClear: () => void;
};

export function CartPanel({
  cart,
  phone,
  name,
  address,
  busy,
  onPhone,
  onName,
  onAddress,
  onIncrement,
  onDecrement,
  onConfirm,
  onClear,
}: Props) {
  const total = cart.reduce((sum, it) => sum + it.qty * it.price, 0);

  return (
    <aside className="flex w-80 shrink-0 flex-col rounded-2xl border border-line bg-card p-5 shadow-sm">
      <div className="mb-3 flex items-center justify-between">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-muted">
          Live order
        </h2>
        {cart.length > 0 && (
          <button
            onClick={onClear}
            className="text-xs font-medium text-muted hover:text-brand"
          >
            Clear
          </button>
        )}
      </div>

      {cart.length === 0 ? (
        <p className="rounded-xl bg-cream px-3 py-6 text-center text-sm text-muted">
          Items Maya hears appear here automatically.
        </p>
      ) : (
        <ul className="mb-4 flex flex-col gap-2">
          {cart.map((it) => (
            <li
              key={it.name}
              className="flex items-center justify-between gap-2 rounded-xl border border-line px-3 py-2"
            >
              <div className="min-w-0">
                <div className="truncate text-sm font-medium">{it.name}</div>
                <div className="text-xs text-muted">{formatPrice(it.price)}</div>
              </div>
              <div className="flex items-center gap-1.5">
                <button
                  onClick={() => onDecrement(it.name)}
                  className="grid h-6 w-6 place-items-center rounded-md bg-cream text-sm font-semibold hover:bg-line"
                  aria-label={`Decrease ${it.name}`}
                >
                  −
                </button>
                <span className="w-5 text-center text-sm font-semibold">
                  {it.qty}
                </span>
                <button
                  onClick={() => onIncrement(it.name)}
                  className="grid h-6 w-6 place-items-center rounded-md bg-cream text-sm font-semibold hover:bg-line"
                  aria-label={`Increase ${it.name}`}
                >
                  +
                </button>
              </div>
            </li>
          ))}
        </ul>
      )}

      <div className="mb-4 flex items-center justify-between border-t border-line pt-3 text-sm">
        <span className="text-muted">Total · Cash on Delivery</span>
        <span className="text-lg font-bold text-brand">{formatPrice(total)}</span>
      </div>

      <div className="flex flex-col gap-2.5">
        <input
          value={phone}
          onChange={(e) => onPhone(e.target.value)}
          placeholder="Customer phone"
          className="rounded-lg border border-line bg-cream px-3 py-2 text-sm outline-none focus:border-brand"
        />
        <input
          value={name}
          onChange={(e) => onName(e.target.value)}
          placeholder="Customer name (optional)"
          className="rounded-lg border border-line bg-cream px-3 py-2 text-sm outline-none focus:border-brand"
        />
        <input
          value={address}
          onChange={(e) => onAddress(e.target.value)}
          placeholder="Address — e.g. Baneshwor, Eyeplex Mall ko pachadi"
          className="rounded-lg border border-line bg-cream px-3 py-2 text-sm outline-none focus:border-brand"
        />
        <button
          onClick={onConfirm}
          disabled={cart.length === 0 || busy}
          className="mt-1 rounded-xl bg-brand px-4 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-brand-600 disabled:cursor-not-allowed disabled:opacity-40"
        >
          Confirm order
        </button>
      </div>
    </aside>
  );
}
