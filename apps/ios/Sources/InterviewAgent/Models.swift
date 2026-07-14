import Foundation

enum InterviewMode: String, Codable {
    case interviewer
    case candidate
}

enum Industry: String, Codable, CaseIterable {
    case internet
    case aiApplication = "ai_application"
    case ecommerce
    case fintech
    case enterpriseSaas = "enterprise_saas"
}

struct HealthResponse: Codable {
    let status: String
    let embeddingServiceURL: String?
    let authRequired: Bool?

    enum CodingKeys: String, CodingKey {
        case status
        case embeddingServiceURL = "embedding_service_url"
        case authRequired = "auth_required"
    }
}

struct AuthTokenResponse: Codable {
    let accessToken: String
    let tokenType: String
    let expiresAt: Int
    let tenantID: String
    let userID: String
    let platform: String
    let displayName: String
    let trialUsesRemaining: Int?
    let creditBalance: String?

    enum CodingKeys: String, CodingKey {
        case accessToken = "access_token"
        case tokenType = "token_type"
        case expiresAt = "expires_at"
        case tenantID = "tenant_id"
        case userID = "user_id"
        case platform
        case displayName = "display_name"
        case trialUsesRemaining = "trial_uses_remaining"
        case creditBalance = "credit_balance"
    }
}

struct AccountResponse: Codable {
    let tenantID: String
    let userID: String
    let displayName: String
    let email: String?
    let platform: String
    let trialUsesRemaining: Int
    let creditBalance: String
    let creditBalanceMicros: Int

    enum CodingKeys: String, CodingKey {
        case tenantID = "tenant_id"
        case userID = "user_id"
        case displayName = "display_name"
        case email
        case platform
        case trialUsesRemaining = "trial_uses_remaining"
        case creditBalance = "credit_balance"
        case creditBalanceMicros = "credit_balance_micros"
    }
}

struct IndustryOption: Codable, Identifiable {
    var id: String { value }
    let value: String
    let label: String
    let description: String
    let productionSignals: [String]
    let recommendedFocusAreas: [String]

    enum CodingKeys: String, CodingKey {
        case value
        case label
        case description
        case productionSignals = "production_signals"
        case recommendedFocusAreas = "recommended_focus_areas"
    }
}

struct CreateSessionRequest: Codable {
    var offline: Bool = false
    var webSearch: Bool = false
    var mode: InterviewMode = .interviewer
    var industry: String = Industry.internet.rawValue
    var targetRole: String = "AI 应用工程师"
    var seniority: String = "高级"
    var interviewGoal: String = "请基于我的简历和 AI 项目经历进行真实面试。"
    var focusAreas: [String] = ["简历项目深挖", "RAG / Agent 生产化", "评测、上线、安全与观测"]
    var resumeID: String?

    enum CodingKeys: String, CodingKey {
        case offline
        case webSearch = "web_search"
        case mode
        case industry
        case targetRole = "target_role"
        case seniority
        case interviewGoal = "interview_goal"
        case focusAreas = "focus_areas"
        case resumeID = "resume_id"
    }
}

struct ChatResponse: Codable {
    let sessionID: String
    let message: String
    let completed: Bool
    let fallbackUsed: Bool
    let guardrails: [String]

    enum CodingKeys: String, CodingKey {
        case sessionID = "session_id"
        case message
        case completed
        case fallbackUsed = "fallback_used"
        case guardrails
    }
}

struct ChatMessage: Identifiable, Equatable {
    enum Role {
        case user
        case agent
        case system
    }

    let id = UUID()
    let role: Role
    let text: String
}

struct StreamEvent {
    let event: String
    let data: [String: Any]
}
