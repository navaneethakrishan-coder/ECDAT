import { useEffect, useRef, useState } from "react";
import { Check, Copy, Eraser, RefreshCw, Send, Sparkles, X } from "lucide-react";

import { Markdown } from "./Markdown";
import { useChat } from "./useChat";

/**
 * The ECDAT assistant: a conversation about the analysis already on
 * screen. It is deliberately separate from the per-finding AI Analysis
 * panel, which keeps working exactly as before -- this one answers
 * follow-up questions across the whole portfolio.
 *
 * When a finding is selected it is attached as context, and the header
 * says so, because an answer about "this finding" is only trustworthy if
 * the user can see which finding the assistant was given.
 */

const QUICK_PROMPTS_PORTFOLIO = [
  "Explain my highest-risk assets",
  "What should I migrate first?",
  "Compare direct PQC vs hybrid migration",
];

const QUICK_PROMPTS_FINDING = [
  "Why is this finding risky?",
  "Explain this asset's evidence",
  "Explain the blast radius",
  "Explain this finding in simple terms",
];

function formatTime(at) {
  try {
    return new Date(at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  } catch {
    return "";
  }
}

function CopyButton({ text }) {
  const [copied, setCopied] = useState(false);

  return (
    <button
      type="button"
      className="chat-copy"
      onClick={async () => {
        try {
          await navigator.clipboard.writeText(text);
          setCopied(true);
          setTimeout(() => setCopied(false), 1600);
        } catch {
          // Clipboard access can be denied; the answer is still on screen.
        }
      }}
      aria-label={copied ? "Answer copied" : "Copy answer"}
      title="Copy answer"
    >
      {copied ? <Check size={12} aria-hidden="true" /> : <Copy size={12} aria-hidden="true" />}
    </button>
  );
}

export function ChatPanel({ open, onClose, selectedFinding, backendConnected }) {
  const { messages, status, error, send, retry, clear } = useChat();
  const [draft, setDraft] = useState("");
  const scrollRef = useRef(null);
  const inputRef = useRef(null);
  const closeRef = useRef(null);
  const bomRef = selectedFinding?.bomRef || null;

  // Auto-scroll as the conversation grows.
  useEffect(() => {
    const node = scrollRef.current;
    if (node) node.scrollTop = node.scrollHeight;
  }, [messages, status]);

  // Focus the composer when the panel opens, so it is usable from the
  // keyboard immediately.
  useEffect(() => {
    if (open) {
      const timer = setTimeout(() => inputRef.current?.focus(), 60);
      return () => clearTimeout(timer);
    }
    return undefined;
  }, [open]);

  // Escape closes, and focus stays inside the panel while it is open.
  useEffect(() => {
    if (!open) return undefined;

    function handleKeyDown(event) {
      if (event.key === "Escape") {
        event.stopPropagation();
        onClose();
      }
    }

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [open, onClose]);

  if (!open) return null;

  const sending = status === "sending";
  const quickPrompts = bomRef ? QUICK_PROMPTS_FINDING : QUICK_PROMPTS_PORTFOLIO;

  function submit(text) {
    const message = (text ?? draft).trim();
    if (!message || sending) return;
    setDraft("");
    send(message, bomRef);
  }

  return (
    <aside
      id="ecdat-chat-panel"
      className="chat-panel"
      role="dialog"
      aria-modal="false"
      aria-labelledby="chat-panel-title"
      data-has-finding={bomRef ? "true" : "false"}
    >
      <header className="chat-header">
        <div className="chat-identity">
          <span className="chat-avatar" aria-hidden="true">
            <Sparkles size={15} />
          </span>
          <div>
            <h2 id="chat-panel-title">ECDAT AI</h2>
            <p>Quantum Migration Assistant</p>
          </div>
        </div>

        <div className="chat-header-actions">
          <span className={`chat-status${backendConnected ? "" : " is-down"}`}>
            <span className="chat-status-dot" aria-hidden="true" />
            {backendConnected ? "Qwen3:14B · Ollama" : "Backend unreachable"}
          </span>
          <button type="button" className="chat-icon-button" onClick={clear} aria-label="Clear conversation" title="Clear conversation">
            <Eraser size={14} aria-hidden="true" />
          </button>
          <button type="button" className="chat-icon-button" onClick={onClose} ref={closeRef} aria-label="Close ECDAT AI" title="Close">
            <X size={15} aria-hidden="true" />
          </button>
        </div>
      </header>

      {bomRef && (
        <div className="chat-context-chip">
          <span className="chat-context-label">Context</span>
          <span className="chat-context-name">{selectedFinding.name}</span>
          <code>{bomRef.slice(0, 8)}…</code>
          {selectedFinding.strategy && <span className="chat-context-meta">{selectedFinding.strategy}</span>}
        </div>
      )}

      <div className="chat-scroll" ref={scrollRef}>
        {messages.length === 0 && (
          <div className="chat-empty">
            <p className="chat-empty-title">Ask about this analysis</p>
            <p className="chat-empty-body">
              The assistant answers from ECDAT&apos;s recorded results — the findings, evidence, risk scores,
              strategies and dependencies on screen. It explains the analysis; it never changes it, and it says so
              when ECDAT has not recorded something.
            </p>
          </div>
        )}

        {messages.map((message) => (
          <article key={message.id} className={`chat-message chat-message-${message.role}`}>
            <header className="chat-message-meta">
              <span className="chat-message-author">{message.role === "user" ? "You" : "ECDAT AI"}</span>
              <time dateTime={new Date(message.at).toISOString()}>{formatTime(message.at)}</time>
              {message.role === "assistant" && <CopyButton text={message.content} />}
            </header>
            {message.role === "assistant" ? (
              <Markdown content={message.content} />
            ) : (
              <p className="chat-user-text">{message.content}</p>
            )}
          </article>
        ))}

        {sending && (
          <div className="chat-thinking" role="status" aria-live="polite">
            <span className="chat-thinking-dots" aria-hidden="true">
              <i />
              <i />
              <i />
            </span>
            Consulting the local model — the first answer after an idle period can take a couple of minutes.
          </div>
        )}

        {status === "error" && error && (
          <div className="chat-error" role="alert">
            <p>{error.message}</p>
            {error.reasonCode && <code>{error.reasonCode}</code>}
            <button type="button" className="btn btn-outline btn-sm chat-retry" onClick={retry}>
              <RefreshCw size={13} aria-hidden="true" />
              Retry
            </button>
          </div>
        )}
      </div>

      {messages.length === 0 && (
        <div className="chat-suggestions">
          {quickPrompts.map((prompt) => (
            <button key={prompt} type="button" onClick={() => submit(prompt)} disabled={sending}>
              {prompt}
            </button>
          ))}
        </div>
      )}

      <form
        className="chat-composer"
        onSubmit={(event) => {
          event.preventDefault();
          submit();
        }}
      >
        <label htmlFor="chat-input" className="sr-only">
          Ask the ECDAT assistant
        </label>
        <textarea
          id="chat-input"
          ref={inputRef}
          rows={1}
          value={draft}
          placeholder={bomRef ? `Ask about ${selectedFinding.name}…` : "Ask about the current analysis…"}
          disabled={sending}
          onChange={(event) => setDraft(event.target.value)}
          onKeyDown={(event) => {
            // Enter sends; Shift+Enter is a newline.
            if (event.key === "Enter" && !event.shiftKey) {
              event.preventDefault();
              submit();
            }
          }}
        />
        <button type="submit" className="chat-send" disabled={sending || !draft.trim()} aria-label="Send question">
          {sending ? <RefreshCw size={15} className="spin-icon" aria-hidden="true" /> : <Send size={15} aria-hidden="true" />}
        </button>
      </form>
    </aside>
  );
}
