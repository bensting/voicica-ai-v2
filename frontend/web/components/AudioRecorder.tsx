"use client";

import { useCallback, useEffect, useRef, useState } from "react";

const MAX_SECONDS = 30; // matches the prior project's own clone recorder — a
// voice sample doesn't need to be long, and it caps how much a user can
// accidentally record before noticing.

export interface RecordedAudio {
  blob: Blob;
  fileName: string;
}

/** Records (or accepts an uploaded file for) a short voice sample for
 * cloning — the Clone tab's input. Recording is the prior project's own
 * verified UX (`AudioUploader.tsx`: MediaRecorder, webm/opus, 30s cap); the
 * "or choose a file" fallback is new here — useful for anyone who'd rather
 * reuse an existing clip than grant mic access, and the only way this flow
 * is testable without a real microphone. */
export function AudioRecorder({
  value,
  onChange,
}: {
  value: RecordedAudio | null;
  onChange: (audio: RecordedAudio | null) => void;
}) {
  const [isRecording, setIsRecording] = useState(false);
  const [elapsed, setElapsed] = useState(0);
  const [isPlaying, setIsPlaying] = useState(false);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);

  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const previewUrlRef = useRef<string | null>(null);

  const setPreview = useCallback((blob: Blob | null) => {
    if (previewUrlRef.current) URL.revokeObjectURL(previewUrlRef.current);
    const url = blob ? URL.createObjectURL(blob) : null;
    previewUrlRef.current = url;
    setPreviewUrl(url);
  }, []);

  const stopRecording = useCallback(() => {
    if (timerRef.current) {
      clearInterval(timerRef.current);
      timerRef.current = null;
    }
    if (mediaRecorderRef.current && mediaRecorderRef.current.state !== "inactive") {
      mediaRecorderRef.current.stop();
    }
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((t) => t.stop());
      streamRef.current = null;
    }
    setIsRecording(false);
    setElapsed(0);
  }, []);

  const startRecording = useCallback(async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamRef.current = stream;

      const mimeType = MediaRecorder.isTypeSupported("audio/webm;codecs=opus")
        ? "audio/webm;codecs=opus"
        : MediaRecorder.isTypeSupported("audio/ogg;codecs=opus")
          ? "audio/ogg;codecs=opus"
          : "";

      const recorder = new MediaRecorder(stream, mimeType ? { mimeType } : undefined);
      mediaRecorderRef.current = recorder;
      chunksRef.current = [];

      recorder.ondataavailable = (e) => {
        if (e.data.size > 0) chunksRef.current.push(e.data);
      };
      recorder.onstop = () => {
        const ext = (recorder.mimeType || "").includes("ogg") ? "ogg" : "webm";
        const blob = new Blob(chunksRef.current, { type: recorder.mimeType || "audio/webm" });
        setPreview(blob);
        onChange({ blob, fileName: `recording.${ext}` });
      };

      recorder.start(100);
      setIsRecording(true);
      setElapsed(0);

      let secs = 0;
      timerRef.current = setInterval(() => {
        secs += 1;
        setElapsed(secs);
        if (secs >= MAX_SECONDS) stopRecording();
      }, 1000);
    } catch {
      onChange(null);
    }
  }, [onChange, setPreview, stopRecording]);

  function handleFilePicked(file: File) {
    setPreview(file);
    onChange({ blob: file, fileName: file.name });
  }

  useEffect(
    () => () => {
      if (timerRef.current) clearInterval(timerRef.current);
      streamRef.current?.getTracks().forEach((t) => t.stop());
      if (previewUrlRef.current) URL.revokeObjectURL(previewUrlRef.current);
    },
    [],
  );

  function togglePlayback() {
    if (!previewUrl) return;
    if (isPlaying && audioRef.current) {
      audioRef.current.pause();
      setIsPlaying(false);
      return;
    }
    const audio = new Audio(previewUrl);
    audio.onended = () => setIsPlaying(false);
    audio.play();
    audioRef.current = audio;
    setIsPlaying(true);
  }

  function remove() {
    audioRef.current?.pause();
    setIsPlaying(false);
    setPreview(null);
    onChange(null);
  }

  if (value) {
    return (
      <div className="rounded-2xl border border-border-soft bg-surface p-3.5">
        <div className="flex items-center gap-3">
          <button
            onClick={togglePlayback}
            aria-label={isPlaying ? "Pause" : "Play"}
            className="flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-full bg-surface-2 text-a3"
          >
            {isPlaying ? (
              <svg width="15" height="15" viewBox="0 0 24 24" fill="currentColor">
                <rect x="6" y="4" width="4" height="16" />
                <rect x="14" y="4" width="4" height="16" />
              </svg>
            ) : (
              <svg width="15" height="15" viewBox="0 0 24 24" fill="currentColor">
                <path d="M8 5v14l11-7z" />
              </svg>
            )}
          </button>
          <div className="min-w-0 flex-1">
            <div className="truncate text-[13.5px] font-medium">{value.fileName}</div>
            <div className="mt-0.5 text-[11.5px] text-text-2">Ready to clone</div>
          </div>
          <button onClick={remove} aria-label="Remove" className="p-1.5 text-text-2 active:text-danger">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6">
              <path d="M3 6h18M8 6V4a2 2 0 012-2h4a2 2 0 012 2v2M19 6v14a2 2 0 01-2 2H7a2 2 0 01-2-2V6" />
            </svg>
          </button>
        </div>
      </div>
    );
  }

  if (isRecording) {
    const pct = (elapsed / MAX_SECONDS) * 100;
    return (
      <div className="rounded-2xl border border-border-soft bg-surface p-3.5">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className="h-2 w-2 animate-pulse rounded-full bg-danger" />
            <span className="text-[13.5px] font-medium">Recording…</span>
          </div>
          <span className="text-[11.5px] tabular-nums text-text-2">
            {elapsed}s / {MAX_SECONDS}s
          </span>
        </div>
        <div className="mt-2.5 h-1.5 w-full overflow-hidden rounded-full bg-surface-2">
          <div className="h-full bg-danger transition-[width] duration-1000 ease-linear" style={{ width: `${pct}%` }} />
        </div>
        <button
          onClick={stopRecording}
          className="mt-3 flex w-full items-center justify-center gap-2 rounded-xl border border-danger/30 bg-danger/10 py-2.5 text-sm font-medium text-danger"
        >
          <svg width="13" height="13" viewBox="0 0 24 24" fill="currentColor">
            <rect x="5" y="5" width="14" height="14" rx="2" />
          </svg>
          Stop recording
        </button>
      </div>
    );
  }

  return (
    <div className="flex flex-col items-center rounded-2xl border border-border-soft bg-surface px-4 py-6 text-center">
      <button
        onClick={() => void startRecording()}
        className="flex flex-col items-center gap-2.5 focus:outline-none"
      >
        <div className="flex h-14 w-14 items-center justify-center rounded-full bg-a3/15 text-a3">
          <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7">
            <path d="M12 1a3 3 0 00-3 3v8a3 3 0 006 0V4a3 3 0 00-3-3z" />
            <path d="M19 10v2a7 7 0 01-14 0v-2" />
            <line x1="12" y1="19" x2="12" y2="23" />
          </svg>
        </div>
        <div>
          <div className="text-[13.5px] font-medium">Start recording</div>
          <div className="mt-0.5 text-[11.5px] text-text-2">Up to {MAX_SECONDS} seconds</div>
        </div>
      </button>
      <button
        onClick={() => fileInputRef.current?.click()}
        className="mt-4 text-[12px] font-medium text-a3 focus:outline-none"
      >
        or choose an audio file
      </button>
      <input
        ref={fileInputRef}
        type="file"
        accept="audio/*"
        className="hidden"
        onChange={(e) => {
          const file = e.target.files?.[0];
          if (file) handleFilePicked(file);
          e.target.value = "";
        }}
      />
    </div>
  );
}
