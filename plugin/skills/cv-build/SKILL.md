---
name: cv-build
description: Build a cvcite CV into gated PDFs and fix whatever the build reports (page budget, gate failures, RenderCV and Typst traps). Use when someone asks to build, render or export their CV, when a build or the PDF gate fails, or when a variant runs over its page budget.
---

# Build the CV and fix what the gate finds

## Run it

In the CV repository: `cvcite build` (all variants) or `cvcite build <variant>`;
`-v` prints the full gate report. Every variant must come out at its page budget with GATE
PASSED, or it is not ready to send. `cvcite doctor` checks the toolchain first if anything
looks broken.

## What each failure means, and the fix

| Report | Cause | Fix |
|---|---|---|
| `CHECK FAILED, not rendered` | An error from `cvcite check` | Fix it in the ledger or `cv.yaml`; see cv-fact-check |
| `expected N page(s)` | The variant runs long or short | Add bullets to the overlay's `_omit`, or tighten text in the master with the person; never shrink fonts or margins below readable |
| `hyphenated across a line break` | Typst split a word, so parsers see two fragments | `design.typography.alignment: justified-with-no-hyphenation` |
| `banned character` | An em dash or another banned character | Rewrite with a colon, a comma or parentheses |
| `do not appear whole in <extractor>'s reading` | A bullet came out split, reordered or with a lost glyph | Look at the bullet in that extractor's text (`cvcite ingest <pdf>`); common causes are a ligature, a bold word next to punctuation, or two columns |
| `shattered the text layer` | One extractor reads one word per line | A layout problem: return to a single-column theme |
| `reading order differs` | Extractors read words in different orders | Columns, tables or floats: keep a single column |
| `below 4.5:1`, `render mode`, `cannot check` | Text too light, invisible or in a colour space the gate cannot read | Use opaque hex colours in `design.colors` that reach 4.5:1 on white; turn off the theme's grey top note (`design.page.show_top_note: false`) |
| `RENDER FAILED` | RenderCV rejected the YAML or Typst failed | Read the message; see the traps below |

## RenderCV traps worth knowing

- `" - "` (space, hyphen, space) inside a bullet splits it into two bullets. Use a colon or a comma.
- A bold keyword followed by `;` loses the semicolon in the PDF. Use `.` or `, and`.
- A bold keyword that also appears in a title or company field shows literal asterisks.
- A quoted year-only date (`"2015"`) may print as January; write it unquoted (`2015`).
- Put colours in quotes (`"#1d4f91"`): YAML reads a bare `#` as the start of a comment.
- Custom section names print as written; capitalise them yourself.
- The phone number needs its country code and `design.header.connections.phone_number_format:
  international`, or the PDF drops the code.
- cvcite renders with ligatures and kerning off, on purpose: with them on, some extractors
  lost or split words ("traffic", bold "Airflow"). The gate's tests prove both cases.

## After a clean build

Show the person `build/<variant>/preview_*.png`, and tell them which file to send for which kind
of role. For a release they can download anywhere: `gh workflow run release.yml` in their private
repository (it refuses to run in a public one).
