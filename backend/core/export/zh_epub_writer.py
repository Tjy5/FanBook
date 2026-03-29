from __future__ import annotations

from backend.core.export.exporter import BaseEpubWriter


class ZHEpubWriter(BaseEpubWriter):
    def __init__(self) -> None:
        super().__init__(bilingual=False)
