---
name: cv-presence-audit
description: Check that a person's LinkedIn profile, personal website and GitHub profile agree with their cv-builder CV and fact ledger, recommend improvements, and write paste-ready profile texts with character counts. Read only: works from the LinkedIn data export or profile PDF, public web pages and the GitHub API, and never signs in to or edits any account. Use when someone asks to optimise LinkedIn, check their online presence, or make their profiles consistent with their CV.
---

# Audit LinkedIn, the personal site and GitHub against the CV

Recruiters read all three. A title, a date or a number that differs between them reads as a
mistake at best. The CV's fact ledger is the reference: a profile may say less than the CV,
never something different, and never a fact the ledger marks `cv-only` or `private`.

**Read only, always.** Do not sign in to LinkedIn or any other account, do not drive a browser
on them, and do not automate edits: LinkedIn's terms forbid automated access, and accounts get
restricted for it. The person pastes the texts themselves.

## Before you start

Work in the CV repository; read its `AGENTS.md`, `facts.yaml` and `cv.yaml`. Ask with the
AskUserQuestion tool when you have it (one decision per question, two to four options, your
recommendation first and marked "(Recommended)"); otherwise one numbered question at a time.
Ask for: the LinkedIn data export, the personal site's address, and the GitHub username. Any of
the three may be skipped.

How the person gets their LinkedIn data, on a computer: Me, Settings & Privacy, Data privacy,
"Download your data", pick the categories, request the archive. The picked categories arrive
within minutes. What the export does not hold: which skills are linked to which role, the top
skills, and any secondary-language profile; ask for those as text. A profile saved as PDF ("More"
in the intro card, "Save to PDF") works only for English profiles and lists few skills.

## 1. Gather

- **LinkedIn:** `cv-builder ingest <export.zip> --out inputs/extracted` gives the profile,
  positions, education, skills, certifications and languages as JSON (private fields dropped).
  `cv-builder compare --linkedin <export.zip>` lists every role whose title or dates differ, and
  roles that exist on only one side. A profile PDF gives the visible text when there is no export.
- **Website:** fetch the pages that describe the person (home, about, CV, projects). Note every
  title, employer, date, number and claim.
- **GitHub:** `gh api users/<login>` (name, bio, company, location, blog), the profile README
  (repository `<login>/<login>`), and the pinned repositories.

## 2. Compare

Build one table: each fact (current title, each role's title, employer and dates, location,
headline claims, numbers, certifications, education) against the CV, LinkedIn, the site and
GitHub, with a verdict: *same*, *says less* (fine), *differs* (fix), *not in the ledger* (ask),
*leaks a cv-only or private fact* (fix first).

For each *differs*, ask which side is right. The fix goes into the ledger first if the CV was
wrong, then into the CV, then into the profile texts.

## 3. Recommend

LinkedIn, checked against the export. LinkedIn publishes few of its limits; these are the ones
in common use, so check the editor when a count is close: the headline (about 220 characters;
the target title and the two or three terms recruiters search for, first), the About section
(2,600 characters; first person, short paragraphs; the first lines are what shows before "see
more"), each position's title (100) and description (2,000), skills (up to 100; real skills, not
phrases; each ticked on the roles where it was used; up to five top skills, set from the About
editor), certifications with issuer and year, the same job titles and months as the CV, and a
secondary-language profile kept in step with the primary one (LinkedIn does not translate it).
Open to Work has two settings: recruiters only, or everyone (with the photo frame); the person
chooses.

Website and GitHub: the same current title and headline as the CV, no outdated role, and a short
bio with a link to the site or LinkedIn.

## 4. Write the texts

Write `profiles/linkedin.md` (and `profiles/website.md`, `profiles/github.md` if needed) with
every text ready to paste, each with its character count and limit. Only ledger facts with
`visibility: public`. Show them to the person section by section and apply their edits; when
they rewrite something, keep their wording.

## 5. Verify after they paste

When the person says they have updated the profiles, check again from fresh material: a new
LinkedIn export or profile PDF, the live site, the GitHub API. Check every field, not only the
ones just edited: on LinkedIn, saving one section (a role in a secondary language, for example)
can reset another (that language's headline). Report what now matches and what does not.
