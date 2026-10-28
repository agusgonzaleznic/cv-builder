"""The no-render checks: each rule has a case that must trip it and a case that must not."""

from __future__ import annotations

import datetime as dt

import pytest

from cv_builder import checks

TODAY = dt.date(2026, 6, 15)
BANNED = (chr(0x2014),)


def role(company, start, end, *bullets, **extra):
    entry = {"company": company, "position": "Engineer", "start_date": start, "end_date": end,
             "highlights": list(bullets)}
    entry.update(extra)
    return entry


def cv(*experience, **sections):
    return {"name": "Test", "sections": {"experience": list(experience), **sections}}


def messages(issues, level=None):
    return " | ".join(i.message for i in issues if level is None or i.level == level)


# ------------------------------------------------------------------------------------------ dates

def test_clean_dates_pass():
    data = cv(role("B", "2021-03", "present"), role("A", "2018-01", "2021-02"))
    assert checks.check_dates(data, TODAY) == []


def test_future_date_fails():
    assert "in the future" in messages(checks.check_dates(cv(role("A", "2027-01", "present")),
                                                          TODAY), "error")


def test_start_after_end_fails():
    assert "after it ends" in messages(checks.check_dates(cv(role("A", "2022-05", "2021-01")),
                                                          TODAY), "error")


def test_bad_format_fails():
    assert "is not YYYY" in messages(checks.check_dates(cv(role("A", "March 2020", "present")),
                                                        TODAY), "error")


def test_quoted_year_warns():
    assert "quoted" in messages(checks.check_dates(cv(role("A", "2015", 2018)), TODAY), "warning")


def test_overlap_and_gap_and_order_warn():
    data = cv(role("A", "2015-01", "2019-06"), role("B", "2019-01", "2020-01"),
              role("C", "2021-06", "present"))
    text = messages(checks.check_dates(data, TODAY), "warning")
    assert "overlaps" in text and "a reader will ask about the gap" in text
    assert "not newest first" in text


def test_year_only_end_does_not_overlap_a_month_start():
    data = cv(role("B", "2018-06", "2022-02"), role("A", 2015, 2018))
    assert "overlaps" not in messages(checks.check_dates(data, TODAY))


def test_promotion_at_same_company_is_not_an_overlap():
    data = cv(role("A", "2021-01", "present"), role("A", "2019-01", "2021-01"))
    assert "overlaps" not in messages(checks.check_dates(data, TODAY))


# ------------------------------------------------------------------------------------- text traps

def test_spaced_hyphen_in_bullet_fails():
    data = cv(role("A", "2020-01", "present", "Built the API - and the docs."))
    assert "RenderCV splits it" in messages(checks.check_text(data, {}, BANNED), "error")


def test_banned_character_and_todo_fail():
    data = cv(role("A", "2020-01", "present", "Shipped it " + chr(0x2014) + " fast.",
                   "TODO: needs a real number"))
    text = messages(checks.check_text(data, {}, BANNED), "error")
    assert "U+2014" in text and "TODO" in text


def test_bold_keyword_in_title_warns():
    data = cv(role("A", "2020-01", "present", "Ran the analytics team.", position="Analytics Lead"))
    assert "asterisks" in messages(checks.check_text(data, {"bold_keywords": ["Analytics"]},
                                                     BANNED), "warning")


# ------------------------------------------------------------------------- skills and the ledger

def test_skill_without_bullet_warns_and_backed_skill_passes():
    data = cv(role("A", "2020-01", "present", "Ran Kafka in production."),
              Skills=[{"label": "Data", "details": "Kafka, Spark (Structured Streaming)"}])
    text = messages(checks.check_skills_backed(data))
    assert "'Spark (Structured Streaming)'" in text and "'Kafka'" not in text


def test_number_without_fact_fails():
    data = cv(role("A", "2020-01", "present", "Cut the bill by 37% for 12 teams."))
    facts = [{"text": "Cut the bill by 37% over a year.", "visibility": "public"}]
    text = messages(checks.check_numbers_in_ledger(data, facts), "error")
    assert "'12'" in text and "'37%'" not in text


def test_private_number_fails():
    data = cv(role("A", "2020-01", "present", "Platform carries GBP 90M a year."))
    facts = [{"text": "Carries GBP 90M a year.", "visibility": "private"}]
    assert "private fact" in messages(checks.check_numbers_in_ledger(data, facts), "error")


def test_years_and_missing_ledger():
    data = cv(role("A", "2020-01", "present", "Passed the exam in 2021."))
    assert checks.check_numbers_in_ledger(data, []) == []
    assert "no fact ledger" in messages(checks.check_numbers_in_ledger(data, None), "warning")


# ------------------------------------------------------------------------------------- privacy

def test_privacy_fields_and_text_fail():
    data = cv(role("A", "2020-01", "present", "Date of birth: 1 May 1990."))
    data.update(photo="me.jpg", location="12 High Street, London")
    text = messages(checks.check_privacy(data), "error")
    assert "a photo" in text and "date of birth" in text and "street address" in text


def test_iban_and_whatsapp_fail():
    data = cv(role("A", "2020-01", "present", "Pay to GB33 BUKB 2020 1555 5555 55.",
                   "Reach me at https://wa.me/441234"))
    text = messages(checks.check_privacy(data), "error")
    assert "IBAN" in text and "WhatsApp" in text


def test_privacy_words_in_running_text_only_warn():
    quiet = cv(role("A", "2020-01", "present", "Built the passport scanning service.",
                    "Ich habe nie aufgegeben."))
    assert checks.check_privacy(quiet) == []
    data = cv(role("A", "2020-01", "present", "Built the date of birth check for sign-ups."))
    issues = checks.check_privacy(data)
    assert not [i for i in issues if i.level == "error"], issues
    assert "never your own date of birth" in messages(issues, "warning")


@pytest.mark.parametrize("text", ["Geburtsdatum: 1.5.1990", "Nationalité : française",
                                  "NIE: X1234567L", "CPF 123.456.789-00",
                                  "Passport number: 123456"])
def test_privacy_labels_with_values_fail(text):
    data = cv(role("A", "2020-01", "present", text))
    assert [i for i in checks.check_privacy(data) if i.level == "error"], text


def test_city_and_country_pass_privacy():
    data = cv(role("A", "2020-01", "present", "Ran the data platform."))
    data["location"] = "London, United Kingdom"
    assert checks.check_privacy(data) == []
