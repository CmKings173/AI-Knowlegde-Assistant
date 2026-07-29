import { createContext, useContext } from "react";

import type { AppMessage, ChatContinuation } from "./types";

export type ChatState = {
  messages: AppMessage[];
  continuation: ChatContinuation | null;
  isRunning: boolean;
  progressLabel: string | null;
  sendMessage: (question: string) => Promise<void>;
  clearChat: () => void;
};

export const ChatStateContext = createContext<ChatState | null>(null);

export function useChatState(): ChatState {
  const state = useContext(ChatStateContext);
  if (!state) {
    throw new Error("useChatState must be used inside ChatRuntimeProvider");
  }
  return state;
}
