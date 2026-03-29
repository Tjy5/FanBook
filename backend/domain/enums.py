from enum import StrEnum


class SegmentType(StrEnum):
    PARAGRAPH = "paragraph"
    TITLE = "title"
    IMAGE_CAPTION = "image_caption"
    FOOTNOTE = "footnote"
    LIST_ITEM = "list_item"
    OTHER = "other"


class SegmentStatus(StrEnum):
    PENDING = "pending"
    TRANSLATED = "translated"
    FAILED = "failed"
    SKIPPED = "skipped"


class TranslationJobStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELED = "canceled"


class ExportArtifactKind(StrEnum):
    ZH = "zh"
    BILINGUAL = "bilingual"
    CONSISTENCY_REPORT = "consistency_report"


class ExportArtifactStatus(StrEnum):
    PENDING = "pending"
    READY = "ready"
    FAILED = "failed"
