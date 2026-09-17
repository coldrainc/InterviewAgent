import SwiftUI

struct RootView: View {
    @StateObject var viewModel: ChatViewModel
    @StateObject var productStore: ProductWorkspaceStore
    @State private var selectedTab = 0

    var body: some View {
        if !viewModel.isAuthenticated {
            AuthGateView(viewModel: viewModel)
                .task { viewModel.load() }
        } else {
        TabView(selection: $selectedTab) {
            TodayWorkspaceView(
                store: productStore,
                openInterview: { selectedTab = 1 },
                openTask: { task in
                    productStore.open(task)
                    viewModel.prepareLearningTask(task)
                    if task.taskType == "practice" {
                        if let category = task.linkPayload?.category, !category.isEmpty {
                            Task { await viewModel.selectPracticeCategory(category) }
                        }
                        selectedTab = 2
                    } else if task.taskType == "interview" {
                        selectedTab = 1
                    } else {
                        selectedTab = 3
                    }
                }
            )
            .tabItem {
                Label("今日", systemImage: "sun.max")
            }
            .tag(0)

            InterviewWorkspaceView(viewModel: viewModel, store: productStore)
                .tabItem {
                    Label("面试", systemImage: "message")
                }
                .tag(1)

            PracticeView(viewModel: viewModel)
                .tabItem {
                    Label("刷题", systemImage: "checklist")
                }
                .tag(2)

            ReviewWorkspaceView(store: productStore, viewModel: viewModel)
                .tabItem {
                    Label("复习", systemImage: "calendar.badge.checkmark")
                }
                .tag(3)

            MyWorkspaceView(viewModel: viewModel) { selectedTab = 1 }
            .tabItem {
                Label("我的", systemImage: "person.crop.circle")
            }
            .tag(4)
        }
        .task { await productStore.loadAll(authenticated: viewModel.isAuthenticated) }
        .onChange(of: viewModel.isAuthenticated) { _, value in if value { Task { await productStore.loadAll(authenticated: true) } } else { productStore.reset() } }
        }
    }
}
