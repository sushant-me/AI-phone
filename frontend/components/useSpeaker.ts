"use client";

import { useCallback, useEffect, useRef, useState } from "react";

function base64ToBytes(b64: string): Uint8Array {
  const bin = atob(b64);
  const bytes = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
  return bytes;
}

/**
 * Gapless speech playback. Each sentence's MP3 is decoded to an AudioBuffer and
 * scheduled back-to-back on one AudioContext, so Maya speaks smoothly with no
 * gaps (the source of the "robotic" sound when files are switched via <audio>).
 */
export function useSpeaker() {
  const ctxRef = useRef<AudioContext | null>(null);
  const nextTimeRef = useRef(0);
  const sourcesRef = useRef<AudioBufferSourceNode[]>([]);
  const [speaking, setSpeaking] = useState(false);

  const ensureCtx = useCallback(() => {
    if (!ctxRef.current) ctxRef.current = new AudioContext();
    return ctxRef.current;
  }, []);

  const speak = useCallback(
    async (b64: string) => {
      if (!b64) return;
      const ctx = ensureCtx();
      if (ctx.state === "suspended") await ctx.resume();
      try {
        const bytes = base64ToBytes(b64);
        // decodeAudioData detaches the buffer, so hand it a real ArrayBuffer.
        const buffer = await ctx.decodeAudioData(bytes.buffer);
        const now = ctx.currentTime + 0.03;
        const when = Math.max(nextTimeRef.current, now);
        const src = ctx.createBufferSource();
        src.buffer = buffer;
        src.connect(ctx.destination);
        src.start(when);
        sourcesRef.current.push(src);
        nextTimeRef.current = when + buffer.duration;
        setSpeaking(true);
      } catch {
        /* skip undecodable chunk */
      }
    },
    [ensureCtx],
  );

  const stop = useCallback(() => {
    sourcesRef.current.forEach((s) => {
      try {
        s.stop();
      } catch {
        /* already stopped */
      }
    });
    sourcesRef.current = [];
    nextTimeRef.current = 0;
    setSpeaking(false);
  }, []);

  // Poll: clear the "speaking" flag once the scheduled speech has finished.
  useEffect(() => {
    const timer = setInterval(() => {
      const ctx = ctxRef.current;
      if (ctx && nextTimeRef.current > 0 && ctx.currentTime >= nextTimeRef.current) {
        setSpeaking(false);
      }
    }, 200);
    return () => clearInterval(timer);
  }, []);

  const release = useCallback(() => {
    stop();
    if (ctxRef.current) {
      ctxRef.current.close();
      ctxRef.current = null;
    }
  }, [stop]);

  return { speak, stop, release, speaking };
}
