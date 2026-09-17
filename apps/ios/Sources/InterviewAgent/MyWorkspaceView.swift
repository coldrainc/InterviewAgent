import SwiftUI

struct MyWorkspaceView: View {
    @ObservedObject var viewModel: ChatViewModel
    let openInterview: () -> Void

    var body: some View {
        NavigationStack {
            List {
                Section("账号") { AccountView(viewModel: viewModel) }
                Section("资料与记录") {
                    NavigationLink { ResumeView(viewModel: viewModel) } label: { Label("我的简历", systemImage: "doc.text") }
                    NavigationLink { HistoryView(viewModel: viewModel, onOpenChat: openInterview) } label: { Label("面试历史", systemImage: "clock") }
                }
                Section("隐私") {
                    Label("账号数据相互隔离", systemImage: "lock.shield")
                    Text("简历与面试内容仅用于当前账号的练习和复习。")
                        .font(.footnote).foregroundStyle(BrandPalette.muted)
                }
            }.navigationTitle("我的")
        }
    }
}
