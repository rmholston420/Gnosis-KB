import React, { useState, useEffect } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  Settings, User, Share2, UserPlus, Trash2,
  CheckCircle, AlertCircle, Loader2, Shield,
  ChevronDown, ChevronRight, Cpu, Wifi, WifiOff,
} from 'lucide-react';
import { useAppStore } from '../store/useAppStore';

// ---- Authenticated fetch helper ------------------------------------------

function token() { return localStorage.getItem('gnosis_token') ?? ''; }

async function apiFetch<T>(path: string, init: RequestInit = {}): Promise<T> {
  const res = await fetch(`/api/v1${path}`, {
    ...init,
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token()}`,
      ...(init.headers as Record<string, string> ?? {}),
    },
  });
  if (!res.ok) {
    const d = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(typeof d.detail === 'string' ? d.detail : JSON.stringify(d));
  }
  if (res.status === 204) return undefined as unknown as T;
  return res.json();
}

// ---- Types ---------------------------------------------------------------

interface UserProfile {
  id: number;
  email: string;
  full_name: string | null;
  vault_slug: string | null;
  vault_path: string | null;
  vault_display_name: string | null;
  is_superuser: boolean;
}

interface SharedVaultGrant {
  id: number;
  owner_id: number;
  owner_email: string;
  owner_vault_display_name: string | null;
  member_id: number;
  member_email: string;
  permission: string;
  is_active: boolean;
  accepted_at: string | null;
}

interface AIProviderInfo {
  provider: string;
  model: string;
  available: boolean;
  models?: string[];
}

// ---- Section shell -------------------------------------------------------

function Section({ icon: Icon, title, children }: {
  icon: React.ElementType; title: string; children: React.ReactNode;
}) {
  const [open, setOpen] = useState(true);
  return (
    <div className="rounded-xl border border-border overflow-hidden">
      <button
        onClick={() => setOpen(v => !v)}
        className="flex w-full items-center gap-2 px-5 py-4 bg-bg-secondary text-left hover:bg-bg-tertiary transition-colors"
      >
        <Icon size={16} className="text-text-muted" />
        <span className="font-semibold text-sm flex-1 text-text-primary">{title}</span>
        {open
          ? <ChevronDown size={14} className="text-text-muted" />
          : <ChevronRight size={14} className="text-text-muted" />}
      </button>
      {open && <div className="p-5 space-y-4 bg-bg-primary">{children}</div>}
    </div>
  );
}

// ---- Input / Label shared styles -----------------------------------------

const inputCls = [
  'w-full rounded-lg border border-border bg-bg-tertiary',
  'px-3 py-2 text-sm text-text-primary placeholder-text-muted',
  'focus:outline-none focus:ring-2 focus:ring-accent-blue transition-colors',
].join(' ');

const labelCls = 'block space-y-1';
const labelTextCls = 'text-xs font-medium text-text-muted';

// ---- Profile section -----------------------------------------------------

function ProfileSection() {
  const qc = useQueryClient();
  const { data: me, isLoading } = useQuery<UserProfile>({
    queryKey: ['me'],
    queryFn: () => apiFetch<UserProfile>('/users/me'),
  });
  const [form, setForm] = useState({ full_name: '', vault_slug: '', vault_display_name: '' });
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    if (me) setForm({
      full_name: me.full_name ?? '',
      vault_slug: me.vault_slug ?? '',
      vault_display_name: me.vault_display_name ?? '',
    });
  }, [me]);

  const mutation = useMutation({
    mutationFn: () => apiFetch<UserProfile>('/users/me', {
      method: 'PATCH',
      body: JSON.stringify(form),
    }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['me'] });
      setSaved(true);
      setTimeout(() => setSaved(false), 2500);
    },
  });

  if (isLoading) return (
    <div className="flex justify-center py-6">
      <Loader2 size={20} className="animate-spin text-text-muted" />
    </div>
  );

  return (
    <Section icon={User} title="Profile & Vault Identity">
      <div className="grid gap-3 sm:grid-cols-2">
        <label className={labelCls}>
          <span className={labelTextCls}>Full name</span>
          <input
            value={form.full_name}
            onChange={e => setForm(v => ({ ...v, full_name: e.target.value }))}
            className={inputCls}
          />
        </label>
        <label className={labelCls}>
          <span className={labelTextCls}>Email</span>
          <input
            value={me?.email ?? ''}
            disabled
            className="w-full rounded-lg border border-border bg-bg-secondary px-3 py-2 text-sm text-text-muted cursor-not-allowed"
          />
        </label>
        <label className={labelCls}>
          <span className={labelTextCls}>Vault slug</span>
          <input
            value={form.vault_slug}
            onChange={e => setForm(v => ({ ...v, vault_slug: e.target.value }))}
            placeholder="e.g. ryan"
            className={`${inputCls} font-mono`}
          />
          <p className="text-xs text-text-muted">Lowercase a-z, 0-9, dashes, underscores.</p>
        </label>
        <label className={labelCls}>
          <span className={labelTextCls}>Vault display name</span>
          <input
            value={form.vault_display_name}
            onChange={e => setForm(v => ({ ...v, vault_display_name: e.target.value }))}
            placeholder="e.g. Ryan's KB"
            className={inputCls}
          />
        </label>
      </div>

      {me?.vault_path && (
        <div className="flex items-center gap-2 rounded-lg bg-bg-tertiary px-3 py-2 text-xs">
          <span className="font-mono text-text-muted">{me.vault_path}</span>
          {me.is_superuser && (
            <span className="ml-auto rounded-full bg-accent-orange/20 px-2 py-0.5 text-accent-orange text-xs font-medium">
              admin
            </span>
          )}
        </div>
      )}

      <div className="flex items-center gap-2">
        <button
          onClick={() => mutation.mutate()}
          disabled={mutation.isPending}
          className="flex items-center gap-2 rounded-lg bg-accent-blue px-4 py-2 text-sm text-white font-medium hover:opacity-90 disabled:opacity-50 transition-opacity"
        >
          {mutation.isPending && <Loader2 size={13} className="animate-spin" />}
          Save changes
        </button>
        {saved && <span className="flex items-center gap-1 text-sm text-accent-green"><CheckCircle size={14} /> Saved</span>}
        {mutation.isError && <span className="flex items-center gap-1 text-sm text-accent-red"><AlertCircle size={14} /> Error saving</span>}
      </div>
    </Section>
  );
}

// ---- AI Provider section -------------------------------------------------

function AIProviderSection() {
  const { ragMode, setRagMode } = useAppStore();
  const [selectedModel, setSelectedModel] = useState('');
  const [saveStatus, setSaveStatus] = useState<'idle' | 'saving' | 'saved' | 'error'>('idle');

  const { data, isLoading, error, refetch } = useQuery<AIProviderInfo>({
    queryKey: ['ai-providers'],
    queryFn: () => apiFetch<AIProviderInfo>('/ai/providers'),
    retry: false,
    staleTime: 10_000,
  });

  useEffect(() => {
    if (data?.model && !selectedModel) setSelectedModel(data.model);
  }, [data]);

  async function handleSaveModel() {
    if (!selectedModel) return;
    setSaveStatus('saving');
    try {
      await apiFetch('/ai/providers/model', {
        method: 'POST',
        body: JSON.stringify({ model: selectedModel }),
      });
      await refetch();
      setSaveStatus('saved');
      setTimeout(() => setSaveStatus('idle'), 2500);
    } catch {
      setSaveStatus('error');
      setTimeout(() => setSaveStatus('idle'), 3000);
    }
  }

  const isAvailable = data?.available ?? false;
  const models = data?.models ?? (data?.model ? [data.model] : []);

  return (
    <Section icon={Cpu} title="AI Provider">
      {/* Connection status */}
      <div className="flex items-center gap-2">
        {isLoading ? (
          <Loader2 size={14} className="animate-spin text-text-muted" />
        ) : isAvailable ? (
          <Wifi size={14} className="text-accent-green" />
        ) : (
          <WifiOff size={14} className="text-accent-red" />
        )}
        <span className="text-sm text-text-primary">
          {isLoading
            ? 'Checking provider…'
            : isAvailable
              ? `${data?.provider ?? 'Unknown'} — connected`
              : 'No AI provider available'}
        </span>
        {error && (
          <span className="text-xs text-accent-red ml-2">{(error as Error).message}</span>
        )}
      </div>

      {/* Ollama hint when unavailable */}
      {!isLoading && !isAvailable && (
        <div className="rounded-lg bg-bg-tertiary border border-border px-4 py-3 text-sm space-y-1">
          <p className="font-medium text-text-primary">Ollama not detected</p>
          <p className="text-text-muted text-xs">Make sure Ollama is running and the <code className="font-mono bg-bg-elevated px-1 rounded">OLLAMA_BASE_URL</code> env var points to it.</p>
          <code className="block font-mono text-xs text-accent-cyan mt-2">ollama serve &amp;&amp; ollama pull llama3</code>
        </div>
      )}

      {/* Model picker */}
      {isAvailable && models.length > 0 && (
        <div className="space-y-2">
          <label className={labelCls}>
            <span className={labelTextCls}>Active model</span>
            <div className="flex gap-2">
              <select
                value={selectedModel}
                onChange={e => setSelectedModel(e.target.value)}
                className={`${inputCls} flex-1`}
              >
                {models.map(m => (
                  <option key={m} value={m}>{m}</option>
                ))}
              </select>
              <button
                onClick={handleSaveModel}
                disabled={saveStatus === 'saving'}
                className="flex items-center gap-1.5 rounded-lg bg-accent-blue px-4 py-2 text-sm text-white font-medium hover:opacity-90 disabled:opacity-50 transition-opacity"
              >
                {saveStatus === 'saving' ? <Loader2 size={13} className="animate-spin" /> : null}
                Apply
              </button>
            </div>
          </label>
          {saveStatus === 'saved' && <p className="text-xs text-accent-green flex items-center gap-1"><CheckCircle size={12} /> Model updated</p>}
          {saveStatus === 'error' && <p className="text-xs text-accent-red flex items-center gap-1"><AlertCircle size={12} /> Failed to update model</p>}
        </div>
      )}

      {/* RAG mode */}
      <label className={labelCls}>
        <span className={labelTextCls}>RAG mode</span>
        <select
          value={ragMode}
          onChange={e => setRagMode(e.target.value as typeof ragMode)}
          className={inputCls}
        >
          <option value="hybrid">Hybrid (local + global)</option>
          <option value="local">Local (vector similarity)</option>
          <option value="global">Global (graph traversal)</option>
        </select>
        <p className="text-xs text-text-muted">Controls how the AI retrieves context from your vault.</p>
      </label>
    </Section>
  );
}

// ---- Vault sharing section -----------------------------------------------

function VaultSharingSection() {
  const qc = useQueryClient();
  const { data: me } = useQuery<UserProfile>({
    queryKey: ['me'],
    queryFn: () => apiFetch<UserProfile>('/users/me'),
  });
  const { data: grants = [], isLoading } = useQuery<SharedVaultGrant[]>({
    queryKey: ['myVaults'],
    queryFn: () => apiFetch<SharedVaultGrant[]>('/users/me/vaults'),
  });

  const issued   = grants.filter(g => g.owner_id === me?.id);
  const received = grants.filter(g => g.member_id === me?.id);

  const [inviteEmail, setInviteEmail]           = useState('');
  const [invitePermission, setInvitePermission] = useState('read');
  const [inviteError, setInviteError]           = useState<string | null>(null);

  const inviteMutation = useMutation({
    mutationFn: () => apiFetch<SharedVaultGrant>('/users/me/vaults/invite', {
      method: 'POST',
      body: JSON.stringify({ member_email: inviteEmail.trim(), permission: invitePermission }),
    }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['myVaults'] });
      setInviteEmail('');
      setInviteError(null);
    },
    onError: (e: Error) => setInviteError(e.message),
  });

  const revokeMutation = useMutation({
    mutationFn: (id: number) => apiFetch<void>(`/users/me/vaults/${id}`, { method: 'DELETE' }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['myVaults'] }),
  });

  const acceptMutation = useMutation({
    mutationFn: (id: number) => apiFetch<SharedVaultGrant>(`/users/me/vaults/${id}/accept`, { method: 'POST' }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['myVaults'] }),
  });

  const updatePermMutation = useMutation({
    mutationFn: ({ id, permission }: { id: number; permission: string }) =>
      apiFetch<SharedVaultGrant>(`/users/me/vaults/${id}`, {
        method: 'PATCH',
        body: JSON.stringify({ permission }),
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['myVaults'] }),
  });

  return (
    <Section icon={Share2} title="Vault Sharing">
      <div className="space-y-2">
        <p className="text-sm font-medium text-text-primary">Share my vault with someone</p>
        <div className="flex gap-2">
          <input
            value={inviteEmail}
            onChange={e => setInviteEmail(e.target.value)}
            placeholder="colleague@example.com"
            type="email"
            className={`${inputCls} flex-1`}
          />
          <select
            value={invitePermission}
            onChange={e => setInvitePermission(e.target.value)}
            className={inputCls}
            style={{ width: 'auto' }}
          >
            <option value="read">Read</option>
            <option value="write">Write</option>
          </select>
          <button
            onClick={() => inviteMutation.mutate()}
            disabled={!inviteEmail.trim() || inviteMutation.isPending}
            className="flex items-center gap-1.5 rounded-lg bg-accent-blue px-4 py-2 text-sm text-white font-medium hover:opacity-90 disabled:opacity-50 transition-opacity"
          >
            {inviteMutation.isPending ? <Loader2 size={13} className="animate-spin" /> : <UserPlus size={13} />}
            Invite
          </button>
        </div>
        {inviteError && (
          <p className="flex items-center gap-1 text-xs text-accent-red">
            <AlertCircle size={12} />{inviteError}
          </p>
        )}
      </div>

      {issued.length > 0 && (
        <div className="space-y-2">
          <p className="text-xs font-semibold uppercase tracking-wider text-text-muted">Shared with</p>
          {issued.map(g => (
            <div key={g.id} className="flex items-center gap-2 rounded-lg border border-border px-3 py-2.5 text-sm">
              <User size={14} className="text-text-muted flex-shrink-0" />
              <span className="flex-1 truncate text-text-primary">{g.member_email}</span>
              <select
                value={g.permission}
                onChange={e => updatePermMutation.mutate({ id: g.id, permission: e.target.value })}
                className="rounded border border-border bg-bg-tertiary px-2 py-1 text-xs text-text-primary"
              >
                <option value="read">Read</option>
                <option value="write">Write</option>
              </select>
              <span className={`rounded-full px-2 py-0.5 text-xs ${
                g.accepted_at
                  ? 'bg-accent-green/10 text-accent-green'
                  : 'bg-accent-orange/10 text-accent-orange'
              }`}>
                {g.accepted_at ? 'Accepted' : 'Pending'}
              </span>
              <button
                onClick={() => revokeMutation.mutate(g.id)}
                className="text-text-muted hover:text-accent-red transition-colors"
                title="Revoke"
              >
                <Trash2 size={14} />
              </button>
            </div>
          ))}
        </div>
      )}

      {received.length > 0 && (
        <div className="space-y-2">
          <p className="text-xs font-semibold uppercase tracking-wider text-text-muted">Vaults I have access to</p>
          {received.map(g => (
            <div key={g.id} className="flex items-center gap-2 rounded-lg border border-border px-3 py-2.5 text-sm">
              <Shield size={14} className="text-text-muted flex-shrink-0" />
              <span className="flex-1 truncate text-text-primary">{g.owner_vault_display_name ?? g.owner_email}</span>
              <span className="rounded-full bg-accent-blue/10 px-2 py-0.5 text-xs text-accent-blue">{g.permission}</span>
              {!g.accepted_at && (
                <button
                  onClick={() => acceptMutation.mutate(g.id)}
                  className="rounded-lg bg-accent-green px-3 py-1 text-xs text-white hover:opacity-90 transition-opacity"
                >
                  Accept
                </button>
              )}
            </div>
          ))}
        </div>
      )}

      {!isLoading && issued.length === 0 && received.length === 0 && (
        <p className="text-sm text-text-muted text-center py-4">No shared vaults yet. Invite a colleague above.</p>
      )}
    </Section>
  );
}

// ---- Main Page -----------------------------------------------------------

export default function SettingsPage() {
  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center gap-3 border-b border-border px-6 py-4 flex-shrink-0">
        <Settings size={20} className="text-text-muted" />
        <div>
          <h1 className="text-lg font-semibold text-text-primary">Settings</h1>
          <p className="text-xs text-text-muted">Profile, vault identity, AI provider, and sharing</p>
        </div>
      </div>
      <div className="flex-1 overflow-y-auto p-6 space-y-4 max-w-2xl">
        <AIProviderSection />
        <ProfileSection />
        <VaultSharingSection />
      </div>
    </div>
  );
}
