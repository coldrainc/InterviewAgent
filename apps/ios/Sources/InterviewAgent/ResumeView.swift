import SwiftUI

struct ResumeView: View {
    @ObservedObject var viewModel: ChatViewModel

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(spacing: 12) {
                    editor
                    current
                    list
                }
                .padding()
            }
            .background(BrandPalette.background)
            .navigationTitle("简历")
            .task {
                await viewModel.loadResumes()
            }
        }
    }

    private var editor: some View {
        VStack(alignment: .leading, spacing: 10) {
            Text("导入简历")
                .font(.headline)
            TextField("文件名", text: $viewModel.resumeDraftName)
                .textFieldStyle(.roundedBorder)
            TextField("粘贴 Markdown / 文本简历", text: $viewModel.resumeDraftText, axis: .vertical)
                .lineLimit(5...10)
                .textFieldStyle(.roundedBorder)
            Button("保存简历") {
                Task { await viewModel.importResumeDraft() }
            }
            .buttonStyle(.borderedProminent)
            .disabled(viewModel.isBusy || viewModel.resumeDraftText.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty)
            if !viewModel.resumeMessage.isEmpty {
                Text(viewModel.resumeMessage)
                    .font(.caption)
                    .foregroundStyle(viewModel.resumeMessage.contains("失败") ? BrandPalette.danger : BrandPalette.success)
            }
        }
        .cardStyle()
    }

    private var current: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("当前简历")
                .font(.headline)
            Text(viewModel.resumes.first { $0.id == viewModel.selectedResumeID }?.filename ?? "暂未选择")
                .foregroundStyle(BrandPalette.muted)
        }
        .cardStyle()
    }

    private var list: some View {
        VStack(alignment: .leading, spacing: 10) {
            Text("历史简历")
                .font(.headline)
            ForEach(viewModel.resumes) { resume in
                VStack(alignment: .leading, spacing: 8) {
                    HStack {
                        Text(resume.filename)
                            .font(.subheadline.weight(.semibold))
                        Spacer()
                        if resume.id == viewModel.selectedResumeID {
                            Text("当前")
                                .font(.caption)
                                .foregroundStyle(BrandPalette.success)
                        }
                    }
                    Text(resume.summary.isEmpty ? "暂无摘要" : resume.summary)
                        .font(.caption)
                        .foregroundStyle(BrandPalette.muted)
                        .lineLimit(3)
                    HStack {
                        Button("选择") {
                            viewModel.selectResume(resume.id)
                        }
                        .buttonStyle(.bordered)
                        Button("删除", role: .destructive) {
                            Task { await viewModel.deleteResume(resume.id) }
                        }
                        .buttonStyle(.bordered)
                    }
                }
                .padding(12)
                .background(BrandPalette.surfaceSoft)
                .clipShape(RoundedRectangle(cornerRadius: 10))
            }
        }
        .cardStyle()
    }
}
