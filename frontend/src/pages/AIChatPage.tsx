/**
 * AIChatPage.tsx — canonical AI chat page re-exported from AiPage.
 *
 * The two pages (AiPage.tsx and AIChatPage.tsx) were duplicated:
 * - AIChatPage wrapped AIChat component directly (simple RAG chat only)
 * - AiPage wrapped AiSidebar + LinkSuggestions (richer context panel)
 *
 * Resolution (P5 #11): AIChatPage is now a thin re-export of AiPage so there
 * is one authoritative implementation. Routes that previously pointed at
 * AIChatPage automatically get the richer AiPage experience.
 *
 * If a future route needs the bare <AIChat /> embed without the AI sidebar,
 * import AIChat directly from '@/components/AIChat'.
 */
export { default } from './AiPage';
