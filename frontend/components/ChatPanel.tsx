"use client";

import { FormEvent, useEffect, useRef, useState } from "react";
import { getChatHistory, sendAgentMessage, sendVoiceMessage, type AgentResponse, type ChatMessage as HistoryMessage } from "../lib/api";
import { ResultCards } from "./ResultCards";

interface ChatPanelProps {
  hostelId?: string;
  title?: string;
  subtitle?: string;
}

interface Message {
  role: "user" | "assistant";
  content: string;
}

const promptSuggestions = {
  general: [
    "Is this rent fair for the neighborhood?",
    "Could this listing be a scam?",
    "How reliable is water and power here?",
  ],
  hostel: [
    "Compare this hostel's rent to nearby options.",
    "Check the utility risk for this hostel.",
    "Summarize any scam signals in this listing.",
  ],
};

function getSessionId(): string {
  if (typeof window === "undefined") return "demo-session";
  const storageKey = "housingScoutSessionId";
  const current = window.localStorage.getItem(storageKey);
  if (current) return current;

  const nextId = globalThis.crypto?.randomUUID?.() ?? `session-${Date.now()}`;
  window.localStorage.setItem(storageKey, nextId);
  return nextId;
}

export function ChatPanel({ hostelId, title = "Ask the agent", subtitle = "Use the same checked flow for rent, utilities, and scam risks." }: ChatPanelProps) {
  const welcomeMessage = hostelId
    ? "I can review this hostel in context and explain the rent, utility, or scam signal."
    : "I can help you compare nearby prices, check utility reliability, or scan suspicious messages.";

  const [messages, setMessages] = useState<Message[]>([{ role: "assistant", content: welcomeMessage }]);
  const [draft, setDraft] = useState("");
  const [loading, setLoading] = useState(false);
  const [voiceLoading, setVoiceLoading] = useState(false);
  const [voiceStatus, setVoiceStatus] = useState("Use typed chat or record a voice note.");
  const [recording, setRecording] = useState(false);
  const [agentResult, setAgentResult] = useState<AgentResponse | null>(null);
  const messagesEndRef = useRef<HTMLDivElement | null>(null);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const streamRef = useRef<MediaStream | null>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading, voiceLoading]);

  useEffect(() => {
    let active = true;

    async function loadHistory() {
      try {
        const history = await getChatHistory(getSessionId(), hostelId);
        if (!active) return;
        if (history.length > 0) {
          const restored = history.map((item: HistoryMessage) => ({ role: item.role as Message["role"], content: item.content }));
          setMessages(restored);
        } else {
          setMessages([{ role: "assistant", content: welcomeMessage }]);
        }
      } catch {
        if (active) {
          setMessages([{ role: "assistant", content: welcomeMessage }]);
        }
      }
    }

    loadHistory();
    return () => {
      active = false;
    };
  }, [hostelId, welcomeMessage]);

  useEffect(() => {
    return () => {
      mediaRecorderRef.current?.stop();
      streamRef.current?.getTracks().forEach((track) => track.stop());
    };
  }, []);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    const message = draft.trim();
    if (!message) return;

    const sessionId = getSessionId();
    setMessages((current) => [...current, { role: "user", content: message }]);
    setDraft("");
    setLoading(true);

    try {
      const result = await sendAgentMessage(message, hostelId, sessionId);
      setAgentResult(result);
      const replyText = result.reply;
      if (typeof replyText === "string" && replyText.trim()) {
        setMessages((current) => [...current, { role: "assistant", content: replyText }]);
      }
    } catch {
      setMessages((current) => [...current, { role: "assistant", content: "The agent is currently unavailable. Please try again in a moment." }]);
    } finally {
      setLoading(false);
    }
  }

  async function toggleRecording() {
    if (recording) {
      mediaRecorderRef.current?.stop();
      setRecording(false);
      return;
    }

    if (typeof window === "undefined" || typeof window.MediaRecorder === "undefined" || !navigator.mediaDevices?.getUserMedia) {
      setVoiceStatus("Voice recording is not available in this browser.");
      return;
    }

    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const recorder = new MediaRecorder(stream);
      const chunks: Blob[] = [];

      recorder.ondataavailable = (event) => {
        if (event.data.size > 0) chunks.push(event.data);
      };

      recorder.onstop = async () => {
        const audio = new Blob(chunks, { type: recorder.mimeType || "audio/webm" });
        stream.getTracks().forEach((track) => track.stop());
        streamRef.current = null;
        setVoiceLoading(true);
        setVoiceStatus("Sending your voice note…");

        try {
          const result = await sendVoiceMessage(audio, hostelId, getSessionId(), true);
          const transcript = result.transcript?.trim() || "Voice message";
          const replyText = result.reply?.trim() || "The agent did not return a reply.";
          setMessages((current) => [
            ...current,
            { role: "user", content: transcript },
            { role: "assistant", content: replyText },
          ]);
          setVoiceStatus(result.voiceError ? `Voice reply unavailable: ${result.voiceError}` : "Voice note sent successfully.");
        } catch {
          setVoiceStatus("Voice chat could not be completed. Typed chat is still available.");
        } finally {
          setVoiceLoading(false);
        }
      };

      recorder.start();
      mediaRecorderRef.current = recorder;
      streamRef.current = stream;
      setRecording(true);
      setVoiceStatus("Recording… tap stop when you are done.");
    } catch {
      setVoiceStatus("Microphone access was blocked. Please allow it and try again.");
    }
  }

  function selectSuggestion(suggestion: string) {
    setDraft(suggestion);
  }

  const suggestions = hostelId ? promptSuggestions.hostel : promptSuggestions.general;

  return (
    <div className="rounded-[32px] border border-white/15 bg-black/30 p-5 shadow-[0_30px_100px_rgba(0,0,0,0.32)] backdrop-blur-xl">
      <div className="mb-6 flex flex-col gap-4 rounded-[28px] border border-white/10 bg-white/5 p-5 text-white shadow-inner shadow-black/10">
        <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <p className="text-sm uppercase tracking-[0.3em] text-zinc-400">{title}</p>
            <h3 className="mt-2 text-3xl font-semibold text-white">{subtitle}</h3>
          </div>
          {hostelId ? (
            <span className="rounded-full border border-white/15 bg-white/10 px-4 py-2 text-xs uppercase tracking-[0.2em] text-zinc-200">
              Scoped to hostel
            </span>
          ) : null}
        </div>
        <p className="max-w-2xl text-sm leading-6 text-zinc-300">
          Ask a clear question and the agent will answer with rent, utility, and scam insight in a conversational layout.
        </p>
      </div>

      <div className="rounded-[28px] border border-white/10 bg-white/5 p-4 shadow-inner shadow-black/10">
        <div className="mb-4 flex flex-wrap gap-2 text-sm text-zinc-300">
          {suggestions.map((suggestion) => (
            <button
              key={suggestion}
              type="button"
              onClick={() => selectSuggestion(suggestion)}
              className="rounded-full border border-white/10 bg-white/5 px-4 py-2 text-left text-sm text-zinc-200 transition hover:border-white/20 hover:bg-white/10"
            >
              {suggestion}
            </button>
          ))}
        </div>

        <div className="mb-4 flex flex-wrap items-center justify-between gap-3 rounded-[24px] border border-white/10 bg-slate-950/50 px-4 py-3">
          <div>
            <p className="text-[11px] uppercase tracking-[0.24em] text-zinc-400">Voice mode</p>
            <p className="mt-1 text-sm text-zinc-300">{voiceStatus}</p>
          </div>
          <button
            type="button"
            onClick={toggleRecording}
            className="rounded-full border border-white/10 bg-white/10 px-4 py-2 text-sm text-white transition hover:bg-white/20"
          >
            {recording ? "Stop recording" : voiceLoading ? "Sending…" : "Record voice"}
          </button>
        </div>

        <div className="max-h-[420px] space-y-3 overflow-y-auto px-1 py-1">
          {messages.map((item, index) => (
            <div key={`${item.role}-${index}`} className={`flex ${item.role === "user" ? "justify-end" : "justify-start"}`}>
              <div className={`max-w-[80%] rounded-[28px] px-4 py-3 text-sm leading-7 shadow-[0_10px_30px_rgba(0,0,0,0.15)] ${
                item.role === "user"
                  ? "bg-white/10 text-white ring-1 ring-white/10"
                  : "bg-slate-950/90 text-zinc-200 ring-1 ring-white/5"
              }`}>
                <div className="mb-2 flex items-center gap-2 text-[11px] uppercase tracking-[0.24em] text-zinc-400">
                  <span className="inline-flex h-2.5 w-2.5 rounded-full bg-current text-transparent" />
                  {item.role === "user" ? "You" : "Agent"}
                </div>
                <div className="whitespace-pre-wrap">{item.content}</div>
              </div>
            </div>
          ))}
          {loading ? (
            <div className="flex justify-start">
              <div className="max-w-[70%] rounded-[28px] bg-slate-950/90 px-4 py-3 text-sm text-zinc-300 ring-1 ring-white/5">Thinking…</div>
            </div>
          ) : null}
          <div ref={messagesEndRef} />
        </div>
      </div>

      {agentResult ? <ResultCards toolCalls={agentResult.tool_calls} /> : null}

      <form onSubmit={handleSubmit} className="mt-5 flex flex-col gap-3 sm:flex-row">
        <textarea
          rows={2}
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
          placeholder="Type your question here..."
          className="min-h-[72px] flex-1 resize-none rounded-[999px] border border-white/15 bg-white/10 px-5 py-4 text-sm text-white outline-none placeholder:text-zinc-500 focus:border-white/25 focus:ring-1 focus:ring-white/10"
        />
        <button
          type="submit"
          disabled={loading}
          className="inline-flex items-center justify-center rounded-full bg-white/15 px-6 py-4 text-sm uppercase tracking-[0.2em] text-white transition hover:bg-white/20 disabled:cursor-not-allowed disabled:opacity-60 sm:w-auto"
        >
          {loading ? "Sending…" : "Send message"}
        </button>
      </form>
    </div>
  );
}
