"use client";

import { useCallback, useRef, useState } from "react";

/**
 * Automatic barge-in: monitors the microphone for voice while Maya is speaking,
 * so the caller can interrupt her just like a real call. Uses a small
 * AnalyserNode RMS check — no audio leaves the browser.
 */
export function useBargeIn(onSpeech: () => void) {
  const streamRef = useRef<MediaStream | null>(null);
  const ctxRef = useRef<AudioContext | null>(null);
  const rafRef = useRef<number | null>(null);
  const onSpeechRef = useRef(onSpeech);
  onSpeechRef.current = onSpeech;
  const [listening, setListening] = useState(false);

  const stop = useCallback(() => {
    if (rafRef.current) {
      cancelAnimationFrame(rafRef.current);
      rafRef.current = null;
    }
    streamRef.current?.getTracks().forEach((t) => t.stop());
    streamRef.current = null;
    if (ctxRef.current) {
      ctxRef.current.close();
      ctxRef.current = null;
    }
    setListening(false);
  }, []);

  const start = useCallback(async () => {
    if (streamRef.current) return;
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamRef.current = stream;
      const ctx = new AudioContext();
      ctxRef.current = ctx;
      const source = ctx.createMediaStreamSource(stream);
      const analyser = ctx.createAnalyser();
      analyser.fftSize = 1024;
      source.connect(analyser);

      const data = new Uint8Array(analyser.fftSize);
      let above = 0;
      setListening(true);

      const tick = () => {
        analyser.getByteTimeDomainData(data);
        let sum = 0;
        for (let i = 0; i < data.length; i++) {
          const v = (data[i] - 128) / 128;
          sum += v * v;
        }
        const rms = Math.sqrt(sum / data.length);
        if (rms > 0.035) above += 1;
        else above = 0;

        if (above > 6) {
          // Sustained speech -> caller is interrupting.
          stop();
          onSpeechRef.current();
        } else {
          rafRef.current = requestAnimationFrame(tick);
        }
      };
      rafRef.current = requestAnimationFrame(tick);
    } catch {
      /* mic unavailable — barge-in simply won't arm */
    }
  }, [stop]);

  return { start, stop, listening };
}
