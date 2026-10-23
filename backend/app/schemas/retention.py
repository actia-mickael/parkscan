from pydantic import BaseModel


class RetentionReportRead(BaseModel):
    dry_run: bool
    scanned: int
    images_deleted: int
    passages_anonymized: int
    reviews_rejected: int
    errors: int
    sites: dict[str, int]
