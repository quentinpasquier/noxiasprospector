"""Tests for the Pappers HTML parser."""

from __future__ import annotations

from app.enrichment.pappers import parse_pappers_html


def test_parse_triplets_picks_most_recent() -> None:
    html = """
    {"data":[
      {"annee":2021,"chiffre_affaires":1000000,"resultat":50000},
      {"annee":2023,"chiffre_affaires":1500000,"resultat":80000},
      {"annee":2022,"chiffre_affaires":1200000,"resultat":60000}
    ]}
    """
    data = parse_pappers_html(html)
    assert data.financials_year == 2023
    assert data.revenue_eur == 1500000
    assert data.profit_eur == 80000


def test_parse_triplet_with_nulls() -> None:
    html = '"annee":2024,"chiffre_affaires":null,"resultat":-5000'
    data = parse_pappers_html(html)
    assert data.financials_year == 2024
    assert data.revenue_eur is None
    assert data.profit_eur == -5000


def test_textual_revenue_fallback() -> None:
    html = "<p>Le chiffre d'affaires était inférieur à 100 000 € en 2023.</p>"
    data = parse_pappers_html(html)
    assert data.revenue_eur == 100000


def test_employees_count_picks_most_recent() -> None:
    html = '"annee":2020,"effectif":5 "annee":2024,"effectif":12 "annee":2022,"effectif":8'
    data = parse_pappers_html(html)
    assert data.employees_count == 12


def test_no_data_returns_empty() -> None:
    data = parse_pappers_html("<html>nothing useful</html>")
    assert data.revenue_eur is None
    assert data.profit_eur is None
    assert data.financials_year is None
    assert data.employees_count is None
    assert data.has_financials is False
