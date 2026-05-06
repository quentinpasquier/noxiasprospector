"""Tests for social-profile extraction."""

from __future__ import annotations

from app.enrichment.socials import extract_socials


def test_extract_clean_handles() -> None:
    html = """
    <footer>
      <a href="https://facebook.com/acme.travaux">Facebook</a>
      <a href="https://www.instagram.com/acme_travaux/">Instagram</a>
      <a href="https://fr.linkedin.com/company/acme-travaux">LinkedIn</a>
    </footer>
    """
    profiles = extract_socials(html)
    assert profiles.facebook_url == "https://facebook.com/acme.travaux"
    assert profiles.instagram_url == "https://instagram.com/acme_travaux"
    assert profiles.linkedin_url == "https://linkedin.com/acme-travaux"


def test_skip_share_widgets() -> None:
    html = """
    <a href="https://facebook.com/sharer/sharer.php">Share</a>
    <a href="https://www.facebook.com/plugins/like.php">Like</a>
    <a href="https://facebook.com/dialog/feed?...">Dialog</a>
    <a href="https://www.facebook.com/acme.travaux">Profile</a>
    """
    profiles = extract_socials(html)
    assert profiles.facebook_url == "https://facebook.com/acme.travaux"


def test_skip_instagram_posts_and_reels() -> None:
    html = """
    <a href="https://instagram.com/p/AbCdEf">Post</a>
    <a href="https://instagram.com/reel/XyZw">Reel</a>
    <a href="https://instagram.com/stories/foo">Stories</a>
    <a href="https://www.instagram.com/acme_travaux">Profile</a>
    """
    profiles = extract_socials(html)
    assert profiles.instagram_url == "https://instagram.com/acme_travaux"


def test_linkedin_in_or_school_or_company() -> None:
    html_a = '<a href="https://linkedin.com/in/jdupont">In</a>'
    html_b = '<a href="https://linkedin.com/school/insa-lyon">School</a>'
    html_c = '<a href="https://linkedin.com/company/acme">Company</a>'
    assert extract_socials(html_a).linkedin_url == "https://linkedin.com/jdupont"
    assert extract_socials(html_b).linkedin_url == "https://linkedin.com/insa-lyon"
    assert extract_socials(html_c).linkedin_url == "https://linkedin.com/acme"


def test_no_match_returns_empty() -> None:
    profiles = extract_socials("<html><body>no socials here</body></html>")
    assert profiles.facebook_url is None
    assert profiles.instagram_url is None
    assert profiles.linkedin_url is None


def test_filters_bad_handles() -> None:
    """Bare ``facebook.com/fr`` and similar paths must be dropped."""
    html = '<a href="https://facebook.com/fr">FR</a>'
    assert extract_socials(html).facebook_url is None
