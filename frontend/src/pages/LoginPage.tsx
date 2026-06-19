import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { apiClient } from '@/api/client';

export default function LoginPage() {
  const navigate = useNavigate();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const res = await apiClient.post('/api/v1/auth/token', {
        username: email,
        password,
      });
      localStorage.setItem('gnosis_token', res.data.access_token);
      navigate('/');
    } catch {
      setError('Invalid email or password.');
    } finally {
      setLoading(false);
    }
  }

  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        minHeight: '100dvh',
        background: 'var(--color-bg)',
      }}
    >
      <form
        onSubmit={handleSubmit}
        style={{
          width: '100%',
          maxWidth: 360,
          padding: 'var(--space-8)',
          background: 'var(--color-surface)',
          border: '1px solid var(--color-border)',
          borderRadius: 'var(--radius-xl)',
          boxShadow: 'var(--shadow-md)',
          display: 'flex',
          flexDirection: 'column',
          gap: 'var(--space-4)',
        }}
      >
        <h1 style={{ fontSize: 'var(--text-xl)', fontWeight: 700, textAlign: 'center' }}>
          Gnosis KB
        </h1>

        {error && (
          <p style={{ color: 'var(--color-error)', fontSize: 'var(--text-sm)', textAlign: 'center' }}>
            {error}
          </p>
        )}

        <label style={{ fontSize: 'var(--text-sm)', fontWeight: 500 }}>
          Email
          <input
            type="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            style={{
              display: 'block',
              width: '100%',
              marginTop: 'var(--space-1)',
              padding: 'var(--space-2) var(--space-3)',
              background: 'var(--color-surface-2)',
              border: '1px solid var(--color-border)',
              borderRadius: 'var(--radius-md)',
              fontSize: 'var(--text-base)',
              color: 'var(--color-text)',
            }}
          />
        </label>

        <label style={{ fontSize: 'var(--text-sm)', fontWeight: 500 }}>
          Password
          <input
            type="password"
            required
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            style={{
              display: 'block',
              width: '100%',
              marginTop: 'var(--space-1)',
              padding: 'var(--space-2) var(--space-3)',
              background: 'var(--color-surface-2)',
              border: '1px solid var(--color-border)',
              borderRadius: 'var(--radius-md)',
              fontSize: 'var(--text-base)',
              color: 'var(--color-text)',
            }}
          />
        </label>

        <button
          type="submit"
          disabled={loading}
          style={{
            padding: 'var(--space-3)',
            background: 'var(--color-primary)',
            color: '#fff',
            border: 'none',
            borderRadius: 'var(--radius-md)',
            fontSize: 'var(--text-sm)',
            fontWeight: 600,
            cursor: loading ? 'not-allowed' : 'pointer',
            opacity: loading ? 0.7 : 1,
          }}
        >
          {loading ? 'Signing in…' : 'Sign in'}
        </button>
      </form>
    </div>
  );
}
