"use client";

import { FormEvent, KeyboardEvent, useCallback, useEffect, useMemo, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import rehypeSanitize from "rehype-sanitize";
import remarkGfm from "remark-gfm";

import FeedbackTab from "./FeedbackTab";

type SourcePassage = {
  text: string;
  source: string;
  chunk_id: string;
  citation?: string;
  url?: string;
  page?: number;
};

type ChatMessage = {
  id: string;
  role: "user" | "assistant";
  content: string;
  sources?: SourcePassage[];
  criticApproved?: boolean;
  criticNote?: string | null;
};

type StartSessionResponse = {
  session_id: string;
  message: string;
  status: string;
};

type RespondResponse = {
  session_id: string;
  reply: string;
  sources: SourcePassage[];
  critic_approved: boolean;
  critic_note?: string | null;
};

const apiBaseUrl = (process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:9090").replace(/\/$/, "");

function uniqueSources(sources: SourcePassage[]) {
  const seen = new Set<string>();
  return sources.filter((source) => {
    const key = source.citation || source.source;
    if (seen.has(key)) {
      return false;
    }
    seen.add(key);
    return true;
  });
}

function SourcesPanel({ sources }: { sources: SourcePassage[] }) {
  const [open, setOpen] = useState(false);
  // Deduplicated by citation, keeping the first (highest-ranked) snippet per citation
  const unique = uniqueSources(sources);

  return (
    <>
      <button type="button" className={`sources-toggle ${open ? "open" : ""}`} onClick={() => setOpen(!open)}>
        <span className="arrow">&#9654;</span> Sources ({unique.length})
      </button>
      {open ? (
        <div className="sources-panel">
          {unique.map((source) => {
            const label = source.citation || source.source;
            return (
              <div className="source-item" key={`${source.chunk_id}-${label}`}>
                <div className="source-citation">
                  {source.url ? (
                    <a href={source.url} target="_blank" rel="noopener noreferrer">
                      {label}
                    </a>
                  ) : (
                    label
                  )}
                </div>
                {source.text ? <div className="source-snippet">&ldquo;{source.text.trim()}&rdquo;</div> : null}
              </div>
            );
          })}
        </div>
      ) : null}
    </>
  );
}

async function parseApiError(response: Response) {
  try {
    const data = await response.json();
    return data.detail || response.statusText;
  } catch {
    return response.statusText;
  }
}

export default function Home() {
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [status, setStatus] = useState("Starting session...");
  const [isSending, setIsSending] = useState(false);
  const [isStarting, setIsStarting] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);

  const shortSessionId = useMemo(() => sessionId?.slice(0, 8), [sessionId]);

  useEffect(() => {
    scrollRef.current?.scrollTo({
      top: scrollRef.current.scrollHeight,
      behavior: "smooth",
    });
  }, [messages, isSending]);

  const startSession = useCallback(async () => {
    setIsStarting(true);
    setStatus("Starting session...");
    setMessages([]);
    setSessionId(null);

    try {
      const response = await fetch(`${apiBaseUrl}/session/start`, {
        method: "POST",
      });
      if (!response.ok) {
        throw new Error(await parseApiError(response));
      }
      const data = (await response.json()) as StartSessionResponse;
      setSessionId(data.session_id);
      setMessages([
        {
          id: crypto.randomUUID(),
          role: "assistant",
          content: data.message,
          sources: [],
          criticApproved: true,
        },
      ]);
      setStatus(`Ready - ${data.session_id.slice(0, 8)}...`);
    } catch (error) {
      setStatus(error instanceof Error ? `Error starting session: ${error.message}` : "Error starting session");
    } finally {
      setIsStarting(false);
    }
  }, []);

  useEffect(() => {
    startSession();
  }, [startSession]);

  async function sendMessage(event?: FormEvent<HTMLFormElement>) {
    event?.preventDefault();
    const message = input.trim();
    if (!message || !sessionId || isSending) {
      return;
    }

    setInput("");
    setMessages((current) => [
      ...current,
      {
        id: crypto.randomUUID(),
        role: "user",
        content: message,
      },
    ]);
    setIsSending(true);
    setStatus("Consulting the teachings...");

    try {
      const response = await fetch(`${apiBaseUrl}/session/${sessionId}/respond`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ message }),
      });
      if (!response.ok) {
        throw new Error(await parseApiError(response));
      }
      const data = (await response.json()) as RespondResponse;
      setMessages((current) => [
        ...current,
        {
          id: crypto.randomUUID(),
          role: "assistant",
          content: data.reply,
          sources: data.sources,
          criticApproved: data.critic_approved,
          criticNote: data.critic_note,
        },
      ]);
      setStatus(data.critic_note ? `Note: ${data.critic_note}` : "Ready");
    } catch (error) {
      setMessages((current) => [
        ...current,
        {
          id: crypto.randomUUID(),
          role: "assistant",
          content: error instanceof Error ? `An error occurred: ${error.message}` : "An error occurred.",
          sources: [],
          criticApproved: false,
        },
      ]);
      setStatus("Error");
    } finally {
      setIsSending(false);
    }
  }

  function handleKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      sendMessage();
    }
  }

  return (
    <main className="container">
      <section>
        <header>
          <h1>Vipassana AI Assistant</h1>
          <p>Answers grounded in the provided teaching documents. AI can make mistakes - always verify with a qualified teacher.</p>
        </header>

        <div id="chat-window" ref={scrollRef}>
          {messages.map((message) => (
            <article
              className={`msg ${message.role === "assistant" ? "ai" : "user"} ${
                message.criticApproved === false ? "refused" : ""
              }`}
              key={message.id}
            >
              <div className="bubble">
                {message.role === "assistant" ? (
                  <ReactMarkdown rehypePlugins={[rehypeSanitize]} remarkPlugins={[remarkGfm]}>
                    {message.content}
                  </ReactMarkdown>
                ) : (
                  message.content
                )}
              </div>

              {message.sources && message.sources.length > 0 ? <SourcesPanel sources={message.sources} /> : null}

              {message.criticNote ? <div className="critic-note">Critic: {message.criticNote}</div> : null}
            </article>
          ))}

          {isSending ? (
            <article className="msg ai">
              <div className="bubble thinking">...</div>
            </article>
          ) : null}
        </div>

        <form className="input-row" onSubmit={sendMessage}>
          <textarea
            value={input}
            onChange={(event) => setInput(event.target.value)}
            onKeyDown={handleKeyDown}
            rows={2}
            placeholder="Ask about Vipassana practice, technique, or teachings..."
            disabled={!sessionId || isStarting}
          />
          <button type="submit" disabled={!input.trim() || !sessionId || isSending || isStarting}>
            Ask
          </button>
        </form>

        <p className="disclaimer">
          This tool is under improvement. It&apos;s not endorsed by VRI. Please use it at your own risk.
        </p>
        <div id="status">{shortSessionId && status === "Ready" ? `Ready - ${shortSessionId}...` : status}</div>
      </section>

      <FeedbackTab apiBaseUrl={apiBaseUrl} />
    </main>
  );
}
