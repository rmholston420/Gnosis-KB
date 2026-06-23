"""Unit tests for the MOC generator helper — _build_moc_markdown."""

from __future__ import annotations

from gnosis.routers.ai import _build_moc_markdown
from gnosis.schemas.ai import MocSection


def _make_sections() -> list[MocSection]:
    return [
        MocSection(
            heading="Signal Acquisition",
            summary="Notes on EEG hardware and electrode setup.",
            wikilinks=["EEG Electrode Placement", "Amplifier Selection Guide"],
        ),
        MocSection(
            heading="Preprocessing",
            summary="Filtering, artefact removal, and epoching.",
            wikilinks=["Bandpass Filtering Principles", "ICA Artefact Removal"],
        ),
    ]


def test_markdown_has_frontmatter():
    md = _build_moc_markdown("EEG", "MOC — EEG", _make_sections())
    assert md.startswith("---\n")
    assert "type: moc" in md
    assert "title: MOC — EEG" in md


def test_markdown_h1_title():
    md = _build_moc_markdown("EEG", "MOC — EEG", _make_sections())
    assert "# MOC — EEG" in md


def test_markdown_h2_sections():
    md = _build_moc_markdown("EEG", "MOC — EEG", _make_sections())
    assert "## Signal Acquisition" in md
    assert "## Preprocessing" in md


def test_markdown_wikilinks_formatted():
    md = _build_moc_markdown("EEG", "MOC — EEG", _make_sections())
    assert "[[EEG Electrode Placement]]" in md
    assert "[[ICA Artefact Removal]]" in md


def test_markdown_section_summaries_present():
    md = _build_moc_markdown("EEG", "MOC — EEG", _make_sections())
    assert "Notes on EEG hardware" in md
    assert "Filtering, artefact removal" in md


def test_markdown_tags_contain_topic_slug():
    md = _build_moc_markdown("EEG Signals", "MOC — EEG Signals", _make_sections())
    assert "eeg-signals" in md


def test_empty_sections_fallback():
    """A MOC with no sections should still produce valid Markdown."""
    md = _build_moc_markdown("Test", "MOC — Test", [])
    assert "# MOC — Test" in md
    assert "---" in md
