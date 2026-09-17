import SwiftUI

struct ReviewWorkspaceView: View {
    @ObservedObject var store: ProductWorkspaceStore
    @ObservedObject var viewModel: ChatViewModel
    @State private var segment = 0
    @State private var role = "AI 应用工程师"
    @State private var focus = "RAG、Agent、系统设计"
    @State private var days = 14
    @State private var minutes = 60
    @State private var note = ""

    var body: some View {
        NavigationStack {
            VStack(spacing: 12) {
                Picker("复习模式", selection: $segment) { Text("复习计划").tag(0); Text("计划生成").tag(1) }
                    .pickerStyle(.segmented).padding(.horizontal)
                ScrollView {
                    LazyVStack(spacing: 12) {
                        if segment == 1 { generator } else { plans }
                        if !store.message.isEmpty {
                            Text(store.message).font(.footnote).foregroundStyle(BrandPalette.muted).frame(maxWidth: .infinity, alignment: .leading)
                        }
                    }.padding()
                }.background(BrandPalette.background)
            }.navigationTitle("复习站")
        }
    }

    private var generator: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("制定可执行的复习节奏").font(.headline)
            TextField("目标岗位", text: $role).textFieldStyle(.roundedBorder)
            TextField("重点方向", text: $focus).textFieldStyle(.roundedBorder)
            Picker("周期", selection: $days) { Text("7 天").tag(7); Text("14 天").tag(14); Text("30 天").tag(30) }.pickerStyle(.segmented)
            Button("生成计划") { Task { await store.generatePlan(role: role, days: days, focus: focus, resumeID: viewModel.selectedResumeID) } }
                .buttonStyle(.borderedProminent).disabled(store.isBusy)
        }.padding(16).background(.white).clipShape(RoundedRectangle(cornerRadius: 14))
    }

    private var plans: some View {
        Group {
            if let task = store.activeTask, task.taskType != "practice", task.taskType != "interview" {
                VStack(alignment: .leading, spacing: 5) {
                    Text("当前任务").font(.caption.bold()).foregroundStyle(BrandPalette.teal)
                    Text(task.title).font(.headline)
                    Text("完成内容后可返回今日页更新状态。").font(.subheadline).foregroundStyle(BrandPalette.muted)
                }.frame(maxWidth: .infinity, alignment: .leading).padding(16).background(.white).clipShape(RoundedRectangle(cornerRadius: 12))
            }
            ForEach(store.reviewPlans) { plan in
                Button { store.selectedPlanID = plan.id } label: {
                    VStack(alignment: .leading, spacing: 5) {
                        Text(plan.title).font(.headline).foregroundStyle(BrandPalette.text)
                        Text("\(plan.status) · \(plan.completedTasks ?? 0)/\(plan.totalTasks ?? 0) 项完成")
                            .font(.subheadline).foregroundStyle(BrandPalette.muted)
                    }.frame(maxWidth: .infinity, alignment: .leading).padding(16).background(store.selectedPlanID == plan.id ? BrandPalette.primary.opacity(0.1) : .white).clipShape(RoundedRectangle(cornerRadius: 12))
                }.buttonStyle(.plain)
                .onAppear {
                    if plan.id == store.reviewPlans.dropLast(min(6, store.reviewPlans.count)).last?.id || plan.id == store.reviewPlans.last?.id {
                        Task { await store.loadPlans(append: true) }
                    }
                }
            }
            VStack(alignment: .leading, spacing: 10) {
                Text("今日打卡").font(.headline)
                Stepper("学习 \(minutes) 分钟", value: $minutes, in: 10...720, step: 10)
                TextField("复盘一句话", text: $note).textFieldStyle(.roundedBorder)
                Button("完成打卡") { Task { await store.checkin(minutes: minutes, note: note) } }
                    .buttonStyle(.borderedProminent).disabled(store.selectedPlanID == nil || store.isBusy)
            }.padding(16).background(.white).clipShape(RoundedRectangle(cornerRadius: 14))
        }
    }
}
