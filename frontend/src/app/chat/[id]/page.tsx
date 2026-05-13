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
      <aside className="w-80 bg-[var(--sidebar)] border-r border-[var(--card-border)] flex flex-col">
        {/* Back Button */}
        <div className="px-5 pt-4">
          <button
            onClick={() => router.push("/")}
            className="text-xs text-[var(--muted)] hover:text-[var(--accent)] flex items-center gap-1"
          >
            ← All Patients
          </button>
        </div>

        {/* Patient Info & Medical History */}
        {patient && (
          <div className="px-5 py-4 border-b border-[var(--card-border)]">
            {/* Name & Demographics */}
            <div className="flex items-center gap-3 mb-4">
              <div className="w-11 h-11 rounded-full bg-[var(--accent)]/10 flex items-center justify-center text-[var(--accent)] font-bold text-sm">
                {patient.name.split(" ").map((n) => n[0]).join("")}
              </div>
              <div>
                <p className="font-semibold text-[15px]">{patient.name}</p>
                <p className="text-xs text-[var(--muted)] mt-0.5">
                  {patient.age} yrs • {patient.gender} • {patient.country}
                </p>
              </div>
            </div>

            {/* Medical History */}
            <div className="space-y-3">
              {/* Known Conditions */}
              <div>
                <p className="text-[11px] font-semibold text-[var(--muted)] uppercase tracking-wider mb-1.5">
                  Medical History
                </p>
                {patient.known_conditions.length > 0 ? (
                  <div className="flex flex-wrap gap-1.5">
                    {patient.known_conditions.map((c) => (
                      <span
                        key={c}
                        className="text-[11px] px-2 py-1 rounded-md bg-[var(--accent)]/8 text-[var(--accent)] border border-[var(--accent)]/15"
                      >
                        {c}
                      </span>
                    ))}
                  </div>
                ) : (
                  <p className="text-[11px] text-[var(--muted)] italic">No known conditions</p>
                )}
              </div>

              {/* Allergies */}
              <div>
                <p className="text-[11px] font-semibold text-[var(--muted)] uppercase tracking-wider mb-1.5">
                  Allergies
                </p>
                {patient.allergies.length > 0 ? (
                  <div className="flex flex-wrap gap-1.5">
                    {patient.allergies.map((a) => (
                      <span
                        key={a}
                        className="text-[11px] px-2 py-1 rounded-md bg-[var(--danger)]/8 text-[var(--danger)] border border-[var(--danger)]/15"
                      >
                        ⚠ {a}
                      </span>
                    ))}
                  </div>
                ) : (
                  <p className="text-[11px] text-[var(--muted)] italic">No known allergies</p>
                )}
              </div>
            </div>
          </div>
        )}

        {/* Conversations List */}
        <div className="flex-1 overflow-y-auto px-4 py-3 space-y-1">
          <p className="text-[11px] font-semibold text-[var(--muted)] uppercase tracking-wider px-2 mb-2">
            Consultations
          </p>
          <button
            onClick={newConversation}
            className="w-full text-left px-3 py-2.5 rounded-lg text-sm font-medium text-[var(--accent)] hover:bg-[var(--accent)]/8 transition-colors"
          >
            + New Consultation
          </button>
          {conversations.map((c) => (
            <button
              key={c.id}
              onClick={() => router.push(`/chat/${c.id}?patient=${patientId}`)}
              className={`w-full text-left px-3 py-2.5 rounded-lg text-sm truncate transition-colors ${
                c.id === conversationId
                  ? "bg-[var(--accent)]/10 text-[var(--accent)] font-medium"
                  : "text-[var(--foreground)] hover:bg-[var(--card-border)]/50"
              }`}
            >
              {c.title || "New consultation"}
              <span className="block text-[11px] text-[var(--muted)] mt-0.5">{c.status}</span>
            </button>
          ))}
        </div>

        <div className="p-4 border-t border-[var(--card-border)]">
          <ThemeToggle />
        </div>
      </aside>

      {/* Chat Area */}
      <div className="flex-1 flex flex-col">
        {/* Messages */}
        <div className="flex-1 overflow-y-auto px-8 py-8 space-y-5">
          {messages.length === 0 && (
            <div className="flex items-center justify-center h-full">
              <div className="text-center">
                <p className="text-5xl mb-4">💬</p>
                <p className="text-[var(--muted)] text-base">
                  Describe the patient&apos;s symptoms to begin
                </p>
                <p className="text-[var(--muted)] text-xs mt-2 opacity-60">
                  Include details like duration, severity, and location
                </p>
              </div>
            </div>
          )}
          {messages.map((msg) => (
            <div
              key={msg.id}
              className={`flex ${msg.role === "patient" ? "justify-end" : "justify-start"}`}
            >
              <div
                className={`max-w-[70%] rounded-2xl px-5 py-4 ${
                  msg.role === "patient"
                    ? "bg-[var(--accent)] text-white"
                    : "bg-[var(--card)] border border-[var(--card-border)] shadow-sm"
                }`}
              >
                <p className="text-[15px] whitespace-pre-wrap leading-7">{msg.content}</p>
                {msg.role === "assistant" && msg.metadata && (
                  <MetadataPanel metadata={msg.metadata} />
                )}
              </div>
            </div>
          ))}
          {sending && (
            <div className="flex justify-start">
              <div className="bg-[var(--card)] border border-[var(--card-border)] rounded-2xl px-5 py-4 shadow-sm">
                <div className="flex gap-1.5">
                  <span className="w-2.5 h-2.5 bg-[var(--muted)] rounded-full animate-bounce" style={{ animationDelay: "0ms" }} />
                  <span className="w-2.5 h-2.5 bg-[var(--muted)] rounded-full animate-bounce" style={{ animationDelay: "150ms" }} />
                  <span className="w-2.5 h-2.5 bg-[var(--muted)] rounded-full animate-bounce" style={{ animationDelay: "300ms" }} />
                </div>
              </div>
            </div>
          )}
          <div ref={bottomRef} />
        </div>

        {/* Input */}
        <div className="border-t border-[var(--card-border)] px-8 py-5">
          <div className="flex gap-3">
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && !e.shiftKey && send()}
              placeholder="Describe symptoms or answer questions..."
              className="flex-1 bg-[var(--input-bg)] border border-[var(--input-border)] rounded-xl px-5 py-3.5 text-[15px] focus:outline-none focus:ring-2 focus:ring-[var(--accent)] focus:border-transparent placeholder:text-[var(--muted)]"
              disabled={sending}
            />
            <button
              onClick={send}
              disabled={sending || !input.trim()}
              className="bg-[var(--accent)] hover:bg-[var(--accent-hover)] text-white px-5 py-3.5 rounded-xl text-sm font-medium disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
            >
              <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
              </svg>
            </button>
          </div>
          <p className="text-[11px] text-[var(--muted)] mt-2.5 text-center">
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
    <div className="mt-4 pt-4 border-t border-[var(--card-border)] space-y-4 text-sm">
      {redFlags.length > 0 && (
        <div className="bg-[var(--danger)]/10 text-[var(--danger)] px-4 py-2.5 rounded-lg font-medium">
          ⚠️ {redFlags.join(" • ")}
        </div>
      )}
      {diagnoses.length > 0 && (
        <div>
          <p className="font-semibold text-[var(--muted)] uppercase tracking-wider text-[11px] mb-2">
            Differential Diagnosis
          </p>
          <div className="space-y-2.5">
            {diagnoses.map((d, i) => (
              <div key={i}>
                <div className="flex items-center justify-between mb-1">
                  <span className="font-medium text-[13px]">{d.condition}</span>
                  <span className="text-[var(--muted)] text-xs">{Math.round(d.confidence * 100)}%</span>
                </div>
                <div className="w-full h-2 bg-[var(--card-border)] rounded-full overflow-hidden">
                  <div
                    className="h-full bg-[var(--accent)] rounded-full transition-all"
                    style={{ width: `${d.confidence * 100}%` }}
                  />
                </div>
                {d.reasoning && (
                  <p className="text-[11px] text-[var(--muted)] mt-1 leading-relaxed">{d.reasoning}</p>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
      {treatments.length > 0 && (
        <div>
          <p className="font-semibold text-[var(--muted)] uppercase tracking-wider text-[11px] mb-2">
            Treatment Options
          </p>
          <div className="flex flex-wrap gap-2">
            {treatments.map((t, i) => (
              <span key={i} className="px-2.5 py-1.5 rounded-lg bg-[var(--success)]/10 text-[var(--success)] text-xs font-medium">
                {t}
              </span>
            ))}
          </div>
        </div>
      )}
      {tests.length > 0 && (
        <div>
          <p className="font-semibold text-[var(--muted)] uppercase tracking-wider text-[11px] mb-2">
            Suggested Tests
          </p>
          <div className="flex flex-wrap gap-2">
            {tests.map((t, i) => (
              <span key={i} className="px-2.5 py-1.5 rounded-lg bg-[var(--accent)]/10 text-[var(--accent)] text-xs font-medium">
                {t}
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
