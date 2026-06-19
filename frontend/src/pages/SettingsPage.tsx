export default function SettingsPage() {
  return (
    <div className="p-6 max-w-2xl">
      <h1 className="text-lg font-semibold text-text-primary mb-6">Settings</h1>
      <div className="space-y-4 text-sm text-text-secondary">
        <div className="border border-border rounded-lg p-4">
          <h2 className="font-medium text-text-primary mb-2">Vault</h2>
          <p>Vault syncs automatically from <code className="text-text-link">~/gnosis-vault/</code>.</p>
        </div>
        <div className="border border-border rounded-lg p-4">
          <h2 className="font-medium text-text-primary mb-2">LLM Providers</h2>
          <p>Configure providers via environment variables in <code className="text-text-link">.env</code>:</p>
          <ul className="mt-2 space-y-1 text-text-muted list-disc list-inside">
            <li>OLLAMA_LLM_MODEL (default: mistral)</li>
            <li>GROQ_API_KEY</li>
            <li>OPENAI_API_KEY</li>
            <li>OPENROUTER_API_KEY</li>
          </ul>
        </div>
        <div className="border border-border rounded-lg p-4">
          <h2 className="font-medium text-text-primary mb-2">MCP Server</h2>
          <p>MCP endpoint: <code className="text-text-link">http://localhost:8010/mcp</code></p>
          <p className="mt-1">Connect AI agents (Claude, Cursor) to this endpoint for vault access.</p>
        </div>
      </div>
    </div>
  );
}
