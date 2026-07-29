import type {
  ChatContinuation,
  ChatFilters,
  ChatHistoryMessage,
  ChatResponse,
  ChatStreamEvent,
  DocumentRecord
} from "./types";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "";

function apiPath(path: string): string {
  return `${API_BASE_URL}${path}`;
}

async function parseJsonResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || `Request failed with status ${response.status}`);
  }
  return response.json() as Promise<T>;
}

export async function checkHealth(signal?: AbortSignal): Promise<boolean> {
  try {
    const response = await fetch(apiPath("/health"), { signal });
    return response.ok;
  } catch {
    return false;
  }
}

export async function sendChatRequest(input: {
  question: string;
  history: ChatHistoryMessage[];
  filters?: ChatFilters;
  continuation?: ChatContinuation | null;
  signal?: AbortSignal;
}): Promise<ChatResponse> {
  const payload = buildChatPayload(input);
  const response = await fetch(apiPath("/api/v1/chat"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
    signal: input.signal
  });
  return parseJsonResponse<ChatResponse>(response);
}

export async function sendChatStream(
  input: {
    question: string;
    history: ChatHistoryMessage[];
    filters?: ChatFilters;
    continuation?: ChatContinuation | null;
    signal?: AbortSignal;
  },
  onEvent: (event: ChatStreamEvent) => void
): Promise<void> {
  const payload = buildChatPayload(input);
  const response = await fetch(apiPath("/api/v1/chat/stream"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
    signal: input.signal
  });
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || `Request failed with status ${response.status}`);
  }
  if (!response.body) {
    throw new Error("Streaming response body is not available.");
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  while (true) {
    const { value, done } = await reader.read();
    if (done) {
      break;
    }
    buffer += decoder.decode(value, { stream: true });
    buffer = dispatchSseBlocks(buffer, onEvent);
  }
  buffer += decoder.decode();
  dispatchSseBlocks(`${buffer}\n\n`, onEvent);
}

export async function listDocuments(signal?: AbortSignal): Promise<DocumentRecord[]> {
  const response = await fetch(apiPath("/api/v1/documents"), { signal });
  const data = await parseJsonResponse<{ documents: DocumentRecord[] }>(response);
  return data.documents;
}

function buildChatPayload(input: {
  question: string;
  history: ChatHistoryMessage[];
  filters?: ChatFilters;
  continuation?: ChatContinuation | null;
}): Record<string, unknown> {
  const payload: Record<string, unknown> = {
    question: input.question
  };
  if (input.history.length) {
    payload.history = input.history;
  }
  if (input.filters?.document_ids?.length) {
    payload.filters = input.filters;
  }
  if (input.continuation) {
    payload.continuation = input.continuation;
  }
  return payload;
}

function dispatchSseBlocks(
  buffer: string,
  onEvent: (event: ChatStreamEvent) => void
): string {
  let remaining = buffer;
  let boundary = remaining.indexOf("\n\n");
  while (boundary >= 0) {
    const block = remaining.slice(0, boundary);
    remaining = remaining.slice(boundary + 2);
    dispatchSseBlock(block, onEvent);
    boundary = remaining.indexOf("\n\n");
  }
  return remaining;
}

function dispatchSseBlock(block: string, onEvent: (event: ChatStreamEvent) => void): void {
  const lines = block.split(/\r?\n/);
  const eventLine = lines.find((line) => line.startsWith("event:"));
  const dataLines = lines.filter((line) => line.startsWith("data:"));
  if (!eventLine || !dataLines.length) {
    return;
  }
  const eventName = eventLine.slice("event:".length).trim();
  const data = JSON.parse(
    dataLines.map((line) => line.slice("data:".length).trimStart()).join("\n")
  ) as ChatStreamEvent["data"];
  if (
    eventName === "progress" ||
    eventName === "delta" ||
    eventName === "final" ||
    eventName === "error"
  ) {
    onEvent({ event: eventName, data } as ChatStreamEvent);
  }
}

export async function uploadDocument(file: File): Promise<unknown> {
  const formData = new FormData();
  formData.append("file", file);
  const response = await fetch(apiPath("/api/v1/documents"), {
    method: "POST",
    body: formData
  });
  return parseJsonResponse<unknown>(response);
}

export function resolveAssetUrl(path: string | undefined): string {
  if (!path) {
    return "";
  }
  return `${API_BASE_URL}${path}`;
}
