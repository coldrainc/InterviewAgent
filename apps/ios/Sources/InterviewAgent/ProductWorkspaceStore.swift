import Foundation

@MainActor
final class ProductWorkspaceStore: ObservableObject {
    @Published var today: LearningTodayResponse?
    @Published var reviewPlans: [ReviewPlan] = []
    @Published var selectedPlanID: String?
    @Published var interviewKits: [InterviewKit] = []
    @Published var message = ""
    @Published var isBusy = false
    @Published var activeTask: LearningTask?
    @Published var plansHasMore = true
    @Published var kitsHasMore = true

    private let api: InterviewApiClient
    private var paging = Set<String>()

    init(api: InterviewApiClient) { self.api = api }

    func loadAll(authenticated: Bool) async {
        guard authenticated else { return }
        async let todayLoad: Void = loadToday()
        async let planLoad: Void = loadPlans()
        async let kitLoad: Void = loadKits()
        _ = await (todayLoad, planLoad, kitLoad)
    }

    func reset() {
        today = nil
        reviewPlans = []
        selectedPlanID = nil
        interviewKits = []
        message = ""
        activeTask = nil
    }

    func loadToday() async {
        do { today = try await api.learningToday() }
        catch { message = "加载今日任务失败：\(error.localizedDescription)" }
    }

    func run(_ task: LearningTask) async {
        guard !isBusy else { return }
        isBusy = true
        defer { isBusy = false }
        let action = task.done ? "reopen" : (task.status == "todo" ? "start" : "complete")
        do {
            _ = try await api.commandLearningTask(task, action: action)
            message = "任务状态已更新"
            await loadToday()
        } catch { message = "更新任务失败：\(error.localizedDescription)" }
    }

    func open(_ task: LearningTask) {
        activeTask = task
        if let planID = task.linkPayload?.planID, !planID.isEmpty {
            selectedPlanID = planID
        }
    }

    func loadPlans(append: Bool = false) async {
        guard !paging.contains("plans"), !append || plansHasMore else { return }
        paging.insert("plans"); defer { paging.remove("plans") }
        do {
            let incoming = try await api.listReviewPlans(offset: append ? reviewPlans.count : 0)
            reviewPlans = append ? unique(reviewPlans + incoming) : incoming
            plansHasMore = incoming.count == 20
            if selectedPlanID == nil { selectedPlanID = reviewPlans.first?.id }
        } catch { message = "加载复习计划失败：\(error.localizedDescription)" }
    }

    func generatePlan(role: String, days: Int, focus: String, resumeID: String?) async {
        guard !isBusy else { return }
        isBusy = true
        message = "正在生成计划…"
        defer { isBusy = false }
        do {
            let response = try await api.generateReviewPlan(PlanGenerateRequest(
                title: "\(role) 面试计划", targetRole: role, seniority: "高级", totalDays: days,
                hoursPerDay: 1.5, focusAreas: focus.components(separatedBy: "、").filter { !$0.isEmpty },
                resumeID: resumeID, useHistory: true
            ))
            selectedPlanID = response.planID
            message = "计划已生成"
            await loadPlans()
            await loadToday()
        } catch { message = "生成计划失败：\(error.localizedDescription)" }
    }

    func checkin(minutes: Int, note: String) async {
        guard let selectedPlanID, !isBusy else { return }
        isBusy = true
        defer { isBusy = false }
        do {
            let response = try await api.checkin(planID: selectedPlanID, minutes: minutes, note: note)
            message = "打卡成功，连续 \(response.streak?.currentStreak ?? 0) 天"
            await loadToday()
        } catch { message = "打卡失败：\(error.localizedDescription)" }
    }

    func loadKits(append: Bool = false) async {
        guard !paging.contains("kits"), !append || kitsHasMore else { return }
        paging.insert("kits"); defer { paging.remove("kits") }
        do {
            let incoming = try await api.listInterviewKits(offset: append ? interviewKits.count : 0)
            interviewKits = append ? unique(interviewKits + incoming) : incoming
            kitsHasMore = incoming.count == 20
        }
        catch { message = "加载面试题单失败：\(error.localizedDescription)" }
    }

    private func unique<T: Identifiable>(_ items: [T]) -> [T] where T.ID: Hashable {
        var seen = Set<T.ID>()
        return items.filter { seen.insert($0.id).inserted }
    }

    func createKit(role: String, duration: Int) async {
        guard !isBusy else { return }
        isBusy = true
        defer { isBusy = false }
        do {
            let kit = try await api.createInterviewKit(InterviewKitRequest(
                title: "\(role) 面试题单", targetRole: role, seniority: "高级",
                durationMinutes: duration, dimensions: ["技术深度", "系统设计", "表达与协作"]
            ))
            interviewKits.insert(kit, at: 0)
            message = "面试题单已创建"
        } catch { message = "创建题单失败：\(error.localizedDescription)" }
    }
}
