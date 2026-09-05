package com.interviewagent.data

data class IndustryOption(
    val value: String,
    val label: String,
    val description: String,
    val productionSignals: List<String> = emptyList(),
    val recommendedFocusAreas: List<String> = emptyList()
)

data class AuthTokenResponse(
    val accessToken: String,
    val expiresAt: Long,
    val tenantId: String,
    val userId: String,
    val platform: String,
    val displayName: String = "",
    val trialUsesRemaining: Int = 0,
    val creditBalance: String = "0"
)

data class AccountResponse(
    val tenantId: String,
    val userId: String,
    val displayName: String,
    val email: String?,
    val platform: String,
    val trialUsesRemaining: Int,
    val creditBalance: String,
    val creditBalanceMicros: Long
)

data class UserSettingsResponse(
    val defaultInterviewMode: String
)

data class PracticeCategory(
    val value: String,
    val label: String,
    val description: String,
    val subjects: List<String> = emptyList()
)

data class PracticeQuestion(
    val id: String,
    val practiceCategory: String,
    val examYear: Int,
    val examName: String,
    val subject: String,
    val questionType: String,
    val prompt: String,
    val choices: List<String> = emptyList(),
    val answer: String?,
    val explanation: String?,
    val difficulty: String
)

data class PracticeQuestionListResponse(
    val items: List<PracticeQuestion>,
    val total: Int,
    val limit: Int,
    val offset: Int
)

data class PracticeAttemptResponse(
    val questionId: String,
    val correct: Boolean?,
    val score: Int,
    val feedback: String,
    val referenceAnswer: String,
    val explanation: String,
    val suggestions: List<String>,
    val elapsedSeconds: Int?
)

data class ImportResultResponse(
    val created: Int,
    val updated: Int,
    val total: Int
)

data class ResumeRecord(
    val id: String,
    val filename: String,
    val fileType: String,
    val summary: String,
    val text: String,
    val truncated: Boolean,
    val createdAt: String,
    val updatedAt: String
)

data class SessionSummary(
    val id: String,
    val resumeId: String?,
    val mode: String,
    val industry: String,
    val candidateName: String,
    val targetRole: String,
    val seniority: String,
    val status: String,
    val createdAt: String,
    val updatedAt: String
)

data class SessionDetail(
    val id: String,
    val turns: List<TurnPayload>
)

data class TurnPayload(
    val interviewer: String?,
    val candidate: String?
)

data class CreateSessionRequest(
    val offline: Boolean = true,
    val webSearch: Boolean = false,
    val mode: String = "interviewer",
    val industry: String = "internet",
    val targetRole: String = "AI 应用工程师",
    val seniority: String = "高级",
    val interviewGoal: String = "请基于我的简历和 AI 项目经历进行真实面试。",
    val focusAreas: List<String> = listOf("简历项目深挖", "RAG / Agent 生产化", "评测、上线、安全与观测"),
    val resumeId: String? = null
)

data class ChatResponse(
    val sessionId: String,
    val message: String,
    val completed: Boolean = false,
    val fallbackUsed: Boolean = false,
    val guardrails: List<String> = emptyList()
)

data class ChatMessage(
    val role: Role,
    val text: String
) {
    enum class Role {
        User,
        Agent,
        System
    }
}

data class StreamEvent(
    val event: String,
    val data: Map<String, Any?>
)
