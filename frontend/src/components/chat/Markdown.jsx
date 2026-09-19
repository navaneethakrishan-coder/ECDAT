/**
 * A small Markdown renderer for assistant answers.
 *
 * It covers what the assistant is asked to produce -- paragraphs, headings,
 * bullet and numbered lists, fenced code blocks, inline code, bold and
 * italic -- and nothing else. Everything is built as React elements, never
 * as HTML, so model output cannot inject markup into the dashboard.
 */

function renderInline(text, keyPrefix) {
  // Split on inline code first: nothing inside backticks is formatted.
  const parts = [];
  const pattern = /(`[^`]+`|\*\*[^*]+\*\*|\*[^*]+\*|_[^_]+_)/g;
  let lastIndex = 0;
  let match;
  let index = 0;

  while ((match = pattern.exec(text)) !== null) {
    if (match.index > lastIndex) {
      parts.push(text.slice(lastIndex, match.index));
    }
    const token = match[0];
    const key = `${keyPrefix}-i${index++}`;

    if (token.startsWith("`")) {
      parts.push(<code key={key}>{token.slice(1, -1)}</code>);
    } else if (token.startsWith("**")) {
      parts.push(<strong key={key}>{token.slice(2, -2)}</strong>);
    } else {
      parts.push(<em key={key}>{token.slice(1, -1)}</em>);
    }
    lastIndex = match.index + token.length;
  }

  if (lastIndex < text.length) parts.push(text.slice(lastIndex));
  return parts;
}

function parseBlocks(markdown) {
  const lines = String(markdown || "").split("\n");
  const blocks = [];
  let index = 0;

  while (index < lines.length) {
    const line = lines[index];

    // Fenced code block
    if (line.trim().startsWith("```")) {
      const language = line.trim().slice(3).trim();
      const code = [];
      index += 1;
      while (index < lines.length && !lines[index].trim().startsWith("```")) {
        code.push(lines[index]);
        index += 1;
      }
      index += 1; // closing fence
      blocks.push({ type: "code", language, content: code.join("\n") });
      continue;
    }

    // Heading
    const heading = line.match(/^(#{1,4})\s+(.*)$/);
    if (heading) {
      blocks.push({ type: "heading", level: heading[1].length, content: heading[2] });
      index += 1;
      continue;
    }

    // List (bulleted or numbered)
    if (/^\s*([-*+]|\d+\.)\s+/.test(line)) {
      const ordered = /^\s*\d+\.\s+/.test(line);
      const items = [];
      while (index < lines.length && /^\s*([-*+]|\d+\.)\s+/.test(lines[index])) {
        items.push(lines[index].replace(/^\s*([-*+]|\d+\.)\s+/, ""));
        index += 1;
      }
      blocks.push({ type: "list", ordered, items });
      continue;
    }

    // Blank line
    if (!line.trim()) {
      index += 1;
      continue;
    }

    // Paragraph: consume until a blank line or a new block starts
    const paragraph = [];
    while (
      index < lines.length &&
      lines[index].trim() &&
      !lines[index].trim().startsWith("```") &&
      !/^(#{1,4})\s+/.test(lines[index]) &&
      !/^\s*([-*+]|\d+\.)\s+/.test(lines[index])
    ) {
      paragraph.push(lines[index]);
      index += 1;
    }
    blocks.push({ type: "paragraph", content: paragraph.join(" ") });
  }

  return blocks;
}

export function Markdown({ content }) {
  const blocks = parseBlocks(content);

  return (
    <div className="chat-markdown">
      {blocks.map((block, blockIndex) => {
        const key = `b${blockIndex}`;

        if (block.type === "code") {
          return (
            <pre key={key} className="chat-code">
              <code data-language={block.language || undefined}>{block.content}</code>
            </pre>
          );
        }

        if (block.type === "heading") {
          const Tag = `h${Math.min(block.level + 2, 6)}`;
          return <Tag key={key}>{renderInline(block.content, key)}</Tag>;
        }

        if (block.type === "list") {
          const Tag = block.ordered ? "ol" : "ul";
          return (
            <Tag key={key}>
              {block.items.map((item, itemIndex) => (
                <li key={`${key}-${itemIndex}`}>{renderInline(item, `${key}-${itemIndex}`)}</li>
              ))}
            </Tag>
          );
        }

        return <p key={key}>{renderInline(block.content, key)}</p>;
      })}
    </div>
  );
}
