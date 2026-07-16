import SwiftUI

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
