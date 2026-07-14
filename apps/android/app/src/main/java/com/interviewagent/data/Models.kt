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

data class CreateSessionRequest(
    val offline: Boolean = true,
    val webSearch: Boolean = false,
    val mode: String = "interviewer",
    val industry: String = "internet",
    val targetRole: String = "AI 应用工程师",
    val seniority: String = "高级",
    val interviewGoal: String = "请基于我的简历和 AI 项目经历进行真实面试。",
    val focusAreas: List<String> = listOf("简历项目深挖", "RAG / Agent 生产化", "评测、上线、安全与观测")
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
