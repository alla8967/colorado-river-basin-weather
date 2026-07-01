"""Provide small HTML rendering helpers for static diagnostic reports.

The goal is consistent escaping, tables, and metric cards without introducing a full template system."""

from __future__ import annotations

import html
from collections.abc import Sequence


class TrustedHtml(str):
    """HTML that was intentionally escaped or constructed by report code."""


def trusted_html(value: str) -> TrustedHtml:
    return TrustedHtml(value)


def escape_html(value: object) -> str:
    return html.escape(str(value))


def render_html_value(value: object) -> str:
    """Escape ordinary values while preserving intentionally trusted HTML."""
    if isinstance(value, TrustedHtml):
        return str(value)
    return escape_html(value)


def render_html_table(
    headers: Sequence[object],
    rows: Sequence[Sequence[object]],
) -> str:
    """Render a small escaped HTML table for static research reports."""
    header_html = "".join(f"<th>{escape_html(header)}</th>" for header in headers)
    row_html = "".join(
        "<tr>"
        + "".join(
            f"<td>{render_html_value(value)}</td>"
            for value in row
        )
        + "</tr>"
        for row in rows
    )
    return (
        f"<table><thead><tr>{header_html}</tr></thead>"
        f"<tbody>{row_html}</tbody></table>"
    )


def render_metric_card(
    label: object,
    value: object,
    note: object | None = None,
    *,
    card_class: str = "card",
    label_class: str = "label",
    value_class: str = "value",
    note_class: str = "note",
) -> str:
    """Render the repeated label/value card shape used by HTML reports."""
    note_html = ""
    if note not in (None, ""):
        note_html = f'<div class="{escape_html(note_class)}">{render_html_value(note)}</div>'

    return (
        f'<div class="{escape_html(card_class)}">'
        f'<div class="{escape_html(label_class)}">{render_html_value(label)}</div>'
        f'<div class="{escape_html(value_class)}">{render_html_value(value)}</div>'
        f"{note_html}</div>"
    )
