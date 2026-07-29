import {
  AuiIf,
  MessagePrimitive,
  ThreadPrimitive
} from "@assistant-ui/react";
import {
  ArrowUp,
  Bot,
  CheckCircle2,
  FileText,
  Loader2,
  Plus,
  RefreshCw,
  Upload,
  WifiOff,
  X
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { checkHealth, listDocuments, resolveAssetUrl, uploadDocument } from "./api";
import { ChatRuntimeProvider } from "./chat-runtime";
import { useChatState } from "./chat-state";
import type { Citation, CitationBlock, DocumentRecord } from "./types";

type PreviewImage = {
  url?: string;
  file_name?: string;
  anchor_text?: string;
};

export default function App() {
  const [documents, setDocuments] = useState<DocumentRecord[]>([]);
  const [selectedDocumentIds, setSelectedDocumentIds] = useState<string[]>([]);
  const [isOnline, setIsOnline] = useState(false);
  const [isLoadingDocuments, setIsLoadingDocuments] = useState(false);
  const [documentError, setDocumentError] = useState<string | null>(null);

  const refreshDocuments = async () => {
    setIsLoadingDocuments(true);
    setDocumentError(null);
    try {
      const [online, records] = await Promise.all([checkHealth(), listDocuments()]);
      setIsOnline(online);
      setDocuments(records);
      setSelectedDocumentIds(records.map((document) => document.document_id));
    } catch (error) {
      setIsOnline(false);
      setDocumentError(error instanceof Error ? error.message : "Kh\u00f4ng t\u1ea3i \u0111\u01b0\u1ee3c t\u00e0i li\u1ec7u.");
    } finally {
      setIsLoadingDocuments(false);
    }
  };

  useEffect(() => {
    void refreshDocuments();
  }, []);

  const selectedDocuments = useMemo(
    () => new Set(selectedDocumentIds),
    [selectedDocumentIds]
  );

  return (
    <ChatRuntimeProvider selectedDocumentIds={selectedDocumentIds}>
      <main className="app-shell">
        <aside className="sidebar">
          <Header isOnline={isOnline} />
          <ChatActions />
          <DocumentPanel
            documents={documents}
            selectedDocuments={selectedDocuments}
            isLoading={isLoadingDocuments}
            error={documentError}
            onToggleDocument={(documentId) => {
              const allDocumentIds = documents.map((document) => document.document_id);
              setSelectedDocumentIds((current) => {
                if (!current.includes(documentId)) {
                  return [...current, documentId];
                }
                const next = current.filter((id) => id !== documentId);
                return next.length ? next : allDocumentIds;
              });
            }}
            onSelectAll={() =>
              setSelectedDocumentIds(documents.map((document) => document.document_id))
            }
            onRefresh={() => void refreshDocuments()}
          />
        </aside>

        <section className="workspace">
          <TopBar
            selectedCount={selectedDocumentIds.length}
            totalCount={documents.length}
          />
          <KnowledgeThread />
        </section>
      </main>
    </ChatRuntimeProvider>
  );
}

function Header({ isOnline }: { isOnline: boolean }) {
  return (
    <div className="header-block">
      <div className="brand-mark">
        <Bot size={22} />
      </div>
      <div>
        <h1>{"Tr\u1ee3 l\u00fd Ki\u1ebfn th\u1ee9c N\u1ed9i b\u1ed9"}</h1>
        <p>{"Vi\u1ec7t Th\u00e1i D\u01b0\u01a1ng"}</p>
      </div>
      <span className={isOnline ? "status online" : "status offline"}>
        {isOnline ? <CheckCircle2 size={14} /> : <WifiOff size={14} />}
        {isOnline ? "Online" : "Offline"}
      </span>
    </div>
  );
}

function ChatActions() {
  const { clearChat, continuation } = useChatState();
  return (
    <div className="actions-card">
      <button className="primary-action" type="button" onClick={clearChat}>
        <Plus size={16} />
        {"Cu\u1ed9c tr\u00f2 chuy\u1ec7n m\u1edbi"}
      </button>
      {continuation ? (
        <p className="hint">
          {"\u0110ang c\u00f3 ph\u1ea7n tr\u1ea3 l\u1eddi ti\u1ebfp. G\u00f5 \"xem ti\u1ebfp\" \u0111\u1ec3 \u0111\u1ecdc ph\u1ea7n sau."}
        </p>
      ) : (
        <p className="hint">
          {"L\u1ecbch s\u1eed h\u1ed9i tho\u1ea1i ch\u1ec9 l\u01b0u trong tr\u00ecnh duy\u1ec7t hi\u1ec7n t\u1ea1i."}
        </p>
      )}
    </div>
  );
}

function TopBar({
  selectedCount,
  totalCount
}: {
  selectedCount: number;
  totalCount: number;
}) {
  const label =
    selectedCount === totalCount
      ? "\u0110ang d\u00f9ng to\u00e0n b\u1ed9 t\u00e0i li\u1ec7u"
      : `${selectedCount}/${totalCount} t\u00e0i li\u1ec7u \u0111\u01b0\u1ee3c ch\u1ecdn`;

  return (
    <div className="topbar">
      <div>
        <p className="eyebrow">RAG Chatbot</p>
        <h2>{"Tra c\u1ee9u n\u1ed9i quy, SOP, NAS, Outlook, email v\u00e0 Windows"}</h2>
      </div>
      <div className="scope-pill">{label}</div>
    </div>
  );
}

function KnowledgeThread() {
  const { progressLabel } = useChatState();

  return (
    <ThreadPrimitive.Root className="thread-root">
      <ThreadPrimitive.Viewport className="thread-viewport">
        <AuiIf condition={(state) => state.thread.isEmpty}>
          <EmptyState />
        </AuiIf>

        <ThreadPrimitive.Messages>
          {({ message }) =>
            message.role === "user" ? (
              <UserMessage />
            ) : (
              <AssistantMessage messageId={message.id} />
            )
          }
        </ThreadPrimitive.Messages>

        <ThreadPrimitive.ViewportFooter className="viewport-footer">
          {progressLabel ? <div className="progress-line">{progressLabel}</div> : null}
          <Composer />
        </ThreadPrimitive.ViewportFooter>
      </ThreadPrimitive.Viewport>
    </ThreadPrimitive.Root>
  );
}

function EmptyState() {
  const { sendMessage, isRunning } = useChatState();
  const suggestions = [
    "N\u1ed9i quy c\u00f4ng ty g\u1ed3m nh\u1eefng g\u00ec?",
    "C\u00e1ch truy c\u1eadp NAS c\u00f4ng ty?",
    "H\u01b0\u1edbng d\u1eabn c\u00e0i Outlook tr\u00ean m\u00e1y t\u00ednh m\u1edbi?",
    "Quy \u0111\u1ecbnh ngh\u1ec9 ph\u00e9p n\u0103m nh\u01b0 th\u1ebf n\u00e0o?"
  ];

  return (
    <div className="empty-state">
      <div className="empty-icon">
        <Bot size={34} />
      </div>
      <h3>{"T\u00f4i c\u00f3 th\u1ec3 gi\u00fap g\u00ec cho b\u1ea1n h\u00f4m nay?"}</h3>
      <p>{"H\u1ecfi tr\u1ef1c ti\u1ebfp theo t\u00e0i li\u1ec7u n\u1ed9i b\u1ed9 \u0111\u00e3 ingest v\u00e0o h\u1ec7 th\u1ed1ng."}</p>
      <div className="suggestion-grid">
        {suggestions.map((suggestion) => (
          <button
            disabled={isRunning}
            key={suggestion}
            type="button"
            onClick={() => void sendMessage(suggestion)}
          >
            {suggestion}
          </button>
        ))}
      </div>
    </div>
  );
}

function UserMessage() {
  return (
    <MessagePrimitive.Root className="message-row user-row">
      <div className="message-bubble user-bubble">
        <MessagePrimitive.Parts />
      </div>
    </MessagePrimitive.Root>
  );
}

function AssistantMessage({ messageId }: { messageId?: string }) {
  const { isRunning, messages } = useChatState();
  const metadata = messages.find((message) => message.id === messageId);
  const isTyping = Boolean(isRunning && metadata && !metadata.content && !metadata.status);

  return (
    <MessagePrimitive.Root className="message-row assistant-row">
      <div className="assistant-avatar">
        <Bot size={18} />
      </div>
      <div className="assistant-message">
        {isTyping ? <TypingIndicator /> : <MessagePrimitive.Parts />}
        {metadata ? <MessageMetadata message={metadata} /> : null}
      </div>
    </MessagePrimitive.Root>
  );
}

function TypingIndicator() {
  return (
    <div className="typing-indicator" aria-label="Đang trả lời">
      <span />
      <span />
      <span />
    </div>
  );
}

function MessageMetadata({
  message
}: {
  message: ReturnType<typeof useChatState>["messages"][number];
}) {
  const citations = message.citations ?? [];

  if (!citations.length && message.status !== "error") {
    return null;
  }

  return (
    <div className="message-meta">
      {message.status === "error" ? <div className="meta-line"><span>{"L\u1ed7i"}</span></div> : null}
      {citations.length ? <CitationList citations={citations} /> : null}
    </div>
  );
}

function CitationList({ citations }: { citations: Citation[] }) {
  const [previewImage, setPreviewImage] = useState<PreviewImage | null>(null);

  return (
    <>
      <details className="citations" open>
        <summary>{`Ngu\u1ed3n tham kh\u1ea3o (${citations.length})`}</summary>
        <div className="citation-list">
          {citations.map((citation, index) => (
            <article className="citation-card" key={citation.citation_id}>
              <div className="citation-heading">
                <strong>
                  [{sourceDisplayLabel(citation, index)}] {citation.document_name}
                </strong>
                <span>{citation.section}</span>
              </div>
              <SourceBlocks citation={citation} onPreviewImage={setPreviewImage} />
            </article>
          ))}
        </div>
      </details>
      {previewImage ? (
        <ImagePreview image={previewImage} onClose={() => setPreviewImage(null)} />
      ) : null}
    </>
  );
}

function sourceDisplayLabel(citation: Citation, index: number): string {
  const match = citation.citation_id.match(/^SOURCE_(\d+)$/);
  return match ? match[1] : String(index + 1);
}

function SourceBlocks({
  citation,
  onPreviewImage
}: {
  citation: Citation;
  onPreviewImage: (image: PreviewImage) => void;
}) {
  const blocks = normalizedBlocks(citation);
  return (
    <div className="source-blocks">
      {blocks.map((block, index) => (
        <section className="source-block" key={`${citation.citation_id}-${index}`}>
          {block.text ? <p>{block.text}</p> : null}
          {block.images.length ? (
            <div className="citation-images">
              {block.images.map((image) => (
                <button
                  className="citation-image-button"
                  key={image.url ?? image.file_name}
                  type="button"
                  onClick={() => onPreviewImage(image)}
                >
                  <img
                    alt={image.file_name ?? "H\u00ecnh \u1ea3nh t\u00e0i li\u1ec7u"}
                    src={resolveAssetUrl(image.url)}
                  />
                </button>
              ))}
            </div>
          ) : null}
        </section>
      ))}
    </div>
  );
}

function normalizedBlocks(citation: Citation): CitationBlock[] {
  if (citation.content_blocks?.length) {
    return citation.content_blocks;
  }
  const text = citation.content || citation.excerpt;
  return [
    {
      text,
      images: citation.images ?? []
    }
  ];
}

function ImagePreview({
  image,
  onClose
}: {
  image: PreviewImage;
  onClose: () => void;
}) {
  useEffect(() => {
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        onClose();
      }
    };
    window.addEventListener("keydown", closeOnEscape);
    return () => window.removeEventListener("keydown", closeOnEscape);
  }, [onClose]);

  return (
    <div
      className="image-preview-backdrop"
      role="dialog"
      aria-modal="true"
      onClick={onClose}
    >
      <div className="image-preview" onClick={(event) => event.stopPropagation()}>
        <button className="image-preview-close" type="button" onClick={onClose}>
          <X size={18} />
        </button>
        <img
          alt={image.file_name ?? "H\u00ecnh \u1ea3nh t\u00e0i li\u1ec7u"}
          src={resolveAssetUrl(image.url)}
        />
        {image.file_name ? <p>{image.file_name}</p> : null}
      </div>
    </div>
  );
}

function Composer() {
  const { isRunning, sendMessage } = useChatState();
  const [value, setValue] = useState("");
  const canSend = value.trim().length > 0 && !isRunning;

  const submit = () => {
    const question = value.trim();
    if (!question || isRunning) {
      return;
    }
    setValue("");
    void sendMessage(question);
  };

  return (
    <form
      className="composer"
      onSubmit={(event) => {
        event.preventDefault();
        submit();
      }}
    >
      <textarea
        className="composer-input"
        placeholder={"Nh\u1eadp c\u00e2u h\u1ecfi v\u1ec1 n\u1ed9i quy, SOP, NAS, Outlook..."}
        rows={1}
        value={value}
        disabled={isRunning}
        onChange={(event) => setValue(event.currentTarget.value)}
        onKeyDown={(event) => {
          if (event.key === "Enter" && !event.shiftKey) {
            event.preventDefault();
            submit();
          }
        }}
      />
      <button className="send-button" disabled={!canSend} type="submit">
        <ArrowUp size={18} />
      </button>
    </form>
  );
}

function DocumentPanel({
  documents,
  selectedDocuments,
  isLoading,
  error,
  onToggleDocument,
  onSelectAll,
  onRefresh
}: {
  documents: DocumentRecord[];
  selectedDocuments: Set<string>;
  isLoading: boolean;
  error: string | null;
  onToggleDocument: (documentId: string) => void;
  onSelectAll: () => void;
  onRefresh: () => void;
}) {
  const [isUploading, setIsUploading] = useState(false);
  const [uploadMessage, setUploadMessage] = useState<string | null>(null);
  const isFiltering =
    documents.length > 0 && selectedDocuments.size < documents.length;

  return (
    <section className="documents-card">
      <div className="section-heading">
        <div>
          <p className="eyebrow">Knowledge Base</p>
          <h3>{"T\u00e0i li\u1ec7u"}</h3>
        </div>
        <button className="icon-button" type="button" onClick={onRefresh} disabled={isLoading}>
          {isLoading ? <Loader2 className="spin" size={16} /> : <RefreshCw size={16} />}
        </button>
      </div>

      <label className="upload-box">
        <Upload size={18} />
        <span>{isUploading ? "\u0110ang ingest..." : "Upload .docx, .md, .txt"}</span>
        <input
          type="file"
          accept=".docx,.md,.txt"
          disabled={isUploading}
          onChange={async (event) => {
            const file = event.currentTarget.files?.[0];
            event.currentTarget.value = "";
            if (!file) {
              return;
            }
            setIsUploading(true);
            setUploadMessage(null);
            try {
              await uploadDocument(file);
              setUploadMessage(`\u0110\u00e3 ingest ${file.name}`);
              onRefresh();
            } catch (uploadError) {
              setUploadMessage(
                uploadError instanceof Error ? uploadError.message : "Upload th\u1ea5t b\u1ea1i."
              );
            } finally {
              setIsUploading(false);
            }
          }}
        />
      </label>

      <div className="scope-note">
        {isFiltering
          ? `\u0110ang gi\u1edbi h\u1ea1n trong ${selectedDocuments.size} t\u00e0i li\u1ec7u.`
          : "M\u1eb7c \u0111\u1ecbnh tra c\u1ee9u to\u00e0n b\u1ed9 t\u00e0i li\u1ec7u \u0111\u00e3 ingest."}
        {isFiltering ? (
          <button type="button" onClick={onSelectAll}>
            {"D\u00f9ng t\u1ea5t c\u1ea3"}
          </button>
        ) : null}
      </div>

      {uploadMessage ? (
        <div className="notice">
          <span>{uploadMessage}</span>
          <button type="button" onClick={() => setUploadMessage(null)}>
            <X size={14} />
          </button>
        </div>
      ) : null}

      {error ? <p className="error-text">{error}</p> : null}

      <div className="document-list">
        {documents.length ? (
          documents.map((document) => (
            <label className="document-item" key={document.document_id}>
              <input
                type="checkbox"
                checked={selectedDocuments.has(document.document_id)}
                onChange={() => onToggleDocument(document.document_id)}
              />
              <FileText size={16} />
              <span>
                <strong>{document.original_name}</strong>
                <small>
                  {`${document.chunk_count} chunks \u00b7 ${document.image_count} h\u00ecnh`}
                </small>
              </span>
            </label>
          ))
        ) : (
          <p className="empty-documents">{"Ch\u01b0a c\u00f3 t\u00e0i li\u1ec7u n\u00e0o."}</p>
        )}
      </div>
    </section>
  );
}
