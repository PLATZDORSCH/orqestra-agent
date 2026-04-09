---
title: "Sales Pitch Preparation"
description: "Prepare a tailored sales pitch for a specific prospect or audience."
tags: [sales, pitch, presentation, persuasion]
version: 1
created: "2026-04-08"
---

# Sales Pitch Preparation

Build a compelling, tailored sales pitch for a specific prospect or audience.

## When to use

- User has an upcoming sales meeting or pitch
- User says "prepare a pitch", "sales deck", "how do I pitch to..."
- User wants to tailor messaging for a specific prospect

## Steps

1. **Research the prospect**:
   - Use `kb_search` for existing knowledge about the company/person
   - Use `web_search` + `fetch_url` for: company website, recent news, LinkedIn profiles, funding rounds
   - Identify: industry, size, pain points, tech stack, recent events

2. **Identify the pain point**: What specific problem does the prospect have that you solve? Be concrete. "Better CRM" is weak. "Losing 20% of leads because handoff from marketing to sales takes 3 days" is strong.

3. **Map your solution to their pain**:
   - Feature → Benefit → Proof (case study, data, testimonial)
   - Maximum 3 key value propositions — don't overwhelm

4. **Build the pitch structure**:
   - **Hook** (30 sec): Reference something specific about them (recent news, a challenge in their industry)
   - **Problem** (2 min): Paint the pain — quantify if possible
   - **Solution** (3 min): How you solve it — demo or walkthrough
   - **Proof** (2 min): Case study from a similar company, metrics
   - **Ask** (1 min): Clear next step — trial, second meeting, decision timeline

5. **Prepare objection responses**:
   - Price: ROI calculation
   - "We already have something": Differentiation points
   - "Not now": Cost of delay / urgency trigger
   - "Need to check with...": Provide materials for the decision maker

6. **Save**: `content/drafts/pitch-YYYY-MM-DD-prospect.md`

## Output format

```markdown
# Sales Pitch: [Prospect Name]

## Prospect Profile
- **Company**: ...
- **Industry**: ...
- **Size**: ...
- **Key contact**: ...
- **Known pain points**: ...
- **Recent events**: ...

## Pitch Script

### Hook (30 sec)
"[Opening that references something specific about them]"

### Problem (2 min)
[Paint the pain, quantify the cost]

### Solution (3 min)
1. [Value prop 1]: [Feature] → [Benefit] → [Proof]
2. [Value prop 2]: ...
3. [Value prop 3]: ...

### Proof (2 min)
[Case study: Similar company, metrics achieved]

### Ask (1 min)
"[Clear CTA with specific next step]"

## Objection Handling
| Objection | Response |
|---|---|
| "Too expensive" | [ROI argument] |
| "We use competitor X" | [Differentiation] |
| "Not the right time" | [Cost of delay] |

## Follow-up Plan
- Same day: [Thank you email with summary]
- Day 3: [Value-add content]
- Day 7: [Check-in with specific question]
```

## Pitfalls

- Don't pitch features — pitch outcomes
- Don't talk more than 50% of the meeting — ask questions, listen
- Research is non-negotiable — a generic pitch is worse than no pitch
- Always have a clear ask at the end — "let's stay in touch" is not a next step
