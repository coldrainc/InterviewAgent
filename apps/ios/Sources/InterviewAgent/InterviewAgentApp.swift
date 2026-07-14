import SwiftUI

@main
struct InterviewAgentApp: App {
    var body: some Scene {
        WindowGroup {
            RootView(viewModel: ChatViewModel(
                api: InterviewApiClient(
                    baseURL: AppEnvironment.apiBaseURL,
                    token: nil
                )
            ))
        }
    }
}

private enum AppEnvironment {
    static var apiBaseURL: URL {
        let value = Bundle.main.object(forInfoDictionaryKey: "InterviewApiBaseURL") as? String
        return URL(string: value ?? "http://127.0.0.1:8020")!
    }
}
