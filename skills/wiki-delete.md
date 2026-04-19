---
title: "Wiki Delete"
description: "Delete wiki pages cleanly — removes the file and all cross-references automatically."
tags: [wiki, knowledge-management]
version: 1
created: "2026-04-10"
---

# Wiki Delete

Delete one or more wiki pages. The system automatically cleans up all cross-references.

## When to use

- User asks to remove, delete, or clean up specific wiki pages
- Outdated or incorrect pages need to be removed
- Duplicate pages need to be consolidated (delete the duplicate, keep the original)

## What the system handles automatically

When you call `kb_delete`, the backend:

1. Removes the file from disk
2. Scans ALL other wiki pages for links to the deleted page and removes them
3. Cleans the `sources` and `references` arrays in frontmatter of referencing pages
4. Rebuilds `wiki/index.md` (catalog and statistics)
5. Logs the deletion in `wiki/log.md`

You do **not** need to manually clean up references — `kb_delete` handles it.

## Steps

1. **Confirm with user** — Before deleting, show the page title and path. Ask for confirmation if the user didn't explicitly name the page.

2. **Check references** — Use `kb_related` to see which pages link to the target. Inform the user how many pages will have references removed.

3. **Delete** — Call `kb_delete` with the page path. Review the response to see which pages were cleaned.

4. **Verify** — Use `kb_search` to confirm the page no longer appears in search results.

5. **Report** — Tell the user:
   - Which page was deleted
   - How many pages had references cleaned
   - List the cleaned pages by name

## Protected pages

These pages **cannot** be deleted:
- `wiki/index.md` — auto-generated catalog and statistics
- `wiki/log.md` — append-only operations log
- `wiki/memory.md` — agent memory

## Bulk delete

If the user wants to delete multiple pages:
- Process them one at a time
- After all deletions, `wiki/index.md` is rebuilt automatically; no manual cleanup needed

## Pitfalls

- **Never delete raw/ files** unless the user explicitly asks — raw sources are the immutable archive
- **Never delete without confirmation** for pages that have many incoming references
