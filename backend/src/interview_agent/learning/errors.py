class LearningConflictError(RuntimeError):
    code = "learning_conflict"


class VersionConflictError(LearningConflictError):
    code = "version_conflict"

    def __init__(self, *, expected: int, current: int) -> None:
        self.expected = expected
        self.current = current
        super().__init__(f"task version conflict: expected {expected}, current {current}")


class IdempotencyConflictError(LearningConflictError):
    code = "idempotency_conflict"
