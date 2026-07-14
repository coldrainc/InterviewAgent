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

struct ChatView: View {
    @ObservedObject var viewModel: ChatViewModel
    var onRequireAccount: () -> Void = {}

    var body: some View {
        NavigationStack {
            VStack(spacing: 12) {
                header
                controls
                messageList
                composer
            }
            .padding()
            .background(Color(red: 0.93, green: 0.95, blue: 0.98))
            .navigationTitle("Interview Agent")
            .onAppear {
                viewModel.load()
            }
            .alert("需要登录", isPresented: $viewModel.showAuthPrompt) {
                Button("稍后", role: .cancel) {
                    viewModel.dismissAuthPrompt()
                }
                Button("去我的") {
                    viewModel.dismissAuthPrompt()
                    onRequireAccount()
                }
            } message: {
                Text(viewModel.authPromptMessage)
            }
        }
    }

    private var header: some View {
        HStack {
            VStack(alignment: .leading, spacing: 4) {
                Text("AI 技术面试")
                    .font(.title2.weight(.bold))
                Text(viewModel.healthText)
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }
            Spacer()
            VStack(alignment: .trailing, spacing: 4) {
                Text(viewModel.account == nil ? "未登录" : "已登录")
                    .font(.caption.weight(.semibold))
                    .foregroundStyle(viewModel.account == nil ? .orange : .green)
                if let account = viewModel.account {
                    Text("\(account.creditBalance) 积分")
                        .font(.caption2)
                        .foregroundStyle(.secondary)
                }
            }
        }
        .cardStyle()
    }

    private var controls: some View {
        VStack(alignment: .leading, spacing: 10) {
            Picker("行业", selection: $viewModel.selectedIndustry) {
                ForEach(viewModel.industries) { industry in
                    Text(industry.label).tag(industry.value)
                }
            }
            .pickerStyle(.menu)

            Button("开始面试") {
                viewModel.startInterview()
            }
            .buttonStyle(.borderedProminent)
            .disabled(viewModel.isBusy)
        }
        .cardStyle()
    }

    private var messageList: some View {
        ScrollView {
            LazyVStack(alignment: .leading, spacing: 10) {
                ForEach(viewModel.messages) { message in
                    MessageBubble(message: message)
                }
            }
            .frame(maxWidth: .infinity, alignment: .leading)
        }
    }

    private var composer: some View {
        HStack(alignment: .bottom, spacing: 8) {
            TextField("输入你的回答", text: $viewModel.input, axis: .vertical)
                .lineLimit(1...5)
                .textFieldStyle(.roundedBorder)
            Button("发送") {
                viewModel.send()
            }
            .buttonStyle(.borderedProminent)
            .disabled(viewModel.input.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty || viewModel.isBusy)
        }
        .cardStyle()
    }
}

struct AccountView: View {
    @ObservedObject var viewModel: ChatViewModel
    private let rechargeOptions = ["10", "50", "100"]

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(spacing: 12) {
                    profileCard
                    quotaCard
                    serviceCard
                    actions
                }
                .padding()
            }
            .background(Color(red: 0.93, green: 0.95, blue: 0.98))
            .navigationTitle("我的")
            .task {
                await viewModel.refreshAccount()
            }
        }
    }

    private var profileCard: some View {
        HStack(spacing: 14) {
            ZStack {
                RoundedRectangle(cornerRadius: 12)
                    .fill(Color.blue.gradient)
                Image(systemName: viewModel.account == nil ? "person" : "person.fill")
                    .foregroundStyle(.white)
                    .font(.title3.weight(.semibold))
            }
            .frame(width: 58, height: 58)

            VStack(alignment: .leading, spacing: 4) {
                Text(viewModel.account?.displayName ?? "未登录")
                    .font(.title3.weight(.bold))
                Text(viewModel.account?.email ?? viewModel.account?.userID ?? "登录后保存简历、会话和用量记录")
                    .font(.caption)
                    .foregroundStyle(.secondary)
                    .lineLimit(1)
            }
            Spacer()
        }
        .cardStyle()
    }

    private var quotaCard: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("权益")
                .font(.headline)
            HStack(spacing: 10) {
                MetricBox(title: "剩余试用", value: viewModel.account.map { "\($0.trialUsesRemaining)" } ?? "-")
                MetricBox(title: "积分余额", value: viewModel.account?.creditBalance ?? "-")
            }
            HStack(spacing: 8) {
                ForEach(rechargeOptions, id: \.self) { amount in
                    Button("充 \(amount)") {
                        Task {
                            await viewModel.recharge(amountCredits: amount)
                        }
                    }
                    .buttonStyle(.bordered)
                    .disabled(viewModel.account == nil || viewModel.isBusy)
                }
            }
            if !viewModel.accountMessage.isEmpty {
                Text(viewModel.accountMessage)
                    .font(.caption)
                    .foregroundStyle(viewModel.accountMessage.contains("失败") ? .red : .green)
            }
        }
        .cardStyle()
    }

    private var serviceCard: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("账号信息")
                .font(.headline)
            InfoRow(label: "租户", value: viewModel.account?.tenantID ?? "-")
            InfoRow(label: "用户", value: viewModel.account?.userID ?? "-")
            InfoRow(label: "平台", value: viewModel.account?.platform ?? "-")
            InfoRow(label: "服务", value: viewModel.healthText)
        }
        .cardStyle()
    }

    private var actions: some View {
        VStack(spacing: 10) {
            Button(viewModel.account == nil ? "开发登录" : "刷新账户") {
                Task {
                    if viewModel.account == nil {
                        await viewModel.login()
                    } else {
                        await viewModel.refreshAccount()
                    }
                }
            }
            .buttonStyle(.borderedProminent)
            .frame(maxWidth: .infinity)

            if viewModel.account != nil {
                Button("退出登录", role: .destructive) {
                    viewModel.logout()
                }
                .buttonStyle(.bordered)
                .frame(maxWidth: .infinity)
            }
        }
        .cardStyle()
    }
}

private struct MetricBox: View {
    let title: String
    let value: String

    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            Text(title)
                .font(.caption)
                .foregroundStyle(.secondary)
            Text(value)
                .font(.title2.weight(.bold))
                .foregroundStyle(Color(red: 0.06, green: 0.30, blue: 0.39))
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(12)
        .background(Color(red: 0.97, green: 0.98, blue: 1.0))
        .clipShape(RoundedRectangle(cornerRadius: 10))
    }
}

private struct InfoRow: View {
    let label: String
    let value: String

    var body: some View {
        HStack(alignment: .top) {
            Text(label)
                .foregroundStyle(.secondary)
            Spacer()
            Text(value)
                .multilineTextAlignment(.trailing)
        }
        .font(.subheadline)
    }
}

private struct MessageBubble: View {
    let message: ChatMessage

    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            Text(label)
                .font(.caption)
                .foregroundStyle(.secondary)
            Text(message.text)
                .padding(12)
                .foregroundStyle(message.role == .user ? Color.white : Color.primary)
                .background(message.role == .user ? Color.blue : Color.white)
                .clipShape(RoundedRectangle(cornerRadius: 10))
        }
        .frame(maxWidth: .infinity, alignment: message.role == .user ? .trailing : .leading)
    }

    private var label: String {
        switch message.role {
        case .user:
            return "我"
        case .agent:
            return "面试官"
        case .system:
            return "系统"
        }
    }
}

private extension View {
    func cardStyle() -> some View {
        padding(14)
            .frame(maxWidth: .infinity, alignment: .leading)
            .background(Color.white)
            .clipShape(RoundedRectangle(cornerRadius: 10))
    }
}
