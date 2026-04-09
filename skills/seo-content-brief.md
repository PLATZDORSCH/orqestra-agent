---
title: "SEO Content Brief"
description: "Create a research-backed content brief optimized for search."
tags: [marketing, seo, content, writing]
version: 1
created: "2026-04-08"
---

# SEO Content Brief

Create a comprehensive content brief that writers can follow to produce search-optimized articles.

## When to use

- User wants to create content that ranks in search engines
- User says "write a content brief", "SEO article", "blog post plan"
- Planning content for specific keywords or topics

## Steps

1. **Clarify target keyword**: What's the primary keyword? Who's the target audience? What's the search intent (informational, commercial, transactional)?

2. **Keyword research**: Use `web_search` to find:
   - Related long-tail keywords and questions
   - "People also ask" type queries
   - Search volume estimates (if tools available)

3. **Competitor content analysis**: Search for the target keyword, fetch top 3-5 results with `fetch_url`:
   - What topics do they cover?
   - Average word count
   - Heading structure (H2/H3)
   - Content gaps they miss

4. **Check wiki knowledge**: Use `kb_search` for existing expertise on the topic.

5. **Build the brief**:
   - Suggested title (with keyword)
   - Meta description (155 chars)
   - Target word count
   - Heading structure with subheadings
   - Key points to cover per section
   - Internal/external linking opportunities
   - Unique angle (what we add that competitors don't)

6. **Save as draft**: `content/drafts/brief-YYYY-MM-DD-keyword.md`

## Output format

```markdown
# Content Brief: [Target Keyword]

## SEO Data
- **Primary keyword**: ...
- **Secondary keywords**: ...
- **Search intent**: informational / commercial / transactional
- **Target word count**: X-Y words
- **Target audience**: ...

## Suggested Title
"[Title with primary keyword]"

## Meta Description
"[155 chars max, includes keyword, has CTA]"

## Article Structure

### H2: [Section 1]
- Cover: ...
- Keywords to include: ...

### H2: [Section 2]
- Cover: ...
- Keywords to include: ...

[...]

## Competitor Gaps
- [What top-ranking articles miss that we should include]

## Internal Links
- [Links to relevant wiki pages or existing content]

## Unique Angle
[What makes our article better/different]
```

## Pitfalls

- Don't keyword-stuff — primary keyword 3-5 times in a 2000-word article is enough
- Match search intent — an informational query needs a guide, not a sales page
- Don't ignore competitor content — understand what already ranks and why
- Include concrete data, examples, or original insights — that's what beats generic content
