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

            AccountView(viewModel: viewModel)
                .tabItem {
                    Label("我的", systemImage: "person.crop.circle")
                }
                .tag(1)
        }
    }
}
