"""Tests for the scoring formula."""

from __future__ import annotations

import pytest
from app.db.models import ProspectLabel
from app.enrichment.scoring import label_for, score_prospect


def test_score_all_signals_max() -> None:
    s = score_prospect(rating=5.0, reviews_count=200, has_website=True, has_phone=True)
    assert s == 100


def test_score_no_signals() -> None:
    s = score_prospect(rating=None, reviews_count=None, has_website=False, has_phone=False)
    assert s == 0


def test_score_partial() -> None:
    # rating 4 → 32, reviews 50 → 15, site → 20, no phone → 0  -> 67
    s = score_prospect(rating=4.0, reviews_count=50, has_website=True, has_phone=False)
    assert s == 67


@pytest.mark.parametrize(
    ("score", "expected"),
    [
        (100, ProspectLabel.HOT),
        (75, ProspectLabel.HOT),
        (74, ProspectLabel.WARM),
        (55, ProspectLabel.WARM),
        (54, ProspectLabel.COLD),
        (35, ProspectLabel.COLD),
        (34, ProspectLabel.UNQUALIFIED),
        (0, ProspectLabel.UNQUALIFIED),
    ],
)
def test_label_for_thresholds(score: int, expected: ProspectLabel) -> None:
    assert label_for(score) is expected


def test_score_clamps_low_rating() -> None:
    s = score_prospect(rating=0.0, reviews_count=0, has_website=False, has_phone=False)
    assert s == 0


def test_reviews_count_capped_at_100() -> None:
    s_capped = score_prospect(rating=None, reviews_count=10_000, has_website=False, has_phone=False)
    s_at_cap = score_prospect(rating=None, reviews_count=100, has_website=False, has_phone=False)
    assert s_capped == s_at_cap == 30
