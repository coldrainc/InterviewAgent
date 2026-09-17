import SwiftUI

@main
struct InterviewAgentApp: App {
    private let api: InterviewApiClient

    init() {
        let defaults = UserDefaults.standard
        api = InterviewApiClient(
            baseURL: AppEnvironment.apiBaseURL,
            token: defaults.string(forKey: "interview-agent-access-token"),
            onTokenChanged: { token in
                if let token { defaults.set(token, forKey: "interview-agent-access-token") }
                else { defaults.removeObject(forKey: "interview-agent-access-token") }
            }
        )
    }

    var body: some Scene {
        WindowGroup {
            RootView(viewModel: ChatViewModel(api: api), productStore: ProductWorkspaceStore(api: api))
        }
    }
}

private enum AppEnvironment {
    static var apiBaseURL: URL {
        let value = Bundle.main.object(forInfoDictionaryKey: "InterviewApiBaseURL") as? String
        return URL(string: value ?? "http://127.0.0.1:8020")!
    }
}
