---
name: cv-fact-check
description: Check every date and claim of a cvcite CV against its fact ledger and the truth rules, with an adversarial reviewer, and settle each finding with the person. Use before sending a CV, after editing it, when someone asks whether their CV overclaims, or to validate dates and claims.
---

# Fact-check a CV

A CV fails in an interview, not on the page: one claim the person cannot defend under questioning
costs more than any missing keyword. This skill finds those claims before a reader does.

## Before you start

Work in the CV repository (`cvcite.toml` at its root). Read its `AGENTS.md`: the truth rules
there are the standard. Ask with the AskUserQuestion tool when you have it (one decision per
question, two to four options, your recommendation first and marked "(Recommended)"); otherwise
one numbered question at a time.

## 1. The deterministic pass

Run `cvcite check`. It covers what a program can decide: dates (format, order, future dates,
overlaps, gaps), every number in a bullet traced to the ledger, numbers that only private facts
hold, skills backed by a bullet, banned characters, RenderCV traps, TODOs, and privacy (photo,
date of birth, nationality, marital status, street address, identity and bank numbers). Fix the
errors with the person before going on; explain each warning and let them decide.

## 2. The judgment pass

Run the `cv-claim-reviewer` agent on the master and on every overlay, giving it the paths of
`cv.yaml`, `variants/`, `facts.yaml` and `AGENTS.md`. It returns only claims it could refute, each
with file, line and evidence. Then add your own read of anything it could not judge:

- **Ownership.** "Built", "designed", "created" claim sole authorship. Where others built
  alongside the person, the honest verb is "led", "collaborated in" or "contributed to". Being
  named in a document is not ownership.
- **Metrics.** Each outcome metric needs a baseline, a timeframe and the person's part, in the
  same bullet. Percentages without a baseline read as invented. Prefer scope facts: they are
  stronger and verifiable.
- **Direction.** For delivery metrics, deployment frequency and lead time go up; change failure
  rate and time to restore go down. A "reduced deployment frequency" is not an achievement.
- **Unfalsifiable claims.** "Zero incidents", "100% uptime", "best in class": cut, or replace with
  what was measured.
- **Status.** Certifications passed, not planned; audits completed, not targeted; products
  launched, not announced. Ongoing work says so in words.
- **Terms that mean two things.** Spell out an acronym once, and check it means what the person
  means to the reader: "PM" is a product manager in one company and a project manager in
  the next.
- **Visibility.** Nothing from a `private` fact on the CV; `cv-only` facts may stay on the CV but
  never on a public profile.
- **Consistency across variants.** Overlays position; they never state a fact the master lacks.

## 3. Settle each finding with the person

One finding per question: quote the claim, say what is wrong in one sentence, and offer concrete
rewrites as options (keep the strongest honest one first and recommended). Options usually look
like: *reword to the honest verb*, *add the baseline and timeframe from fact X*, *drop the
number*, *cut the bullet*, *keep it: I can defend it* (then ask for the source and add it to the
ledger). When two sources disagree, ask which is right; never pick one.

Apply the answers: the ledger first, then `cv.yaml`, then the overlays. Run `cvcite check`
and `cvcite build` again; every variant must reach its page budget with GATE PASSED.

## 4. Report

End with a short list: what changed, what the person chose to keep against advice (and why), and
anything still open. Nothing else.
