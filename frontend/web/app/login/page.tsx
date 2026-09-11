"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { useAuth } from "@/lib/auth-context";
import { ApiError } from "@/lib/api";

export default function LoginPage() {
  const { user, loading, signInWithEmail, signUpWithEmail, signInWithGoogle } =
    useAuth();
  const router = useRouter();

  const [mode, setMode] = useState<"signin" | "signup">("signin");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (!loading && user) router.replace("/");
  }, [loading, user, router]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      if (mode === "signin") {
        await signInWithEmail(email, password);
      } else {
        await signUpWithEmail(email, password);
      }
    } catch (err) {
      setError(err instanceof ApiError ? err.message : describeFirebaseError(err));
    } finally {
      setSubmitting(false);
    }
  }

  async function handleGoogle() {
    setError(null);
    setSubmitting(true);
    try {
      await signInWithGoogle();
    } catch (err) {
      setError(describeFirebaseError(err));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="relative min-h-screen bg-bg overflow-hidden">
      <div className="pointer-events-none absolute inset-0 overflow-hidden">
        <div className="absolute -top-[10%] -left-[10%] w-[60%] h-[34%] rounded-full bg-a1/15 blur-[90px]" />
        <div className="absolute bottom-[6%] -right-[14%] w-[55%] h-[30%] rounded-full bg-a2/10 blur-[90px]" />
      </div>

      <div className="relative flex min-h-screen flex-col justify-center px-6 py-12 max-w-sm mx-auto">
        <div className="flex items-center gap-2.5 mb-10 justify-center">
          <div className="w-8 h-8 rounded-[9px] grad-bg flex items-center justify-center">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#0a0a1a" strokeWidth="2.2" strokeLinecap="round">
              <path d="M12 3v9" />
              <path d="M8 8c0 4 1.8 6 4 6s4-2 4-6" />
              <path d="M12 17v4" />
            </svg>
          </div>
          <span className="font-display font-bold text-xl tracking-tight">Voicica</span>
        </div>

        <h1 className="font-display font-bold text-2xl text-center mb-1.5">
          {mode === "signin" ? "Welcome back" : "Create your account"}
        </h1>
        <p className="text-text-2 text-sm text-center mb-8">
          {mode === "signin"
            ? "Sign in to keep creating."
            : "A few seconds and you're in."}
        </p>

        <form onSubmit={handleSubmit} className="flex flex-col gap-3">
          <input
            type="email"
            required
            placeholder="Email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="rounded-2xl bg-surface border border-border-soft px-4 py-3.5 text-sm outline-none focus:border-a3 placeholder:text-text-3"
          />
          <input
            type="password"
            required
            minLength={6}
            placeholder="Password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="rounded-2xl bg-surface border border-border-soft px-4 py-3.5 text-sm outline-none focus:border-a3 placeholder:text-text-3"
          />

          {error && (
            <div className="rounded-xl bg-danger/10 border border-danger/25 px-3.5 py-2.5 text-sm text-danger">
              {error}
            </div>
          )}

          <button
            type="submit"
            disabled={submitting}
            className="grad-bg mt-1 rounded-2xl py-3.5 font-semibold text-sm text-[#120a1c] disabled:opacity-50"
          >
            {submitting
              ? "Please wait…"
              : mode === "signin"
                ? "Sign in"
                : "Sign up"}
          </button>
        </form>

        <div className="flex items-center gap-3 my-5">
          <div className="h-px flex-1 bg-border-soft" />
          <span className="text-xs text-text-3">or</span>
          <div className="h-px flex-1 bg-border-soft" />
        </div>

        <button
          onClick={handleGoogle}
          disabled={submitting}
          className="flex items-center justify-center gap-2.5 rounded-2xl border border-border-soft bg-surface py-3.5 text-sm font-medium disabled:opacity-50"
        >
          <GoogleIcon />
          Continue with Google
        </button>

        <button
          onClick={() => {
            setError(null);
            setMode(mode === "signin" ? "signup" : "signin");
          }}
          className="mt-7 text-center text-sm text-text-2"
        >
          {mode === "signin" ? (
            <>Don&apos;t have an account? <span className="text-a3 font-medium">Sign up</span></>
          ) : (
            <>Already have an account? <span className="text-a3 font-medium">Sign in</span></>
          )}
        </button>
      </div>
    </div>
  );
}

function describeFirebaseError(err: unknown): string {
  const code = (err as { code?: string } | undefined)?.code ?? "";
  const known: Record<string, string> = {
    "auth/invalid-email": "That email address doesn't look right.",
    "auth/invalid-credential": "Email or password is incorrect.",
    "auth/email-already-in-use": "An account already exists with that email.",
    "auth/weak-password": "Use at least 6 characters.",
    "auth/popup-closed-by-user": "Sign-in was cancelled.",
  };
  return known[code] ?? "Something went wrong. Please try again.";
}

function GoogleIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24">
      <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92a5.06 5.06 0 0 1-2.2 3.32v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.1z" />
      <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.99.66-2.25 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84A11 11 0 0 0 12 23z" />
      <path fill="#FBBC05" d="M5.84 14.09A6.6 6.6 0 0 1 5.49 12c0-.73.12-1.43.35-2.09V7.07H2.18A11 11 0 0 0 1 12c0 1.78.43 3.46 1.18 4.93z" />
      <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1A11 11 0 0 0 2.18 7.07l3.66 2.84C6.71 7.31 9.14 5.38 12 5.38z" />
    </svg>
  );
}
