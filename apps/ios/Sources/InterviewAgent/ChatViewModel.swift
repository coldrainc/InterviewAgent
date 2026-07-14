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

    private let api: InterviewApiClient
    private var sessionID: String?

    init(api: InterviewApiClient) {
        self.api = api
    }

    func load() {
        Task {
            await checkHealth()
            await loadIndustries()
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
            accountMessage = "已登录开发账号"
        } catch {
            accountMessage = "开发登录失败：\(error.localizedDescription)"
        }
    }

    func logout() {
        api.logout()
        account = nil
        sessionID = nil
        messages = []
        accountMessage = "已退出登录"
    }

    func refreshAccount() async {
        do {
            account = try await api.account()
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
            industries = try await api.listIndustries()
            selectedIndustry = industries.first?.value ?? Industry.internet.rawValue
        } catch {
            industries = []
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
                let response = try await api.createSession(request)
                sessionID = response.sessionID
                messages.append(ChatMessage(role: .agent, text: response.message))
                await refreshAccount()
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
                } else {
                    let response = try await api.sendMessage(sessionID: sessionID, message: text)
                    messages.append(ChatMessage(role: .agent, text: response.message))
                }
                await refreshAccount()
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
