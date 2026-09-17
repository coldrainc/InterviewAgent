import SwiftUI

struct InterviewWorkspaceView: View {
    @ObservedObject var viewModel: ChatViewModel
    @ObservedObject var store: ProductWorkspaceStore
    @State private var mode = 0
    @State private var role = "AI 应用工程师"
    @State private var duration = 45

    var body: some View {
        NavigationStack {
            VStack(spacing: 12) {
                Picker("使用身份", selection: $mode) {
                    Text("作为面试者").tag(0)
                    Text("作为面试官").tag(1)
                }.pickerStyle(.segmented).padding(.horizontal)
                if mode == 0 {
                    ChatView(viewModel: viewModel, onRequireAccount: {})
                } else {
                    ScrollView {
                        LazyVStack(spacing: 12) {
                            VStack(alignment: .leading, spacing: 10) {
                                Text("结构化面试题单").font(.headline)
                                TextField("目标岗位", text: $role).textFieldStyle(.roundedBorder)
                                Picker("时长", selection: $duration) {
                                    Text("30 分钟").tag(30); Text("45 分钟").tag(45); Text("60 分钟").tag(60)
                                }.pickerStyle(.segmented)
                                Button("创建题单") { Task { await store.createKit(role: role, duration: duration) } }
                                    .buttonStyle(.borderedProminent).disabled(store.isBusy || role.isEmpty)
                            }.padding(16).background(.white).clipShape(RoundedRectangle(cornerRadius: 14))
                            ForEach(store.interviewKits) { kit in
                                VStack(alignment: .leading, spacing: 5) {
                                    Text(kit.title).font(.headline)
                                    Text("\(kit.targetRole) · \(kit.durationMinutes) 分钟 · \(kit.questions?.count ?? 0) 题")
                                        .font(.subheadline).foregroundStyle(BrandPalette.muted)
                                }.frame(maxWidth: .infinity, alignment: .leading).padding(16).background(.white).clipShape(RoundedRectangle(cornerRadius: 12))
                                .onAppear {
                                    if kit.id == store.interviewKits.dropLast(min(6, store.interviewKits.count)).last?.id || kit.id == store.interviewKits.last?.id {
                                        Task { await store.loadKits(append: true) }
                                    }
                                }
                            }
                        }.padding()
                    }.background(BrandPalette.background)
                }
            }
            .navigationTitle("面试")
            .toolbar { if mode == 1 { Button { Task { await store.loadKits() } } label: { Image(systemName: "arrow.clockwise") } } }
        }
    }
}
