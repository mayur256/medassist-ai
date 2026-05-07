"use client";

import { useEffect, useRef, useState } from "react";
import { useParams, useSearchParams, useRouter } from "next/navigation";
import { api, Conversation, Message, Patient } from "@/lib/api";
import { ThemeToggle } from "@/components/theme-provider";

export default function ChatPage() {
  const { id: conversationId } = useParams<{ id: string }>();
  const searchParams = useSearchParams();
  const patientId = searchParams.get("patient") || "";
  const router = useRouter();

  const [messages, setMessages] = useState<Message[]>([]);
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [patient, setPatient] = useState<Patient | null>(null);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (patientId) {
      api.getPatient(patientId).then(setPatient);
      api.getConversations(patientId).then(setConversations);
    }
    if (conversationId) api.getMessages(conversationId).then(setMessages);
  }, [conversationId, patientId]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const send = async () => {
    if (!input.trim() || sending) return;
    setSending(true);
    try {
      const newMsgs = await api.sendMessage(conversationId, input.trim());
      setMessages((prev) => [...prev, ...newMsgs]);
      setInput("");
    } catch (e) {
      console.error(e);
    } finally {
      setSending(false);
    }
  };

  const newConversation = async () => {
    const conv = await api.createConversation(patientId);
    setConversations((prev) => [conv, ...prev]);
    router.push(`/chat/${conv.id}?patient=${patientId}`);
  };

  return (
    <div className="flex h-screen">
      {/* Sidebar */}
      <aside className="w-72 bg-[var(--sidebar)] border-r border-[var(--card-border)] flex flex-col">
        {/* Patient Info */}
        <div className="p-4 border-b border-[var(--card-border)]">
          <button onClick={() => router.push("/")} className="text-xs text-[var(--muted)] hover:text-[var(--accent)] mb-3 block">← All Patients</button>
          {patient && (
            <div>
              <div className="flex items-center gap-3">
                <div className="w-9 h-9 rounded-full bg-[var(--accent)]/10 flex items-center justify-center text-[var(--accent)] font-semibold text-xs">
                  {patient.name.split(" ").map((n) => n[0]).join("")}
                </div>
                <div>
                  <p className="font-semibold text-sm">{patient.name}</p>
                  <p className="text-[11px] text-[var(--muted)]">{patient.age}y • {patient.gender} • {patient.country}</p>
                </div>
              </div>
              {patient.allergies.length > 0 && (
                <div className="mt-2 flex flex-wrap gap-1">
                  {patient.allergies.map((a) => (
                    <span key={a} className="text-[10px] px-1.5 py-0.5 rounded bg-[var(--danger)]/10 text-[var(--danger)]">⚠ {a}</span>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>

        {/* Conversations List */}
        <div className="flex-1 overflow-y-auto p-3 space-y-1">
          <button onClick={newConversation} className="w-full text-left px-3 py-2 rounded-lg text-xs font-medium text-[var(--accent)] hover:bg-[var(--card-border)]/50">
            + New Consultation
          </button>
          {conversations.map((c) => (
            <button
              key={c.id}
              onClick={() => router.push(`/chat/${c.id}?patient=${patientId}`)}
              className={`w-full text-left px-3 py-2 rounded-lg text-xs truncate ${c.id === conversationId ? "bg-[var(--accent)]/10 text-[var(--accent)]" : "text-[var(--muted)] hover:bg-[var(--card-border)]/50"}`}
            >
              {c.title || "New consultation"}
              <span className="block text-[10px] opacity-60 mt-0.5">{c.status}</span>
            </button>
          ))}
        </div>

        <div className="p-3 border-t border-[var(--card-border)]">
          <ThemeToggle />
        </div>
      </aside>

      {/* Chat Area */}
      <div className="flex-1 flex flex-col">
        {/* Messages */}
        <div className="flex-1 overflow-y-auto px-6 py-6 space-y-4">
          {messages.length === 0 && (
            <div className="flex items-center justify-center h-full">
              <div className="text-center">
                <p className="text-4xl mb-3">💬</p>
                <p className="text-[var(--muted)] text-sm">Describe the patient&apos;s symptoms to begin</p>
              </div>
            </div>
          )}
          {messages.map((msg) => (
            <div key={msg.id} className={`flex ${msg.role === "patient" ? "justify-end" : "justify-start"}`}>
              <div className={`max-w-[70%] rounded-2xl px-4 py-3 ${
                msg.role === "patient"
                  ? "bg-[var(--accent)] text-white"
                  : "bg-[var(--card)] border border-[var(--card-border)]"
              }`}>
                <p className="text-sm whitespace-pre-wrap leading-relaxed">{msg.content}</p>
                {msg.role === "assistant" && msg.metadata && <MetadataPanel metadata={msg.metadata} />}
              </div>
            </div>
          ))}
          {sending && (
            <div className="flex justify-start">
              <div className="bg-[var(--card)] border border-[var(--card-border)] rounded-2xl px-4 py-3">
                <div className="flex gap-1">
                  <span className="w-2 h-2 bg-[var(--muted)] rounded-full animate-bounce" style={{ animationDelay: "0ms" }} />
                  <span className="w-2 h-2 bg-[var(--muted)] rounded-full animate-bounce" style={{ animationDelay: "150ms" }} />
                  <span className="w-2 h-2 bg-[var(--muted)] rounded-full animate-bounce" style={{ animationDelay: "300ms" }} />
                </div>
              </div>
            </div>
          )}
          <div ref={bottomRef} />
        </div>

        {/* Input */}
        <div className="border-t border-[var(--card-border)] px-6 py-4">
          <div className="flex gap-3">
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && !e.shiftKey && send()}
              placeholder="Describe symptoms or answer questions..."
              className="flex-1 bg-[var(--input-bg)] border border-[var(--input-border)] rounded-xl px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-[var(--accent)] focus:border-transparent placeholder:text-[var(--muted)]"
              disabled={sending}
            />
            <button
              onClick={send}
              disabled={sending || !input.trim()}
              className="bg-[var(--accent)] hover:bg-[var(--accent-hover)] text-white px-5 py-3 rounded-xl text-sm font-medium disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
            >
              <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
              </svg>
            </button>
          </div>
          <p className="text-[10px] text-[var(--muted)] mt-2 text-center">
            AI-assisted output — must be verified by a licensed medical professional
          </p>
        </div>
      </div>
    </div>
  );
}

function MetadataPanel({ metadata }: { metadata: Record<string, unknown> }) {
  const diagnoses = (metadata.diagnoses as Array<{ condition: string; confidence: number; reasoning: string }>) || [];
  const treatments = (metadata.treatments as string[]) || [];
  const redFlags = (metadata.red_flags as string[]) || [];
  const tests = (metadata.suggested_tests as string[]) || [];

  if (!diagnoses.length && !treatments.length && !redFlags.length && !tests.length) return null;

  return (
    <div className="mt-3 pt-3 border-t border-[var(--card-border)] space-y-3 text-xs">
      {redFlags.length > 0 && (
        <div className="bg-[var(--danger)]/10 text-[var(--danger)] px-3 py-2 rounded-lg font-medium">
          ⚠️ {redFlags.join(" • ")}
        </div>
      )}
      {diagnoses.length > 0 && (
        <div>
          <p className="font-semibold text-[var(--muted)] uppercase tracking-wide text-[10px] mb-1.5">Differential Diagnosis</p>
          <div className="space-y-1.5">
            {diagnoses.map((d, i) => (
              <div key={i} className="flex items-center justify-between">
                <span className="font-medium">{d.condition}</span>
                <div className="flex items-center gap-2">
                  <div className="w-16 h-1.5 bg-[var(--card-border)] rounded-full overflow-hidden">
                    <div className="h-full bg-[var(--accent)] rounded-full" style={{ width: `${d.confidence * 100}%` }} />
                  </div>
                  <span className="text-[var(--muted)] w-8 text-right">{Math.round(d.confidence * 100)}%</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
      {treatments.length > 0 && (
        <div>
          <p className="font-semibold text-[var(--muted)] uppercase tracking-wide text-[10px] mb-1.5">Treatments</p>
          <div className="flex flex-wrap gap-1.5">
            {treatments.map((t, i) => (
              <span key={i} className="px-2 py-1 rounded-md bg-[var(--success)]/10 text-[var(--success)]">{t}</span>
            ))}
          </div>
        </div>
      )}
      {tests.length > 0 && (
        <div>
          <p className="font-semibold text-[var(--muted)] uppercase tracking-wide text-[10px] mb-1.5">Suggested Tests</p>
          <div className="flex flex-wrap gap-1.5">
            {tests.map((t, i) => (
              <span key={i} className="px-2 py-1 rounded-md bg-[var(--accent)]/10 text-[var(--accent)]">{t}</span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
