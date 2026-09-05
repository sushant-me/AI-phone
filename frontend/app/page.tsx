"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { CartPanel } from "@/components/CartPanel";
import { useBargeIn } from "@/components/useBargeIn";
import { useRecorder } from "@/components/useRecorder";
import { useSpeaker } from "@/components/useSpeaker";
import {
  api,
  audioFromB64,
  streamTurn,
  type CartItem,
} from "@/lib/api";

type Msg = { role: "user" | "assistant"; content: string; audio?: string | null };

export default function TalkPage() {
  const [messages, setMessages] = useState<Msg[]>([]);
  const [cart, setCart] = useState<CartItem[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [online, setOnline] = useState<boolean | null>(null);
  const [phone, setPhone] = useState("");
  const [name, setName] = useState("");
  const [address, setAddress] = useState("");
  const [text, setText] = useState("");

  const bottomRef = useRef<HTMLDivElement>(null);
  const { speak, stop: stopSpeaker, speaking } = useSpeaker();

  const { recording, error: recError, start, stop } = useRecorder();

  // Stop Maya's speech (used on interruption and before a new turn).
  const interruptAudio = useCallback(() => {
    stopSpeaker();
  }, [stopSpeaker]);

  const {
    start: startBargeIn,
    stop: stopBargeIn,
    listening: bargeListening,
  } = useBargeIn(() => {
    interruptAudio();
    start(); // begin recording what the caller is saying
  });

  // Arm interruption detection while Maya is speaking, disable it when she stops.
  useEffect(() => {
    if (speaking) startBargeIn();
    else stopBargeIn();
  }, [speaking, startBargeIn, stopBargeIn]);

  // Greeting + health on mount.
  useEffect(() => {
    let alive = true;
    api
      .health()
      .then((h) => alive && setOnline(h.ollama))
      .catch(() => alive && setOnline(false));
    api
      .greet()
      .then((g) => {
        if (!alive) return;
        setMessages([
          { role: "assistant", content: g.text, audio: audioFromB64(g.audio_b64, g.fmt) },
        ]);
      })
      .catch(() => {
        if (alive)
          setError(
            "Backend not reachable — start it with: .venv\\Scripts\\python -m uvicorn backend.main:app --port 8000",
          );
      });
    return () => {
      alive = false;
    };
  }, []);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, busy, speaking]);

  const runTurn = useCallback(
    async (opts: { audio?: Blob; text?: string }) => {
      setBusy(true);
      setError(null);
      setSuccess(null);
      interruptAudio();
      const history = messages.map((m) => ({ role: m.role, content: m.content }));
      try {
        await streamTurn(
          { audio: opts.audio, text: opts.text, history, order: cart },
          {
            onTranscript: (t) =>
              setMessages((prev) => [...prev, { role: "user", content: t }]),
            onAudio: speak,
            onCart: (items) => setCart(items),
            onDone: (response, order, orderConfirmed) => {
              setMessages((prev) => [
                ...prev,
                { role: "assistant", content: response },
              ]);
              setCart(orderConfirmed ? [] : order);
              if (orderConfirmed) {
                setSuccess(`✅ Order #${orderConfirmed} saved — Cash on Delivery`);
                setPhone("");
                setName("");
                setAddress("");
              }
            },
            onError: (msg) => setError(msg),
          },
        );
      } catch (e) {
        setError(e instanceof Error ? e.message : "Something went wrong");
      } finally {
        setBusy(false);
      }
    },
    [messages, cart, speak, interruptAudio],
  );

  const handleMic = useCallback(async () => {
    if (recording) {
      const wav = await stop();
      if (wav) await runTurn({ audio: wav });
    } else {
      interruptAudio(); // tapping the mic interrupts Maya
      await start();
    }
  }, [recording, start, stop, runTurn, interruptAudio]);

  const handleText = useCallback(
    async (e: React.FormEvent) => {
      e.preventDefault();
      const value = text.trim();
      if (!value || busy) return;
      setText("");
      await runTurn({ text: value });
    },
    [text, busy, runTurn],
  );

  const confirmOrder = useCallback(async () => {
    setBusy(true);
    setError(null);
    interruptAudio();
    try {
      const res = await api.createOrder({ phone, name, address, items: cart });
      setCart([]);
      setMessages([]);
      setPhone("");
      setName("");
      setAddress("");
      setError(`Order #${res.order_id} placed — Cash on Delivery 🎉`);
      api.greet().then((g) => {
        setMessages([
          { role: "assistant", content: g.text, audio: audioFromB64(g.audio_b64, g.fmt) },
        ]);
      });
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not place order");
    } finally {
      setBusy(false);
    }
  }, [cart, phone, name, address, interruptAudio]);

  return (
    <div className="flex h-full gap-6 p-6">
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="mb-4 flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold tracking-tight">📞 Talk to Maya</h1>
            <p className="text-sm text-muted">
              Speak in <span className="font-medium text-ink">Nepanglish</span>{" "}
              (Nepali + English) — interrupt her any time, like a real call.
            </p>
          </div>
          <div className="flex items-center gap-2 rounded-full border border-line bg-card px-3 py-1.5 text-xs font-medium">
            <span
              className={`h-2 w-2 rounded-full ${
                online === null
                  ? "bg-muted"
                  : online
                    ? "bg-good"
                    : "bg-brand"
              }`}
            />
            {online === null ? "Connecting…" : online ? "Engine ready" : "LLM offline"}
          </div>
        </header>

        <div className="flex-1 space-y-3 overflow-y-auto rounded-2xl border border-line bg-card p-5 shadow-sm">
          {messages.map((m, i) =>
            m.role === "assistant" ? (
              <div key={i} className="flex justify-start">
                <div className="max-w-[85%] rounded-2xl rounded-tl-sm border border-line bg-cream px-4 py-3">
                  <div className="mb-1 text-xs font-semibold uppercase tracking-wide text-brand">
                    Maya
                  </div>
                  <p className="whitespace-pre-wrap text-[15px] leading-relaxed">
                    {m.content}
                  </p>
                  {m.audio && (
                    <audio controls src={m.audio} className="mt-2 h-9 w-full" />
                  )}
                </div>
              </div>
            ) : (
              <div key={i} className="flex justify-end">
                <div className="max-w-[85%] rounded-2xl rounded-tr-sm bg-brand px-4 py-3 text-white">
                  <p className="whitespace-pre-wrap text-[15px] leading-relaxed">
                    {m.content}
                  </p>
                </div>
              </div>
            ),
          )}

          {busy && (
            <div className="flex justify-start">
              <div className="flex items-center gap-2 rounded-2xl border border-line bg-cream px-4 py-3 text-sm text-muted">
                <span className="h-2 w-2 animate-pulse rounded-full bg-brand" />
                {recording
                  ? "Listening…"
                  : speaking
                    ? "Maya is speaking…"
                    : "Maya is thinking…"}
              </div>
            </div>
          )}

          {error && (
            <div className="rounded-xl bg-brand-50 px-4 py-3 text-sm text-brand-700">
              {error}
            </div>
          )}

          {success && (
            <div className="rounded-xl bg-[#e7f5ec] px-4 py-3 text-sm font-medium text-good">
              {success}
            </div>
          )}
          <div ref={bottomRef} />
        </div>

        <div className="mt-4 flex items-center gap-3">
          <button
            onClick={handleMic}
            disabled={busy && !recording}
            className={`grid h-14 w-14 shrink-0 place-items-center rounded-full text-2xl text-white shadow-md transition-transform hover:scale-105 disabled:opacity-50 ${
              recording ? "animate-pulse bg-brand" : "bg-brand hover:bg-brand-600"
            }`}
            aria-label={recording ? "Stop and send" : "Start recording"}
          >
            {recording ? "⏹" : "🎤"}
          </button>
          <form onSubmit={handleText} className="flex flex-1 items-center gap-2">
            <input
              value={text}
              onChange={(e) => setText(e.target.value)}
              placeholder='Or type — e.g. "Euta mixed pizza ra dui ota cold coffee"'
              className="flex-1 rounded-full border border-line bg-card px-5 py-3 text-sm outline-none focus:border-brand"
            />
            <button
              type="submit"
              disabled={busy || !text.trim()}
              className="rounded-full bg-ink px-5 py-3 text-sm font-semibold text-white transition-colors hover:opacity-90 disabled:opacity-40"
            >
              Send
            </button>
          </form>
        </div>

        {(recError || bargeListening) && (
          <p className="mt-2 text-xs text-muted">
            {recError}
            {bargeListening && !recError ? "Listening for interruptions…" : ""}
          </p>
        )}
      </div>

      <CartPanel
        cart={cart}
        phone={phone}
        name={name}
        address={address}
        busy={busy}
        onPhone={setPhone}
        onName={setName}
        onAddress={setAddress}
        onIncrement={(n) =>
          setCart((prev) =>
            prev.map((it) => (it.name === n ? { ...it, qty: it.qty + 1 } : it)),
          )
        }
        onDecrement={(n) =>
          setCart((prev) =>
            prev
              .map((it) => (it.name === n ? { ...it, qty: it.qty - 1 } : it))
              .filter((it) => it.qty > 0),
          )
        }
        onConfirm={confirmOrder}
        onClear={() => setCart([])}
      />
    </div>
  );
}
