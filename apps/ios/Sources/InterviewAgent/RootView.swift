import SwiftUI

struct RootView: View {
    @StateObject var viewModel: ChatViewModel
    @State private var selectedTab = 0

    var body: some View {
        TabView(selection: $selectedTab) {
            ChatView(viewModel: viewModel, onRequireAccount: {
                selectedTab = 1
            })
            .tabItem {
                Label("面试", systemImage: "message")
            }
            .tag(0)

            PracticeView(viewModel: viewModel)
                .tabItem {
                    Label("刷题", systemImage: "checklist")
                }
                .tag(4)

            AccountView(viewModel: viewModel)
                .tabItem {
                    Label("我的", systemImage: "person.crop.circle")
                }
                .tag(1)

            ResumeView(viewModel: viewModel)
                .tabItem {
                    Label("简历", systemImage: "doc.text")
                }
                .tag(2)

            HistoryView(viewModel: viewModel, onOpenChat: {
                selectedTab = 0
            })
            .tabItem {
                Label("历史", systemImage: "clock")
            }
            .tag(3)
        }
    }
}
