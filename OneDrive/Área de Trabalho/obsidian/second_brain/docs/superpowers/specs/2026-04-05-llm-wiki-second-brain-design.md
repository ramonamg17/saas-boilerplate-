# LLM Wiki — Second Brain Design

**Date:** 2026-04-05  
**Status:** Approved  
**Domain:** All (general-purpose second brain)  
**Languages:** Portuguese + English  

---

## 1. Overview

A persistent, LLM-maintained personal wiki that compiles and synthesizes knowledge from all source types (articles, PDFs, personal notes, transcripts). The LLM owns the wiki layer entirely — creating, updating, and cross-referencing pages. The human owns the raw sources and directs the analysis.

Architecture follows the **source/wiki separation** pattern: `raw/` is immutable (human-owned), `wiki/` is LLM-maintained. A `CLAUDE.md` schema governs all LLM behavior each session.

---

## 2. Directory Structure

```
second_brain/
  raw/
    articles/        ← web clips, markdown articles
    pdfs/            ← papers, books, reports
    notes/           ← user's own writing, journal entries
    transcripts/     ← podcast, video, meeting transcripts
    assets/          ← images downloaded locally
  wiki/
    entities/        ← people, places, organizations, books
    concepts/        ← ideas, frameworks, themes
    sources/         ← one summary page per raw source
    synthesis/       ← analyses, comparisons, theses
    domains/         ← overview pages per domain
  docs/
    superpowers/
      specs/         ← design and planning documents
  CLAUDE.md          ← schema and operating rules
  index.md           ← catalog of all wiki pages
  log.md             ← append-only ingest/query history
```

---

## 3. Frontmatter Schema

Every wiki page uses this YAML frontmatter:

```yaml
---
title: "Page Title"
type: entity | concept | source | synthesis | domain
domain: personal | research | books | work | cross
language: pt | en | both
tags: [tag1, tag2]
sources: [raw/articles/foo.md]
updated: YYYY-MM-DD
---
```

- `type` determines which wiki subfolder the page lives in
- `domain` enables Dataview queries scoped to a domain without folder nesting
- `sources` creates an explicit provenance chain from wiki page back to raw source
- `updated` is set by the LLM on every edit

---

## 4. index.md Format

Updated on every ingest. Structure:

```markdown
# Wiki Index
_Last updated: YYYY-MM-DD | Pages: N_

## Sources
- [[wiki/sources/slug]] — One-sentence summary. `domain:X` `tags:y,z`

## Entities

## Concepts

## Synthesis

## Domains
```

Below 20 wiki pages, the LLM reads the full index to find relevant pages. Above 20 pages, it uses qmd search first.

---

## 5. log.md Format

Append-only, newest entry at top. Each entry starts with `## [YYYY-MM-DD] type | title` for greppability.

```markdown
# Wiki Log

## [YYYY-MM-DD] ingest | Source Title
- Source: `raw/category/filename.md`
- Mode: active | passive
- Pages created: [[wiki/sources/x]], [[wiki/entities/y]]
- Pages updated: [[wiki/concepts/z]]
- Notes: any contradictions flagged, decisions made

## [YYYY-MM-DD] query | "Query text"
- Pages consulted: [[wiki/concepts/x]]
- Filed as synthesis: yes/no → [[wiki/synthesis/slug]]

## [YYYY-MM-DD] lint | Lint pass
- Orphans found: N
- Contradictions flagged: N
- New source suggestions: ...
```

---

## 6. CLAUDE.md Operating Rules

The full CLAUDE.md (to be created at vault root) governs:

### Session start
1. Read CLAUDE.md
2. Read index.md (if it exists; if not, wiki is empty — say so and offer to ingest first source)
3. Read last 10 entries of log.md (if it exists)
4. Confirm readiness before taking any action

### Ingest workflow
Two modes, specified per ingest:

**Active mode:**
1. Read source
2. Discuss key takeaways with user
3. Write `wiki/sources/<slug>.md` summary page
4. Update relevant entity, concept, and domain pages (may touch 10–15 pages)
5. Update index.md (add new entries, update page count)
6. Append entry to log.md
7. Re-index qmd: `qmd index wiki/`

**Passive mode:**
1. Read source
2. Process silently (steps 3–6 above)
3. Report: pages created, pages updated, contradictions flagged

### Wiki maintenance rules
- Never delete a page without asking the user
- Always update `updated:` frontmatter on edit
- Always add inbound links when creating a new page (at least one existing page must link to it)
- Flag contradictions with a `> [!warning] Contradiction` callout — never silently overwrite
- When a concept has both PT and EN names, note both in the page title line and tags

### Query workflow
1. Read index.md (or run `qmd search "<query>"` if >20 pages)
2. Read relevant pages in full
3. Synthesize answer with `[[page]]` citations
4. Offer to file the answer as a synthesis page in `wiki/synthesis/`
5. Append query entry to log.md

### Lint protocol
Run on request. Check for:
- Orphan pages (no inbound links)
- Stale claims superseded by newer sources
- Missing cross-references (concept mentioned but not linked)
- Data gaps that could be filled with a web search
- Suggest new sources to look for

### Language rules
- Write source summary pages in the language of the source
- Write entity/concept/domain pages in the language the user is currently writing in
- Flag when a concept has both PT and EN names; keep both in frontmatter tags
- Never mix languages within a single page section

---

## 7. qmd Search Integration

- **Threshold:** used above 20 wiki pages; index.md scanning below
- **Index scope:** `wiki/` only (not `raw/`)
- **Setup:** `pip install qmd && qmd init wiki/`
- **Re-index:** `qmd index wiki/` at end of every ingest (automated)
- **Fallback:** if qmd is unavailable, fall back to index.md scanning — system never hard-depends on qmd

---

## 8. Output Formats

Depending on the query, answers can be delivered as:

| Format | When to use |
|--------|-------------|
| Markdown page | Default — filed in `wiki/synthesis/` if worth keeping |
| Comparison table | Side-by-side analysis of entities or concepts |
| Marp slide deck | Presentations from wiki content |
| Dataview query | Dynamic tables from frontmatter (requires Dataview plugin) |

---

## 9. Out of Scope (for now)

- Automated ingest pipelines (Zapier, n8n, etc.)
- Multi-user / team collaboration
- Embedding-based RAG (qmd covers search needs)
- Mobile-specific workflows

---

## 10. Success Criteria

- Every session starts with the LLM oriented (CLAUDE.md + index + log)
- Every ingested source results in at least one new wiki page and updates to existing pages
- Every query produces a cited answer; substantive answers are optionally filed back
- The wiki graph in Obsidian shows meaningful cross-links after 10+ sources
- qmd search returns relevant pages within the wiki after 20+ pages
