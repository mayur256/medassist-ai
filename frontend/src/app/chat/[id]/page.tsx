"use client";

import { useEffect, useRef, useState } from "react";
import { useParams, useSearchParams, useRouter } from "next/navigation";
import { api, Conversation, DrugInteraction, Message, Patient, SOAPNote } from "@/lib/api";
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
  const [soapNote, setSoapNote] = useState<SOAPNote | null>(null);
  const [showSoap, setShowSoap] = useState(false);
  const [completingConv, setCompletingConv] = useState(false);
  const [streamStage, setStreamStage] = useState<string | null>(null);
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
    setStreamStage("processing");
    try {
      const newMsgs = await api.sendMessage(conversationId, input.trim());
      setMessages((prev) => [...prev, ...newMsgs]);
      setInput("");
    } catch (e) {
      console.error(e);
    } finally {
      setSending(false);
      setStreamStage(null);
    }
  };

  const newConversation = async () => {
    const conv = await api.createConversation(patientId);
    setConversations((prev) => [conv, ...prev]);
    router.push(`/chat/${conv.id}?patient=${patientId}`);
  };

  const completeAndExportSOAP = async () => {
    if (completingConv) return;
    setCompletingConv(true);
    try {
      const result = await api.completeConversation(conversationId);
      setSoapNote(result);
      setShowSoap(true);
      // Update conversation status in sidebar
      setConversations((prev) =>
        prev.map((c) => (c.id === conversationId ? { ...c, status: "completed" } : c))
      );
    } catch (e) {
      console.error("SOAP export failed:", e);
      alert("Failed to generate SOAP note. Ensure conversation has messages.");
    } finally {
      setCompletingConv(false);
    }
  };

  const currentConv = conversations.find((c) => c.id === conversationId);
  const isCompleted = currentConv?.status === "completed";


  return (
    <div className="flex h-screen">
      {/* Sidebar */}
      <aside className="w-80 bg-[var(--sidebar)] border-r border-[var(--card-border)] flex flex-col">
        <div className="px-5 pt-4">
          <button
            onClick={() => router.push("/")}
            className="text-xs text-[var(--muted)] hover:text-[var(--accent)] flex items-center gap-1"
          >
            ← All Patients
          </button>
        </div>

        {/* Patient Info */}
        {patient && (
          <div className="px-5 py-4 border-b border-[var(--card-border)]">
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
            <div className="space-y-3">
              <div>
                <p className="text-[11px] font-semibold text-[var(--muted)] uppercase tracking-wider mb-1.5">Medical History</p>
                {patient.known_conditions.length > 0 ? (
                  <div className="flex flex-wrap gap-1.5">
                    {patient.known_conditions.map((c) => (
                      <span key={c} className="text-[11px] px-2 py-1 rounded-md bg-[var(--accent)]/8 text-[var(--accent)] border border-[var(--accent)]/15">{c}</span>
                    ))}
                  </div>
                ) : (
                  <p className="text-[11px] text-[var(--muted)] italic">No known conditions</p>
                )}
              </div>
              <div>
                <p className="text-[11px] font-semibold text-[var(--muted)] uppercase tracking-wider mb-1.5">Allergies</p>
                {patient.allergies.length > 0 ? (
                  <div className="flex flex-wrap gap-1.5">
                    {patient.allergies.map((a) => (
                      <span key={a} className="text-[11px] px-2 py-1 rounded-md bg-[var(--danger)]/8 text-[var(--danger)] border border-[var(--danger)]/15">⚠ {a}</span>
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
          <p className="text-[11px] font-semibold text-[var(--muted)] uppercase tracking-wider px-2 mb-2">Consultations</p>
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
              <span className="block text-[11px] text-[var(--muted)] mt-0.5">
                {c.status === "completed" ? "✓ Completed" : "Active"}
              </span>
            </button>
          ))}
        </div>

        {/* Sidebar Footer */}
        <div className="p-4 border-t border-[var(--card-border)] space-y-2">
          {messages.length > 0 && !isCompleted && (
            <button
              onClick={completeAndExportSOAP}
              disabled={completingConv}
              className="w-full px-3 py-2.5 rounded-lg text-sm font-medium bg-green-600 hover:bg-green-700 text-white disabled:opacity-50 transition-colors"
            >
              {completingConv ? "Generating SOAP..." : "📋 Complete & Export SOAP"}
            </button>
          )}
          {isCompleted && (
            <button
              onClick={() => setShowSoap(true)}
              className="w-full px-3 py-2.5 rounded-lg text-sm font-medium bg-[var(--card)] border border-[var(--card-border)] hover:border-[var(--accent)] transition-colors"
            >
              📋 View SOAP Note
            </button>
          )}
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
                <p className="text-[var(--muted)] text-base">Describe the patient&apos;s symptoms to begin</p>
                <p className="text-[var(--muted)] text-xs mt-2 opacity-60">Include details like duration, severity, and location</p>
                <p className="text-[var(--muted)] text-xs mt-1 opacity-60">🌐 Supports Hindi, Bengali, Tamil, and other languages</p>
              </div>
            </div>
          )}
          {messages.map((msg) => (
            <div key={msg.id} className={`flex ${msg.role === "patient" ? "justify-end" : "justify-start"}`}>
              <div
                className={`max-w-[70%] rounded-2xl px-5 py-4 ${
                  msg.role === "patient"
                    ? "bg-[var(--accent)] text-white"
                    : msg.role === "system"
                    ? "bg-[var(--card)] border border-dashed border-[var(--card-border)] opacity-70"
                    : "bg-[var(--card)] border border-[var(--card-border)] shadow-sm"
                }`}
              >
                {msg.role === "patient" && msg.metadata && typeof msg.metadata.detected_language === "string" && msg.metadata.detected_language !== "English" && (
                  <div className="text-[10px] opacity-75 mb-1 flex items-center gap-1">
                    <span>🌐</span>
                    <span>Translated from {String(msg.metadata.detected_language)}</span>
                  </div>
                )}
                <p className="text-[15px] whitespace-pre-wrap leading-7">{msg.content}</p>
                {msg.role === "assistant" && msg.metadata && (
                  <MetadataPanel metadata={msg.metadata} />
                )}
              </div>
            </div>
          ))}


          {/* Streaming/Processing indicator */}
          {sending && (
            <div className="flex justify-start">
              <div className="bg-[var(--card)] border border-[var(--card-border)] rounded-2xl px-5 py-4 shadow-sm">
                <div className="flex items-center gap-3">
                  <div className="flex gap-1.5">
                    <span className="w-2.5 h-2.5 bg-[var(--accent)] rounded-full animate-bounce" style={{ animationDelay: "0ms" }} />
                    <span className="w-2.5 h-2.5 bg-[var(--accent)] rounded-full animate-bounce" style={{ animationDelay: "150ms" }} />
                    <span className="w-2.5 h-2.5 bg-[var(--accent)] rounded-full animate-bounce" style={{ animationDelay: "300ms" }} />
                  </div>
                  {streamStage && (
                    <span className="text-xs text-[var(--muted)] animate-pulse">
                      {streamStage === "processing" && "Analyzing symptoms..."}
                      {streamStage === "ner" && "Extracting clinical entities..."}
                      {streamStage === "translation" && "Translating input..."}
                      {streamStage === "diagnosis" && "Generating differential diagnosis..."}
                      {streamStage === "compliance" && "Running safety checks..."}
                    </span>
                  )}
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
              placeholder={isCompleted ? "Conversation completed — start a new consultation" : "Describe symptoms or answer questions..."}
              className="flex-1 bg-[var(--input-bg)] border border-[var(--input-border)] rounded-xl px-5 py-3.5 text-[15px] focus:outline-none focus:ring-2 focus:ring-[var(--accent)] focus:border-transparent placeholder:text-[var(--muted)] disabled:opacity-50"
              disabled={sending || isCompleted}
            />
            <button
              onClick={send}
              disabled={sending || !input.trim() || isCompleted}
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

      {/* SOAP Note Modal */}
      {showSoap && <SOAPModal note={soapNote} onClose={() => setShowSoap(false)} />}
    </div>
  );
}


function MetadataPanel({ metadata }: { metadata: Record<string, unknown> }) {
  const diagnoses = (metadata.diagnoses as Array<{ condition: string; confidence: number; reasoning: string }>) || [];
  const treatments = (metadata.treatments as string[]) || [];
  const redFlags = (metadata.red_flags as string[]) || [];
  const tests = (metadata.suggested_tests as string[]) || [];
  const drugInteractions = (metadata.drug_interactions as DrugInteraction[]) || [];
  const interactionWarnings = (metadata.interaction_warnings as string[]) || [];
  const urgencyScore = metadata.urgency_score as number | undefined;
  const urgencyRationale = metadata.urgency_rationale as string | undefined;

  if (!diagnoses.length && !treatments.length && !redFlags.length && !tests.length && !drugInteractions.length) return null;

  return (
    <div className="mt-4 pt-4 border-t border-[var(--card-border)] space-y-4 text-sm">
      {/* Urgency Score */}
      {urgencyScore && urgencyScore >= 4 && (
        <div className="bg-red-500/10 text-red-600 px-4 py-2.5 rounded-lg font-medium flex items-center gap-2">
          <span className="text-lg">🚨</span>
          <div>
            <p className="font-semibold">Urgency: {urgencyScore}/5</p>
            {urgencyRationale && <p className="text-xs opacity-80 mt-0.5">{urgencyRationale}</p>}
          </div>
        </div>
      )}

      {/* Red Flags */}
      {redFlags.length > 0 && (
        <div className="bg-[var(--danger)]/10 text-[var(--danger)] px-4 py-2.5 rounded-lg font-medium">
          ⚠️ {redFlags.join(" • ")}
        </div>
      )}


      {/* Drug Interactions */}
      {drugInteractions.length > 0 && (
        <div>
          <p className="font-semibold text-[var(--muted)] uppercase tracking-wider text-[11px] mb-2">
            ⚕️ Drug Interactions
          </p>
          <div className="space-y-2">
            {drugInteractions.map((interaction, i) => (
              <div
                key={i}
                className={`px-3 py-2.5 rounded-lg border text-xs ${
                  interaction.severity === "severe"
                    ? "bg-red-500/8 border-red-500/20 text-red-700 dark:text-red-400"
                    : interaction.severity === "moderate"
                    ? "bg-yellow-500/8 border-yellow-500/20 text-yellow-700 dark:text-yellow-400"
                    : "bg-blue-500/8 border-blue-500/20 text-blue-700 dark:text-blue-400"
                }`}
              >
                <div className="flex items-center gap-2 mb-1">
                  <span className={`px-1.5 py-0.5 rounded text-[10px] font-bold uppercase ${
                    interaction.severity === "severe" ? "bg-red-500/20" :
                    interaction.severity === "moderate" ? "bg-yellow-500/20" : "bg-blue-500/20"
                  }`}>
                    {interaction.severity}
                  </span>
                  <span className="font-medium">
                    {interaction.drug_in_treatment} ↔ {interaction.drug_in_patient_meds}
                  </span>
                </div>
                <p className="opacity-80">{interaction.description}</p>
                <p className="mt-1 font-medium opacity-90">💡 {interaction.recommendation}</p>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Interaction Warnings (summary) */}
      {interactionWarnings.length > 0 && !drugInteractions.length && (
        <div className="bg-yellow-500/8 border border-yellow-500/20 rounded-lg px-3 py-2.5">
          <p className="font-semibold text-[11px] text-yellow-700 dark:text-yellow-400 uppercase mb-1">⚠️ Interaction Warnings</p>
          {interactionWarnings.map((w, i) => (
            <p key={i} className="text-xs text-yellow-700 dark:text-yellow-400 opacity-80">{w}</p>
          ))}
        </div>
      )}


      {/* Diagnoses */}
      {diagnoses.length > 0 && (
        <div>
          <p className="font-semibold text-[var(--muted)] uppercase tracking-wider text-[11px] mb-2">Differential Diagnosis</p>
          <div className="space-y-2.5">
            {diagnoses.map((d, i) => (
              <div key={i}>
                <div className="flex items-center justify-between mb-1">
                  <span className="font-medium text-[13px]">{d.condition}</span>
                  <span className="text-[var(--muted)] text-xs">{Math.round(d.confidence * 100)}%</span>
                </div>
                <div className="w-full h-2 bg-[var(--card-border)] rounded-full overflow-hidden">
                  <div className="h-full bg-[var(--accent)] rounded-full transition-all" style={{ width: `${d.confidence * 100}%` }} />
                </div>
                {d.reasoning && <p className="text-[11px] text-[var(--muted)] mt-1 leading-relaxed">{d.reasoning}</p>}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Treatments */}
      {treatments.length > 0 && (
        <div>
          <p className="font-semibold text-[var(--muted)] uppercase tracking-wider text-[11px] mb-2">Treatment Options</p>
          <div className="flex flex-wrap gap-2">
            {treatments.map((t, i) => (
              <span key={i} className="px-2.5 py-1.5 rounded-lg bg-[var(--success)]/10 text-[var(--success)] text-xs font-medium">{t}</span>
            ))}
          </div>
        </div>
      )}

      {/* Tests */}
      {tests.length > 0 && (
        <div>
          <p className="font-semibold text-[var(--muted)] uppercase tracking-wider text-[11px] mb-2">Suggested Tests</p>
          <div className="flex flex-wrap gap-2">
            {tests.map((t, i) => (
              <span key={i} className="px-2.5 py-1.5 rounded-lg bg-[var(--accent)]/10 text-[var(--accent)] text-xs font-medium">{t}</span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}


function SOAPModal({ note, onClose }: { note: SOAPNote | null; onClose: () => void }) {
  const [viewMode, setViewMode] = useState<"structured" | "plain">("structured");
  const [copied, setCopied] = useState(false);

  const copyToClipboard = () => {
    if (!note) return;
    navigator.clipboard.writeText(note.plain_text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  if (!note) {
    return (
      <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4" onClick={onClose}>
        <div className="bg-[var(--card)] rounded-2xl p-8 text-center" onClick={(e) => e.stopPropagation()}>
          <p className="text-[var(--muted)]">No SOAP note available yet.</p>
          <button onClick={onClose} className="mt-4 px-4 py-2 text-sm text-[var(--accent)]">Close</button>
        </div>
      </div>
    );
  }

  const { soap_note: soap } = note;

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4" onClick={onClose}>
      <div
        className="bg-[var(--card)] border border-[var(--card-border)] rounded-2xl w-full max-w-3xl max-h-[85vh] overflow-hidden flex flex-col"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-[var(--card-border)]">
          <div>
            <h2 className="text-lg font-semibold">📋 SOAP Note</h2>
            <p className="text-xs text-[var(--muted)] mt-0.5">Generated {new Date(note.generated_at).toLocaleString()}</p>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={() => setViewMode(viewMode === "structured" ? "plain" : "structured")}
              className="px-3 py-1.5 rounded-lg text-xs font-medium bg-[var(--input-bg)] border border-[var(--input-border)] hover:border-[var(--accent)]"
            >
              {viewMode === "structured" ? "Plain Text" : "Structured"}
            </button>
            <button
              onClick={copyToClipboard}
              className="px-3 py-1.5 rounded-lg text-xs font-medium bg-[var(--accent)] text-white hover:bg-[var(--accent-hover)]"
            >
              {copied ? "✓ Copied!" : "Copy"}
            </button>
            <button onClick={onClose} className="text-[var(--muted)] hover:text-[var(--foreground)] text-lg px-2">✕</button>
          </div>
        </div>


        {/* Content */}
        <div className="flex-1 overflow-y-auto px-6 py-5">
          {viewMode === "plain" ? (
            <pre className="text-sm font-mono whitespace-pre-wrap text-[var(--foreground)] leading-6">{note.plain_text}</pre>
          ) : (
            <div className="space-y-6">
              {/* Subjective */}
              <section>
                <h3 className="text-sm font-bold text-[var(--accent)] uppercase tracking-wider mb-3">Subjective</h3>
                <div className="space-y-2 text-sm">
                  <SOAPField label="Chief Complaint" value={soap.subjective.chief_complaint} />
                  <SOAPField label="HPI" value={soap.subjective.history_of_present_illness} />
                  <SOAPField label="Review of Systems" value={soap.subjective.review_of_systems} />
                  <SOAPField label="Past Medical History" value={soap.subjective.past_medical_history} />
                  <SOAPField label="Allergies" value={soap.subjective.allergies} />
                  <SOAPField label="Medications" value={soap.subjective.medications} />
                </div>
              </section>

              {/* Objective */}
              <section>
                <h3 className="text-sm font-bold text-[var(--accent)] uppercase tracking-wider mb-3">Objective</h3>
                <div className="space-y-2 text-sm">
                  <SOAPField label="Vitals" value={soap.objective.vitals} />
                  <SOAPField label="Physical Exam" value={soap.objective.physical_exam} />
                  <SOAPField label="Labs/Imaging" value={soap.objective.labs_imaging} />
                </div>
              </section>

              {/* Assessment */}
              <section>
                <h3 className="text-sm font-bold text-[var(--accent)] uppercase tracking-wider mb-3">Assessment</h3>
                <div className="space-y-2 text-sm">
                  <SOAPField label="Primary Diagnosis" value={soap.assessment.primary_diagnosis} highlight />
                  {soap.assessment.differential_diagnoses.length > 0 && (
                    <SOAPField label="Differentials" value={soap.assessment.differential_diagnoses.join(", ")} />
                  )}
                  <SOAPField label="Severity" value={soap.assessment.severity} />
                  <SOAPField label="Clinical Reasoning" value={soap.assessment.clinical_reasoning} />
                </div>
              </section>

              {/* Plan */}
              <section>
                <h3 className="text-sm font-bold text-[var(--accent)] uppercase tracking-wider mb-3">Plan</h3>
                <div className="space-y-2 text-sm">
                  {soap.plan.diagnostic_workup.length > 0 && (
                    <SOAPField label="Workup" value={soap.plan.diagnostic_workup.join(", ")} />
                  )}
                  {soap.plan.treatment.length > 0 && (
                    <SOAPField label="Treatment" value={soap.plan.treatment.join(", ")} />
                  )}
                  <SOAPField label="Patient Education" value={soap.plan.patient_education} />
                  <SOAPField label="Follow-up" value={soap.plan.follow_up} />
                  <SOAPField label="Referrals" value={soap.plan.referrals} />
                  <SOAPField label="Red Flags Discussed" value={soap.plan.red_flags_discussed} />
                </div>
              </section>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="px-6 py-3 border-t border-[var(--card-border)] text-center">
          <p className="text-[11px] text-[var(--muted)]">AI-generated — must be reviewed and co-signed by a licensed healthcare professional</p>
        </div>
      </div>
    </div>
  );
}


function SOAPField({ label, value, highlight }: { label: string; value: string; highlight?: boolean }) {
  if (!value) return null;
  return (
    <div className="flex gap-3">
      <span className="text-[var(--muted)] font-medium min-w-[120px] text-xs uppercase tracking-wider pt-0.5">{label}:</span>
      <span className={highlight ? "font-semibold text-[var(--foreground)]" : "text-[var(--foreground)]"}>{value}</span>
    </div>
  );
}
