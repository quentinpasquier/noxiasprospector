"""Prospect scoring — a pure-function module (no I/O, easy to test).

The formula matches the May 2026 POC documented in the spec:

- 40 points proportional to the Google rating (out of 5)
- 30 points proportional to the review count, capped at 100 reviews
- 20 points if the prospect has a website
- 10 points if a phone number is known

Total range is 0-100. Labels follow the same mapping as the POC:

- ``>= 75`` → Hot
- ``>= 55`` → Warm
- ``>= 35`` → Cold
- else      → À qualifier
"""

from __future__ import annotations

from app.db.models import ProspectLabel


def score_prospect(
    *,
    rating: float | None,
    reviews_count: int | None,
    has_website: bool,
    has_phone: bool,
) -> int:
    """Return a 0-100 prospecting score.

    Args:
        rating: Google Maps rating (0-5) or ``None`` if unknown.
        reviews_count: Number of reviews; capped at 100.
        has_website: Whether the prospect has a public website.
        has_phone: Whether a phone number was detected.

    Returns:
        Integer score, clamped to ``[0, 100]``.
    """
    total = 0.0
    if rating is not None and rating > 0:
        total += (rating / 5) * 40
    if reviews_count is not None and reviews_count > 0:
        total += min(reviews_count, 100) / 100 * 30
    if has_website:
        total += 20
    if has_phone:
        total += 10
    return max(0, min(100, round(total)))


def label_for(score: int) -> ProspectLabel:
    """Return the label corresponding to a score."""
    if score >= 75:
        return ProspectLabel.HOT
    if score >= 55:
        return ProspectLabel.WARM
    if score >= 35:
        return ProspectLabel.COLD
    return ProspectLabel.UNQUALIFIED
