# Documentation Structure — Clear Labels & Navigation

**Updated:** 2026-08-03  
**Decision:** Keep both plan and status documents with clear labels for different use cases

---

## 📖 Documentation Hierarchy

```
README.md (ENTRY POINT)
├── 📚 Documentation Guide (new section at top)
│   ├── 👉 CURRENT_STATUS.md [ACTIVE]
│   ├── 📋 IMPLEMENTATION_PLAN.md [HISTORICAL]
│   ├── 📊 FR_AUDIT.md
│   ├── 🚀 ENHANCEMENT_PROPOSAL.md
│   └── 🔌 SAMPLE_REQUESTS.md
│
└── SRS (Software Requirements Specification)
    └── ... rest of README
```

---

## Document Purposes & Use Cases

### [ACTIVE] CURRENT_STATUS.md
**Purpose:** Authoritative reference for production system state  
**Updated:** Regularly (quarterly or after major changes)  
**Readers:** New developers, operations, stakeholders  
**Questions It Answers:**
- "What is the system right now?"
- "What endpoints exist?"
- "What's been implemented?"
- "What's the architecture?"
- "What are the known limitations?"

**Content:**
- Architecture overview
- 7/12 completed enhancements (with implementation details)
- API endpoints with examples
- Data models
- Test coverage
- Performance metrics
- Next steps

### [HISTORICAL] IMPLEMENTATION_PLAN.md
**Purpose:** Shows what was originally planned vs. what was actually built  
**Updated:** Only at project milestones (for comparison)  
**Readers:** Project managers, retrospectives, team retrospectives  
**Questions It Answers:**
- "What was the original plan?"
- "What divergences occurred?"
- "Were we accurate in our estimates?"
- "What scope creep happened?"

**Content:**
- Original planned structure (preserved)
- Sections highlighting what actually happened
- Divergences from plan
- Enhancements implemented early

### Other Documents
| Document | Purpose | Updates |
|----------|---------|---------|
| **FR_AUDIT.md** | Maps 22 FRs to implementation | When FRs change or new features added |
| **ENHANCEMENT_PROPOSAL.md** | Tracks 12 proposed enhancements | As enhancements complete |
| **SAMPLE_REQUESTS.md** | API request/response examples | When API changes |
| **PRD.md** | Product requirements | Rarely—foundational document |

---

## Navigation Flow

### For First-Time Users
1. Read README.md **📚 Documentation Guide** section (new)
2. Go to **CURRENT_STATUS.md** 
3. If curious about history → IMPLEMENTATION_PLAN.md

### For Developers Implementing Features
1. Check **CURRENT_STATUS.md** — "What exists now?"
2. Check **ENHANCEMENT_PROPOSAL.md** — "What's next?"
3. Check **SAMPLE_REQUESTS.md** — "How does the API work?"

### For Project Retrospectives
1. Compare **IMPLEMENTATION_PLAN.md** vs **CURRENT_STATUS.md**
2. Review **FR_AUDIT.md** for any requirement changes
3. Analyze **ENHANCEMENT_PROPOSAL.md** timeline

---

## Clear Labeling System

### Document Headers
Each document now has a clear status label:

```markdown
# [ACTIVE] MedAssist-CDSS — Current Implementation Status
# [HISTORICAL] Implementation Plan
# FR Audit & Tracking Document
# MedAssist-CDSS Enhancement Proposal
```

### Status Definitions
- **[ACTIVE]** — Current/living document; treated as source of truth
- **[HISTORICAL]** — Snapshot from a point in time; preserved for reference
- *(no label)* — Reference/tracking document; updated as needed

---

## Why Both?

### Benefits of Keeping Both
1. **Historical accuracy** — Can reference what was planned
2. **Learning opportunity** — Understand where estimates diverged
3. **No loss of information** — Complete audit trail
4. **Clear separation of concerns** — Plan ≠ Status

### Example Use Cases
- **Bug analysis:** "Was this feature in scope?" → Check IMPLEMENTATION_PLAN.md
- **New dev onboarding:** "What does the system do?" → Check CURRENT_STATUS.md
- **Performance review:** "Did we hit our timelines?" → Compare both docs
- **Architecture decision:** "Why was it built this way?" → Check FR_AUDIT.md + CURRENT_STATUS.md

---

## Maintenance Policy

### CURRENT_STATUS.md
- **Update frequency:** Quarterly or after major changes
- **Trigger:** New enhancement complete, API change, architecture shift
- **Responsibility:** Dev lead

### IMPLEMENTATION_PLAN.md
- **Update frequency:** Only at project milestones (end of phase)
- **Trigger:** Major pivot, scope change, or end-of-project retrospective
- **Responsibility:** Project manager

### Other Docs
- **FR_AUDIT.md:** Updated when FRs change
- **ENHANCEMENT_PROPOSAL.md:** Updated as enhancements complete
- **SAMPLE_REQUESTS.md:** Updated when API changes

---

## Documentation Sync Audit

**Last Audit:** 2026-08-03  
**Next Audit:** 2026-09-03 (quarterly)

**Audit Checklist:**
- [ ] CURRENT_STATUS.md reflects actual implementation
- [ ] IMPLEMENTATION_PLAN.md marked clearly as historical
- [ ] README.md has navigation guide
- [ ] All links work
- [ ] No conflicting information between docs
- [ ] Sample requests show current API format
- [ ] Enhancement status is accurate

---

## Summary

✅ **Documentation is now clearly labeled and organized:**
- Developers → CURRENT_STATUS.md (current system state)
- Historians → IMPLEMENTATION_PLAN.md (what was planned)
- Both perspectives preserved without information loss
- README.md guides users to the right document
- Maintenance policy established for consistency
