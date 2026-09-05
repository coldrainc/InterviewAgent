import Foundation

@MainActor
final class ChatViewModel: ObservableObject {
    @Published var messages: [ChatMessage] = []
    @Published var industries: [IndustryOption] = []
    @Published var selectedIndustry = Industry.internet.rawValue
    @Published var input = ""
    @Published var healthText = "检查中"
    @Published var isBusy = false
    @Published var account: AccountResponse?
    @Published var accountMessage = ""
    @Published var showAuthPrompt = false
    @Published var authPromptMessage = ""
    @Published var resumes: [ResumeRecord] = []
    @Published var selectedResumeID: String?
    @Published var resumeDraftName = "resume.md"
    @Published var resumeDraftText = ""
    @Published var resumeMessage = ""
    @Published var sessions: [SessionSummary] = []
    @Published var historyMessage = ""
    @Published var settings: UserSettingsResponse?
    @Published var practiceCategories: [PracticeCategory] = []
    @Published var selectedPracticeCategory = "ai_application"
    @Published var practiceQuestions: [PracticeQuestion] = []
    @Published var currentPracticeIndex = 0
    @Published var practiceAnswer = ""
    @Published var practiceResult: PracticeAttemptResponse?
    @Published var practiceMessage = ""

    private let api: InterviewApiClient
    private var sessionID: String?
    private var practiceStartedAt = Date()

    init(api: InterviewApiClient) {
        self.api = api
    }

    func load() {
        Task {
            await checkHealth()
            await loadIndustries()
            await refreshAccount()
            await loadResumes()
            await loadSessions()
            await loadPractice()
        }
    }

    var isAuthenticated: Bool {
        account != nil
    }

    func dismissAuthPrompt() {
        showAuthPrompt = false
        authPromptMessage = ""
    }

    func login() async {
        guard !isBusy else { return }
        isBusy = true
        accountMessage = ""
        defer { isBusy = false }
        do {
            _ = try await api.devLogin()
            account = try await api.account()
            settings = try? await api.getSettings()
            accountMessage = "已登录开发账号"
            await loadResumes()
            await loadSessions()
            await loadPractice()
        } catch {
            accountMessage = "开发登录失败：\(error.localizedDescription)"
        }
    }

    func logout() {
        api.logout()
        account = nil
        settings = nil
        sessionID = nil
        messages = []
        resumes = []
        sessions = []
        selectedResumeID = nil
        practiceQuestions = []
        practiceResult = nil
        accountMessage = "已退出登录"
    }

    func refreshAccount() async {
        do {
            account = try await api.account()
            settings = try? await api.getSettings()
        } catch {
            account = nil
        }
    }

    func recharge(amountCredits: String) async {
        guard account != nil else {
            requireAccount("充值积分前需要先登录账号。")
            return
        }
        guard !isBusy else { return }
        isBusy = true
        accountMessage = ""
        defer { isBusy = false }
        do {
            account = try await api.recharge(amountCredits: amountCredits)
            accountMessage = "已充值 \(amountCredits) 积分"
        } catch {
            accountMessage = "充值失败：\(error.localizedDescription)"
        }
    }

    func checkHealth() async {
        do {
            let health = try await api.health()
            healthText = health.status == "ok" ? "已连接" : "服务异常"
        } catch {
            healthText = error.localizedDescription
        }
    }

    func loadIndustries() async {
        do {
            let loaded = try await api.listIndustries()
            industries = loaded
            if !loaded.contains(where: { $0.value == selectedIndustry }) {
                selectedIndustry = loaded.first?.value ?? Industry.internet.rawValue
            }
        } catch {
            industries = []
        }
    }

    var currentPracticeQuestion: PracticeQuestion? {
        guard practiceQuestions.indices.contains(currentPracticeIndex) else { return nil }
        return practiceQuestions[currentPracticeIndex]
    }

    func loadPractice() async {
        guard account != nil else { return }
        do {
            let categories = try await api.listPracticeCategories()
            practiceCategories = categories
            if !categories.contains(where: { $0.value == selectedPracticeCategory }) {
                selectedPracticeCategory = categories.first?.value ?? "ai_application"
            }
            let response = try await api.listPracticeQuestions(category: selectedPracticeCategory)
            practiceQuestions = response.items
            currentPracticeIndex = 0
            practiceAnswer = ""
            practiceResult = nil
            practiceStartedAt = Date()
        } catch {
            practiceMessage = "加载刷题失败：\(error.localizedDescription)"
        }
    }

    func selectPracticeCategory(_ category: String) async {
        selectedPracticeCategory = category
        await loadPractice()
    }

    func seedPracticeQuestions() async {
        guard requireAccount("初始化练习样题前需要先登录账号。") else { return }
        do {
            let result = try await api.seedPracticeQuestions()
            practiceMessage = "样题已初始化：\(result.total) 道"
            await loadPractice()
        } catch {
            practiceMessage = "初始化样题失败：\(error.localizedDescription)"
        }
    }

    func choosePracticeOption(_ option: String) {
        practiceAnswer = option
    }

    func nextPracticeQuestion() {
        guard !practiceQuestions.isEmpty else { return }
        currentPracticeIndex = (currentPracticeIndex + 1) % practiceQuestions.count
        practiceAnswer = ""
        practiceResult = nil
        practiceStartedAt = Date()
    }

    func submitPracticeAnswer() async {
        guard requireAccount("提交答案前需要先登录账号。") else { return }
        guard let question = currentPracticeQuestion, !isBusy else { return }
        isBusy = true
        defer { isBusy = false }
        do {
            let elapsed = max(0, Int(Date().timeIntervalSince(practiceStartedAt)))
            practiceResult = try await api.submitPracticeAttempt(
                questionID: question.id,
                answer: practiceAnswer,
                elapsedSeconds: elapsed
            )
        } catch {
            practiceMessage = "提交答案失败：\(error.localizedDescription)"
        }
    }

    func loadResumes() async {
        guard account != nil else { return }
        do {
            resumes = try await api.listResumes()
            if selectedResumeID == nil {
                selectedResumeID = resumes.first?.id
            }
        } catch {
            resumeMessage = "加载简历失败：\(error.localizedDescription)"
        }
    }

    func importResumeDraft() async {
        guard requireAccount("上传和保存简历前需要先登录账号。") else { return }
        let text = resumeDraftText.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !text.isEmpty, !isBusy else { return }
        isBusy = true
        resumeMessage = ""
        defer { isBusy = false }
        do {
            let filename = resumeDraftName.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty ? "resume.md" : resumeDraftName
            let resume = try await api.importResume(filename: filename, text: text)
            selectedResumeID = resume.id
            resumeDraftText = ""
            resumeMessage = "简历已保存"
            await loadResumes()
        } catch {
            resumeMessage = "上传简历失败：\(error.localizedDescription)"
        }
    }

    func selectResume(_ id: String) {
        selectedResumeID = id
        resumeMessage = "已选择当前简历"
    }

    func deleteResume(_ id: String) async {
        guard requireAccount("删除简历前需要先登录账号。") else { return }
        guard !isBusy else { return }
        isBusy = true
        resumeMessage = ""
        defer { isBusy = false }
        do {
            _ = try await api.deleteResume(id: id)
            if selectedResumeID == id {
                selectedResumeID = nil
            }
            resumeMessage = "简历已删除"
            await loadResumes()
        } catch {
            resumeMessage = "删除简历失败：\(error.localizedDescription)"
        }
    }

    func loadSessions() async {
        guard account != nil else { return }
        do {
            sessions = try await api.listSessions()
        } catch {
            historyMessage = "加载历史失败：\(error.localizedDescription)"
        }
    }

    func restoreSession(_ id: String) async {
        guard requireAccount("恢复历史会话前需要先登录账号。") else { return }
        guard !isBusy else { return }
        isBusy = true
        historyMessage = ""
        defer { isBusy = false }
        do {
            let detail = try await api.getSession(id: id)
            sessionID = detail.id
            if let summary = sessions.first(where: { $0.id == id }) {
                selectedResumeID = summary.resumeID ?? selectedResumeID
                selectedIndustry = summary.industry
            }
            messages = detail.turns.flatMap { turn -> [ChatMessage] in
                var items: [ChatMessage] = []
                if let interviewer = turn.interviewer, !interviewer.isEmpty {
                    items.append(ChatMessage(role: .agent, text: interviewer))
                }
                if let candidate = turn.candidate, !candidate.isEmpty {
                    items.append(ChatMessage(role: .user, text: candidate))
                }
                return items
            }
            historyMessage = "会话已恢复"
        } catch {
            historyMessage = "恢复会话失败：\(error.localizedDescription)"
        }
    }

    func deleteSession(_ id: String) async {
        guard requireAccount("删除历史会话前需要先登录账号。") else { return }
        do {
            _ = try await api.deleteSession(id: id)
            if sessionID == id {
                sessionID = nil
                messages = []
            }
            historyMessage = "历史会话已删除"
            await loadSessions()
        } catch {
            historyMessage = "删除历史失败：\(error.localizedDescription)"
        }
    }

    func updateDefaultMode(_ mode: InterviewMode) async {
        guard requireAccount("更新设置前需要先登录账号。") else { return }
        do {
            settings = try await api.updateDefaultInterviewMode(mode)
            accountMessage = "设置已保存"
        } catch {
            accountMessage = "保存设置失败：\(error.localizedDescription)"
        }
    }

    func startInterview() {
        guard !isBusy else { return }
        guard requireAccount("开始面试前需要先登录，登录后会保存会话、简历和用量记录。") else { return }
        isBusy = true
        messages = []
        Task {
            defer { isBusy = false }
            do {
                var request = CreateSessionRequest()
                request.offline = true
                request.industry = selectedIndustry
                request.resumeID = selectedResumeID
                let response = try await api.createSession(request)
                sessionID = response.sessionID
                messages.append(ChatMessage(role: .agent, text: response.message))
                await refreshAccount()
                await loadSessions()
            } catch {
                messages.append(ChatMessage(role: .system, text: "创建会话失败：\(error.localizedDescription)"))
            }
        }
    }

    func send() {
        let text = input.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !text.isEmpty, let sessionID, !isBusy else { return }
        guard requireAccount("发送回答前需要先登录账号。") else { return }
        input = ""
        isBusy = true
        messages.append(ChatMessage(role: .user, text: text))
        Task {
            defer { isBusy = false }
            do {
                let events = try await api.streamMessage(sessionID: sessionID, message: text)
                if let done = events.last(where: { $0.event == "message.done" }),
                   let reply = done.data["message"] as? String {
                    messages.append(ChatMessage(role: .agent, text: reply))
                } else if let error = events.last(where: { $0.event == "message.error" }),
                          let message = error.data["message"] as? String {
                    messages.append(ChatMessage(role: .system, text: "发送失败：\(message)"))
                } else {
                    let response = try await api.sendMessage(sessionID: sessionID, message: text)
                    messages.append(ChatMessage(role: .agent, text: response.message))
                }
                await refreshAccount()
                await loadSessions()
            } catch {
                messages.append(ChatMessage(role: .system, text: "发送失败：\(error.localizedDescription)"))
            }
        }
    }

    @discardableResult
    private func requireAccount(_ message: String) -> Bool {
        if account != nil {
            return true
        }
        authPromptMessage = message
        showAuthPrompt = true
        return false
    }
}
