from __future__ import annotations

from backend.core.export.exporter import BaseEpubWriter


class BilingualEpubWriter(BaseEpubWriter):
    def __init__(self) -> None:
        super().__init__(bilingual=True)
