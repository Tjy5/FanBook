from __future__ import annotations

import re

from backend.domain.models import Segment


class ContentFilter:
    _url_only_re = re.compile(r"^https?://\S+$", re.IGNORECASE)
    _punctuation_only_re = re.compile(r"^[\W_]+$", re.UNICODE)
    _numeric_only_re = re.compile(r"^\d+$")
    _page_marker_re = re.compile(
        r"^(?:"
        r"(?:page|p(?:g)?\.?)\s*\d+"
        r"|"
        r"\d+\s*(?:/|-|\u2013)\s*\d+"
        r")$",
        re.IGNORECASE,
    )
    _roman_numeral_marker_re = re.compile(
        r"^(?=[ivxlcdm]{2,}\.?$)[ivxlcdm]+\.?$",
        re.IGNORECASE,
    )
    _href_anchor_fragment_re = re.compile(
        r"^[^\s]+\.(?:xhtml|html|htm|xml|ncx|opf)#[A-Za-z0-9][A-Za-z0-9._:-]*$",
        re.IGNORECASE,
    )
    _nav_anchor_like_re = re.compile(
        r"^(?:#)?[A-Za-z0-9]+(?:[-_.:][A-Za-z0-9]+)+$"
    )

    def should_translate_text(self, text: str) -> bool:
        normalized = text.strip()
        if not normalized:
            return False
        if self._url_only_re.fullmatch(normalized):
            return False
        if self._punctuation_only_re.fullmatch(normalized):
            return False
        if self._numeric_only_re.fullmatch(normalized):
            return False
        if self._page_marker_re.fullmatch(normalized):
            return False
        if self._roman_numeral_marker_re.fullmatch(normalized):
            return False
        if self._href_anchor_fragment_re.fullmatch(normalized):
            return False
        return True

    def should_translate_segment(self, segment: Segment) -> bool:
        normalized = segment.source_text.strip()
        if not self.should_translate_text(normalized):
            return False
        if (
            (segment.extra.is_nav or segment.extra.is_ncx)
            and self._nav_anchor_like_re.fullmatch(normalized)
        ):
            return False
        return True
