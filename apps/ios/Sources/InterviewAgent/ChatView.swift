import SwiftUI

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
            .background(BrandPalette.background)
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
        HStack(spacing: 12) {
            Image("BrandIcon")
                .resizable()
                .frame(width: 44, height: 44)
                .clipShape(RoundedRectangle(cornerRadius: 11))
            VStack(alignment: .leading, spacing: 4) {
                Text("AI 技术面试")
                    .font(.title2.weight(.bold))
                Text(viewModel.healthText)
                    .font(.caption)
                    .foregroundStyle(BrandPalette.muted)
            }
            Spacer()
            VStack(alignment: .trailing, spacing: 4) {
                Text(viewModel.account == nil ? "未登录" : "已登录")
                    .font(.caption.weight(.semibold))
                    .foregroundStyle(viewModel.account == nil ? BrandPalette.warning : BrandPalette.success)
                if let account = viewModel.account {
                    Text("\(account.creditBalance) 积分")
                        .font(.caption2)
                        .foregroundStyle(BrandPalette.muted)
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
