"""Database model mixins for shared functionality."""


class ProgressTrackingMixin:
    """Mixin for models that track progress of a task.

    Requires the model to have these attributes:
    - completed_paragraphs: int
    - total_paragraphs: int
    - progress: float (0-100 scale, percentage)
    """

    completed_paragraphs: int
    total_paragraphs: int
    progress: float

    def update_progress(self) -> None:
        """Update progress percentage based on completed paragraphs.

        Progress is stored as a percentage (0-100), not a ratio (0-1).
        """
        if self.total_paragraphs > 0:
            self.progress = (self.completed_paragraphs / self.total_paragraphs) * 100.0

