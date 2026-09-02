"use client";

import { useCallback, useEffect, useState } from "react";
import { useRecorder } from "@/components/useRecorder";
import { api, audioFromB64 } from "@/lib/api";

const VOICES = [
  { id: "ne-NP-HemkalaNeural", label: "Hemkala — female (recommended)" },
  { id: "ne-NP-SagarNeural", label: "Sagar — male" },
];

const ASR_MODELS = [
  { id: "small", label: "small — fastest (low latency)" },
  { id: "base", label: "base — very fast" },
  { id: "medium", label: "medium — more accurate Nepali" },
  { id: "large-v3", label: "large-v3 — best accuracy (slow)" },
];

export default function SettingsPage() {
  const [health, setHealth] = useState<{
    model: string;
    voice: string;
    restaurant: string;
    city: string;
    ollama: boolean;
    provider: string;
    tts: string;
    asr_model: string;
  } | null>(null);
  const [models, setModels] = useState<string[]>([]);
  const [provider, setProvider] = useState("deepseek");
  const [tts, setTts] = useState("natural");
  const [model, setModel] = useState("");
  const [voice, setVoice] = useState(VOICES[0].id);
  const [asr, setAsr] = useState("small");
  const [restaurant, setRestaurant] = useState("");
  const [city, setCity] = useState("");
  const [preview, setPreview] = useState(
    "नमस्ते! Everest Burger मा Maya बोल्दै छु। के order गर्नु हुन्छ?",
  );
  const [previewAudio, setPreviewAudio] = useState<string | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const [cloneText, setCloneText] = useState(
    "नमस्ते, यो मेरो आवाज हो। म यहाँ छु।",
  );
  const { recording: recClone, start: startClone, stop: stopClone } = useRecorder();

  useEffect(() => {
    api
      .health()
      .then((h) => {
        setHealth(h);
        setProvider(h.provider);
        setTts(h.tts);
        setModel(h.model);
        setVoice(h.voice);
        setAsr(h.asr_model);
        setRestaurant(h.restaurant);
        setCity(h.city);
      })
      .catch(() => setMsg("Backend not reachable on :8000"));
    api
      .models()
      .then((r) => setModels(r.models))
      .catch(() => {});
  }, []);

  const save = useCallback(async () => {
    setMsg(null);
    try {
      await api.updateSettings({
        provider,
        tts,
        model,
        voice,
        restaurant,
        city,
        asr,
      });
      setMsg("Saved ✅");
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "Save failed");
    }
  }, [provider, tts, model, voice, restaurant, city, asr]);

  const playPreview = useCallback(async () => {
    setMsg(null);
    try {
      const r = await api.speak(preview);
      setPreviewAudio(audioFromB64(r.audio_b64));
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "Preview failed");
    }
  }, [preview]);

  const handleClone = useCallback(async () => {
    if (recClone) {
      const wav = await stopClone();
      if (!wav) return;
      setMsg(null);
      try {
        const r = await api.voiceReference(wav, cloneText);
        setMsg(
          r.cloned
            ? "Voice cloned ✅ — set Voice engine to OmniVoice and press Play to hear it"
            : "No audio recorded",
        );
      } catch (e) {
        setMsg(e instanceof Error ? e.message : "Clone failed");
      }
    } else {
      await startClone();
    }
  }, [recClone, startClone, stopClone, cloneText]);

  return (
    <div className="mx-auto max-w-2xl p-6">
      <header className="mb-6">
        <h1 className="text-2xl font-bold tracking-tight">⚙️ Settings</h1>
        <p className="text-sm text-muted">
          Model, voice and restaurant identity for Maya.
        </p>
      </header>

      {msg && (
        <div className="mb-4 rounded-xl bg-brand-50 px-4 py-3 text-sm text-brand-700">
          {msg}
        </div>
      )}

      <section className="rounded-2xl border border-line bg-card p-5 shadow-sm">
        <h2 className="mb-4 text-sm font-semibold uppercase tracking-wide text-muted">
          Model & voice
        </h2>

        <label className="mb-1 block text-sm font-medium">AI engine</label>
        <select
          value={provider}
          onChange={(e) => setProvider(e.target.value)}
          className="mb-4 w-full rounded-lg border border-line bg-cream px-3 py-2.5 text-sm outline-none focus:border-brand"
        >
          <option value="deepseek">DeepSeek (cloud · better conversation)</option>
          <option value="ollama">Local (Ollama · offline, free)</option>
        </select>

        <label className="mb-1 block text-sm font-medium">
          {provider === "deepseek" ? "Model (DeepSeek)" : "Model (Ollama)"}
        </label>
        <select
          value={model}
          onChange={(e) => setModel(e.target.value)}
          className="mb-4 w-full rounded-lg border border-line bg-cream px-3 py-2.5 text-sm outline-none focus:border-brand"
        >
          {!models.includes(model) && <option value={model}>{model}</option>}
          {models.map((m) => (
            <option key={m} value={m}>
              {m}
            </option>
          ))}
        </select>

        <label className="mb-1 block text-sm font-medium">
          Voice (humanized Nepali neural)
        </label>
        <select
          value={voice}
          onChange={(e) => setVoice(e.target.value)}
          className="mb-4 w-full rounded-lg border border-line bg-cream px-3 py-2.5 text-sm outline-none focus:border-brand"
        >
          {VOICES.map((v) => (
            <option key={v.id} value={v.id}>
              {v.label}
            </option>
          ))}
        </select>

        <label className="mb-1 block text-sm font-medium">Voice engine</label>
        <select
          value={tts}
          onChange={(e) => setTts(e.target.value)}
          className="mb-4 w-full rounded-lg border border-line bg-cream px-3 py-2.5 text-sm outline-none focus:border-brand"
        >
          <option value="natural">Natural (edge-tts · human · needs internet)</option>
          <option value="omnivoice">OmniVoice (GPU · most human · clone your voice)</option>
          <option value="local">Local (Piper · offline, free)</option>
        </select>

        <label className="mb-1 block text-sm font-medium">
          Speech recognition (faster-whisper)
        </label>
        <select
          value={asr}
          onChange={(e) => setAsr(e.target.value)}
          className="mb-4 w-full rounded-lg border border-line bg-cream px-3 py-2.5 text-sm outline-none focus:border-brand"
        >
          {ASR_MODELS.map((m) => (
            <option key={m.id} value={m.id}>
              {m.label}
            </option>
          ))}
        </select>

        <label className="mb-1 block text-sm font-medium">Preview the voice</label>
        <div className="flex gap-2">
          <input
            value={preview}
            onChange={(e) => setPreview(e.target.value)}
            className="flex-1 rounded-lg border border-line bg-cream px-3 py-2.5 text-sm outline-none focus:border-brand"
          />
          <button
            onClick={playPreview}
            className="rounded-lg bg-ink px-4 py-2.5 text-sm font-semibold text-white hover:opacity-90"
          >
            ▶ Play
          </button>
        </div>
        {previewAudio && (
          <audio controls autoPlay src={previewAudio} className="mt-3 h-9 w-full" />
        )}
      </section>

      <section className="mt-4 rounded-2xl border border-line bg-card p-5 shadow-sm">
        <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-muted">
          Clone your voice (OmniVoice)
        </h2>
        <p className="mb-3 text-xs text-muted">
          Record ~5 seconds of yourself, type exactly what you said below, then
          clone. Maya will then speak in your voice.
        </p>
        <div className="flex items-center gap-3">
          <button
            onClick={handleClone}
            className={`grid h-12 w-12 shrink-0 place-items-center rounded-full text-xl text-white ${
              recClone ? "animate-pulse bg-brand" : "bg-brand hover:bg-brand-600"
            }`}
            aria-label={recClone ? "Stop and clone" : "Record your voice"}
          >
            {recClone ? "⏹" : "🎤"}
          </button>
          <input
            value={cloneText}
            onChange={(e) => setCloneText(e.target.value)}
            placeholder="Type what you will say / said"
            className="flex-1 rounded-lg border border-line bg-cream px-3 py-2.5 text-sm outline-none focus:border-brand"
          />
        </div>
      </section>

      <section className="mt-4 rounded-2xl border border-line bg-card p-5 shadow-sm">
        <h2 className="mb-4 text-sm font-semibold uppercase tracking-wide text-muted">
          Restaurant identity
        </h2>
        <div className="flex gap-3">
          <div className="flex-1">
            <label className="mb-1 block text-sm font-medium">Restaurant name</label>
            <input
              value={restaurant}
              onChange={(e) => setRestaurant(e.target.value)}
              className="w-full rounded-lg border border-line bg-cream px-3 py-2.5 text-sm outline-none focus:border-brand"
            />
          </div>
          <div className="flex-1">
            <label className="mb-1 block text-sm font-medium">City</label>
            <input
              value={city}
              onChange={(e) => setCity(e.target.value)}
              className="w-full rounded-lg border border-line bg-cream px-3 py-2.5 text-sm outline-none focus:border-brand"
            />
          </div>
        </div>
      </section>

      <div className="mt-6 flex justify-end">
        <button
          onClick={save}
          className="rounded-xl bg-brand px-5 py-2.5 text-sm font-semibold text-white hover:bg-brand-600"
        >
          Save settings
        </button>
      </div>

      {health && (
        <section className="mt-8 rounded-2xl border border-line bg-card p-5 text-sm text-muted shadow-sm">
          <h2 className="mb-2 text-sm font-semibold uppercase tracking-wide">
            System
          </h2>
          <ul className="flex flex-col gap-1">
            <li>
              <span className="text-ink">ASR:</span> faster-whisper{" "}
              <code>{health.asr_model}</code> · Silero VAD enabled
            </li>
            <li>
              <span className="text-ink">LLM:</span> Ollama (local, on-device) —{" "}
              {health.ollama ? "🟢 running" : "🔴 offline"}
            </li>
            <li>
              <span className="text-ink">TTS:</span> edge-tts · Microsoft neural
              Nepali voice (free, no key)
            </li>
            <li>
              <span className="text-ink">Database:</span> SQLite at{" "}
              <code>data/maya.db</code>
            </li>
          </ul>
        </section>
      )}
    </div>
  );
}
