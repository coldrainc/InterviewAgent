import SwiftUI

struct TodayWorkspaceView: View {
    @ObservedObject var store: ProductWorkspaceStore
    let openInterview: () -> Void
    let openTask: (LearningTask) -> Void

    var body: some View {
        NavigationStack {
            ScrollView {
                LazyVStack(spacing: 12) {
                    let summary = store.today?.today
                    HStack(spacing: 10) {
                        metric("今日完成", "\(summary?.tasksDone ?? 0)/\(summary?.totalTasks ?? 0)")
                        metric("连续打卡", "\(store.today?.streak?.currentStreak ?? 0) 天")
                    }
                    if let advice = store.today?.advice?.text, !advice.isEmpty {
                        Text(advice).font(.subheadline).foregroundStyle(BrandPalette.muted).frame(maxWidth: .infinity, alignment: .leading).padding(16).background(.white).clipShape(RoundedRectangle(cornerRadius: 12))
                    }
                    if summary?.tasks.isEmpty != false {
                        VStack(spacing: 12) {
                            Text("今天还没有任务").font(.headline)
                            Text("先做一次轻量模拟，或到复习页生成计划。").foregroundStyle(BrandPalette.muted)
                            Button("开始模拟面试", action: openInterview).buttonStyle(.borderedProminent)
                        }.frame(maxWidth: .infinity).padding(24).background(.white).clipShape(RoundedRectangle(cornerRadius: 14))
                    }
                    ForEach(summary?.tasks ?? []) { task in
                        HStack(spacing: 12) {
                            Button { openTask(task) } label: {
                                VStack(alignment: .leading, spacing: 4) {
                                    Text(task.title).font(.headline).foregroundStyle(BrandPalette.text)
                                    Text("\(task.taskType.uppercased()) · \(task.status)").font(.caption).foregroundStyle(BrandPalette.muted)
                                }.frame(maxWidth: .infinity, alignment: .leading)
                            }.buttonStyle(.plain)
                            Button(task.done ? "重开" : task.primaryAction.label) { Task { await store.run(task) } }
                                .buttonStyle(.borderedProminent).disabled(store.isBusy)
                        }
                        .padding(16)
                        .background(.white)
                        .clipShape(RoundedRectangle(cornerRadius: 12))
                    }
                }.padding()
            }
            .background(BrandPalette.background)
            .navigationTitle("今天")
            .toolbar { Button { Task { await store.loadToday() } } label: { Image(systemName: "arrow.clockwise") } }
        }
    }

    private func metric(_ title: String, _ value: String) -> some View {
        VStack(alignment: .leading, spacing: 6) { Text(title).font(.caption).foregroundStyle(BrandPalette.muted); Text(value).font(.title2.bold()).foregroundStyle(BrandPalette.teal) }
            .frame(maxWidth: .infinity, alignment: .leading).padding(16).background(.white).clipShape(RoundedRectangle(cornerRadius: 12))
    }
}
