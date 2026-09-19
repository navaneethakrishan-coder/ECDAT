"""The ECDAT chat assistant.

A conversational front end to the analysis ECDAT has already produced. It
is deliberately *not* a second analysis engine: it receives the recorded
results as context (services/chat_context.py) and explains them. It never
computes risk, chooses an algorithm, or changes anything in data/.

It uses the same locally hosted Ollama model as the AI Advisor, with the
same error philosophy: a failure is reported as a specific, non-technical
reason with a machine-readable code, never as a stack trace and never as a
plausible-sounding answer.
"""

import json

import requests

from services.chat_context import build_context

# The same local model and endpoint the AI Advisor already uses -- one
# model, one configuration, no second provider.
OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "qwen3:14b"

REQUEST_TIMEOUT = 300
MAX_MESSAGE_CHARS = 4000
MAX_HISTORY_TURNS = 8

SYSTEM_PROMPT = """You are the ECDAT Assistant: a Cryptographic Discovery, Quantum Risk and \
PQC Migration Assistant for the ECDAT platform.

ECDAT scans a source repository with CBOMKit, producing a CycloneDX CBOM, then runs a \
13-stage analysis pipeline that classifies each finding, scores explainable quantum risk, \
computes blast radius, migration complexity and migration priority, ranks PQC candidates \
and decides a migration strategy.

YOUR ROLE
- Explain the findings ECDAT has already produced, using the ECDAT CONTEXT supplied below.
- Answer as a security engineer would: precise, calm, no marketing language.

ABSOLUTE RULES
- Use ONLY the ECDAT CONTEXT for facts about this repository. If the context does not \
contain what the user asks for, say that ECDAT has not recorded it. Never fill the gap \
with general knowledge presented as this repository's data.
- NEVER invent a cryptographic finding, a file path, a dependency, a score, or a bom_ref.
- NEVER claim a migration, fix, scan or change has been performed. ECDAT analyses; it does \
not modify the repository it scans, and you cannot change ECDAT's data.
- Distinguish fact from interpretation. State recorded values as facts; mark your own \
reasoning as interpretation.
- Explain uncertainty rather than hiding it. Where ECDAT recorded a value as UNKNOWN, say \
it is unknown and why that matters, and never treat it as zero.

HOW TO EXPLAIN ECDAT'S CONCEPTS
- bom_ref is the only canonical identity of a finding. Two findings can share an algorithm \
name (for example two distinct RSA-2048 findings in different files) and are still \
separate findings. Never merge them.
- NEEDS_REVIEW means the evidence does not determine the finding's role, so ECDAT \
deliberately selected NO PQC component. If ranked candidates exist for such a finding, \
they are ranking-model output only and explicitly NOT a recommendation. Say so plainly.
- KEEP means no PQC replacement applies to that role (hashes, MACs, KDFs), not that the \
finding is unimportant.
- DIRECT_PQC replaces the primitive; HYBRID runs the classical primitive and a PQC one \
together, chosen when there is evidence of external interoperability or phased-transition \
pressure. Explain which evidence drove the decision when the context records it.
- Key material inherits the strategy of the algorithm it depends on; if the context shows \
inherited_from, explain the inheritance.
- Blast radius is computed ONLY from CycloneDX dependsOn relationships recorded in the \
CBOM. It is potential dependency impact, not a confirmed code change. Never assert a \
relationship that is not in the context.
- What-If results are simulations run on a copy. They never change the real finding, its \
scores or the dataset. Always describe them as hypothetical.
- Quantum risk is a weighted, explainable score; unknown factors are excluded and the \
remaining weights rescaled.

STYLE
- Answer in Markdown. Short paragraphs, and lists where they help.
- Reference findings by name AND bom_ref when identifying them.
- Keep answers under roughly 250 words unless asked for more detail.
- If asked something outside ECDAT's scope (unrelated to this analysis, cryptographic \
discovery or PQC migration), say so briefly and offer what ECDAT can answer instead.
"""


class ChatError(Exception):
    """A chat failure with a machine-readable reason code for the UI."""

    def __init__(self, code: str, message: str, status_code: int = 502):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


def normalise_history(conversation):
    """The recent turns, trimmed and validated.

    Only role and content survive: anything else the client sends is
    dropped rather than forwarded to the model.
    """
    if not isinstance(conversation, list):
        return []

    turns = []
    for entry in conversation[-(MAX_HISTORY_TURNS * 2) :]:
        if not isinstance(entry, dict):
            continue
        role = entry.get("role")
        content = entry.get("content")
        if role not in ("user", "assistant") or not isinstance(content, str):
            continue
        content = content.strip()[:MAX_MESSAGE_CHARS]
        if content:
            turns.append({"role": role, "content": content})
    return turns


def build_prompt(message, context, conversation=None):
    """The full prompt: instructions, ECDAT facts, recent turns, question."""
    sections = [
        SYSTEM_PROMPT,
        "",
        "ECDAT CONTEXT (the only source of facts about this repository):",
        json.dumps(context, indent=2, default=str),
    ]

    history = normalise_history(conversation)
    if history:
        sections.append("")
        sections.append("CONVERSATION SO FAR:")
        for turn in history:
            speaker = "User" if turn["role"] == "user" else "Assistant"
            sections.append(f"{speaker}: {turn['content']}")

    sections.append("")
    sections.append(f"User: {message}")
    sections.append("Assistant:")
    return "\n".join(sections)


def ask(message, bom_ref=None, conversation=None, data_dir=None, session=None):
    """Answers one chat turn from ECDAT's recorded analysis.

    Raises ChatError with a reason code the API surfaces verbatim.
    """
    if not isinstance(message, str) or not message.strip():
        raise ChatError("empty-message", "Enter a question for the ECDAT assistant.", 400)

    message = message.strip()
    if len(message) > MAX_MESSAGE_CHARS:
        raise ChatError(
            "message-too-long",
            f"Questions are limited to {MAX_MESSAGE_CHARS} characters.",
            400,
        )

    context = build_context(bom_ref=bom_ref, data_dir=data_dir)
    prompt = build_prompt(message, context, conversation)

    client = session or requests
    try:
        response = client.post(
            OLLAMA_URL,
            json={
                "model": MODEL,
                "prompt": prompt,
                "stream": False,
                "think": False,
                "options": {"temperature": 0.2, "num_predict": 700},
            },
            timeout=REQUEST_TIMEOUT,
        )
    except requests.Timeout as error:
        raise ChatError(
            "model-timeout",
            "The local model did not answer in time. Try again, or ask a shorter question.",
        ) from error
    except requests.RequestException as error:
        raise ChatError(
            "model-unavailable",
            f"The local model is not reachable at {OLLAMA_URL}. Check that Ollama is running.",
        ) from error

    status = getattr(response, "status_code", 500)
    if status >= 400:
        # Ollama returns 500s intermittently; the UI offers a retry, so the
        # message says what to do rather than exposing the transport error.
        raise ChatError(
            "model-error",
            f"The local model returned an error (HTTP {status}). Retrying usually succeeds.",
        )

    try:
        payload = response.json()
    except (ValueError, json.JSONDecodeError) as error:
        raise ChatError(
            "malformed-response",
            "The local model returned a response ECDAT could not read.",
        ) from error

    if not isinstance(payload, dict):
        raise ChatError("malformed-response", "The local model returned an unexpected response shape.")

    answer = payload.get("response")
    if not isinstance(answer, str) or not answer.strip():
        raise ChatError("empty-response", "The local model returned an empty answer. Try asking again.")

    return {
        "response": answer.strip(),
        "model": MODEL,
        "context": {
            "bom_ref": bom_ref,
            "dataset_available": context.get("dataset_available", False),
            "selected_finding": bool(context.get("selected_finding")),
            "repository": (context.get("repository") or {}).get("git_url"),
        },
    }
