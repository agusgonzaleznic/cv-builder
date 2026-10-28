# cvcite

Build your CV from one master YAML file, tailor it for each kind of role with a small overlay,
and gate every PDF the way applicant tracking systems (ATS) read it. Every claim on the CV traces
to a fact you confirmed, with its source.

It comes in three parts that work together or alone:

- **A command line** (`cvcite`) that checks, renders and gates your CV. No AI involved.
- **A Claude Code plugin** whose skills interview you, one multiple-choice question at a time:
  they turn an old CV or a LinkedIn export into a fact ledger, check every date and claim, tailor
  the CV for a job posting, and compare LinkedIn, your website and GitHub against it.
- **A GitHub Action** that builds and gates the CV on every change, publishes the PDFs as a
  private release when you ask, and can run an AI claim review on pull requests with your own key.

Your CV lives in your own private repository. This one holds the tool and a made-up sample person.

## Why

- **Two CVs drift apart.** Keep one master with every fact; each variant is an overlay that only
  changes emphasis (headline, summary, bolded words, skills line, which bullets to drop).
- **CVs overclaim.** Every number on the CV must appear in the fact ledger (`facts.yaml`) with
  its source, or the build fails. Facts marked `private` can never reach the CV.
- **A PDF that looks right can read wrong.** Parsers split hyphenated words, lose ligature glyphs,
  shatter text into one word per line, or read columns in the wrong order. The gate reads each
  PDF with two to four independent extractors and fails it unless they agree and every bullet
  survives whole.

## Quick start

You need Python 3.12 or newer (RenderCV 2.8 needs it). [uv](https://docs.astral.sh/uv/) is the easiest way to install;
Ghostscript is optional (a third extractor for the gate).

```sh
uv tool install git+https://github.com/agusgonzaleznic/cvcite
cvcite init my-cv --sample      # try it with the made-up sample; drop --sample to start blank
cd my-cv
cvcite build                    # check, render and gate every variant
```

The PDFs land in `build/<variant>/`, one folder per variant, each holding the file under the same
name, so a recruiter cannot tell that variants exist. Keep the repository private:

```sh
git init -b main && git add -A && git commit -m "Start my CV"
gh repo create my-cv --private --source . --push
```

## With Claude Code

```text
/plugin install cvcite --marketplace agusgonzaleznic/cvcite
```

Or in two steps: `/plugin marketplace add agusgonzaleznic/cvcite`, then
`/plugin install cvcite@cvcite`.

Then ask in your own words, for example "start my CV from inputs/old-cv.pdf" or "tailor my CV
for this posting: <link>". The skills:

| Skill | What it does |
|---|---|
| `cv-ingest` | Reads your old CV, LinkedIn export or JSON Resume, then builds the fact ledger with you, role by role, before writing the CV |
| `cv-fact-check` | Runs the checks, then an adversarial reviewer that tries to refute every claim; you settle each finding |
| `cv-tailor` | Maps a job posting's requirements to your facts, writes an overlay for it, builds and reviews it, and names the gaps honestly |
| `cv-presence-audit` | Compares LinkedIn, your site and GitHub with the CV, and writes paste-ready texts with character counts |
| `cv-build` | Explains every gate failure and how to fix it |

The skills follow the open Agent Skills format, so other agents that read `SKILL.md` files can use
them too; `cvcite init` also writes an `AGENTS.md` with the rules into your CV repository.

The plugin holds only its skills and the reviewer agent, in `plugin/`; the skills run the
`cvcite` command line you installed above, and ask before installing it if it is missing.

**LinkedIn is read only.** The audit works from LinkedIn's own data export or a profile saved as
PDF. Nothing signs in to your account or edits it: LinkedIn's terms forbid automated access.

## In GitHub Actions

`cvcite init` writes three workflows into your CV repository:

- `cv.yml` checks, renders and gates every variant on each pull request and each push to `main`.
- `release.yml` (run by hand) publishes the build as a release you can download anywhere. It
  refuses to run in a public repository, because the PDFs carry your contact details.
- `cv-review.yml` runs the claim reviewer on pull requests. It does nothing until you add an
  `ANTHROPIC_API_KEY` secret, and each run is billed to that key. It sends `AGENTS.md`,
  `facts.yaml`, `cv.yaml` (contact details included), the overlays and the diff to Anthropic's
  API; facts in `facts.private.yaml` are never committed, so never sent. The AI can only read
  the CV files, and its review is posted as plain text.

The action runs cvcite from the release you pin, with every Python package taken from a lock
with its hashes and no package built from source. `init` pins it to that release's full commit
SHA. The action refuses to build in a repository that is not private; set `allow-public: "true"`
only for a made-up CV, as this repository does for its sample.

## What gets checked

`cvcite check` (no rendering) and every build:

- dates: format, order, future dates, overlaps, gaps over six months
- every number in a bullet present in a fact of the ledger; none from a `private` fact, and none
  of the `terms` a private fact lists (keep private facts in `facts.private.yaml`, which git
  ignores); every fact's visibility one of `public`, `cv-only` or `private`
- every skill on a skills line backed by a bullet of the same variant
- an overlay never adds a skill the master lacks
- only RenderCV's built-in themes, and no render settings that move files: a custom theme runs
  code from the repository
- no TODO, no banned character (em dashes by default), no RenderCV trap
- privacy: no photo, date of birth, nationality, marital status, street address, identity or bank
  number, or WhatsApp link

The gate, on every PDF:

- the extractors agree on the words and their order, and every bullet appears whole in each
- no word hyphenated across a line by the typesetter
- no text layer shattered into single words
- every glyph plainly filled, in a colour with at least 4.5:1 contrast on white
- the page count matches the budget in `cvcite.toml`

Each check has a test that plants the defect and proves the check fails on it.

## Commands

| Command | What it does |
|---|---|
| `cvcite init [--sample]` | Creates a CV repository |
| `cvcite check` | The checks above, without rendering |
| `cvcite build [variant...]` | Check, render and gate; `-v` prints the full gate report |
| `cvcite gate <pdf> [yaml]` | Gates one PDF |
| `cvcite package` | Zips the build with checksums, as a release does |
| `cvcite ingest <file...>` | Text or data out of a CV (PDF, DOCX, ODT, HTML, Markdown), a LinkedIn export or a JSON Resume |
| `cvcite compare --linkedin <zip>` | The CV's roles against a LinkedIn export: titles and dates |
| `cvcite doctor` | Checks the toolchain |

## How it renders

[RenderCV](https://github.com/rendercv/rendercv) turns the YAML into [Typst](https://typst.app)
and then into the PDF. cvcite renders with ligatures and kerning off: with ligatures on, one
extractor lost every word containing "ff", "ffi" or "ffl", and with kerning on, another read a
bold "Airflow" as two words. It also ships the one Typst package RenderCV's template imports and
switches off RenderCV's check for a newer release (a PyPI request made without verifying TLS),
so a render makes no network request and writes nothing outside the build.

## Development

```sh
uv venv --python 3.13 && uv pip install -e ".[test]"
.venv/bin/python -m pytest
```

## Licence

MIT. RenderCV is MIT-licensed; the vendored Typst package `fontawesome` 0.6.0 is MIT-licensed,
with its licence in `src/cvcite/vendor/`.
