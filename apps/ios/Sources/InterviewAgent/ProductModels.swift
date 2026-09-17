import Foundation

struct LearningTask: Codable, Identifiable {
    let id: String
    let title: String
    let taskType: String
    let status: String
    let version: Int
    let done: Bool
    let primaryAction: LearningAction
    let linkPayload: LearningTaskTarget?

    enum CodingKeys: String, CodingKey {
        case id, title, status, version, done
        case taskType = "task_type"
        case primaryAction = "primary_action"
        case linkPayload = "link_payload"
    }
}

struct LearningTaskTarget: Codable {
    let planID: String?
    let dayID: String?
    let taskID: String?
    let category: String?
    let questionID: String?
    let mode: String?
    let focus: String?

    enum CodingKeys: String, CodingKey {
        case category, mode, focus
        case planID = "plan_id"
        case dayID = "day_id"
        case taskID = "task_id"
        case questionID = "question_id"
    }
}

struct LearningAction: Codable {
    let command: String
    let label: String
}

struct LearningTodayResponse: Codable {
    let today: LearningTodaySummary
    let streak: LearningStreak?
    let advice: LearningAdvice?
    let nextBestAction: LearningNextAction?

    enum CodingKeys: String, CodingKey {
        case today, streak, advice
        case nextBestAction = "next_best_action"
    }
}

struct LearningTodaySummary: Codable {
    let tasks: [LearningTask]
    let totalTasks: Int
    let tasksDone: Int

    enum CodingKeys: String, CodingKey {
        case tasks
        case totalTasks = "total_tasks"
        case tasksDone = "tasks_done"
    }
}

struct LearningStreak: Codable { let currentStreak: Int
    enum CodingKeys: String, CodingKey { case currentStreak = "current_streak" }
}
struct LearningAdvice: Codable { let text: String? }
struct LearningNextAction: Codable { let title: String }

struct ReviewPlan: Codable, Identifiable {
    let id: String
    let title: String
    let status: String
    let totalDays: Int?
    let completedTasks: Int?
    let totalTasks: Int?

    enum CodingKeys: String, CodingKey {
        case id, title, status
        case totalDays = "total_days"
        case completedTasks = "completed_tasks"
        case totalTasks = "total_tasks"
    }
}

struct PlanGenerateRequest: Codable {
    let title: String
    let targetRole: String
    let seniority: String
    let totalDays: Int
    let hoursPerDay: Double
    let focusAreas: [String]
    let resumeID: String?
    let useHistory: Bool

    enum CodingKeys: String, CodingKey {
        case title, seniority
        case targetRole = "target_role"
        case totalDays = "total_days"
        case hoursPerDay = "hours_per_day"
        case focusAreas = "focus_areas"
        case resumeID = "resume_id"
        case useHistory = "use_history"
    }
}

struct PlanGenerateResponse: Codable { let planID: String
    enum CodingKeys: String, CodingKey { case planID = "plan_id" }
}
struct CheckinRequest: Codable { let elapsedMinutes: Int; let note: String
    enum CodingKeys: String, CodingKey { case elapsedMinutes = "elapsed_minutes"; case note }
}
struct CheckinResponse: Codable { let streak: LearningStreak? }

struct InterviewKit: Codable, Identifiable {
    let id: String
    let title: String
    let targetRole: String
    let durationMinutes: Int
    let version: Int
    let questions: [InterviewKitQuestion]?

    enum CodingKeys: String, CodingKey {
        case id, title, version, questions
        case targetRole = "target_role"
        case durationMinutes = "duration_minutes"
    }
}
struct InterviewKitQuestion: Codable, Identifiable {
    var id: String { key ?? title }
    let key: String?
    let title: String
}
struct InterviewKitRequest: Codable {
    let title: String
    let targetRole: String
    let seniority: String
    let durationMinutes: Int
    let dimensions: [String]

    enum CodingKeys: String, CodingKey {
        case title, seniority, dimensions
        case targetRole = "target_role"
        case durationMinutes = "duration_minutes"
    }
}
struct LearningCommandRequest: Codable { let action: String; let expectedVersion: Int
    enum CodingKeys: String, CodingKey { case action; case expectedVersion = "expected_version" }
}
struct LearningCommandResponse: Codable { let task: LearningTask }
