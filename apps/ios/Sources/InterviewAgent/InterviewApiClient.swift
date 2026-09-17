import Foundation

final class InterviewApiClient {
    private let baseURL: URL
    private var token: String?
    private let session: URLSession
    private let encoder: JSONEncoder
    private let decoder: JSONDecoder

    private let onTokenChanged: (String?) -> Void

    private var clientVersion: String {
        Bundle.main.object(forInfoDictionaryKey: "CFBundleShortVersionString") as? String ?? "unknown"
    }

    init(baseURL: URL, token: String?, session: URLSession = .shared, onTokenChanged: @escaping (String?) -> Void = { _ in }) {
        self.baseURL = baseURL
        self.token = token
        self.session = session
        self.encoder = JSONEncoder()
        self.decoder = JSONDecoder()
        self.onTokenChanged = onTokenChanged
    }

    func health() async throws -> HealthResponse {
        try await request(path: "/health")
    }

    func login(email: String, password: String) async throws -> AuthTokenResponse {
        let response: AuthTokenResponse = try await request(path: "/auth/login", method: "POST", body: ["email": email.trimmingCharacters(in: .whitespacesAndNewlines), "password": password.trimmingCharacters(in: .whitespacesAndNewlines), "platform": "ios"])
        token = response.accessToken
        onTokenChanged(response.accessToken)
        return response
    }

    func register(email: String, password: String, displayName: String) async throws -> AuthTokenResponse {
        let response: AuthTokenResponse = try await request(path: "/auth/register", method: "POST", body: ["email": email.trimmingCharacters(in: .whitespacesAndNewlines), "password": password.trimmingCharacters(in: .whitespacesAndNewlines), "display_name": displayName.trimmingCharacters(in: .whitespacesAndNewlines), "platform": "ios"])
        token = response.accessToken
        onTokenChanged(response.accessToken)
        return response
    }

    func logout() {
        token = nil
        onTokenChanged(nil)
    }

    func learningToday() async throws -> LearningTodayResponse { try await request(path: "/learning/today") }

    func commandLearningTask(_ task: LearningTask, action: String) async throws -> LearningTask {
        let response: LearningCommandResponse = try await request(path: "/learning/tasks/\(task.id)/commands", method: "POST", body: LearningCommandRequest(action: action, expectedVersion: task.version), headers: ["Idempotency-Key": "ios-\(UUID().uuidString)"])
        return response.task
    }

    func listReviewPlans(limit: Int = 20, offset: Int = 0) async throws -> [ReviewPlan] { try await request(path: "/review-site/plans?limit=\(limit)&offset=\(offset)") }
    func generateReviewPlan(_ body: PlanGenerateRequest) async throws -> PlanGenerateResponse { try await request(path: "/review-site/planner/generate", method: "POST", body: body) }
    func checkin(planID: String, minutes: Int, note: String) async throws -> CheckinResponse { try await request(path: "/review-site/plans/\(planID)/checkin", method: "POST", body: CheckinRequest(elapsedMinutes: minutes, note: note)) }
    func listInterviewKits(limit: Int = 20, offset: Int = 0) async throws -> [InterviewKit] { try await request(path: "/interviewer-workspace/kits?limit=\(limit)&offset=\(offset)") }
    func createInterviewKit(_ body: InterviewKitRequest) async throws -> InterviewKit { try await request(path: "/interviewer-workspace/kits", method: "POST", body: body) }

    func account() async throws -> AccountResponse {
        try await request(path: "/account")
    }

    func getSettings() async throws -> UserSettingsResponse {
        try await request(path: "/settings")
    }

    func updateDefaultInterviewMode(_ mode: InterviewMode) async throws -> UserSettingsResponse {
        try await request(
            path: "/settings",
            method: "PUT",
            body: ["default_interview_mode": mode.rawValue]
        )
    }

    func recharge(amountCredits: String) async throws -> AccountResponse {
        try await request(
            path: "/account/recharge",
            method: "POST",
            body: [
                "amount_credits": amountCredits,
                "payment_provider": "ios-mock",
                "external_order_id": "ios-\(Int(Date().timeIntervalSince1970 * 1000))"
            ]
        )
    }

    func listIndustries(targetRole: String = "AI 应用工程师") async throws -> [IndustryOption] {
        let encoded = targetRole.addingPercentEncoding(withAllowedCharacters: .urlQueryAllowed) ?? targetRole
        return try await request(path: "/metadata/industries?target_role=\(encoded)")
    }

    func listPracticeCategories() async throws -> [PracticeCategory] {
        try await request(path: "/practice/categories")
    }

    func listPracticeQuestions(category: String, limit: Int = 20, offset: Int = 0) async throws -> PracticeQuestionListResponse {
        let encoded = category.addingPercentEncoding(withAllowedCharacters: .urlQueryAllowed) ?? category
        return try await request(path: "/practice/questions?category=\(encoded)&limit=\(limit)&offset=\(offset)")
    }

    func seedPracticeQuestions() async throws -> ImportResultResponse {
        try await request(path: "/practice/questions/seed", method: "POST")
    }

    func submitPracticeAttempt(questionID: String, answer: String, elapsedSeconds: Int?) async throws -> PracticeAttemptResponse {
        try await request(
            path: "/practice/attempt",
            method: "POST",
            body: PracticeAttemptRequest(questionID: questionID, answer: answer, elapsedSeconds: elapsedSeconds)
        )
    }

    func listResumes(limit: Int = 20, offset: Int = 0) async throws -> [ResumeRecord] {
        try await request(path: "/resumes?limit=\(limit)&offset=\(offset)")
    }

    func importResume(filename: String, text: String) async throws -> ResumeRecord {
        let encoded = Data(text.utf8).base64EncodedString()
        return try await request(
            path: "/resumes",
            method: "POST",
            body: ResumeImportRequest(filename: filename, contentBase64: encoded, sourcePath: nil)
        )
    }

    func deleteResume(id: String) async throws -> DeleteResponse {
        try await request(path: "/resumes/\(id)", method: "DELETE")
    }

    func createSession(_ body: CreateSessionRequest) async throws -> ChatResponse {
        try await request(path: "/sessions", method: "POST", body: body)
    }

    func listSessions(limit: Int = 20, offset: Int = 0) async throws -> [SessionSummary] {
        try await request(path: "/sessions?limit=\(limit)&offset=\(offset)")
    }

    func getSession(id: String) async throws -> SessionDetail {
        try await request(path: "/sessions/\(id)")
    }

    func deleteSession(id: String) async throws -> DeleteResponse {
        try await request(path: "/sessions/\(id)", method: "DELETE")
    }

    func sendMessage(sessionID: String, message: String) async throws -> ChatResponse {
        try await request(
            path: "/sessions/\(sessionID)/messages",
            method: "POST",
            body: ["message": message]
        )
    }

    func streamMessage(sessionID: String, message: String) async throws -> [StreamEvent] {
        let text: String = try await rawText(
            path: "/sessions/\(sessionID)/stream",
            method: "POST",
            body: ["message": message]
        )
        return parseSSE(text)
    }

    private func request<Response: Decodable, Body: Encodable>(
        path: String,
        method: String = "GET",
        body: Body? = Optional<String>.none,
        headers: [String: String] = [:]
    ) async throws -> Response {
        guard let url = URL(string: path, relativeTo: baseURL)?.absoluteURL else {
            throw InterviewApiError.invalidResponse
        }
        var request = URLRequest(url: url)
        request.httpMethod = method
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        headers.forEach { request.setValue($0.value, forHTTPHeaderField: $0.key) }
        setClientHeaders(on: &request)
        if let token {
            request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        }
        if let body {
            request.httpBody = try encoder.encode(body)
        }

        let (data, response) = try await session.data(for: request)
        guard let http = response as? HTTPURLResponse else {
            throw InterviewApiError.invalidResponse
        }
        guard (200..<300).contains(http.statusCode) else {
            let detail = try? decoder.decode(ErrorResponse.self, from: data)
            throw InterviewApiError.server(detail?.detail ?? "HTTP \(http.statusCode)")
        }
        return try decoder.decode(Response.self, from: data)
    }

    private func rawText<Body: Encodable>(
        path: String,
        method: String,
        body: Body
    ) async throws -> String {
        guard let url = URL(string: path, relativeTo: baseURL)?.absoluteURL else {
            throw InterviewApiError.invalidResponse
        }
        var request = URLRequest(url: url)
        request.httpMethod = method
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        setClientHeaders(on: &request)
        if let token {
            request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        }
        request.httpBody = try encoder.encode(body)
        let (data, response) = try await session.data(for: request)
        guard let http = response as? HTTPURLResponse else {
            throw InterviewApiError.invalidResponse
        }
        guard (200..<300).contains(http.statusCode) else {
            throw InterviewApiError.server("HTTP \(http.statusCode)")
        }
        return String(data: data, encoding: .utf8) ?? ""
    }

    private func setClientHeaders(on request: inout URLRequest) {
        let requestID = UUID().uuidString
        request.setValue(requestID, forHTTPHeaderField: "X-Request-ID")
        request.setValue(requestID, forHTTPHeaderField: "X-Client-Request-Id")
        request.setValue("ios", forHTTPHeaderField: "X-Client-Platform")
        request.setValue(clientVersion, forHTTPHeaderField: "X-Client-Version")
    }

    private func parseSSE(_ text: String) -> [StreamEvent] {
        text.components(separatedBy: "\n\n").compactMap { block in
            let lines = block.split(separator: "\n").map(String.init)
            guard !lines.isEmpty else { return nil }
            let event = lines.first { $0.hasPrefix("event:") }?
                .replacingOccurrences(of: "event:", with: "")
                .trimmingCharacters(in: .whitespacesAndNewlines) ?? "message"
            let dataText = lines.first { $0.hasPrefix("data:") }?
                .replacingOccurrences(of: "data:", with: "")
                .trimmingCharacters(in: .whitespacesAndNewlines) ?? "{}"
            let data = (try? JSONSerialization.jsonObject(with: Data(dataText.utf8))) as? [String: Any] ?? [:]
            return StreamEvent(event: event, data: data)
        }
    }
}

private struct ErrorResponse: Codable {
    let detail: String?
}

enum InterviewApiError: LocalizedError {
    case invalidResponse
    case server(String)

    var errorDescription: String? {
        switch self {
        case .invalidResponse:
            return "服务响应无效"
        case .server(let message):
            return message
        }
    }
}
