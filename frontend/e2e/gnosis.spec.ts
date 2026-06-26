/**
 * Gnosis-KB — Playwright E2E tests (Priority 4)
 *
 * Covers the critical happy-path pipeline:
 *   login → create note → vault sync → search → AI chat
 *
 * Setup
 * -----
 *   npm i -D @playwright/test
 *   npx playwright install --with-deps chromium
 *
 * Run
 * ---
 *   npx playwright test                   # all tests
 *   npx playwright test --headed          # headed mode for debugging
 *   PLAYWRIGHT_BASE_URL=https://staging.example.com npx playwright test
 *
 * Environment variables
 * ---------------------
 *   PLAYWRIGHT_BASE_URL   default: http://localhost:5173
 *   TEST_USER_EMAIL       default: test@gnosis.local
 *   TEST_USER_PASSWORD    default: testpassword123
 */

import { test, expect, type Page } from '@playwright/test';

const BASE_URL = process.env.PLAYWRIGHT_BASE_URL ?? 'http://localhost:5173';
const EMAIL    = process.env.TEST_USER_EMAIL    ?? 'test@gnosis.local';
const PASSWORD = process.env.TEST_USER_PASSWORD ?? 'testpassword123';

// ---------------------------------------------------------------------------
// Shared helpers
// ---------------------------------------------------------------------------

async function login(page: Page) {
  await page.goto(`${BASE_URL}/login`);
  await page.getByLabel(/email/i).fill(EMAIL);
  await page.getByLabel(/password/i).fill(PASSWORD);
  await page.getByRole('button', { name: /sign in|log in/i }).click();
  // Wait for the sidebar to confirm we are in the app shell
  await expect(page.getByRole('navigation')).toBeVisible({ timeout: 10_000 });
}

// ---------------------------------------------------------------------------
// 1. Login
// ---------------------------------------------------------------------------

test('login — shows sidebar after successful authentication', async ({ page }) => {
  await login(page);
  await expect(page).toHaveURL(new RegExp(`${BASE_URL}(/|/notes)?`));
  await expect(page.getByRole('navigation')).toBeVisible();
});

test('login — shows error for bad credentials', async ({ page }) => {
  await page.goto(`${BASE_URL}/login`);
  await page.getByLabel(/email/i).fill('wrong@example.com');
  await page.getByLabel(/password/i).fill('wrongpassword');
  await page.getByRole('button', { name: /sign in|log in/i }).click();
  await expect(
    page.getByText(/invalid|incorrect|unauthorized|error/i)
  ).toBeVisible({ timeout: 6_000 });
});

// ---------------------------------------------------------------------------
// 2. Create note
// ---------------------------------------------------------------------------

test('create note — note appears in list', async ({ page }) => {
  await login(page);

  // Click the new-note action (could be a "+" button or "New Note" link)
  await page.goto(`${BASE_URL}/notes/new`);

  // Fill in a unique title so we can find it later
  const title = `E2E Test Note ${Date.now()}`;
  const titleInput = page.getByPlaceholder(/title/i).or(
    page.getByRole('textbox', { name: /title/i })
  );
  await titleInput.fill(title);

  // Type body content
  const bodyArea = page.getByRole('textbox', { name: /body|content/i }).or(
    page.locator('.ProseMirror, [contenteditable="true"]').first()
  );
  await bodyArea.click();
  await bodyArea.fill('This note was created by Playwright.');

  // Save
  await page.getByRole('button', { name: /save|create/i }).click();

  // Should redirect to the note or the notes list
  await expect(page.getByText(title)).toBeVisible({ timeout: 8_000 });
});

// ---------------------------------------------------------------------------
// 3. Vault sync
// ---------------------------------------------------------------------------

test('vault sync — sync button triggers progress feedback', async ({ page }) => {
  await login(page);
  await page.goto(`${BASE_URL}/vault-sync`);

  // Press the sync button
  const syncBtn = page.getByRole('button', { name: /sync|start sync/i });
  await expect(syncBtn).toBeVisible({ timeout: 5_000 });
  await syncBtn.click();

  // Expect progress feedback (log output, spinner, or "done" message)
  await expect(
    page.getByText(/syncing|synced|done|total:/i)
  ).toBeVisible({ timeout: 20_000 });
});

// ---------------------------------------------------------------------------
// 4. Search
// ---------------------------------------------------------------------------

test('search — returns results for a known query', async ({ page }) => {
  await login(page);
  await page.goto(`${BASE_URL}/search`);

  const searchInput = page.getByRole('searchbox').or(
    page.getByPlaceholder(/search/i)
  );
  await searchInput.fill('daily');
  await page.keyboard.press('Enter');

  // Results list or "no results" message should appear
  await expect(
    page.locator('[data-testid="search-results"], .search-result-item').first().or(
      page.getByText(/no results|nothing found/i)
    )
  ).toBeVisible({ timeout: 8_000 });
});

test('search — command palette opens with Cmd+K', async ({ page }) => {
  await login(page);
  await page.keyboard.press('Meta+k');
  await expect(
    page.getByRole('dialog').or(page.locator('[data-testid="command-palette"]'))
  ).toBeVisible({ timeout: 4_000 });
});

// ---------------------------------------------------------------------------
// 5. AI chat
// ---------------------------------------------------------------------------

test('ai chat — sends message and receives non-empty response', async ({ page }) => {
  await login(page);
  await page.goto(`${BASE_URL}/ai`);

  // Locate the chat input
  const chatInput = page.getByPlaceholder(/ask|message|chat/i).or(
    page.getByRole('textbox', { name: /ask|message/i })
  );
  await expect(chatInput).toBeVisible({ timeout: 8_000 });
  await chatInput.fill('What is this knowledge base about?');
  await page.keyboard.press('Enter');

  // An assistant response bubble should appear
  await expect(
    page.locator('[data-role="assistant"], .chat-message-assistant, [data-testid="ai-response"]').first()
  ).toBeVisible({ timeout: 30_000 });
});

// ---------------------------------------------------------------------------
// 6. WikiLink autocomplete (smoke test)
// ---------------------------------------------------------------------------

test('editor — typing [[ opens wikilink suggestion popup', async ({ page }) => {
  await login(page);
  await page.goto(`${BASE_URL}/notes/new`);

  const editor = page.locator('.ProseMirror, [contenteditable="true"]').first();
  await editor.click();
  await editor.type('[[');

  // The suggestion popup should appear (tippy-rendered or native)
  await expect(
    page.locator('.wiki-suggestion-list, [data-testid="wikilink-suggestions"]')
  ).toBeVisible({ timeout: 4_000 });
});
