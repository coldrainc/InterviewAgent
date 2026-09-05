import SwiftUI

struct PracticeView: View {
    @ObservedObject var viewModel: ChatViewModel

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(spacing: 12) {
                    header
                    questionCard
                    resultCard
                }
                .padding()
            }
            .background(BrandPalette.background)
            .navigationTitle("刷题")
            .toolbar {
                Button("初始化") {
                    Task { await viewModel.seedPracticeQuestions() }
                }
            }
            .task {
                await viewModel.loadPractice()
            }
        }
    }

    private var header: some View {
        VStack(alignment: .leading, spacing: 10) {
            Text("训练类型")
                .font(.headline)
            Picker("训练类型", selection: $viewModel.selectedPracticeCategory) {
                ForEach(viewModel.practiceCategories) { category in
                    Text(category.label).tag(category.value)
                }
            }
            .pickerStyle(.menu)
            .onChange(of: viewModel.selectedPracticeCategory) { _, category in
                Task { await viewModel.selectPracticeCategory(category) }
            }
            if !viewModel.practiceMessage.isEmpty {
                Text(viewModel.practiceMessage)
                    .font(.caption)
                    .foregroundStyle(viewModel.practiceMessage.contains("失败") ? BrandPalette.danger : BrandPalette.success)
            }
        }
        .cardStyle()
    }

    @ViewBuilder
    private var questionCard: some View {
        if let question = viewModel.currentPracticeQuestion {
            VStack(alignment: .leading, spacing: 12) {
                HStack {
                    Text("\(question.examYear)")
                    Text(question.subject)
                    Text(question.questionType)
                    Spacer()
                    Text(question.difficulty)
                }
                .font(.caption)
                .foregroundStyle(BrandPalette.muted)
                Text(question.prompt)
                    .font(.body.weight(.semibold))
                if question.choices.isEmpty {
                    TextField("写下你的答题思路", text: $viewModel.practiceAnswer, axis: .vertical)
                        .lineLimit(4...8)
                        .textFieldStyle(.roundedBorder)
                } else {
                    ForEach(Array(question.choices.enumerated()), id: \.offset) { index, choice in
                        let key = String(UnicodeScalar(65 + index)!)
                        Button {
                            viewModel.choosePracticeOption(key)
                        } label: {
                            HStack {
                                Text("\(key). \(choice)")
                                Spacer()
                            }
                        }
                        .buttonStyle(.bordered)
                        .tint(viewModel.practiceAnswer == key ? BrandPalette.primary : BrandPalette.muted)
                    }
                }
                HStack {
                    Button("下一题") {
                        viewModel.nextPracticeQuestion()
                    }
                    .buttonStyle(.bordered)
                    Button("提交答案") {
                        Task { await viewModel.submitPracticeAnswer() }
                    }
                    .buttonStyle(.borderedProminent)
                    .disabled(viewModel.isBusy)
                }
            }
            .cardStyle()
        } else {
            Text("暂无题目，可以先初始化样题。")
                .foregroundStyle(BrandPalette.muted)
                .cardStyle()
        }
    }

    @ViewBuilder
    private var resultCard: some View {
        if let result = viewModel.practiceResult {
            VStack(alignment: .leading, spacing: 10) {
                Text("\(result.score) 分")
                    .font(.largeTitle.weight(.bold))
                    .foregroundStyle(BrandPalette.teal)
                Text(result.feedback)
                InfoRow(label: "参考答案", value: result.referenceAnswer)
                Text("解析")
                    .font(.headline)
                Text(result.explanation)
                    .font(.subheadline)
                    .foregroundStyle(BrandPalette.muted)
                Text("复盘建议")
                    .font(.headline)
                ForEach(result.suggestions, id: \.self) { suggestion in
                    Text("- \(suggestion)")
                        .font(.subheadline)
                }
            }
            .cardStyle()
        }
    }
}
