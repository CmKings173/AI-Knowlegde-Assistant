import {
  AssistantRuntimeProvider,
  useExternalStoreRuntime,
  type AppendMessage,
  type ThreadMessageLike
} from "@assistant-ui/react";
import {
  useCallback,
  useMemo,
  useRef,
  useState,
  type ReactNode
} from "react";

import { sendChatStream } from "./api";
import { ChatStateContext, type ChatState } from "./chat-state";
import type {
  AppMessage,
  ChatContinuation,
  ChatFilters,
  ChatHistoryMessage
} from "./types";

const MAX_HISTORY_MESSAGES = 6;
const MAX_HISTORY_CHARS = 4000;

export function ChatRuntimeProvider({
  selectedDocumentIds,
  children
}: {
  selectedDocumentIds: string[];
  children: ReactNode;
}) {
  const [messages, setMessages] = useState<AppMessage[]>([]);
  const [continuation, setContinuation] = useState<ChatContinuation | null>(null);
  const [isRunning, setIsRunning] = useState(false);
  const [progressLabel, setProgressLabel] = useState<string | null>(null);
  const abortControllerRef = useRef<AbortController | null>(null);

  const onNew = useCallback(
    async (message: AppendMessage) => {
      const question = textFromAppendMessage(message).trim();
      if (!question) {
        return;
      }

      const shouldContinue = Boolean(continuation && isContinuePrompt(question));
      const history = buildHistory(messages);
      const filters: ChatFilters | undefined = selectedDocumentIds.length
        ? {
            document_ids: selectedDocumentIds,
            include_parent_chunks: false
          }
        : undefined;

      const userMessage: AppMessage = {
        id: makeId("user"),
        role: "user",
        content: question,
        createdAt: new Date()
      };
      const assistantId = makeId("assistant");
      const assistantMessage: AppMessage = {
        id: assistantId,
        role: "assistant",
        content: "",
        createdAt: new Date()
      };

      setMessages((previous) => [...previous, userMessage, assistantMessage]);
      setIsRunning(true);
      setProgressLabel("\u0110ang ph\u00e2n lo\u1ea1i c\u00e2u h\u1ecfi v\u00e0 tra c\u1ee9u n\u1ebfu c\u1ea7n...");
      abortControllerRef.current = new AbortController();

      try {
        let streamError: Error | null = null;
        await sendChatStream(
          {
            question,
            history,
            filters,
            continuation: shouldContinue ? continuation : null,
            signal: abortControllerRef.current.signal
          },
          (event) => {
            if (event.event === "progress") {
              setProgressLabel(event.data.message);
              return;
            }
            if (event.event === "delta") {
              setMessages((previous) =>
                previous.map((item) =>
                  item.id === assistantId
                    ? { ...item, content: `${item.content}${event.data.text}` }
                    : item
                )
              );
              return;
            }
            if (event.event === "final") {
              const response = event.data;
              setContinuation(
                response.continuation && response.continuation.has_more
                  ? response.continuation
                  : null
              );
              setMessages((previous) =>
                previous.map((item) =>
                  item.id === assistantId
                    ? {
                        ...item,
                        content: response.answer,
                        status: response.status,
                        citations: response.citations,
                        retrieval: response.retrieval,
                        timing_ms: response.timing_ms,
                        trace: response.trace
                      }
                    : item
                )
              );
              return;
            }
            streamError = new Error(event.data.message);
          }
        );

        if (streamError) {
          throw streamError;
        }
      } catch (error) {
        if (error instanceof DOMException && error.name === "AbortError") {
          setMessages((previous) => previous.filter((item) => item.id !== assistantId));
          return;
        }
        setContinuation(null);
        setMessages((previous) =>
          previous.map((item) =>
            item.id === assistantId
              ? {
                  ...item,
                  content:
                    error instanceof Error
                      ? `Kh\u00f4ng k\u1ebft n\u1ed1i \u0111\u01b0\u1ee3c API server: ${error.message}`
                      : "Kh\u00f4ng k\u1ebft n\u1ed1i \u0111\u01b0\u1ee3c API server.",
                  status: "error"
                }
              : item
          )
        );
      } finally {
        abortControllerRef.current = null;
        setIsRunning(false);
        setProgressLabel(null);
      }
    },
    [continuation, messages, selectedDocumentIds]
  );

  const onCancel = useCallback(async () => {
    abortControllerRef.current?.abort();
    abortControllerRef.current = null;
    setIsRunning(false);
  }, []);

  const runtime = useExternalStoreRuntime<AppMessage>({
    messages,
    isRunning,
    convertMessage,
    onNew,
    onCancel
  });

  const state = useMemo(
    () => ({
      messages,
      continuation,
      isRunning,
      progressLabel,
      clearChat: () => {
        abortControllerRef.current?.abort();
        setMessages([]);
        setContinuation(null);
        setIsRunning(false);
        setProgressLabel(null);
      }
    }),
    [continuation, isRunning, messages, progressLabel]
  );

  return (
    <ChatStateContext.Provider value={state}>
      <AssistantRuntimeProvider runtime={runtime}>{children}</AssistantRuntimeProvider>
    </ChatStateContext.Provider>
  );
}

function convertMessage(message: AppMessage): ThreadMessageLike {
  return {
    id: message.id,
    role: message.role,
    createdAt: message.createdAt,
    content: [
      {
        type: "text",
        text: message.role === "assistant" ? formatCitationMarkers(message.content) : message.content
      }
    ]
  };
}

function formatCitationMarkers(value: string): string {
  return splitSourceMarkerList(value).replace(/\[SOURCE_(\d+)\]/g, "[$1]");
}

function splitSourceMarkerList(value: string): string {
  return value.replace(/\[((?:SOURCE_\d+\s*,\s*)+SOURCE_\d+)\]/g, (_match, group: string) =>
    group
      .split(",")
      .map((sourceId) => `[${sourceId.trim()}]`)
      .join(", ")
  );
}

function buildHistory(messages: AppMessage[]): ChatHistoryMessage[] {
  const selected = messages.slice(-MAX_HISTORY_MESSAGES);
  let remainingChars = MAX_HISTORY_CHARS;
  const history: ChatHistoryMessage[] = [];

  for (const message of [...selected].reverse()) {
    if (!message.content || remainingChars <= 0) {
      continue;
    }
    const content = message.content.slice(-remainingChars);
    remainingChars -= content.length;
    history.push({ role: message.role, content });
  }

  return history.reverse();
}

function textFromAppendMessage(message: AppendMessage): string {
  if (typeof message.content === "string") {
    return message.content;
  }
  return message.content
    .filter((part): part is { type: "text"; text: string } => part.type === "text")
    .map((part) => part.text)
    .join("\n");
}

function isContinuePrompt(value: string): boolean {
  return [
    "tiep",
    "xem tiep",
    "tiep di",
    "noi tiep",
    "tiep nhe",
    "xem tiep nhe",
    "noi tiep di",
    "continue",
    "next"
  ].includes(normalizeForIntent(value));
}

function normalizeForIntent(value: string): string {
  const normalized = value.normalize("NFC").toLowerCase().replace(/\u00a0/g, " ");
  return normalized
    .normalize("NFD")
    .replace(/\p{Diacritic}/gu, "")
    .replace(/\s+/g, " ")
    .trim();
}

function makeId(prefix: string): string {
  return `${prefix}-${crypto.randomUUID()}`;
}
