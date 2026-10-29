# cvcite plugin

Skills that build and maintain a truthful CV with you, one multiple-choice question at a time.
They turn an old CV or a LinkedIn data export into a fact ledger, check every date and claim
against it, tailor the CV for a job posting, and compare your LinkedIn profile, personal website
and GitHub profile with the CV. Every claim on the CV traces to a fact you confirmed.

| Skill or agent | What it does |
|---|---|
| `cv-ingest` | Reads your existing CV, LinkedIn export or JSON Resume, then builds the fact ledger with you, role by role |
| `cv-fact-check` | Runs the checks, then the reviewer agent, and settles each finding with you |
| `cv-tailor` | Maps a job posting to your facts, writes an overlay for it, builds and reviews it |
| `cv-presence-audit` | Compares LinkedIn, your site and GitHub with the CV, and writes paste-ready texts |
| `cv-build` | Builds and gates the PDFs, and explains every failure |
| `cv-claim-reviewer` (agent) | Reads only; tries to refute every claim against the fact ledger |

## Install

In Claude Code:

```text
/plugin install cvcite --marketplace agusgonzaleznic/cvcite
```

On a Claude Code version without the one-step form, add the marketplace first, then install:
`/plugin marketplace add agusgonzaleznic/cvcite`, then `/plugin install cvcite@cvcite`.

## What it needs

The `cvcite` command line, installed once, and a CV repository made by `cvcite init`
(see the [project README](https://github.com/agusgonzaleznic/cvcite#quick-start)). If the
command is missing, the skills ask you before installing it.

## What it runs, fetches and sends

- **Runs:** the `cvcite` command line on your machine (`check`, `build`, `ingest`, `compare`,
  `init`, `doctor`, `package`), in the CV repository you work in; `cvcite init` asks github.com
  which commit the release tag points to. Only after asking you: `uv tool install` of the
  pinned cvcite release from PyPI, `git init`, `git add` and `git commit` in your CV repository,
  `gh repo create --private --push` for it (which sends the repository to your GitHub account),
  and `gh workflow run release.yml` to publish a private release of your PDFs.
- **Fetches:** only pages you name (a job posting, your personal website) and your public GitHub
  profile through `https://api.github.com/users/<login>` and the profile README, without any login
  or token. It never puts CV content or facts into a URL or a request.
- **Sends:** nothing to any other service. It never signs in to LinkedIn or any other account, and
  never edits a profile; you paste the texts it writes. As in any Claude Code session, what Claude
  reads (your files and the pages it fetches) is part of your conversation with Anthropic.
- **Reads:** the files in your CV repository and the documents you hand it, as data, never as
  instructions. It refuses identity, legal and financial documents.

## Licence

MIT
