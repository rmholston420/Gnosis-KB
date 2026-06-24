/**
 * RegisterPage — new account creation form.
 */
import React, { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import api from '../services/api';
import { useAppStore } from '../store/useAppStore';

export default function RegisterPage() {
  const navigate  = useNavigate();
  const setUser   = useAppStore((s) => s.setUser);

  const [form, setForm] = useState({ username: '', email: '', password: '', confirm: '' });
  const [error, setError]     = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) =>
    setForm((f) => ({ ...f, [e.target.name]: e.target.value }));

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    if (form.password !== form.confirm) {
      setError('Passwords do not match.');
      return;
    }

    setLoading(true);
    try {
      const res = await api.post<{ access_token: string; username: string; email: string }>(
        '/auth/register',
        { username: form.username, email: form.email, password: form.password },
      );
      if (typeof localStorage !== 'undefined') {
        localStorage.setItem('gnosis_token', res.access_token);
      }
      setUser({ username: res.username, email: res.email });
      navigate('/', { replace: true });
    } catch (err) {
      setError((err as Error).message ?? 'Registration failed.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-gnosis-bg px-4">
      <div className="w-full max-w-sm">
        <h1 className="text-2xl font-semibold text-gnosis-fg mb-8 text-center">Create account</h1>

        <form onSubmit={handleSubmit} className="space-y-4">
          {['username','email','password','confirm'].map((field) => (
            <div key={field}>
              <label className="block text-sm font-medium text-gnosis-fg mb-1 capitalize">
                {field === 'confirm' ? 'Confirm password' : field}
              </label>
              <input
                type={field.includes('password') || field === 'confirm' ? 'password' : field === 'email' ? 'email' : 'text'}
                name={field}
                value={(form as Record<string, string>)[field]}
                onChange={handleChange}
                required
                className="w-full rounded-lg border border-gnosis-border bg-gnosis-surface px-3 py-2 text-sm text-gnosis-fg focus:outline-none focus:ring-2 focus:ring-gnosis-accent"
              />
            </div>
          ))}

          {error && <p className="text-sm text-red-500">{error}</p>}

          <button
            type="submit"
            disabled={loading}
            className="w-full py-2 rounded-lg bg-gnosis-accent text-white text-sm font-medium disabled:opacity-50 hover:opacity-90 transition-opacity"
          >
            {loading ? 'Creating account…' : 'Register'}
          </button>
        </form>

        <p className="mt-4 text-center text-sm text-gnosis-muted">
          Already have an account?{' '}
          <Link to="/login" className="text-gnosis-accent hover:underline">Sign in</Link>
        </p>
      </div>
    </div>
  );
}
