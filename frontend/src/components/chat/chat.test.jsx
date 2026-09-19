/**
 * The ECDAT assistant panel.
 *
 * The backend is faked throughout -- what is under test is the panel's
 * behaviour around it: that the selected finding is actually attached to
 * the request, that a failure is recoverable rather than a dead end, and
 * that the conversation stays in the browser.
 */

import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ChatLauncher } from "./ChatLauncher";
import { ChatPanel } from "./ChatPanel";

const FINDING = {
  bomRef: "8f1c2f3a-1111-4222-8333-444455556666",
  name: "RSA-2048",
  strategy: "NEEDS_REVIEW",
};

function lastChatRequest() {
  const call = fetch.mock.calls.findLast(([url]) => String(url).includes("/api/chat"));
  return call ? JSON.parse(call[1].body) : null;
}

function answerWith(text = "ECDAT recorded this finding as NEEDS_REVIEW.") {
  return {
    ok: true,
    status: 200,
    json: async () => ({ response: text, model: "qwen3:14b" }),
  };
}

function failWith(reasonCode, reason, status = 502) {
  return {
    ok: false,
    status,
    json: async () => ({ detail: { reason_code: reasonCode, reason } }),
  };
}

beforeEach(() => {
  vi.stubGlobal("fetch", vi.fn());
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("opening and closing", () => {
  it("says what it will do and which panel it controls", async () => {
    const onToggle = vi.fn();
    const { rerender } = render(<ChatLauncher open={false} onToggle={onToggle} hasFinding={false} />);

    const launcher = screen.getByRole("button", { name: "Open ECDAT AI" });
    expect(launcher).toHaveAttribute("aria-expanded", "false");
    // The panel is unmounted while closed, so nothing should claim to control it.
    expect(launcher).not.toHaveAttribute("aria-controls");

    await userEvent.click(launcher);
    expect(onToggle).toHaveBeenCalledOnce();

    rerender(<ChatLauncher open onToggle={onToggle} hasFinding={false} />);
    const open = screen.getByRole("button", { name: "Close ECDAT AI" });
    expect(open).toHaveAttribute("aria-expanded", "true");
    expect(open).toHaveAttribute("aria-controls", "ecdat-chat-panel");
  });

  it("renders nothing while closed", () => {
    const { container } = render(
      <ChatPanel open={false} onClose={() => {}} selectedFinding={null} backendConnected />,
    );
    expect(container).toBeEmptyDOMElement();
  });

  it("moves focus to the composer and closes on Escape", async () => {
    const onClose = vi.fn();
    render(<ChatPanel open onClose={onClose} selectedFinding={null} backendConnected />);

    await waitFor(() => expect(screen.getByLabelText("Ask the ECDAT assistant")).toHaveFocus());

    await userEvent.keyboard("{Escape}");
    expect(onClose).toHaveBeenCalled();
  });
});

describe("sending a question", () => {
  it("shows a loading state, disables the composer, then renders the answer", async () => {
    let release;
    fetch.mockReturnValueOnce(new Promise((resolve) => { release = () => resolve(answerWith()); }));

    render(<ChatPanel open onClose={() => {}} selectedFinding={null} backendConnected />);
    const input = screen.getByLabelText("Ask the ECDAT assistant");

    await userEvent.type(input, "What should I migrate first?");
    await userEvent.keyboard("{Enter}");

    expect(await screen.findByRole("status")).toHaveTextContent(/Consulting the local model/i);
    expect(input).toBeDisabled();

    release();

    expect(await screen.findByText(/NEEDS_REVIEW/)).toBeInTheDocument();
    await waitFor(() => expect(input).toBeEnabled());
    expect(screen.queryByRole("status")).not.toBeInTheDocument();
  });

  it("treats Shift+Enter as a newline rather than a send", async () => {
    render(<ChatPanel open onClose={() => {}} selectedFinding={null} backendConnected />);
    const input = screen.getByLabelText("Ask the ECDAT assistant");

    await userEvent.type(input, "first line");
    await userEvent.keyboard("{Shift>}{Enter}{/Shift}");
    await userEvent.type(input, "second line");

    expect(fetch).not.toHaveBeenCalled();
    expect(input).toHaveValue("first line\nsecond line");
  });

  it("will not send an empty question", async () => {
    render(<ChatPanel open onClose={() => {}} selectedFinding={null} backendConnected />);

    await userEvent.type(screen.getByLabelText("Ask the ECDAT assistant"), "   ");
    await userEvent.keyboard("{Enter}");

    expect(fetch).not.toHaveBeenCalled();
  });

  it("carries the conversation so far, and keeps it in the browser", async () => {
    fetch.mockResolvedValueOnce(answerWith("First answer.")).mockResolvedValueOnce(answerWith("Second answer."));

    render(<ChatPanel open onClose={() => {}} selectedFinding={null} backendConnected />);
    const input = screen.getByLabelText("Ask the ECDAT assistant");

    await userEvent.type(input, "First question");
    await userEvent.keyboard("{Enter}");
    await screen.findByText("First answer.");

    await userEvent.type(input, "Second question");
    await userEvent.keyboard("{Enter}");
    await screen.findByText("Second answer.");

    // The second request replays the earlier turns, and only those.
    expect(lastChatRequest().conversation).toEqual([
      { role: "user", content: "First question" },
      { role: "assistant", content: "First answer." },
    ]);
    // Nothing about the conversation is persisted: there is no database,
    // and a security conversation is not stored behind the user's back.
    expect(window.localStorage.length).toBe(0);
  });

  it("clears the conversation on request", async () => {
    fetch.mockResolvedValue(answerWith("An answer."));
    render(<ChatPanel open onClose={() => {}} selectedFinding={null} backendConnected />);

    await userEvent.type(screen.getByLabelText("Ask the ECDAT assistant"), "A question");
    await userEvent.keyboard("{Enter}");
    await screen.findByText("An answer.");

    await userEvent.click(screen.getByRole("button", { name: "Clear conversation" }));

    expect(screen.queryByText("An answer.")).not.toBeInTheDocument();
    expect(screen.getByText("Ask about this analysis")).toBeInTheDocument();
  });
});

describe("the selected finding", () => {
  it("attaches the finding to the request and shows which one it is", async () => {
    fetch.mockResolvedValueOnce(answerWith());
    render(<ChatPanel open onClose={() => {}} selectedFinding={FINDING} backendConnected />);

    // The user can see which finding the assistant was given -- an answer
    // about "this finding" is only trustworthy if that is visible.
    const chip = document.querySelector(".chat-context-chip");
    expect(chip).toHaveTextContent("RSA-2048");
    expect(chip).toHaveTextContent("NEEDS_REVIEW");
    expect(chip).toHaveTextContent(FINDING.bomRef.slice(0, 8));

    await userEvent.type(screen.getByLabelText("Ask the ECDAT assistant"), "Why does this need review?");
    await userEvent.keyboard("{Enter}");

    await waitFor(() => expect(lastChatRequest()).not.toBeNull());
    expect(lastChatRequest().bom_ref).toBe(FINDING.bomRef);
  });

  it("offers finding-specific prompts when one is selected, portfolio prompts otherwise", () => {
    const { unmount } = render(
      <ChatPanel open onClose={() => {}} selectedFinding={FINDING} backendConnected />,
    );
    const suggestions = document.querySelector(".chat-suggestions");
    expect(within(suggestions).getByText("Why is this finding risky?")).toBeInTheDocument();
    expect(within(suggestions).getByText("Explain this asset's evidence")).toBeInTheDocument();
    unmount();

    render(<ChatPanel open onClose={() => {}} selectedFinding={null} backendConnected />);
    const portfolio = document.querySelector(".chat-suggestions");
    expect(within(portfolio).getByText("Explain my highest-risk assets")).toBeInTheDocument();
    expect(within(portfolio).getByText("What should I migrate first?")).toBeInTheDocument();
  });

  it("sends no bom_ref when nothing is selected", async () => {
    fetch.mockResolvedValueOnce(answerWith());
    render(<ChatPanel open onClose={() => {}} selectedFinding={null} backendConnected />);

    await userEvent.click(screen.getByText("Explain my highest-risk assets"));

    await waitFor(() => expect(lastChatRequest()).not.toBeNull());
    expect(lastChatRequest().bom_ref).toBeNull();
  });
});

describe("when the model fails", () => {
  it("shows the reason it was given, not a stack trace, and offers a retry", async () => {
    fetch.mockResolvedValueOnce(
      failWith("model-unavailable", "The local model is not reachable. Check that Ollama is running."),
    );

    render(<ChatPanel open onClose={() => {}} selectedFinding={null} backendConnected />);
    await userEvent.type(screen.getByLabelText("Ask the ECDAT assistant"), "Explain the blast radius");
    await userEvent.keyboard("{Enter}");

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("The local model is not reachable. Check that Ollama is running.");
    expect(alert).toHaveTextContent("model-unavailable");
    expect(within(alert).getByRole("button", { name: /Retry/ })).toBeInTheDocument();
  });

  it("re-asks the same question on retry, without duplicating it", async () => {
    fetch
      .mockResolvedValueOnce(failWith("model-timeout", "The local model did not answer in time."))
      .mockResolvedValueOnce(answerWith("Recovered."));

    render(<ChatPanel open onClose={() => {}} selectedFinding={FINDING} backendConnected />);
    await userEvent.type(screen.getByLabelText("Ask the ECDAT assistant"), "Explain the blast radius");
    await userEvent.keyboard("{Enter}");

    await userEvent.click(await screen.findByRole("button", { name: /Retry/ }));

    await screen.findByText("Recovered.");
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    // The question the user typed appears once, and the retry carried the finding.
    expect(screen.getAllByText("Explain the blast radius")).toHaveLength(1);
    expect(lastChatRequest().bom_ref).toBe(FINDING.bomRef);
  });

  it("reports an unreadable failure rather than showing nothing", async () => {
    fetch.mockResolvedValueOnce({
      ok: false,
      status: 500,
      json: async () => {
        throw new SyntaxError("not json");
      },
    });

    render(<ChatPanel open onClose={() => {}} selectedFinding={null} backendConnected />);
    await userEvent.type(screen.getByLabelText("Ask the ECDAT assistant"), "Anything");
    await userEvent.keyboard("{Enter}");

    expect(await screen.findByRole("alert")).toHaveTextContent(/unavailable \(500\)/i);
  });

  it("says the backend is unreachable rather than naming a model it cannot reach", () => {
    render(<ChatPanel open onClose={() => {}} selectedFinding={null} backendConnected={false} />);
    expect(screen.getByText("Backend unreachable")).toBeInTheDocument();
    expect(screen.queryByText(/Qwen3:14B/)).not.toBeInTheDocument();
  });

  it("names the model that will answer when the backend is up", () => {
    render(<ChatPanel open onClose={() => {}} selectedFinding={null} backendConnected />);
    expect(screen.getByText(/Qwen3:14B/)).toBeInTheDocument();
  });
});
