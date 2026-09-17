import SwiftUI

struct AuthGateView: View {
    @ObservedObject var viewModel: ChatViewModel
    @State private var isRegister = false
    @State private var name = ""
    @State private var email = ""
    @State private var password = ""

    var body: some View {
        ZStack {
            BrandPalette.background.ignoresSafeArea()
            ScrollView {
                VStack(alignment: .leading, spacing: 24) {
                    VStack(alignment: .leading, spacing: 8) {
                        Text("Interview Agent").font(.largeTitle.bold())
                        Text("把面试、刷题和复习计划收进同一条成长路径")
                            .foregroundStyle(BrandPalette.muted)
                    }
                    VStack(spacing: 14) {
                        Text(isRegister ? "创建账号" : "欢迎回来").font(.title2.bold()).frame(maxWidth: .infinity, alignment: .leading)
                        if isRegister { TextField("昵称", text: $name).textFieldStyle(.roundedBorder) }
                        TextField("邮箱", text: $email).textInputAutocapitalization(.never).keyboardType(.emailAddress).textFieldStyle(.roundedBorder)
                        SecureField("密码", text: $password).textFieldStyle(.roundedBorder)
                        Button(isRegister ? "注册并开始" : "登录") {
                            Task {
                                if isRegister { await viewModel.register(email: email, password: password, displayName: name) }
                                else { await viewModel.passwordLogin(email: email, password: password) }
                            }
                        }
                        .buttonStyle(.borderedProminent)
                        .frame(maxWidth: .infinity)
                        .disabled(viewModel.isBusy || email.isEmpty || password.count < 8 || (isRegister && name.isEmpty))
                        Button(isRegister ? "已有账号，直接登录" : "第一次使用？创建账号") { isRegister.toggle() }
                            .buttonStyle(.plain).foregroundStyle(BrandPalette.primary)
                        if !viewModel.accountMessage.isEmpty {
                            Text(viewModel.accountMessage).font(.footnote).foregroundStyle(viewModel.accountMessage.contains("失败") ? BrandPalette.danger : BrandPalette.success)
                        }
                    }
                    .padding(20).background(.white).clipShape(RoundedRectangle(cornerRadius: 16))
                    Text("你的简历、面试记录与学习数据仅对当前账号可见")
                        .font(.footnote).foregroundStyle(BrandPalette.muted).frame(maxWidth: .infinity)
                }.padding(24)
            }
        }
    }
}
