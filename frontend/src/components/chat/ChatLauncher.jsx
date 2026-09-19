import { MessageSquare, X } from "lucide-react";

/**
 * The always-available way into the assistant.
 *
 * It sits clear of the stage's bottom action bar so it never covers the
 * camera controls, and it announces whether it opens or closes the panel.
 */
export function ChatLauncher({ open, onToggle, hasFinding }) {
  return (
    <button
      type="button"
      className={`chat-launcher${open ? " is-open" : ""}`}
      onClick={onToggle}
      aria-expanded={open}
      aria-controls={open ? "ecdat-chat-panel" : undefined}
      aria-label={open ? "Close ECDAT AI" : "Open ECDAT AI"}
      title={open ? "Close ECDAT AI" : "Ask ECDAT AI"}
    >
      {open ? <X size={16} aria-hidden="true" /> : <MessageSquare size={16} aria-hidden="true" />}
      <span className="chat-launcher-label">{open ? "Close" : "ECDAT AI"}</span>
      {!open && hasFinding && <span className="chat-launcher-dot" aria-hidden="true" />}
    </button>
  );
}
