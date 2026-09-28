"use client";

import { FormEvent, useEffect, useRef, useState } from "react";

type SendState = { kind: "idle" } | { kind: "sending" } | { kind: "sent" } | { kind: "error" };

export default function FeedbackTab({ apiBaseUrl }: { apiBaseUrl: string }) {
  const [open, setOpen] = useState(false);
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [message, setMessage] = useState("");
  // Honeypot: hidden from people, so only bots fill it in
  const [website, setWebsite] = useState("");
  const [sendState, setSendState] = useState<SendState>({ kind: "idle" });
  const messageRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    if (!open) {
      return;
    }
    messageRef.current?.focus();
    const onKeyDown = (event: globalThis.KeyboardEvent) => {
      if (event.key === "Escape") {
        setOpen(false);
      }
    };
    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, [open]);

  useEffect(() => {
    if (sendState.kind !== "sent") {
      return;
    }
    const timer = setTimeout(() => {
      setOpen(false);
      setSendState({ kind: "idle" });
    }, 1800);
    return () => clearTimeout(timer);
  }, [sendState]);

  async function send(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSendState({ kind: "sending" });
    try {
      const response = await fetch(`${apiBaseUrl}/contact`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name, email, message, website }),
      });
      if (!response.ok) {
        throw new Error(response.statusText);
      }
      setMessage("");
      setSendState({ kind: "sent" });
    } catch {
      setSendState({ kind: "error" });
    }
  }

  const statusText = {
    idle: "",
    sending: "Sending...",
    sent: "Thank you, your message was sent.",
    error: "Could not send. Please try again.",
  }[sendState.kind];

  return (
    <>
      <button id="feedback-tab" type="button" onClick={() => setOpen(true)}>
        Suggestions &amp; feedback
      </button>

      {open ? (
        <div
          className="modal-backdrop"
          onClick={(event) => {
            if (event.target === event.currentTarget) {
              setOpen(false);
            }
          }}
        >
          <form className="modal" onSubmit={send}>
            <h2>Suggestions &amp; feedback</h2>
            <p>Feedback, questions, or a problem with an answer? Leave an email if you&apos;d like a reply.</p>
            <input
              value={name}
              onChange={(event) => setName(event.target.value)}
              maxLength={200}
              placeholder="Name (optional)"
              autoComplete="name"
            />
            <input
              type="email"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              maxLength={200}
              placeholder="Email (optional)"
              autoComplete="email"
            />
            <textarea
              ref={messageRef}
              value={message}
              onChange={(event) => setMessage(event.target.value)}
              maxLength={5000}
              placeholder="Your message"
              required
            />
            <input
              className="hp"
              value={website}
              onChange={(event) => setWebsite(event.target.value)}
              tabIndex={-1}
              autoComplete="off"
              aria-hidden="true"
            />
            <div className="modal-actions">
              <span className={`modal-status ${sendState.kind === "error" ? "error" : ""}`}>{statusText}</span>
              <button type="button" className="cancel" onClick={() => setOpen(false)}>
                Cancel
              </button>
              <button type="submit" disabled={sendState.kind === "sending" || !message.trim()}>
                Send
              </button>
            </div>
          </form>
        </div>
      ) : null}
    </>
  );
}
