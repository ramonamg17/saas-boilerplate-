# LLM Wiki — Second Brain Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Bootstrap the second brain vault with full directory structure, CLAUDE.md schema, index.md, log.md, and qmd search — ready to ingest the first source.

**Architecture:** Source/wiki separation — `raw/` is human-owned and immutable, `wiki/` is LLM-maintained. `CLAUDE.md` at vault root governs every session. `index.md` and `log.md` are the navigation and history layer. qmd provides full-text search once the wiki exceeds 20 pages.

**Tech Stack:** Markdown, YAML frontmatter, Obsidian, qmd (pip install qmd), git

**Vault root:** `C:/Users/ramon/OneDrive/Área de Trabalho/obsidian/second_brain`

---

### Task 1: Create directory structure

**Files:**
- Create: `raw/articles/.gitkeep`
- Create: `raw/pdfs/.gitkeep`
- Create: `raw/notes/.gitkeep`
- Create: `raw/transcripts/.gitkeep`
- Create: `raw/assets/.gitkeep`
- Create: `wiki/entities/.gitkeep`
- Create: `wiki/concepts/.gitkeep`
- Create: `wiki/sources/.gitkeep`
- Create: `wiki/synthesis/.gitkeep`
- Create: `wiki/domains/.gitkeep`

- [ ] **Step 1: Create all directories with placeholder files**

Run from vault root:
```bash
mkdir -p raw/articles raw/pdfs raw/notes raw/transcripts raw/assets
mkdir -p wiki/entities wiki/concepts wiki/sources wiki/synthesis wiki/domains
touch raw/articles/.gitkeep raw/pdfs/.gitkeep raw/notes/.gitkeep raw/transcripts/.gitkeep raw/assets/.gitkeep
touch wiki/entities/.gitkeep wiki/concepts/.gitkeep wiki/sources/.gitkeep wiki/synthesis/.gitkeep wiki/domains/.gitkeep
```

- [ ] **Step 2: Verify structure**

Run:
```bash
find . -name ".gitkeep" | sort
```
Expected output (10 lines):
```
./raw/articles/.gitkeep
./raw/assets/.gitkeep
./raw/notes/.gitkeep
./raw/pdfs/.gitkeep
./raw/transcripts/.gitkeep
./wiki/concepts/.gitkeep
./wiki/domains/.gitkeep
./wiki/entities/.gitkeep
./wiki/sources/.gitkeep
./wiki/synthesis/.gitkeep
```

- [ ] **Step 3: Commit**

```bash
git add raw/ wiki/
git commit -m "feat: scaffold raw/ and wiki/ directory structure"
```

---

### Task 2: Create CLAUDE.md

**Files:**
- Create: `CLAUDE.md`

- [ ] **Step 1: Write CLAUDE.md at vault root**

Create `CLAUDE.md` with this exact content:

```markdown
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
9. Re-index qmd: run `python -m qmd update wiki` in shell

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

- **Initialize** (first time only): `python -m qmd collection add wiki wiki/` from vault root
- **Search**: `qmd search "<query>"` — returns ranked results with snippets
- **Re-index**: `python -m qmd update wiki` — run after every ingest
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
```

- [ ] **Step 2: Verify the file exists and is non-empty**

Run:
```bash
wc -l CLAUDE.md
```
Expected: more than 150 lines

- [ ] **Step 3: Commit**

```bash
git add CLAUDE.md
git commit -m "feat: add CLAUDE.md schema and operating rules"
```

---

### Task 3: Create index.md

**Files:**
- Create: `index.md`

- [ ] **Step 1: Write index.md**

Create `index.md` at vault root with this exact content:

```markdown
# Wiki Index
_Last updated: 2026-04-05 | Pages: 0_

## Sources
<!-- Source summary pages — one per ingested document -->

## Entities
<!-- People, places, organizations, books -->

## Concepts
<!-- Ideas, frameworks, themes -->

## Synthesis
<!-- Analyses, comparisons, theses -->

## Domains
<!-- Overview pages per domain -->
```

- [ ] **Step 2: Commit**

```bash
git add index.md
git commit -m "feat: add empty index.md"
```

---

### Task 4: Create log.md

**Files:**
- Create: `log.md`

- [ ] **Step 1: Write log.md**

Create `log.md` at vault root with this exact content:

```markdown
# Wiki Log

## [2026-04-05] setup | Second brain initialized
- Structure created: raw/ and wiki/ directories
- CLAUDE.md written
- index.md and log.md initialized
- qmd: pending initialization (Task 5)
- Notes: Fresh vault, ready to ingest first source
```

- [ ] **Step 2: Commit**

```bash
git add log.md
git commit -m "feat: add log.md with setup entry"
```

---

### Task 5: Install and initialize qmd

**Files:** none (system-level setup + `.qmd/` config directory created by qmd)

- [ ] **Step 1: Install qmd**

Run:
```bash
pip install qmd
```
Expected: `Successfully installed qmd-...`

If pip is unavailable, try `pip3 install qmd` or `python -m pip install qmd`.

- [ ] **Step 2: Verify installation**

Run:
```bash
qmd --version
```
Expected: version string printed, no error.

- [ ] **Step 3: Initialize qmd index over wiki/**

Run from vault root:
```bash
python -m qmd collection add wiki wiki/
```
Expected: index initialized, confirmation message. A `.qmd/` or similar config directory will be created.

- [ ] **Step 4: Verify search works (empty result is fine)**

Run:
```bash
python -m qmd search "test"
```
Expected: either empty results or a message indicating the index is empty. No error.

- [ ] **Step 5: Add qmd index to .gitignore**

The qmd index is a build artifact — don't commit it. Check if `.gitignore` exists:
```bash
cat .gitignore 2>/dev/null || echo "no .gitignore yet"
```

If `.gitignore` exists, append to it. If not, create it:
```bash
echo ".qmd/" >> .gitignore
echo "*.qmd.db" >> .gitignore
```

- [ ] **Step 6: Update log.md — mark qmd initialized**

Edit log.md. Replace the line:
```
- qmd: pending initialization (Task 5)
```
With:
```
- qmd: initialized via `python -m qmd collection add wiki wiki/`
```

- [ ] **Step 7: Commit**

```bash
git add .gitignore log.md
git commit -m "feat: initialize qmd search index, add .gitignore"
```

---

### Task 6: Remove default welcome file and final commit

**Files:**
- Delete: `Bem-vindo.md`

- [ ] **Step 1: Delete the default Obsidian welcome note**

```bash
git rm "Bem-vindo.md"
```

- [ ] **Step 2: Commit**

```bash
git commit -m "chore: remove default Obsidian welcome note"
```

- [ ] **Step 3: Verify final vault structure**

Run:
```bash
find . -not -path './.git/*' -not -name '.gitkeep' -not -path './.qmd/*' | sort
```
Expected output includes:
```
.
./CLAUDE.md
./docs/superpowers/plans/2026-04-05-llm-wiki-second-brain.md
./docs/superpowers/specs/2026-04-05-llm-wiki-second-brain-design.md
./index.md
./log.md
./raw/articles/
./raw/assets/
./raw/notes/
./raw/pdfs/
./raw/transcripts/
./wiki/concepts/
./wiki/domains/
./wiki/entities/
./wiki/sources/
./wiki/synthesis/
```

---

### Task 7: First ingest walkthrough

This task demonstrates the full ingest workflow end-to-end using a sample source — confirming the system works before you rely on it.

**Files:**
- Create: `raw/notes/about-this-wiki.md` (sample source)
- Create: `wiki/sources/about-this-wiki.md`
- Create: `wiki/domains/general.md`
- Modify: `index.md`
- Modify: `log.md`

- [ ] **Step 1: Create a sample source note in raw/notes/**

Create `raw/notes/about-this-wiki.md`:

```markdown
# About This Wiki

This is my personal second brain — a wiki maintained by Claude Code.

Goals:
- Accumulate knowledge from articles, books, notes, and transcripts
- Build cross-referenced pages for entities, concepts, and domains
- Query the wiki with cited answers
- Keep the wiki healthy with periodic lint passes

Domains I'll use this for: personal growth, research, books, work.
Languages: Portuguese and English.
```

- [ ] **Step 2: Create wiki/sources/about-this-wiki.md**

Create `wiki/sources/about-this-wiki.md`:

```markdown
---
title: "About This Wiki"
type: source
domain: cross
language: en
tags: [second-brain, wiki, setup, meta]
sources: [raw/notes/about-this-wiki.md]
updated: 2026-04-05
---

# About This Wiki

**Source:** `raw/notes/about-this-wiki.md`  
**Type:** Personal note  
**Ingested:** 2026-04-05

## Summary

Founding document for this second brain. Describes the purpose, domains, and language conventions for the wiki.

## Key Points

- Purpose: accumulate and cross-reference knowledge across all domains
- Four domains: personal growth, research, books, work
- Languages: Portuguese and English
- Maintained by Claude Code following CLAUDE.md schema

## Links

- [[wiki/domains/general]] — overview of this wiki's scope
```

- [ ] **Step 3: Create wiki/domains/general.md**

Create `wiki/domains/general.md`:

```markdown
---
title: "General — Wiki Overview"
type: domain
domain: cross
language: en
tags: [meta, second-brain, overview]
sources: [raw/notes/about-this-wiki.md]
updated: 2026-04-05
---

# General — Wiki Overview

This wiki serves as a personal second brain across four domains:

| Domain | Description |
|--------|-------------|
| `personal` | Goals, health, psychology, self-improvement, journal entries |
| `research` | Deep dives into specific topics over weeks or months |
| `books` | Chapter notes, character/theme pages, reading companions |
| `work` | Meeting notes, projects, client knowledge, competitive analysis |

Pages tagged `cross` span multiple domains.

## Languages

Sources and wiki pages may be in Portuguese or English. Bilingual concepts include both names.

## See Also

- [[index]] — full catalog of all wiki pages
- [[wiki/sources/about-this-wiki]] — founding note
```

- [ ] **Step 4: Update index.md**

Edit `index.md` to replace:
```markdown
# Wiki Index
_Last updated: 2026-04-05 | Pages: 0_

## Sources
<!-- Source summary pages — one per ingested document -->

## Entities
<!-- People, places, organizations, books -->

## Concepts
<!-- Ideas, frameworks, themes -->

## Synthesis
<!-- Analyses, comparisons, theses -->

## Domains
<!-- Overview pages per domain -->
```

With:
```markdown
# Wiki Index
_Last updated: 2026-04-05 | Pages: 2_

## Sources
- [[wiki/sources/about-this-wiki]] — Founding note describing this wiki's purpose, domains, and language conventions. `domain:cross` `tags:second-brain,meta`

## Entities
<!-- People, places, organizations, books -->

## Concepts
<!-- Ideas, frameworks, themes -->

## Synthesis
<!-- Analyses, comparisons, theses -->

## Domains
- [[wiki/domains/general]] — Overview of all four domains (personal, research, books, work) and language conventions. `domain:cross` `tags:meta,overview`
```

- [ ] **Step 5: Append ingest entry to log.md**

Edit `log.md` to add this block at the top (after `# Wiki Log`, before the setup entry):

```markdown
## [2026-04-05] ingest | About This Wiki
- Source: `raw/notes/about-this-wiki.md`
- Mode: active
- Pages created: [[wiki/sources/about-this-wiki]], [[wiki/domains/general]]
- Pages updated: [[index]]
- Notes: First ingest — meta/setup note. Establishes domain and language conventions.

```

- [ ] **Step 6: Re-index qmd**

```bash
python -m qmd update wiki
```
Expected: index updated with 2 new pages.

- [ ] **Step 7: Test a query**

```bash
python -m qmd search "domains"
```
Expected: `wiki/domains/general.md` appears in results.

- [ ] **Step 8: Commit**

```bash
git add raw/notes/about-this-wiki.md wiki/sources/about-this-wiki.md wiki/domains/general.md index.md log.md
git commit -m "feat: first ingest — about-this-wiki meta note, domains/general overview"
```

---

## Self-Review

**Spec coverage check:**

| Spec requirement | Task |
|-----------------|------|
| Directory structure (raw/ + wiki/ subfolders) | Task 1 |
| CLAUDE.md with all operating rules | Task 2 |
| index.md format | Task 3 |
| log.md format | Task 4 |
| qmd install + init | Task 5 |
| Remove default welcome file | Task 6 |
| First ingest demonstration | Task 7 |
| Frontmatter schema on wiki pages | Task 7 (steps 2 & 3) |
| Both PT + EN language handling in CLAUDE.md | Task 2 |
| Active and passive ingest modes in CLAUDE.md | Task 2 |
| Contradiction callout rules in CLAUDE.md | Task 2 |
| Lint protocol in CLAUDE.md | Task 2 |
| qmd threshold (>20 pages) in CLAUDE.md | Task 2 |

All spec sections covered. No placeholders. No TBDs.
