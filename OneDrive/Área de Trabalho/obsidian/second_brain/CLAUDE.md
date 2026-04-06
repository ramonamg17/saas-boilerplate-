# Second Brain — Schema and Operating Rules

This file governs all LLM behavior in this vault. **Read it at the start of every session before taking any action.**

---

## Session Start Protocol

Run these steps in order at the start of every session:

1. Read this file (CLAUDE.md)
2. Read `index.md` — if missing, wiki is empty; say "Wiki is empty — ready to ingest first source."
3. Read last 10 entries of `log.md` — if missing, no ingest has happened yet
4. Confirm readiness with: "Ready. Wiki has N pages. Last activity: [date and type from log]."

Never take any action before completing these four steps.

---

## Directory Structure

```
second_brain/
  raw/              ← HUMAN-OWNED, immutable. Never modify files here.
    articles/       ← web clips, markdown articles
    pdfs/           ← papers, books, reports
    notes/          ← user's own writing, journal entries
    transcripts/    ← podcast, video, meeting transcripts
    assets/         ← images downloaded locally
  wiki/             ← LLM-OWNED. You create and maintain all files here.
    entities/       ← people, places, organizations, books
    concepts/       ← ideas, frameworks, themes
    sources/        ← one summary page per raw source
    synthesis/      ← analyses, comparisons, theses
    domains/        ← overview pages per domain
  CLAUDE.md         ← this file
  index.md          ← catalog of all wiki pages (you maintain this)
  log.md            ← append-only history (you maintain this)
```

---

## Frontmatter Schema

Every wiki page must have this YAML frontmatter:

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

Rules:
- `type` determines the subfolder: entity→`wiki/entities/`, concept→`wiki/concepts/`, source→`wiki/sources/`, synthesis→`wiki/synthesis/`, domain→`wiki/domains/`
- `domain` is `cross` when a page spans multiple domains
- `sources` lists every raw file that informs this page
- `updated` must be set to today's date on every edit
- `tags` always lowercase, hyphenated for multi-word tags

---

## Ingest Workflow

The user specifies mode per ingest: **active** or **passive**.

### Active mode

1. Read the source file in full
2. Discuss key takeaways with the user — ask what to emphasize
3. Write `wiki/sources/<slug>.md` summary page
4. Identify entities (people, places, orgs, books) → create or update their pages in `wiki/entities/`
5. Identify concepts (ideas, frameworks, themes) → create or update their pages in `wiki/concepts/`
6. Update the relevant domain overview page in `wiki/domains/`
7. Update `index.md`: add new page entries, increment page count, update date
8. Append entry to `log.md` (newest at top)
9. Re-index qmd: run `qmd index wiki/` in shell

### Passive mode

1. Read the source file in full
2. Execute steps 3–9 of active mode silently
3. Report to user: pages created, pages updated, contradictions flagged

### Slug convention

File slugs are lowercase, hyphenated, no special characters.  
Example: "The Art of War" → `the-art-of-war.md`

---

## Wiki Maintenance Rules

- **Never delete a wiki page** without explicit user confirmation
- **Always update `updated:`** frontmatter on every edit — use today's date
- **Always add at least one inbound link** when creating a new page (an existing page must link to it)
- **Flag contradictions** with a callout block — never silently overwrite conflicting claims:
  ```markdown
  > [!warning] Contradiction
  > This claim conflicts with [[wiki/sources/other-source]]. Verify which is current.
  ```
- **Bilingual concepts**: when a concept has both PT and EN names, include both in the title line and in tags. Example title: `Viés de Confirmação (Confirmation Bias)`. Tags: `[confirmation-bias, vies-de-confirmacao]`
- **Source provenance**: every wiki page's `sources:` list must be complete — if you update a page based on a new source, add that source to the frontmatter

---

## Query Workflow

When the user asks a question about the wiki:

1. If wiki has ≤20 pages: read `index.md` in full to find relevant pages
2. If wiki has >20 pages: run `qmd search "<query>"` in shell, then read the top results in full
3. Read all relevant pages completely before answering
4. Synthesize answer using `[[wiki/path/page]]` citation links
5. Ask: "Worth filing this as a synthesis page?" — if yes, create `wiki/synthesis/<slug>.md`
6. Append query entry to `log.md`

---

## Lint Protocol

Run on user request. Systematically check:

1. **Orphan pages**: wiki pages with no inbound links from other wiki pages — list them
2. **Stale claims**: pages whose `updated:` date predates a newer source on the same topic — flag them
3. **Missing cross-references**: concepts mentioned by name in a page but not linked — add links
4. **Data gaps**: topics that appear frequently but have no dedicated page — suggest creating them
5. **Source suggestions**: based on gaps and topics, suggest 3-5 new sources to look for

After lint, append a lint entry to `log.md`.

---

## Language Rules

- Source summary pages (`wiki/sources/`): write in the language of the source
- Entity, concept, domain pages: write in the language the user is currently using in this session
- Never mix languages within a single section of a page
- Bilingual terms: include both PT and EN names as described in Wiki Maintenance Rules above
- If unsure of the user's preferred language for this session, default to the language of their most recent message

---

## qmd Search Integration

qmd is a local markdown search engine. Use it as follows:

- **Initialize** (first time only): `qmd init wiki/` from vault root
- **Search**: `qmd search "<query>"` — returns ranked results with snippets
- **Re-index**: `qmd index wiki/` — run after every ingest
- **Threshold**: use qmd only when wiki has >20 pages; use index.md below that
- **Fallback**: if qmd returns an error, fall back to index.md scanning

---

## index.md Format

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

Each entry is one line: wikilink, em dash, one-sentence summary, inline metadata tags.

---

## log.md Format

Append-only. Newest entry at top. Each entry header uses the pattern `## [YYYY-MM-DD] type | title` for greppability.

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
- Filed as synthesis: yes → [[wiki/synthesis/slug]] | no

## [YYYY-MM-DD] lint | Lint pass
- Orphans found: N
- Contradictions flagged: N
- New source suggestions: ...
```

---

## Output Formats

| Format | When to use | How to produce |
|--------|-------------|----------------|
| Markdown page | Default answer format | Write directly |
| Comparison table | Side-by-side entity/concept analysis | Markdown table |
| Marp slide deck | Presentation from wiki content | Add `marp: true` to frontmatter |
| Dataview query | Dynamic tables from frontmatter | Embed in any page |
