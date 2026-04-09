---
title: "Email Campaign"
description: "Plan and draft an email campaign (cold outreach, nurture sequence, or newsletter)."
tags: [marketing, email, outreach, sales, campaign]
version: 1
created: "2026-04-08"
---

# Email Campaign

Plan and draft an email sequence for outreach, nurture, or announcements.

## When to use

- User wants to create a cold email sequence
- User needs a nurture/drip campaign for leads
- User says "email campaign", "outreach sequence", "newsletter series"

## Steps

1. **Define the campaign**:
   - Type: cold outreach / nurture sequence / announcement / re-engagement
   - Goal: meetings booked / signups / downloads / awareness
   - Target audience: persona, pain points, stage in funnel
   - Number of emails in sequence
   - Cadence (days between emails)

2. **Research the audience**: Use `kb_search` for existing persona data, competitor positioning. Use `web_search` if needed.

3. **Draft each email**:
   - **Subject line**: Short (<50 chars), specific, curiosity or value-driven
   - **Preview text**: Extends the subject, not repeats it
   - **Body**: Follow the chosen framework:
     - Cold: Problem → Credibility → CTA (max 100 words)
     - Nurture: Value → Story → Soft CTA
     - Newsletter: Hook → 3 items → CTA
   - **CTA**: One clear call to action per email

4. **Personalization tokens**: Mark where personalization is needed: `{{first_name}}`, `{{company}}`, `{{pain_point}}`

5. **A/B test suggestions**: For email 1, suggest 2 subject line variants.

6. **Save**: `content/drafts/email-campaign-YYYY-MM-DD-name.md`

## Output format

```markdown
# Email Campaign: [Name]

## Campaign overview
- **Type**: Cold outreach
- **Goal**: Book demo meetings
- **Audience**: [Persona]
- **Emails**: 4
- **Cadence**: Day 0, Day 3, Day 7, Day 14

## Email 1: [Internal name]
**Subject**: ...
**Preview**: ...
**Body**:
[Full email text with {{personalization}} tokens]
**CTA**: ...

## Email 2: [Internal name]
...

## A/B Test: Email 1 Subject Lines
- A: "..."
- B: "..."

## Tracking Metrics
- Open rate target: >40%
- Reply rate target: >5% (cold) / Click rate: >3% (nurture)
```

## Pitfalls

- Cold emails over 150 words get ignored — be concise
- Don't sell in email 1 — build curiosity, offer value
- Subject lines with the recipient's company name get 2x higher open rates
- Always include an unsubscribe option for bulk emails (legal requirement)
- Test on mobile — 60%+ of emails are read on phones
