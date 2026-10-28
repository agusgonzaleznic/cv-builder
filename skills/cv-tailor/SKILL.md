---
name: cv-tailor
description: Position a cv-builder CV for a specific job posting or kind of role, by writing an overlay (headline, summary, bolded words, skills line, bullets to drop) from facts the person already confirmed, then building, gating and reviewing it. Use when someone shares a job ad or link, asks to frame their CV for a role, or wants a new variant.
---

# Tailor the CV for a role

Tailoring changes emphasis, never facts. An overlay may choose what to lead with and what to
drop; it may not add anything the ledger does not hold. A gap stays a gap: name it to the person,
never paper over it.

## Before you start

Work in the CV repository; read its `AGENTS.md` (the truth rules bind) and `facts.yaml`. Ask with
the AskUserQuestion tool when you have it (one decision per question, two to four options, your
recommendation first and marked "(Recommended)"); otherwise one numbered question at a time.

## 1. Read the posting

Get the posting as text (fetch the link, or ask them to paste it). Extract, in the posting's own
words:

- the title and level, the team and who the role reports to;
- must-haves and nice-to-haves, separately;
- the keywords a recruiter or an applicant tracking system will search for, exactly as written
  (search matches only the form typed: "Certified Public Accountant" and "CPA" are different);
- signals about scope: team size, budget, regions, stage of company, on-call, travel;
- terms that mean something specific in that market or industry (ask if unsure).

Ask whether this is a one-off application or a kind of role they will apply to again: the first
gets `variants/<company>-<role>.yaml`, the second a reusable name such as `variants/team-lead.yaml`.

## 2. Map requirements to evidence

For each must-have, find the ledger facts that prove it. Show the person a table: requirement,
the facts that back it, and the gaps. For each gap ask: *a fact I have not recorded yet* (then
record it with its source, through the ledger, before using it), or *a real gap* (then leave it
out, and suggest how to address it in a cover letter or the interview). Never stretch an adjacent
fact to cover a requirement.

## 3. Write the overlay

Start from an existing overlay if one is close. Then:

- **Headline:** the target title in the posting's words, if it is honest for their level.
- **Summary:** four to six lines: level and domain, the strongest scope proof for this role, the
  pattern they are hired for, the role they want. No percentages in the summary.
- **Bold keywords:** a few phrases the posting searches for that the bullets contain. Never a word
  that also appears in a title or company field, never a bare number, never a word followed by a
  semicolon, never a ubiquitous word ("Excel", "SQL"): bold glyphs are wider and can push the CV
  onto another page.
- **Skills line:** narrow the master's line to what this role values and the variant's bullets
  back. Never add a skill the master lacks.
- **`_omit`:** drop the bullets least relevant to this role until the page budget fits. Prefer
  dropping to rewording; rewording a fact belongs in the master.

## 4. Build, gate, review

Run `cv-builder build <variant>`. It must reach the page budget with GATE PASSED; if it runs
long, omit more, or tighten bullets in the master (with the person) and rebuild every variant.
Then run the `cv-claim-reviewer` agent on the new overlay and settle its findings with the person
as the cv-fact-check skill does.

## 5. Hand over

Tell them which file to send (`build/<variant>/<send name>`, without renaming it: the name is the
same in every variant on purpose, so recruiters cannot tell variants exist), the requirements it
covers and with which bullet, and the honest gaps. Offer a short note for the cover letter on the
gaps, written in their voice.
