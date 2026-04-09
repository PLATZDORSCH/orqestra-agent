---
title: "Content Calendar"
description: "Plan a content calendar for 4-12 weeks with topics, formats, and channels."
tags: [marketing, content, planning, calendar]
version: 1
created: "2026-04-08"
---

# Content Calendar

Plan a structured content calendar for consistent publishing across channels.

## When to use

- User wants to plan content for the coming weeks/months
- User says "content plan", "editorial calendar", "what should we publish?"
- User needs a content strategy tied to business goals

## Steps

1. **Define parameters**:
   - Time horizon (4/8/12 weeks)
   - Channels (blog, LinkedIn, newsletter, social media, etc.)
   - Publishing frequency per channel
   - Business goals (awareness, leads, thought leadership, SEO)

2. **Audit existing content**: Use `kb_search` and `kb_list` to check:
   - What wiki topics have strong coverage?
   - What trends are currently rising?
   - What content has already been drafted?

3. **Identify content pillars** (3-5 core themes aligned with business goals):
   - Map each pillar to wiki categories (topics, trends, market, etc.)
   - Ensure each pillar has enough source material

4. **Generate topic ideas**: For each week, plan:
   - Blog post topic + target keyword
   - Social media angles (2-3 posts per blog article)
   - Newsletter inclusion (yes/no)
   - Content format (how-to, listicle, case study, opinion, data analysis)

5. **Build the calendar**: Use `run_script` to generate a structured table or use markdown directly.

6. **Save to wiki**: `content/drafts/content-calendar-YYYY-QX.md`

## Output format

```markdown
# Content Calendar: [Period]

## Content Pillars
1. [Pillar] — Goal: [awareness/leads/SEO]
2. [Pillar] — Goal: ...
3. [Pillar] — Goal: ...

## Calendar

| Week | Date | Topic | Format | Channel | Pillar | Status |
|---|---|---|---|---|---|---|
| 1 | Apr 14 | ... | Blog | Website | 1 | Planned |
| 1 | Apr 15 | ... | Post | LinkedIn | 1 | Planned |
| 2 | Apr 21 | ... | Newsletter | Email | 2 | Planned |
| ... | | | | | | |

## Topic Details

### Week 1: [Topic]
- **Angle**: ...
- **Target keyword**: ...
- **Wiki sources**: [links to relevant wiki pages]
- **Social spin-offs**: ...
```

## Pitfalls

- Don't plan too far ahead with exact topics — market changes fast
- Balance evergreen content (SEO) with timely content (trends)
- Every piece should serve a business goal — no content for content's sake
- Leave buffer for reactive content (industry news, competitor moves)
