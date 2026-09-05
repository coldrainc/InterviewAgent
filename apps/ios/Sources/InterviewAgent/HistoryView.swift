import SwiftUI

struct HistoryView: View {
    @ObservedObject var viewModel: ChatViewModel
    var onOpenChat: () -> Void

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(spacing: 12) {
                    if !viewModel.historyMessage.isEmpty {
                        Text(viewModel.historyMessage)
                            .font(.caption)
                            .foregroundStyle(viewModel.historyMessage.contains("失败") ? BrandPalette.danger : BrandPalette.success)
                            .cardStyle()
                    }
                    ForEach(viewModel.sessions) { session in
                        sessionRow(session)
                    }
                }
                .padding()
            }
            .background(BrandPalette.background)
            .navigationTitle("历史")
            .toolbar {
                Button("刷新") {
                    Task { await viewModel.loadSessions() }
                }
            }
            .task {
                await viewModel.loadSessions()
            }
        }
    }

    private func sessionRow(_ session: SessionSummary) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack {
                Text(session.targetRole)
                    .font(.headline)
                Spacer()
                Text(session.status)
                    .font(.caption)
                    .foregroundStyle(BrandPalette.muted)
            }
            Text("\(session.mode == "candidate" ? "Agent 回答我" : "Agent 面试我") · \(session.seniority) · \(session.updatedAt)")
                .font(.caption)
                .foregroundStyle(BrandPalette.muted)
            HStack {
                Button("恢复") {
                    Task {
                        await viewModel.restoreSession(session.id)
                        onOpenChat()
                    }
                }
                .buttonStyle(.borderedProminent)
                Button("删除", role: .destructive) {
                    Task { await viewModel.deleteSession(session.id) }
                }
                .buttonStyle(.bordered)
            }
        }
        .cardStyle()
    }
}
