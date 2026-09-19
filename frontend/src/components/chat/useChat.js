import { useCallback, useRef, useState } from "react";

import { sendChatMessage } from "../../api";

/**
 * The chat conversation for this session.
 *
 * History lives in memory only: there is no database in ECDAT, and a
 * conversation about a security analysis is not something to persist
 * behind the user's back. Reloading starts a fresh conversation.
 *
 * A failed turn keeps the question, so "Retry" re-asks exactly what was
 * asked rather than making the user retype it.
 */
let nextId = 0;
const newId = () => `msg-${++nextId}`;

export function useChat() {
  const [messages, setMessages] = useState([]);
  const [status, setStatus] = useState("idle"); // idle | sending | error
  const [error, setError] = useState(null);
  const pendingRef = useRef(null);

  const send = useCallback(
    async (text, bomRef = null) => {
      const message = String(text || "").trim();
      if (!message || status === "sending") return;

      const question = { id: newId(), role: "user", content: message, at: Date.now(), bomRef };
      // The model sees the turns before this question, not the question twice.
      const history = messages.filter((item) => item.role === "user" || item.role === "assistant");

      setMessages((current) => [...current, question]);
      setStatus("sending");
      setError(null);
      pendingRef.current = { message, bomRef };

      try {
        const result = await sendChatMessage({ message, bomRef, conversation: history });
        setMessages((current) => [
          ...current,
          {
            id: newId(),
            role: "assistant",
            content: result.response,
            at: Date.now(),
            model: result.model,
            context: result.context,
          },
        ]);
        setStatus("idle");
        pendingRef.current = null;
      } catch (failure) {
        setError({ message: failure.message, reasonCode: failure.reasonCode || null });
        setStatus("error");
      }
    },
    [messages, status],
  );

  /** Re-asks the question that failed, without retyping it. */
  const retry = useCallback(() => {
    const pending = pendingRef.current;
    if (!pending) return;
    // Drop the failed question; send() re-adds it.
    setMessages((current) => {
      const lastUser = [...current].reverse().find((item) => item.role === "user");
      return lastUser ? current.filter((item) => item.id !== lastUser.id) : current;
    });
    setStatus("idle");
    setError(null);
    // Defer so the removal lands before the resend.
    setTimeout(() => send(pending.message, pending.bomRef), 0);
  }, [send]);

  const clear = useCallback(() => {
    setMessages([]);
    setStatus("idle");
    setError(null);
    pendingRef.current = null;
  }, []);

  return { messages, status, error, send, retry, clear };
}
