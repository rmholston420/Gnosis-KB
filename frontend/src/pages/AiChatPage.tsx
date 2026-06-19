/**
 * AiChatPage — Full-screen AI chat interface.
 *
 * Hosts the AiChat component in the main layout.
 * Accessible at /ai-chat.
 */
import React from "react";
import { AiChat } from "../components/ai/AiChat";

/**
 * AiChatPage — Full-screen vault AI chat.
 */
export function AiChatPage() {
  return (
    <div className="page ai-chat-page">
      <AiChat />
    </div>
  );
}
