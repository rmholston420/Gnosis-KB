import { useState } from 'react';
import { useNavigate } from 'react-router-dom';

export default function LoginPage() {
  const navigate = useNavigate();
  const [email, setEmail]       = useState('');
  const [password, setPassword] = useState('');
  const [error, setError]       = useState<string | null>(null);
  const [loading, setLoading]   = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      // FastAPI OAuth2PasswordRequestForm requires form-encoded body, not JSON
      const body = new URLSearchParams();
      body.append('username', email);
      body.append('password', password);

      const res = await fetch('/api/v1/auth/token', {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body: body.toString(),
      });

      if (!res.ok) throw new Error('Invalid credentials');
      const data = await res.json();
      localStorage.setItem('gnosis_token', data.access_token);
      navigate('/');
    } catch {
      setError('Invalid email or password.');
    } finally {
      setLoading(false);
    }
  }

  const inputStyle: React.CSSProperties = {
    display: 'block',
    width: '100%',
    marginTop: '4px',
    padding: '8px 12px',
    background: '#21262d',
    border: '1px solid #30363d',
    borderRadius: '6px',
    fontSize: '0.875rem',
    color: '#e6edf3',
    outline: 'none',
  };

  return (
    <div style={{
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      minHeight: '100dvh',
      background: '#0d1117',
    }}>
      <form
        onSubmit={handleSubmit}
        style={{
          width: '100%',
          maxWidth: 360,
          padding: '2rem',
          background: '#161b22',
          border: '1px solid #30363d',
          borderRadius: '12px',
          boxShadow: '0 8px 32px rgba(0,0,0,0.4)',
          display: 'flex',
          flexDirection: 'column',
          gap: '1rem',
        }}
      >
        {/* Logo mark */}
        <div style={{ textAlign: 'center', marginBottom: '0.5rem' }}>
          <svg width="36" height="36" viewBox="0 0 36 36" fill="none" style={{ margin: '0 auto 8px' }}>
            <circle cx="18" cy="18" r="17" stroke="#4f98a3" strokeWidth="2"/>
            <circle cx="18" cy="18" r="6" fill="#4f98a3" opacity="0.3"/>
            <circle cx="18" cy="18" r="2.5" fill="#4f98a3"/>
            <line x1="18" y1="4" x2="18" y2="11" stroke="#4f98a3" strokeWidth="1.5" strokeLinecap="round"/>
            <line x1="18" y1="25" x2="18" y2="32" stroke="#4f98a3" strokeWidth="1.5" strokeLinecap="round"/>
            <line x1="4" y1="18" x2="11" y2="18" stroke="#4f98a3" strokeWidth="1.5" strokeLinecap="round"/>
            <line x1="25" y1="18" x2="32" y2="18" stroke="#4f98a3" strokeWidth="1.5" strokeLinecap="round"/>
          </svg>
          <h1 style={{ fontSize: '1.25rem', fontWeight: 700, color: '#e6edf3', margin: 0 }}>Gnosis KB</h1>
          <p style={{ fontSize: '0.8125rem', color: '#8b949e', marginTop: '4px' }}>Sign in to your vault</p>
        </div>

        {error && (
          <p style={{ color: '#da3633', fontSize: '0.8125rem', textAlign: 'center', margin: 0 }}>
            {error}
          </p>
        )}

        <label style={{ fontSize: '0.8125rem', fontWeight: 500, color: '#e6edf3' }}>
          Email
          <input type="email" required value={email} onChange={(e) => setEmail(e.target.value)} style={inputStyle} />
        </label>

        <label style={{ fontSize: '0.8125rem', fontWeight: 500, color: '#e6edf3' }}>
          Password
          <input type="password" required value={password} onChange={(e) => setPassword(e.target.value)} style={inputStyle} />
        </label>

        <button
          type="submit"
          disabled={loading}
          style={{
            padding: '10px',
            background: loading ? '#1a4d6b' : '#1f6feb',
            color: '#fff',
            border: 'none',
            borderRadius: '6px',
            fontSize: '0.875rem',
            fontWeight: 600,
            cursor: loading ? 'not-allowed' : 'pointer',
            transition: 'background 0.15s',
            marginTop: '0.25rem',
          }}
        >
          {loading ? 'Signing in…' : 'Sign in'}
        </button>
      </form>
    </div>
  );
}
