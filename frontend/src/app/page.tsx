"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api, Patient } from "@/lib/api";
import { ThemeToggle } from "@/components/theme-provider";

export default function Home() {
  const [patients, setPatients] = useState<Patient[]>([]);
  const [loading, setLoading] = useState(true);
  const [showModal, setShowModal] = useState(false);
  const router = useRouter();

  const load = () => {
    api.getPatients().then(setPatients).finally(() => setLoading(false));
  };

  useEffect(load, []);

  const openChat = async (patientId: string) => {
    const convs = await api.getConversations(patientId);
    const active = convs.find((c) => c.status === "active");
    const convId = active ? active.id : (await api.createConversation(patientId)).id;
    router.push(`/chat/${convId}?patient=${patientId}`);
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-screen">
        <div className="animate-spin w-8 h-8 border-2 border-[var(--accent)] border-t-transparent rounded-full" />
      </div>
    );
  }

  return (
    <main className="min-h-screen p-6 md:p-10">
      <div className="max-w-5xl mx-auto">
        {/* Header */}
        <div className="flex items-center justify-between mb-8">
          <div>
            <h1 className="text-2xl font-bold">🧠 MedAssist CDSS</h1>
            <p className="text-sm text-[var(--muted)] mt-1">Clinical Decision Support System</p>
          </div>
          <div className="flex items-center gap-3">
            <ThemeToggle />
            <button
              onClick={() => setShowModal(true)}
              className="bg-[var(--accent)] hover:bg-[var(--accent-hover)] text-white px-4 py-2 rounded-lg text-sm font-medium"
            >
              + New Patient
            </button>
          </div>
        </div>

        {/* Patient Grid */}
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {patients.map((p) => (
            <button
              key={p.id}
              onClick={() => openChat(p.id)}
              className="bg-[var(--card)] border border-[var(--card-border)] rounded-xl p-5 text-left hover:border-[var(--accent)] transition-colors group"
            >
              <div className="flex items-start justify-between">
                <div className="w-10 h-10 rounded-full bg-[var(--accent)]/10 flex items-center justify-center text-[var(--accent)] font-semibold text-sm">
                  {p.name.split(" ").map((n) => n[0]).join("")}
                </div>
                <span className="text-xs text-[var(--muted)] group-hover:text-[var(--accent)]">Chat →</span>
              </div>
              <h2 className="font-semibold mt-3">{p.name}</h2>
              <p className="text-xs text-[var(--muted)] mt-1">
                {p.age}y • {p.gender} • {p.country}
              </p>
              {p.known_conditions.length > 0 && (
                <div className="flex flex-wrap gap-1 mt-3">
                  {p.known_conditions.map((c) => (
                    <span key={c} className="text-[10px] px-2 py-0.5 rounded-full bg-[var(--accent)]/10 text-[var(--accent)]">
                      {c}
                    </span>
                  ))}
                </div>
              )}
              {p.allergies.length > 0 && (
                <div className="flex flex-wrap gap-1 mt-2">
                  {p.allergies.map((a) => (
                    <span key={a} className="text-[10px] px-2 py-0.5 rounded-full bg-[var(--danger)]/10 text-[var(--danger)]">
                      ⚠ {a}
                    </span>
                  ))}
                </div>
              )}
            </button>
          ))}
        </div>
      </div>

      {showModal && <CreatePatientModal onClose={() => setShowModal(false)} onCreated={() => { setShowModal(false); load(); }} />}
    </main>
  );
}

function CreatePatientModal({ onClose, onCreated }: { onClose: () => void; onCreated: () => void }) {
  const [form, setForm] = useState({ name: "", age: "", gender: "male", country: "India", known_conditions: "", allergies: "" });
  const [saving, setSaving] = useState(false);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    try {
      await api.createPatient({
        name: form.name,
        age: parseInt(form.age),
        gender: form.gender,
        country: form.country,
        known_conditions: form.known_conditions ? form.known_conditions.split(",").map((s) => s.trim()) : [],
        allergies: form.allergies ? form.allergies.split(",").map((s) => s.trim()) : [],
      });
      onCreated();
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4" onClick={onClose}>
      <form
        onClick={(e) => e.stopPropagation()}
        onSubmit={submit}
        className="bg-[var(--card)] border border-[var(--card-border)] rounded-2xl p-6 w-full max-w-md space-y-4"
      >
        <h2 className="text-lg font-semibold">New Patient</h2>
        <input name="name" placeholder="Full Name" required value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} className="w-full px-3 py-2 rounded-lg bg-[var(--input-bg)] border border-[var(--input-border)] text-sm" />
        <div className="grid grid-cols-3 gap-3">
          <input name="age" type="number" placeholder="Age" required value={form.age} onChange={(e) => setForm({ ...form, age: e.target.value })} className="px-3 py-2 rounded-lg bg-[var(--input-bg)] border border-[var(--input-border)] text-sm" />
          <select value={form.gender} onChange={(e) => setForm({ ...form, gender: e.target.value })} className="px-3 py-2 rounded-lg bg-[var(--input-bg)] border border-[var(--input-border)] text-sm">
            <option value="male">Male</option>
            <option value="female">Female</option>
            <option value="other">Other</option>
          </select>
          <select value={form.country} onChange={(e) => setForm({ ...form, country: e.target.value })} className="px-3 py-2 rounded-lg bg-[var(--input-bg)] border border-[var(--input-border)] text-sm">
            <option value="India">India</option>
            <option value="US">US</option>
            <option value="UK">UK</option>
          </select>
        </div>
        <input placeholder="Known conditions (comma-separated)" value={form.known_conditions} onChange={(e) => setForm({ ...form, known_conditions: e.target.value })} className="w-full px-3 py-2 rounded-lg bg-[var(--input-bg)] border border-[var(--input-border)] text-sm" />
        <input placeholder="Allergies (comma-separated)" value={form.allergies} onChange={(e) => setForm({ ...form, allergies: e.target.value })} className="w-full px-3 py-2 rounded-lg bg-[var(--input-bg)] border border-[var(--input-border)] text-sm" />
        <div className="flex justify-end gap-3 pt-2">
          <button type="button" onClick={onClose} className="px-4 py-2 text-sm text-[var(--muted)] hover:text-[var(--foreground)]">Cancel</button>
          <button type="submit" disabled={saving} className="bg-[var(--accent)] hover:bg-[var(--accent-hover)] text-white px-4 py-2 rounded-lg text-sm font-medium disabled:opacity-50">
            {saving ? "Saving..." : "Create"}
          </button>
        </div>
      </form>
    </div>
  );
}
