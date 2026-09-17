from interview_agent.learning.command_service import LearningCommandService

# Compatibility export for Phase 1 callers. New code should use LearningCommandService.
LearningHarnessService = LearningCommandService

__all__ = ["LearningHarnessService"]
