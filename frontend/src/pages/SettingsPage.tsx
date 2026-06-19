import React, { useState, useEffect } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  Settings,
  User,
  FolderOpen,
  Share2,
  UserPlus,
  Trash2,
  CheckCircle,
  AlertCircle,
  Loader2,
  Shield,
  ChevronDown,
  ChevronRight,
} from 'lucide-react';
import axios from 'axios';

const API = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8010';
const ax = axios.create({ baseURL: `${API}/api/v1` });

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

// ---- API helpers ---------------------------------------------------------

const fetchMe = (): Promise<UserProfile> => ax.get('/users/me').then(r => r.data);
const fetchMyVaults = (): Promise<SharedVaultGrant[]> => ax.get('/users/me/vaults').then(r => r.data);
const updateMe = (data: Partial<UserProfile & { vault_slug: string; vault_display_name: string }>): Promise<UserProfile> =>
  ax.patch('/users/me', data).then(r => r.data);
const inviteToVault = (member_email: string, permission: string): Promise<SharedVaultGrant> =>
  ax.post('/users/me/vaults/invite', { member_email, permission }).then(r => r.data);
const revokeGrant = (id: number): Promise<void> =>
  ax.delete(`/users/me/vaults/${id}`).then(() => undefined);
const updateGrant = (id: number, permission: string): Promise<SharedVaultGrant> =>
  ax.patch(`/users/me/vaults/${id}`, { permission }).then(r => r.data);
const acceptInvite = (id: number): Promise<SharedVaultGrant> =>
  ax.post(`/users/me/vaults/${id}/accept`).then(r => r.data);

// ---- Section shell -------------------------------------------------------

function Section({ icon: Icon, title, children }: { icon: React.ElementType; title: string; children: React.ReactNode }) {
  const [open, setOpen] = useState(true);
  return (
    <div className="rounded-xl border border-gray-200 dark:border-gray-700 overflow-hidden">
      <button
        onClick={() => setOpen(v => !v)}
        className="flex w-full items-center gap-2 px-5 py-4 bg-gray-50 dark:bg-gray-800 text-left hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
      >
        <Icon size={16} className="text-gray-500" />
        <span className="font-semibold text-sm flex-1">{title}</span>
        {open ? <ChevronDown size={14} className="text-gray-400" /> : <ChevronRight size={14} className="text-gray-400" />}
      </button>
      {open && <div className="p-5 space-y-4">{children}</div>}
    </div>
  );
}

// ---- Profile section -----------------------------------------------------

function ProfileSection() {
  const qc = useQueryClient();
  const { data: me, isLoading } = useQuery({ queryKey: ['me'], queryFn: fetchMe });
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
    mutationFn: () => updateMe(form),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['me'] });
      setSaved(true);
      setTimeout(() => setSaved(false), 2500);
    },
  });

  if (isLoading) return <div className="flex justify-center py-6"><Loader2 size={20} className="animate-spin text-gray-400" /></div>;

  return (
    <Section icon={User} title="Profile & Vault Identity">
      <div className="grid gap-3 sm:grid-cols-2">
        <label className="block space-y-1">
          <span className="text-xs font-medium text-gray-500">Full name</span>
          <input
            value={form.full_name}
            onChange={e => setForm(v => ({ ...v, full_name: e.target.value }))}
            className="w-full rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </label>
        <label className="block space-y-1">
          <span className="text-xs font-medium text-gray-500">Email</span>
          <input value={me?.email ?? ''} disabled className="w-full rounded-lg border border-gray-200 dark:border-gray-700 bg-gray-100 dark:bg-gray-800 px-3 py-2 text-sm text-gray-400" />
        </label>
        <label className="block space-y-1">
          <span className="text-xs font-medium text-gray-500">Vault slug</span>
          <input
            value={form.vault_slug}
            onChange={e => setForm(v => ({ ...v, vault_slug: e.target.value }))}
            placeholder="e.g. ryan"
            className="w-full rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 px-3 py-2 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
          <p className="text-xs text-gray-400">Lowercase a-z, 0-9, dashes, underscores. Used as vault directory name.</p>
        </label>
        <label className="block space-y-1">
          <span className="text-xs font-medium text-gray-500">Vault display name</span>
          <input
            value={form.vault_display_name}
            onChange={e => setForm(v => ({ ...v, vault_display_name: e.target.value }))}
            placeholder="e.g. Ryan's KB"
            className="w-full rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </label>
      </div>

      {me?.vault_path && (
        <div className="flex items-center gap-2 rounded-lg bg-gray-50 dark:bg-gray-800 px-3 py-2 text-xs">
          <FolderOpen size={13} className="text-gray-400" />
          <span className="font-mono text-gray-500">{me.vault_path}</span>
          {me.is_superuser && <span className="ml-auto rounded-full bg-amber-100 dark:bg-amber-900/30 px-2 py-0.5 text-amber-600 dark:text-amber-400 font-medium">admin override</span>}
        </div>
      )}

      <div className="flex items-center gap-2">
        <button
          onClick={() => mutation.mutate()}
          disabled={mutation.isPending}
          className="flex items-center gap-2 rounded-lg bg-blue-600 px-4 py-2 text-sm text-white font-medium hover:bg-blue-700 disabled:opacity-50 transition-colors"
        >
          {mutation.isPending ? <Loader2 size={13} className="animate-spin" /> : null}
          Save changes
        </button>
        {saved && <span className="flex items-center gap-1 text-sm text-green-600"><CheckCircle size={14} /> Saved</span>}
        {mutation.isError && <span className="flex items-center gap-1 text-sm text-red-500"><AlertCircle size={14} /> Error saving</span>}
      </div>
    </Section>
  );
}

// ---- Vault sharing section -----------------------------------------------

function VaultSharingSection() {
  const qc = useQueryClient();
  const { data: me } = useQuery({ queryKey: ['me'], queryFn: fetchMe });
  const { data: grants = [], isLoading } = useQuery({
    queryKey: ['myVaults'],
    queryFn: fetchMyVaults,
  });

  // Partition into: grants I issued vs. grants I received
  const issued = grants.filter(g => g.owner_id === me?.id);
  const received = grants.filter(g => g.member_id === me?.id);

  const [inviteEmail, setInviteEmail] = useState('');
  const [invitePermission, setInvitePermission] = useState('read');
  const [inviteError, setInviteError] = useState<string | null>(null);

  const inviteMutation = useMutation({
    mutationFn: () => inviteToVault(inviteEmail.trim(), invitePermission),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['myVaults'] });
      setInviteEmail('');
      setInviteError(null);
    },
    onError: (e: any) => setInviteError(e?.response?.data?.detail ?? 'Invite failed'),
  });

  const revokeMutation = useMutation({
    mutationFn: revokeGrant,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['myVaults'] }),
  });

  const acceptMutation = useMutation({
    mutationFn: acceptInvite,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['myVaults'] }),
  });

  const updatePermMutation = useMutation({
    mutationFn: ({ id, permission }: { id: number; permission: string }) =>
      updateGrant(id, permission),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['myVaults'] }),
  });

  return (
    <Section icon={Share2} title="Vault Sharing">
      {/* Invite panel */}
      <div className="space-y-2">
        <p className="text-sm font-medium">Share my vault with someone</p>
        <div className="flex gap-2">
          <input
            value={inviteEmail}
            onChange={e => setInviteEmail(e.target.value)}
            placeholder="colleague@example.com"
            type="email"
            className="flex-1 rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
          <select
            value={invitePermission}
            onChange={e => setInvitePermission(e.target.value)}
            className="rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            <option value="read">Read</option>
            <option value="write">Write</option>
          </select>
          <button
            onClick={() => inviteMutation.mutate()}
            disabled={!inviteEmail.trim() || inviteMutation.isPending}
            className="flex items-center gap-1.5 rounded-lg bg-blue-600 px-4 py-2 text-sm text-white font-medium hover:bg-blue-700 disabled:opacity-50 transition-colors"
          >
            {inviteMutation.isPending ? <Loader2 size={13} className="animate-spin" /> : <UserPlus size={13} />}
            Invite
          </button>
        </div>
        {inviteError && (
          <p className="flex items-center gap-1 text-xs text-red-500"><AlertCircle size={12} />{inviteError}</p>
        )}
      </div>

      {/* Grants I issued */}
      {issued.length > 0 && (
        <div className="space-y-2">
          <p className="text-xs font-semibold uppercase tracking-wider text-gray-400">Shared with</p>
          {issued.map(g => (
            <div key={g.id} className="flex items-center gap-2 rounded-lg border border-gray-200 dark:border-gray-700 px-3 py-2.5 text-sm">
              <User size={14} className="text-gray-400 flex-shrink-0" />
              <span className="flex-1 truncate">{g.member_email}</span>
              <select
                value={g.permission}
                onChange={e => updatePermMutation.mutate({ id: g.id, permission: e.target.value })}
                className="rounded border border-gray-200 dark:border-gray-700 bg-transparent px-2 py-1 text-xs"
              >
                <option value="read">Read</option>
                <option value="write">Write</option>
              </select>
              <span className={`rounded-full px-2 py-0.5 text-xs ${
                g.accepted_at
                  ? 'bg-green-50 dark:bg-green-900/20 text-green-600 dark:text-green-400'
                  : 'bg-yellow-50 dark:bg-yellow-900/20 text-yellow-600 dark:text-yellow-400'
              }`}>
                {g.accepted_at ? 'Accepted' : 'Pending'}
              </span>
              <button
                onClick={() => revokeMutation.mutate(g.id)}
                className="text-gray-400 hover:text-red-500 transition-colors"
                title="Revoke access"
              >
                <Trash2 size={14} />
              </button>
            </div>
          ))}
        </div>
      )}

      {/* Grants I received */}
      {received.length > 0 && (
        <div className="space-y-2">
          <p className="text-xs font-semibold uppercase tracking-wider text-gray-400">Vaults I have access to</p>
          {received.map(g => (
            <div key={g.id} className="flex items-center gap-2 rounded-lg border border-gray-200 dark:border-gray-700 px-3 py-2.5 text-sm">
              <Shield size={14} className="text-gray-400 flex-shrink-0" />
              <span className="flex-1 truncate">
                {g.owner_vault_display_name ?? g.owner_email}
              </span>
              <span className="rounded-full bg-blue-50 dark:bg-blue-900/20 px-2 py-0.5 text-xs text-blue-600 dark:text-blue-400">
                {g.permission}
              </span>
              {!g.accepted_at && (
                <button
                  onClick={() => acceptMutation.mutate(g.id)}
                  className="rounded-lg bg-green-600 px-3 py-1 text-xs text-white hover:bg-green-700 transition-colors"
                >
                  Accept
                </button>
              )}
            </div>
          ))}
        </div>
      )}

      {!isLoading && issued.length === 0 && received.length === 0 && (
        <p className="text-sm text-gray-400 text-center py-4">No shared vaults yet. Invite a colleague above.</p>
      )}
    </Section>
  );
}

// ---- Main Page -----------------------------------------------------------

export default function SettingsPage() {
  return (
    <div className="flex h-full flex-col">
      {/* Header */}
      <div className="flex items-center gap-3 border-b border-gray-200 dark:border-gray-800 px-6 py-4">
        <Settings size={20} className="text-gray-500" />
        <div>
          <h1 className="text-lg font-semibold">Settings</h1>
          <p className="text-xs text-gray-400">Profile, vault identity, and sharing</p>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto p-6 space-y-4 max-w-2xl">
        <ProfileSection />
        <VaultSharingSection />
      </div>
    </div>
  );
}
