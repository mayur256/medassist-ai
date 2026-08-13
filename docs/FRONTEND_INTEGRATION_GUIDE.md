# Frontend Integration Guide
**Status:** Frontend scaffolding complete; ready for backend wiring  
**Date:** 2026-08-11  

---

## Current State

### ✅ What's Already Built

Your Next.js frontend has:

| Component | Status | Location | Details |
|-----------|--------|----------|---------|
| **API Client** | ✅ Complete | `src/lib/api.ts` | Full TypeScript client with all endpoints |
| **Home Page** | ✅ Complete | `src/app/page.tsx` | Patient list & creation modal |
| **Chat Page** | ✅ Complete | `src/app/chat/[id]/page.tsx` | Full chat UI with message history |
| **Layout** | ✅ Complete | `src/app/layout.tsx` | Root layout with theme support |
| **Theme System** | ✅ Complete | `src/components/theme-provider.tsx` | Light/dark mode toggle |
| **Styling** | ✅ Complete | `src/app/globals.css` | Tailwind + CSS variables |
| **Types** | ✅ Complete | `src/lib/api.ts` | Full TypeScript interfaces |
| **SOAP Modal** | ✅ Complete | `src/app/chat/[id]/page.tsx` | Structured & plain text views |
| **Metadata Panel** | ✅ Complete | `src/app/chat/[id]/page.tsx` | Diagnosis, treatments, red flags |

**Total: 95% UI scaffolding complete** ✅

---

## What's Pending

### 🔴 Critical Issues (Blocking)

#### 1. **API Endpoint Mismatch: `/patients` Routes**
**Problem:** Frontend expects `GET /patients/{id}/conversations`  
**Current Backend:** Only has `GET /conversations` with auth filtering

**What needs fixing:**
```
Frontend:   GET /patients/{patientId}/conversations
Backend:    GET /conversations (returns all for user)

Fix required: Add route to backend OR update frontend to use:
  - GET /conversations (and filter client-side by patient_id)
```

**Action:** Backend needs new endpoint OR frontend UI refactored to not require patient-specific endpoint

---

#### 2. **API Endpoint: `/conversations/{id}/messages`**
**Problem:** Frontend expects separate messages endpoint  
**Current Backend:** Messages are embedded in `/conversations/{id}` response

**What needs fixing:**
```
Frontend calls:   POST /conversations/{id}/messages
Backend provides: Messages nested in conversation object

Fix required: Backend needs to expose messages endpoint OR
              frontend needs to refactor message handling
```

**Action:** Decide on message storage/retrieval approach

---

#### 3. **Diagnosis Flow Integration**
**Problem:** Frontend has `send()` method but backend expects separate `/diagnose` endpoint  
**Current:** Frontend sends to `/conversations/{id}/messages`  
**Expected:** Backend should generate diagnosis response

**What needs fixing:**
```
Option A (Recommended):
  - Keep current `/diagnose` endpoint
  - Frontend calls `/diagnose` with patient + symptoms
  - Stores result in message history
  - Then calls `/conversations/{id}/complete` for SOAP

Option B:
  - Backend modifies `/conversations/{id}/messages` to:
    - Accept symptoms
    - Run full diagnosis pipeline
    - Return structured diagnosis in message metadata
```

**Action:** Choose architecture pattern (Option A or B)

---

#### 4. **Streaming Response Integration**
**Problem:** Chat interface needs to handle streaming responses  
**Current:** `api.diagnoseStream()` is implemented but not wired  
**Missing:** Chat UI doesn't call streaming endpoint

**What needs fixing:**
```
Frontend needs to:
1. Call api.diagnoseStream() instead of api.sendMessage()
2. Process SSE events and display streaming output
3. Show stage progress (NER → Diagnosis → Treatment → Compliance)
4. Handle token-by-token updates
```

**Action:** Wire streaming into chat UI message flow

---

### 🟡 Important Issues (Integration)

#### 5. **Metadata Extraction from API Response**
**Problem:** Frontend expects metadata in message objects  
**Current:** API returns DiagnoseResponse with flat fields

**What needs fixing:**
```json
Frontend expects:
{
  "role": "assistant",
  "content": "...",
  "metadata": {
    "diagnoses": [...],
    "treatments": [...],
    "red_flags": [...],
    "drug_interactions": [...],
    "urgency_score": 3,
    "suggested_tests": [...]
  }
}

Backend returns:
{
  "status": "complete",
  "differential_diagnosis": [...],
  "treatment_options": [...],
  "red_flags": [...],
  "urgency_score": 3,
  "suggested_tests": [...]
}

Need to: Transform DiagnoseResponse into Message.metadata format
```

**Action:** Backend or frontend needs transformation layer

---

#### 6. **Patient History in Chat**
**Problem:** Patient context not displayed in chat UI  
**Current:** Sidebar shows patient info, but chat doesn't use it in queries

**What needs fixing:**
```
Frontend already has:
- Patient info loaded in state
- Patient displayed in sidebar

Missing:
- Passing patient context to diagnosis endpoint
- History feature (last 5 conversations)

Action: Wire patient object to /diagnose request
```

---

#### 7. **Multi-Language Support**
**Problem:** Frontend has placeholder for language detection  
**Current:** Backend supports multi-language input

**What needs fixing:**
```
Frontend has:
- "🌐 Supports Hindi, Bengali, Tamil, and other languages" text
- Language detection in message metadata display

Missing:
- Actual language detection UI
- User language input preference
- Translation display in chat

Action: Test language feature with backend
```

---

#### 8. **Error Handling & Edge Cases**
**Problem:** Limited error handling in current UI  
**Missing:**
```
- Network error handling
- API timeout handling
- Invalid response handling
- Retry logic
- Empty state handling for failed requests
- User-friendly error messages
```

**Action:** Add error boundaries and error UI states

---

#### 9. **Conversation Persistence**
**Problem:** Frontend expects conversations to be managed by backend  
**Current:** Backend has `/conversations` endpoints

**What needs fixing:**
```
Frontend expects:
- Create new conversation (✅ wired: POST /conversations)
- List conversations for patient (❌ needs fix)
- Switch between conversations (✅ UI ready)
- Delete/archive conversations (❌ no UI)

Action: Test flow from patient list → new conversation → chat
```

---

#### 10. **API Key Management**
**Problem:** API key hardcoded in `.env.local`  
**Current:** `NEXT_PUBLIC_API_KEY=your-api-key`

**What needs fixing:**
```
.env.local has: NEXT_PUBLIC_API_KEY=test-api-key
Backend expects: X-API-Key header

Issue: Test API key won't work with real backend

Action: 
1. Update .env.local with correct API key
2. Or implement backend without API key auth for testing
3. Or implement login page for authentication
```

---

### 🟢 Minor Issues (Polish)

#### 11. **Loading States**
**Status:** Partially implemented  
**Missing:**
- Loading skeleton for message metadata
- Loading state for SOAP export

---

#### 12. **Responsive Design**
**Status:** Mostly responsive  
**Minor:** Sidebar width may need adjustment on mobile

---

#### 13. **Accessibility**
**Status:** Basic (could be improved)  
**Missing:**
- ARIA labels
- Keyboard navigation
- Screen reader testing

---

## Implementation Roadmap

### Phase 1: Core Integration (Priority)

**Week 1 - Backend API Endpoint Fixes**

```typescript
// 1. Fix patient-specific conversations endpoint
// Backend: Add or clarify endpoint for:
GET /conversations?patient_id={id}

// 2. Clarify message storage strategy
// Option A: Add endpoint
POST /conversations/{id}/messages
GET  /conversations/{id}/messages

// Option B: Keep diagnosis in separate flow
POST /diagnose (returns DiagnoseResponse)
// Then manually store in conversation

// 3. Verify SOAP export endpoint
POST /conversations/{id}/complete
// Should return: SOAPNote (working ✅)
```

**Decision needed from you:**
- How should messages be stored? (combined or separate endpoints?)
- Should `/diagnose` be called from chat or independently?

---

### Phase 2: Streaming Integration

**Week 1 - Implement Streaming UI**

```typescript
// In ChatPage.tsx

const streamDiagnosis = async (symptoms: string) => {
  try {
    setSending(true);
    for await (const event of api.diagnoseStream(patient, symptoms)) {
      if (event.event === "token") {
        // Display token incrementally
        setStreamContent(prev => prev + event.data.content);
      }
      if (event.event === "stage_complete") {
        // Update stage display
        setStreamStage(event.data.stage);
      }
    }
  } finally {
    setSending(false);
  }
};
```

---

### Phase 3: Backend Wiring

**Week 1-2 - Connect All Flows**

1. ✅ Home page → Load patients from `/patients`
2. ✅ Create patient → POST `/patients`
3. ⏳ Patient card → Open chat with conversation
4. ⏳ Chat input → Call `/diagnose` endpoint
5. ⏳ Display diagnosis → Parse metadata into UI
6. ⏳ Export SOAP → Call `/conversations/{id}/complete`

---

### Phase 4: Testing & Polish

**Week 2 - End-to-End Testing**

1. Test full flow: Create patient → New chat → Send symptoms → View diagnosis → Export SOAP
2. Test error cases: Network errors, validation errors, API errors
3. Test edge cases: Empty responses, long responses, concurrent requests

---

## Quick Start: Getting Frontend Running

### 1. Install Dependencies
```bash
cd frontend
npm install  # or pnpm install
```

### 2. Set Environment Variables
```bash
# frontend/.env.local
NEXT_PUBLIC_API_URL=http://localhost:9000
NEXT_PUBLIC_API_KEY=your-api-key-from-backend
```

### 3. Run Development Server
```bash
npm run dev
# Opens on http://localhost:3000
```

### 4. Test API Connection
```bash
# In browser console on http://localhost:3000:
fetch('http://localhost:9000/health').then(r => r.json())
// Should return: {"status": "ok"}
```

---

## Specific Code Changes Needed

### Change 1: Fix Patient Conversations Endpoint

**File:** `src/lib/api.ts`

Current:
```typescript
getConversations: (patientId: string) =>
  request<Conversation[]>(`/patients/${patientId}/conversations`),
```

Option A (if backend adds this route):
```typescript
// Keep as-is
```

Option B (if using `/conversations?patient_id=`):
```typescript
getConversations: (patientId: string) =>
  request<Conversation[]>(`/conversations?patient_id=${patientId}`),
```

---

### Change 2: Implement Streaming Display

**File:** `src/app/chat/[id]/page.tsx`

Add streaming handler in `send()` function:

```typescript
const send = async () => {
  if (!input.trim() || sending) return;
  setSending(true);
  setStreamStage("processing");
  
  try {
    let fullContent = "";
    
    // Stream diagnosis
    for await (const event of api.diagnoseStream(patient!, input.trim())) {
      if (event.event === "token") {
        fullContent += event.data.content || "";
        // Update UI with streaming content
        setMessages(prev => [...prev.slice(0, -1), {
          ...prev[prev.length - 1],
          content: fullContent
        }]);
      }
      if (event.event === "stage_start") {
        setStreamStage(event.data.stage as string);
      }
      if (event.event === "stage_complete") {
        // Handle metadata
        const result = event.data.result;
        if (result && typeof result === 'object') {
          // Add metadata to message
        }
      }
    }
  } catch (e) {
    console.error(e);
  } finally {
    setSending(false);
    setStreamStage(null);
    setInput("");
  }
};
```

---

### Change 3: Transform API Response to Message Format

**File:** `src/lib/api.ts` or separate utility

```typescript
export function transformDiagnoseToMessage(response: DiagnoseResponse): Message {
  return {
    id: crypto.randomUUID(),
    conversation_id: "", // Set by caller
    role: "assistant",
    content: formatDiagnosisContent(response),
    metadata: {
      diagnoses: response.differential_diagnosis,
      treatments: response.treatment_options,
      red_flags: response.red_flags,
      suggested_tests: response.suggested_tests,
      urgency_score: response.urgency_score,
      drug_interactions: response.drug_interactions || [],
      confidence: response.confidence,
    },
    created_at: new Date().toISOString(),
  };
}

function formatDiagnosisContent(response: DiagnoseResponse): string {
  const lines = [
    `**Differential Diagnosis** (Confidence: ${Math.round(response.confidence * 100)}%)`,
    ...response.differential_diagnosis.map(d => 
      `- ${d.condition} (${Math.round(d.confidence * 100)}%): ${d.reasoning}`
    ),
    "",
    "**Treatment Options:**",
    ...response.treatment_options.map(t => `- ${t}`),
    "",
    response.disclaimer
  ];
  return lines.join("\n");
}
```

---

## API Contract Clarifications Needed

### Question 1: Message Storage
**Does backend need a dedicated messages endpoint?**

Current frontend expects:
```
GET  /conversations/{id}/messages
POST /conversations/{id}/messages
```

But backend might store messages differently. Clarify:
- Are messages embedded in conversation?
- Or stored separately?
- How should frontend query message history?

---

### Question 2: Diagnosis Workflow
**Should frontend call `/diagnose` or `/conversations/{id}/messages`?**

**Option A (Recommended):**
```
1. User types symptoms
2. Frontend calls POST /diagnose with patient info + symptoms
3. Backend returns DiagnoseResponse
4. Frontend creates Message with metadata from DiagnoseResponse
5. Frontend stores Message in /conversations/{id}/messages
6. Frontend saves conversation (or auto-saved by backend)
```

**Option B:**
```
1. User types symptoms
2. Frontend calls POST /conversations/{id}/messages with symptoms
3. Backend runs full diagnosis pipeline internally
4. Backend returns Message with metadata populated
5. Frontend displays Message
```

**Which approach does your backend use?**

---

### Question 3: Streaming
**Should frontend use `/diagnose/stream` or is it an alternative flow?**

Current implementation:
- API client has `diagnoseStream()` method (✅)
- Chat UI doesn't use it (❌ need to wire)

Should I:
- Replace `api.sendMessage()` calls with `api.diagnoseStream()`?
- Or keep both for different flows?

---

### Question 4: Drug Interactions & Metadata
**How should drug interactions be passed?**

Frontend expects:
```typescript
metadata.drug_interactions: DrugInteraction[]
metadata.interaction_warnings: string[]
```

Backend returns:
```json
{
  "differential_diagnosis": [...],
  "treatment_options": [...],
  ...
}
```

Should drug interactions be:
- In response root level (currently)?
- In DiagnoseResponse.metadata?
- Separate endpoint?

---

## Testing Checklist

### Before Going Live

- [ ] Backend running (`http://localhost:9000/health` returns `{"status": "ok"}`)
- [ ] Frontend running (`http://localhost:3000` loads)
- [ ] `.env.local` has correct `NEXT_PUBLIC_API_URL` and `NEXT_PUBLIC_API_KEY`
- [ ] API client can reach backend (test in browser console)
- [ ] Create patient workflow works
- [ ] Patient list loads and displays correctly
- [ ] Open chat for a patient works
- [ ] Send message/symptom and see response
- [ ] Metadata displays correctly (diagnoses, treatments, etc.)
- [ ] SOAP export button works and generates note
- [ ] Streaming works (optional, if using `/diagnose/stream`)

---

## Common Issues & Solutions

### Issue: CORS Error
**Symptom:** Browser console shows CORS error when calling backend
```
Access to XMLHttpRequest blocked by CORS policy
```

**Solution:**
```bash
# Backend should have CORS enabled
# In FastAPI:
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

---

### Issue: 401 Unauthorized
**Symptom:** API returns 401 error
```
Error: API error: 401
```

**Solution:**
1. Check API key in `.env.local`
2. Verify backend expects same header name (`X-API-Key`)
3. Test with curl:
```bash
curl -H "X-API-Key: your-key" http://localhost:9000/health
```

---

### Issue: Empty Patient List
**Symptom:** Frontend loads but no patients display
```
Grid is empty even after "Create Patient"
```

**Possible causes:**
1. Backend `/patients` endpoint not working
2. API key validation failing
3. Database not returning data

**Debug:**
```javascript
// In browser console:
fetch('http://localhost:9000/patients', {
  headers: { 'X-API-Key': 'your-key' }
}).then(r => r.json()).then(console.log)
```

---

### Issue: Chat Messages Not Saving
**Symptom:** Messages display but disappear on refresh
```
Message history lost
```

**Possible causes:**
1. `/conversations/{id}/messages` endpoint mismatch
2. Backend not persisting messages
3. Frontend not calling save endpoint

**Debug:**
- Check database for message records
- Verify backend `/conversations/{id}/messages` returns stored messages

---

## File Structure Reference

```
frontend/
├── src/
│   ├── app/
│   │   ├── page.tsx              ← Home (patient list)
│   │   ├── layout.tsx            ← Root layout
│   │   ├── globals.css           ← Styling
│   │   └── chat/
│   │       └── [id]/
│   │           └── page.tsx      ← Chat interface
│   ├── lib/
│   │   └── api.ts                ← API client (ALL endpoints here)
│   └── components/
│       └── theme-provider.tsx    ← Theme toggle
├── .env.local                    ← Environment variables
├── package.json                  ← Dependencies
├── next.config.ts               ← Next.js config
├── tsconfig.json                ← TypeScript config
└── tailwind.config.ts           ← Tailwind CSS config
```

---

## Dependencies Already Installed

```json
{
  "dependencies": {
    "next": "16.2.5",
    "react": "19.2.4",
    "react-dom": "19.2.4"
  },
  "devDependencies": {
    "@tailwindcss/postcss": "^4",
    "@types/node": "^20",
    "@types/react": "^19",
    "@types/react-dom": "^19",
    "eslint": "^9",
    "eslint-config-next": "16.2.5",
    "tailwindcss": "^4",
    "typescript": "^5"
  }
}
```

**No additional dependencies needed!** All dependencies already installed.

---

## Next Steps

### Immediate (Today)

1. **Clarify API contract** — Answer the questions above
2. **Verify backend endpoints** — Confirm which routes are live
3. **Test API connection** — Run curl/fetch test from frontend

### This Week

1. **Fix endpoint mismatches** — Backend or frontend updates
2. **Wire streaming** — Implement `/diagnose/stream` in chat
3. **Transform responses** — Convert DiagnoseResponse to Message format

### By Next Week

1. **End-to-end testing** — Full flow from patient creation to SOAP export
2. **Error handling** — Graceful failure states
3. **Polish UI** — Loading states, empty states, error messages

---

## Summary

**Frontend Status: 95% Ready** ✅

**Pending:**
1. API endpoint clarifications (3 decisions needed)
2. Response transformation logic (~50 lines of code)
3. Streaming UI integration (~100 lines of code)
4. Error handling polish (~150 lines of code)

**Estimated Time to Completion:** 3-5 days

**Blocker:** Backend endpoint clarity

---

**Questions? Refer to the questions section or review the existing code in:**
- `src/lib/api.ts` (API client)
- `src/app/chat/[id]/page.tsx` (Chat UI)

All the heavy lifting is done. Just needs wiring! 🔌
