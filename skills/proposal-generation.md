---
title: "Proposal / Quote Generation"
description: "Generate a structured business proposal or quote for a client."
tags: [sales, proposal, quote, document]
version: 1
created: "2026-04-08"
---

# Proposal / Quote Generation

Create a professional business proposal or quote tailored to a specific client request.

## When to use

- User needs to write a proposal for a client
- User says "create a proposal", "write a quote", "project estimate"
- User has a client brief or RFP to respond to

## Steps

1. **Understand requirements**: Clarify with the user:
   - Client name and background
   - Project scope (what needs to be built/delivered)
   - Timeline expectations
   - Budget range (if known)
   - Evaluation criteria

2. **Research the client**: Use `kb_search` for existing knowledge. Use `web_search` + `fetch_url` for company info if not in wiki.

3. **Define scope and deliverables**: Break the project into clear phases:
   - Phase 1: Discovery / Analysis
   - Phase 2: Development / Execution
   - Phase 3: Launch / Delivery
   - Phase 4: Support / Optimization
   For each phase: deliverables, timeline, dependencies.

4. **Estimate effort**: Use `run_script` if calculations needed:
   - Hours per deliverable
   - Rate × hours = cost
   - Add buffer (15-20% for unknowns)
   - Optional: tiered pricing (basic/standard/premium)

5. **Draft the proposal**:
   - Executive summary (why us, what we'll deliver)
   - Understanding of the problem (show you listened)
   - Proposed solution (approach, methodology)
   - Deliverables and timeline (table or Gantt-style)
   - Investment (pricing with breakdown)
   - Team (who will work on it)
   - Terms and next steps

6. **Save**: `content/drafts/proposal-YYYY-MM-DD-client.md`

## Output format

```markdown
# Proposal: [Project Name]
## For: [Client Name]
## Date: [Date]

---

## Executive Summary
[2-3 paragraphs: Why us. What we deliver. Key benefit.]

## Understanding
[Show you understand their challenge — reference their brief or conversation]

## Proposed Approach
### Phase 1: [Name] (Week 1-2)
- Deliverable 1: ...
- Deliverable 2: ...

### Phase 2: [Name] (Week 3-6)
- ...

### Phase 3: [Name] (Week 7-8)
- ...

## Timeline
| Phase | Duration | Deliverables |
|---|---|---|
| Phase 1 | 2 weeks | ... |
| Phase 2 | 4 weeks | ... |
| Phase 3 | 2 weeks | ... |

## Investment

| Item | Effort | Cost |
|---|---|---|
| Phase 1 | X hours | €X,XXX |
| Phase 2 | X hours | €X,XXX |
| Phase 3 | X hours | €X,XXX |
| **Total** | **X hours** | **€XX,XXX** |

Optional: [Basic/Standard/Premium tiers]

## Team
- [Name], [Role] — [relevant experience]

## Terms
- Payment: [schedule]
- Validity: [30 days]
- Out of scope: [what's NOT included]

## Next Steps
1. Review and feedback by [date]
2. Kick-off meeting on [date]
```

## Pitfalls

- Don't just list features — connect every deliverable to a business outcome
- Always define what's OUT of scope — prevents scope creep
- Tiered pricing (3 options) often increases average deal size
- Include a validity period — prevents "we'll get back to you in 6 months" at the quoted price
- Proofread and format professionally — the proposal IS your first deliverable
