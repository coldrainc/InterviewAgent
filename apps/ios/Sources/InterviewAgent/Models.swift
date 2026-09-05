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

struct UserSettingsResponse: Codable {
    let defaultInterviewMode: String

    enum CodingKeys: String, CodingKey {
        case defaultInterviewMode = "default_interview_mode"
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

struct ResumeRecord: Codable, Identifiable, Equatable {
    let id: String
    let filename: String
    let fileType: String
    let summary: String
    let text: String
    let truncated: Bool
    let createdAt: String
    let updatedAt: String

    enum CodingKeys: String, CodingKey {
        case id
        case filename
        case fileType = "file_type"
        case summary
        case text
        case truncated
        case createdAt = "created_at"
        case updatedAt = "updated_at"
    }
}

struct ResumeImportRequest: Codable {
    let filename: String
    let contentBase64: String
    let sourcePath: String?

    enum CodingKeys: String, CodingKey {
        case filename
        case contentBase64 = "content_base64"
        case sourcePath = "source_path"
    }
}

struct PracticeCategory: Codable, Identifiable, Equatable {
    var id: String { value }
    let value: String
    let label: String
    let description: String
    let subjects: [String]
}

struct PracticeQuestion: Codable, Identifiable, Equatable {
    let id: String
    let practiceCategory: String
    let examYear: Int
    let examName: String
    let subject: String
    let questionType: String
    let prompt: String
    let choices: [String]
    let answer: String?
    let explanation: String?
    let difficulty: String

    enum CodingKeys: String, CodingKey {
        case id
        case practiceCategory = "practice_category"
        case examYear = "exam_year"
        case examName = "exam_name"
        case subject
        case questionType = "question_type"
        case prompt
        case choices
        case answer
        case explanation
        case difficulty
    }
}

struct PracticeQuestionListResponse: Codable {
    let items: [PracticeQuestion]
    let total: Int
    let limit: Int
    let offset: Int
}

struct PracticeAttemptRequest: Codable {
    let questionID: String
    let answer: String
    let elapsedSeconds: Int?

    enum CodingKeys: String, CodingKey {
        case questionID = "question_id"
        case answer
        case elapsedSeconds = "elapsed_seconds"
    }
}

struct PracticeAttemptResponse: Codable {
    let questionID: String
    let correct: Bool?
    let score: Int
    let feedback: String
    let referenceAnswer: String
    let explanation: String
    let suggestions: [String]
    let elapsedSeconds: Int?

    enum CodingKeys: String, CodingKey {
        case questionID = "question_id"
        case correct
        case score
        case feedback
        case referenceAnswer = "reference_answer"
        case explanation
        case suggestions
        case elapsedSeconds = "elapsed_seconds"
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

struct SessionSummary: Codable, Identifiable, Equatable {
    let id: String
    let resumeID: String?
    let mode: String
    let industry: String
    let candidateName: String
    let targetRole: String
    let seniority: String
    let status: String
    let createdAt: String
    let updatedAt: String

    enum CodingKeys: String, CodingKey {
        case id
        case resumeID = "resume_id"
        case mode
        case industry
        case candidateName = "candidate_name"
        case targetRole = "target_role"
        case seniority
        case status
        case createdAt = "created_at"
        case updatedAt = "updated_at"
    }
}

struct SessionDetail: Codable {
    let id: String
    let state: InterviewStatePayload
    let turns: [TurnPayload]
}

struct InterviewStatePayload: Codable {
    let completed: Bool?
}

struct TurnPayload: Codable {
    let stage: String?
    let interviewer: String?
    let candidate: String?
}

struct DeleteResponse: Codable {
    let deleted: Bool
}

struct ImportResultResponse: Codable {
    let created: Int
    let updated: Int
    let total: Int
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
