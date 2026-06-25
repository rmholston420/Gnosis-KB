/**
 * RegisterPage
 * ============
 * User registration form.
 * Mirrors the LoginPage structure — email + password + confirm password.
 * On success the backend returns a JWT; we store it and redirect to /.
 */
import React, { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';

const BASE = (import.meta as { env?: { VITE_API_BASE_URL?: string } }).env?.VITE_API_BASE_URL ?? '/api';

export default function RegisterPage() {
  const navigate = useNavigate();
  const [email,    setEmail]    = useState('');
  const [password, setPassword] = useState('');
  const [confirm,  setConfirm]  = useState('');
  const [error,    setError]    = useState<string | null>(null);
  const [loading,  setLoading]  = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);

    if (password !== confirm) {
      setError('Passwords do not match.');
      return;
    }

    setLoading(true);
    try {
      const res = await fetch(`${BASE}/auth/register`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password }),
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({})) as { detail?: string };
        throw new Error(body.detail ?? 'Registration failed. Please try again.');
      }
      const data = await res.json() as { access_token: string };
      localStorage.setItem('gnosis_token', data.access_token);
      navigate('/', { replace: true });
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Registration failed. Please try again.');
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gnosis-bg">
      <div className="w-full max-w-sm p-8 rounded-xl bg-gnosis-surface border border-gnosis-border shadow-lg">
        {/* Logo / title */}
        <div className="mb-6 text-center">
          <h1 className="text-xl font-semibold text-gnosis-fg tracking-tight">Gnosis KB</h1>
          <p className="mt-1 text-sm text-gnosis-muted">Create your account</p>
        </div>

        <form onSubmit={handleSubmit} className="flex flex-col gap-4">
          {/* Email */}
          <div className="flex flex-col gap-1">
            <label htmlFor="email" className="text-xs font-medium text-gnosis-muted uppercase tracking-wide">
              Email
            </label>
            <input
              id="email"
              type="email"
              autoComplete="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="px-3 py-2 rounded-md bg-gnosis-bg border border-gnosis-border text-gnosis-fg text-sm
                         focus:outline-none focus:ring-2 focus:ring-gnosis-accent"
              placeholder="you@example.com"
            />
          </div>

          {/* Password */}
          <div className="flex flex-col gap-1">
            <label htmlFor="password" className="text-xs font-medium text-gnosis-muted uppercase tracking-wide">
              Password
            </label>
            <input
              id="password"
              type="password"
              autoComplete="new-password"
              required
              minLength={8}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="px-3 py-2 rounded-md bg-gnosis-bg border border-gnosis-border text-gnosis-fg text-sm
                         focus:outline-none focus:ring-2 focus:ring-gnosis-accent"
              placeholder="At least 8 characters"
            />
          </div>

          {/* Confirm password */}
          <div className="flex flex-col gap-1">
            <label htmlFor="confirm" className="text-xs font-medium text-gnosis-muted uppercase tracking-wide">
              Confirm Password
            </label>
            <input
              id="confirm"
              type="password"
              autoComplete="new-password"
              required
              minLength={8}
              value={confirm}
              onChange={(e) => setConfirm(e.target.value)}
              className="px-3 py-2 rounded-md bg-gnosis-bg border border-gnosis-border text-gnosis-fg text-sm
                         focus:outline-none focus:ring-2 focus:ring-gnosis-accent"
              placeholder="Repeat password"
            />
          </div>

          {/* Error message */}
          {error && (
            <p role="alert" className="text-xs text-red-500">
              {error}
            </p>
          )}

          {/* Submit */}
          <button
            type="submit"
            disabled={loading}
            className="mt-1 w-full py-2 rounded-md bg-gnosis-accent text-white text-sm font-medium
                       hover:opacity-90 transition-opacity disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {loading ? 'Creating account…' : 'Create account'}
          </button>
        </form>

        <p className="mt-5 text-center text-xs text-gnosis-muted">
          Already have an account?{' '}
          <Link to="/login" className="text-gnosis-accent hover:underline">
            Sign in
          </Link>
        </p>
      </div>
    </div>
  );
}
