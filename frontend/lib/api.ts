export const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";

export type ChatMessage = { role: "user" | "assistant"; content: string };

export type CartItem = {
  name: string;
  qty: number;
  price: number;
  menu_item_id?: number | null;
};

export type MenuItem = {
  id?: number | null;
  name: string;
  category: string;
  price: number;
  description?: string;
  available?: boolean | number;
};

export type OrderItem = {
  menu_item_id?: number | null;
  item_name?: string;
  name?: string;
  qty: number;
  price: number;
  customizations?: string;
};

export type Order = {
  id: number;
  phone?: string;
  customer_name?: string;
  address?: string;
  total: number;
  status: string;
  created_at: string;
  items: OrderItem[];
};

async function request<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${url}`, init);
  if (!res.ok) {
    let msg = `HTTP ${res.status}`;
    try {
      const body = await res.json();
      if (body && typeof body.detail === "string") msg = body.detail;
    } catch {
      /* ignore */
    }
    throw new Error(msg);
  }
  return res.json() as Promise<T>;
}

export const api = {
  health: () =>
    request<{
      status: string;
      ollama: boolean;
      provider: string;
      tts: string;
      model: string;
      voice: string;
      asr_model: string;
      restaurant: string;
      city: string;
    }>("/api/health"),

  greet: () =>
    request<{ text: string; audio_b64: string | null; fmt: string }>("/api/greet"),

  turn: async (opts: {
    audio?: Blob;
    text?: string;
    history: ChatMessage[];
  }) => {
    const fd = new FormData();
    if (opts.audio) fd.append("audio", opts.audio, "recording.wav");
    if (opts.text) fd.append("text", opts.text);
    fd.append("history", JSON.stringify(opts.history));
    return request<{
      transcript: string;
      response: string;
      audio_b64: string | null;
      cart: CartItem[];
    }>("/api/turn", { method: "POST", body: fd });
  },

  menu: () => request<{ items: MenuItem[] }>("/api/menu"),

  saveMenu: (items: MenuItem[]) =>
    request<{ ok: boolean; count: number }>("/api/menu", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(items),
    }),

  orders: () => request<{ orders: Order[] }>("/api/orders"),

  createOrder: (payload: {
    phone: string;
    name: string;
    address: string;
    items: CartItem[];
  }) =>
    request<{ order_id: number }>("/api/orders", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    }),

  updateOrderStatus: (id: number, status: string) =>
    request<{ ok: boolean }>(`/api/orders/${id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ status }),
    }),

  stats: () =>
    request<{ total: number; today: number; revenue: number; new: number }>(
      "/api/stats",
    ),

  calllogs: () =>
    request<{
      logs: { id: number; phone?: string; summary?: string; started_at: string }[];
    }>("/api/calllogs"),

  models: () => request<{ models: string[] }>("/api/models"),

  speak: (text: string) =>
    request<{ audio_b64: string | null; fmt: string }>("/api/speak", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text }),
    }),

  voiceReference: (audio: Blob, text: string) => {
    const fd = new FormData();
    fd.append("audio", audio, "ref.wav");
    fd.append("text", text);
    return request<{ ok: boolean; cloned: boolean }>("/api/voice/reference", {
      method: "POST",
      body: fd,
    });
  },

  updateSettings: (s: {
    model?: string;
    voice?: string;
    restaurant?: string;
    city?: string;
    asr?: string;
    provider?: string;
    tts?: string;
  }) =>
    request<{ ok: boolean }>("/api/settings", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(s),
    }),
};

export function audioFromB64(
  b64: string | null | undefined,
  fmt: string = "wav",
): string | null {
  return b64 ? `data:audio/${fmt};base64,${b64}` : null;
}

export function formatPrice(n: number): string {
  return `Rs ${Number(n).toLocaleString("en-IN")}`;
}

export type StreamHandlers = {
  onTranscript?: (text: string) => void;
  onToken?: (text: string) => void;
  onAudio?: (b64: string, fmt?: string) => void;
  onCart?: (items: CartItem[]) => void;
  onDone?: (response: string, order: CartItem[]) => void;
  onError?: (message: string) => void;
};

/** Streaming voice turn: transcript → tokens → sentence audio → cart → done. */
export async function streamTurn(
  opts: {
    audio?: Blob;
    text?: string;
    history: ChatMessage[];
    order?: CartItem[];
  },
  handlers: StreamHandlers,
): Promise<void> {
  const fd = new FormData();
  if (opts.audio) fd.append("audio", opts.audio, "recording.wav");
  if (opts.text) fd.append("text", opts.text);
  fd.append("history", JSON.stringify(opts.history));
  if (opts.order) fd.append("order", JSON.stringify(opts.order));

  // Hard timeout so a stalled LLM never leaves the app stuck on "thinking…".
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 120000);

  let res: Response;
  try {
    res = await fetch(`${API_BASE}/api/turn/stream`, {
      method: "POST",
      body: fd,
      signal: controller.signal,
    });
  } catch (e) {
    clearTimeout(timer);
    if ((e as Error).name === "AbortError") {
      throw new Error("Maya took too long to reply — please try again.");
    }
    throw e;
  }

  if (!res.ok || !res.body) {
    clearTimeout(timer);
    let msg = `HTTP ${res.status}`;
    try {
      const b = await res.json();
      if (typeof b.detail === "string") msg = b.detail;
    } catch {
      /* ignore */
    }
    throw new Error(msg);
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    let idx: number;
    while ((idx = buffer.indexOf("\n\n")) !== -1) {
      const raw = buffer.slice(0, idx);
      buffer = buffer.slice(idx + 2);
      const line = raw.trim();
      if (!line.startsWith("data:")) continue;
      const payload = line.slice(5).trim();
      if (!payload) continue;

      let ev: {
        type: string;
        text?: string;
        b64?: string;
        fmt?: string;
        items?: CartItem[];
        response?: string;
        order?: CartItem[];
        message?: string;
      };
      try {
        ev = JSON.parse(payload);
      } catch {
        continue;
      }

      switch (ev.type) {
        case "transcript":
          handlers.onTranscript?.(ev.text ?? "");
          break;
        case "token":
          handlers.onToken?.(ev.text ?? "");
          break;
        case "audio":
          handlers.onAudio?.(ev.b64 ?? "", ev.fmt ?? "wav");
          break;
        case "cart":
          handlers.onCart?.(ev.items ?? []);
          break;
        case "done":
          handlers.onDone?.(ev.response ?? "", ev.order ?? []);
          break;
        case "error":
          handlers.onError?.(ev.message ?? "Something went wrong");
          break;
      }
    }
  }
  clearTimeout(timer);
}
