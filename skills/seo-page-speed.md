---
title: "Page Speed Analysis"
description: "Analyze page load performance and provide optimization recommendations."
tags: [tech, seo, performance, speed, core-web-vitals]
version: 1
created: "2026-04-08"
---

# Page Speed Analysis

Analyze a website's loading performance and identify optimization opportunities.

## When to use

- User says "page speed", "why is my site slow?", "performance audit", "Core Web Vitals"
- Before or after a site launch to check performance
- When SEO rankings drop (speed is a ranking factor)

## Steps

1. **Measure baseline**: Use `run_script` to fetch pages and measure response times:
   ```python
   import httpx, time
   start = time.time()
   resp = httpx.get(url, follow_redirects=True)
   elapsed = time.time() - start
   ```
   Test homepage + 3-5 key pages.

2. **Analyze response characteristics**:
   - Time to first byte (TTFB)
   - Total download size (HTML)
   - Number of redirects
   - HTTP/2 or HTTP/1.1?
   - Compression (Content-Encoding: gzip/br)?
   - Cache headers (Cache-Control, ETag)?

3. **Check for common issues** (use `run_script` to parse HTML):
   - Large inline CSS/JS blocks
   - Render-blocking resources
   - Unoptimized image references
   - Too many external scripts (analytics, chat widgets, fonts)
   - Missing lazy loading attributes on images

4. **External speed test**: Use `web_search` to find PageSpeed Insights results or `fetch_url` on tools like:
   - `https://pagespeed.web.dev/analysis?url=[URL]`
   - Results from web searches for "[domain] page speed"

5. **Server analysis**:
   - Response headers → server type, CDN
   - Multiple redirects (http → https → www)?
   - DNS resolution time

6. **Generate comparison chart**: Use `generate_chart` to visualize:
   - Page load times across tested pages (bar chart)
   - Response size comparison

7. **Compile recommendations by impact**:
   - 🔴 High impact, easy fix
   - 🟡 Medium impact
   - 🟢 Nice to have

8. **Save**: `wiki/synthesis/page-speed-YYYY-MM-DD-domain.md`

## Output format

```markdown
# Page Speed Analysis: [domain.com]
Date: [YYYY-MM-DD]

## Performance Summary
| Page | TTFB | Total time | Size | Redirects |
|---|---|---|---|---|
| / | X.Xs | X.Xs | XX KB | 0 |
| /product | X.Xs | X.Xs | XX KB | 1 |

## Server Configuration
- Server: [nginx/Apache/Cloudflare/...]
- HTTP version: HTTP/2 ✅ / HTTP/1.1 ⚠️
- Compression: gzip ✅ / none ❌
- CDN: [yes/no]
- SSL: ✅

## Issues Found

### High Impact 🔴
| Issue | Affected | Estimated saving | Fix |
|---|---|---|---|
| No compression | All pages | 60-80% size | Enable gzip/brotli |
| Redirect chain | /old → /new → /final | 200-500ms | Direct to final URL |

### Medium Impact 🟡
| Issue | Affected | Estimated saving | Fix |
|---|---|---|---|

### Nice to Have 🟢
| Issue | Affected | Estimated saving | Fix |
|---|---|---|---|

## Optimization Plan
1. [Highest impact fix first]
2. ...

## Expected Improvement
- Current avg. load time: X.Xs
- Estimated after fixes: X.Xs
- Improvement: ~XX%
```

## Pitfalls

- Server response time (TTFB) is often the biggest factor — don't ignore the backend
- Compression alone can reduce transfer size by 60-80%
- Too many third-party scripts (chat, analytics, A/B testing) are a common hidden problem
- Don't optimize for lab scores alone — real user experience matters more
- Every redirect adds 100-300ms — minimize redirect chains
