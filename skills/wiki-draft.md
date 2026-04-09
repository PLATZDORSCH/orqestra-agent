---
title: "Wiki Draft"
description: "Create a content draft (blog, newsletter, briefing) based on wiki knowledge."
tags: [wiki, content, writing]
version: 1
created: "2026-04-08"
---

# Wiki Draft

Create a content draft based on compiled wiki knowledge.

## When to use

- User wants a blog article, briefing, or LinkedIn post
- User says "write me an article about...", "create a briefing for...", etc.

## Steps

1. **Clarify topic and format** — If not obvious, ask briefly. Possible formats: blog, newsletter, briefing, linkedin, slides.

2. **Search the wiki** — Read `wiki/index.md`, identify and read relevant pages. Pay special attention to `wiki/synthesis/` and `wiki/trends/`.

3. **Load template** — Load the matching template from `content/templates/`:
   - `content/templates/blog.md` for blog articles
   - `content/templates/newsletter.md` for newsletters
   - `content/templates/briefing.md` for briefings
   - For LinkedIn/slides: free form

4. **Write draft** — Save in `content/drafts/` using `kb_write`:
   - Path: `content/drafts/YYYY-MM-DD-short-title.md`
   - Metadata:
     - `title`: Content title
     - `format`: blog / newsletter / briefing / linkedin / slides
     - `based_on`: list of wiki pages used as source
     - `created`: today's date
     - `status`: draft
   - Follow the template structure, fill with wiki knowledge

5. **Inform user** — Show the draft to the user, highlight sections that need review.

6. **Write log entry** — Append to `wiki/log.md`:
   ```
   ## [YYYY-MM-DD] draft | Content title
   - Format: blog
   - Based on: wiki/trends/..., wiki/topics/...
   - Saved: content/drafts/YYYY-MM-DD-short-title.md
   ```

## Pitfalls

- Drafts always go in `content/drafts/`, never directly in `content/published/`
- Always use the wiki as the basis, don't invent facts
- Include source references where possible
- Adapt tone to the target audience
- Log entry must NEVER be forgotten

## Verification

Before reporting completion:

1. Draft exists in `content/drafts/`
2. Draft has correct frontmatter with `based_on` references
3. `wiki/log.md` has a draft entry
4. Only then report completion.
