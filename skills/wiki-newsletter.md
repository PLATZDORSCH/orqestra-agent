---
title: "Wiki Newsletter"
description: "Create a weekly review from recent wiki activity."
tags: [wiki, content, newsletter]
version: 1
created: "2026-04-08"
---

# Wiki Newsletter

Create a weekly review from recent wiki activity.

## When to use

- User requests a newsletter or weekly review
- Weekly (e.g. via cron or scheduled task)
- User says "what happened this week", "weekly update", etc.

## Steps

1. **Scan the log** — Read `wiki/log.md` and identify all entries from the last 7 days.

2. **Check new and updated pages** — Read all pages whose `updated` date falls within the last 7 days. Pay special attention to `wiki/trends/` for changes in momentum.

3. **Load template** — Read `content/templates/newsletter.md`.

4. **Write newsletter** — Save in `content/drafts/` as `YYYY-MM-DD-newsletter-cwXX.md`:
   - 3-5 top topics of the week with context
   - Trend update table (what's rising, what's declining)
   - 1-2 "on the radar" topics (weak signals)
   - Metadata:
     - `title`: "Weekly Review CW XX"
     - `format`: newsletter
     - `based_on`: list of sources processed that week
     - `created`: today's date
     - `status`: draft

5. **Write log entry** — Append to `wiki/log.md`:
   ```
   ## [YYYY-MM-DD] newsletter | Weekly Review CW XX
   - Period: YYYY-MM-DD to YYYY-MM-DD
   - New sources: X
   - Updated pages: X
   - Saved: content/drafts/YYYY-MM-DD-newsletter-cwXX.md
   ```

## Pitfalls

- Only use facts from the wiki, don't invent anything
- If no activity during the week: short note instead of an empty newsletter
- Always provide context and analysis, not just lists
- Log entry must NEVER be forgotten

## Verification

Before reporting completion:

1. Newsletter draft exists in `content/drafts/`
2. All referenced data comes from actual wiki pages
3. `wiki/log.md` has a newsletter entry
4. Only then report completion.
