package com.interviewagent.ui

import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.viewModelScope
import com.interviewagent.data.AccountResponse
import com.interviewagent.data.ChatMessage
import com.interviewagent.data.CreateSessionRequest
import com.interviewagent.data.IndustryOption
import com.interviewagent.data.InterviewApiClient
import com.interviewagent.data.InterviewKit
import com.interviewagent.data.LearningTask
import com.interviewagent.data.LearningTaskTarget
import com.interviewagent.data.LearningToday
import com.interviewagent.data.PracticeAttemptResponse
import com.interviewagent.data.PracticeCategory
import com.interviewagent.data.PracticeQuestion
import com.interviewagent.data.ResumeRecord
import com.interviewagent.data.ReviewPlan
import com.interviewagent.data.SessionSummary
import com.interviewagent.data.UserSettingsResponse
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

data class ChatUiState(
    val healthText: String = "检查中",
    val industries: List<IndustryOption> = emptyList(),
    val selectedIndustry: String = "internet",
    val messages: List<ChatMessage> = emptyList(),
    val input: String = "",
    val sessionId: String? = null,
    val busy: Boolean = false,
    val account: AccountResponse? = null,
    val accountMessage: String = "",
    val authPrompt: String? = null,
    val settings: UserSettingsResponse? = null,
    val resumes: List<ResumeRecord> = emptyList(),
    val selectedResumeId: String? = null,
    val resumeDraftName: String = "resume.md",
    val resumeDraftText: String = "",
    val resumeMessage: String = "",
    val sessions: List<SessionSummary> = emptyList(),
    val historyMessage: String = "",
    val practiceCategories: List<PracticeCategory> = emptyList(),
    val selectedPracticeCategory: String = "ai_application",
    val practiceQuestions: List<PracticeQuestion> = emptyList(),
    val currentPracticeIndex: Int = 0,
    val practiceAnswer: String = "",
    val practiceResult: PracticeAttemptResponse? = null,
    val practiceMessage: String = "",
    val learningToday: LearningToday = LearningToday(),
    val learningMessage: String = "",
    val reviewPlans: List<ReviewPlan> = emptyList(),
    val selectedReviewPlanId: String? = null,
    val reviewMessage: String = "",
    val interviewKits: List<InterviewKit> = emptyList(),
    val interviewerMessage: String = "",
    val activeLearningTarget: LearningTaskTarget? = null
    ,val activeLearningTaskType: String = "",
    val practiceHasMore: Boolean = true,
    val resumesHasMore: Boolean = true,
    val sessionsHasMore: Boolean = true,
    val reviewPlansHasMore: Boolean = true,
    val interviewKitsHasMore: Boolean = true
)

class ChatViewModel(
    private val api: InterviewApiClient
) : ViewModel() {
    private val _state = MutableStateFlow(ChatUiState())
    val state: StateFlow<ChatUiState> = _state
    private var practiceStartedAtMillis: Long = System.currentTimeMillis()
    private var paging = mutableSetOf<String>()

    init {
        load()
    }

    fun load() {
        viewModelScope.launch {
            runCatching {
                withContext(Dispatchers.IO) { api.health() }
            }.onSuccess { status ->
                _state.update { it.copy(healthText = if (status == "ok") "已连接" else "服务异常") }
            }.onFailure { error ->
                _state.update { it.copy(healthText = error.message ?: "连接失败") }
            }

            runCatching {
                withContext(Dispatchers.IO) { api.listIndustries() }
            }.onSuccess { industries ->
                _state.update {
                    it.copy(
                        industries = industries,
                        selectedIndustry = if (industries.any { industry -> industry.value == it.selectedIndustry }) {
                            it.selectedIndustry
                        } else {
                            industries.firstOrNull()?.value ?: "internet"
                        }
                    )
                }
            }
            refreshAccount()
        }
    }

    val currentPracticeQuestion: PracticeQuestion?
        get() = _state.value.practiceQuestions.getOrNull(_state.value.currentPracticeIndex)

    fun passwordLogin(email: String, password: String) = authenticate("登录") {
        api.login(email.trim(), password.trim())
    }

    fun register(email: String, password: String, displayName: String) = authenticate("注册") {
        api.register(email.trim(), password.trim(), displayName.trim())
    }

    private fun authenticate(label: String, block: () -> Unit) {
        if (_state.value.busy) return
        _state.update { it.copy(busy = true, accountMessage = "") }
        viewModelScope.launch {
            runCatching {
                withContext(Dispatchers.IO) {
                    block()
                    api.account() to runCatching { api.settings() }.getOrNull()
                }
            }.onSuccess { (account, settings) ->
                _state.update { it.copy(busy = false, account = account, settings = settings, accountMessage = "$label 成功", authPrompt = null) }
                loadPrivateWorkspaces()
            }.onFailure { error ->
                _state.update { it.copy(busy = false, accountMessage = "$label 失败：${error.message}") }
            }
        }
    }

    private fun loadPrivateWorkspaces() {
        loadResumes()
        loadSessions()
        loadPractice()
        loadLearningToday()
        loadReviewPlans()
        loadInterviewKits()
    }

    fun logout() {
        api.logout()
        _state.update {
            it.copy(
                account = null,
                accountMessage = "已退出登录",
                sessionId = null,
                messages = emptyList(),
                resumes = emptyList(),
                sessions = emptyList(),
                selectedResumeId = null,
                settings = null,
                practiceQuestions = emptyList(),
                practiceResult = null,
                learningToday = LearningToday(),
                reviewPlans = emptyList(),
                interviewKits = emptyList()
            )
        }
    }

    fun refreshAccount() {
        viewModelScope.launch {
            runCatching {
                withContext(Dispatchers.IO) {
                    val account = api.account()
                    val settings = runCatching { api.settings() }.getOrNull()
                    account to settings
                }
            }.onSuccess { (account, settings) ->
                _state.update { it.copy(account = account, settings = settings) }
                loadPrivateWorkspaces()
            }.onFailure {
                _state.update { it.copy(account = null) }
            }
        }
    }

    fun loadLearningToday() {
        if (_state.value.account == null) return
        viewModelScope.launch {
            runCatching { withContext(Dispatchers.IO) { api.learningToday() } }
                .onSuccess { today -> _state.update { it.copy(learningToday = today, learningMessage = "") } }
                .onFailure { error -> _state.update { it.copy(learningMessage = "加载今日任务失败：${error.message}") } }
        }
    }

    fun runLearningTask(task: LearningTask) {
        if (!requireAccount("执行学习任务前需要登录。") || _state.value.busy) return
        val action = if (task.done) "reopen" else if (task.status == "todo") "start" else "complete"
        _state.update { it.copy(busy = true, learningMessage = "") }
        viewModelScope.launch {
            runCatching { withContext(Dispatchers.IO) { api.commandLearningTask(task, action) } }
                .onSuccess {
                    _state.update { state -> state.copy(busy = false, learningMessage = "任务状态已更新") }
                    loadLearningToday()
                }
                .onFailure { error -> _state.update { it.copy(busy = false, learningMessage = "更新失败：${error.message}") } }
        }
    }

    fun openLearningTask(task: LearningTask) {
        _state.update {
            it.copy(
                activeLearningTarget = task.target,
                activeLearningTaskType = task.taskType,
                selectedPracticeCategory = task.target.category.ifBlank { it.selectedPracticeCategory },
                selectedReviewPlanId = task.target.planId.takeIf { planId -> planId.isNotBlank() }
                    ?: it.selectedReviewPlanId
            )
        }
        if (task.taskType == "practice") loadPractice()
    }

    fun loadReviewPlans(append: Boolean = false) {
        if (_state.value.account == null) return
        if (!paging.add("plans") || (append && !_state.value.reviewPlansHasMore)) return
        viewModelScope.launch {
            runCatching { withContext(Dispatchers.IO) { api.listReviewPlans(offset = if (append) _state.value.reviewPlans.size else 0) } }
                .onSuccess { plans -> _state.update { state ->
                    val merged = if (append) (state.reviewPlans + plans).distinctBy { it.id } else plans
                    state.copy(reviewPlans = merged, reviewPlansHasMore = plans.size == 20, selectedReviewPlanId = state.selectedReviewPlanId ?: merged.firstOrNull()?.id)
                } }
                .onFailure { error -> _state.update { it.copy(reviewMessage = "加载复习计划失败：${error.message}") } }
            paging.remove("plans")
        }
    }

    fun generateReviewPlan(targetRole: String, days: Int, hours: Double, focus: String) {
        if (!requireAccount("生成复习计划前需要登录。") || _state.value.busy) return
        _state.update { it.copy(busy = true, reviewMessage = "正在生成计划…") }
        viewModelScope.launch {
            runCatching { withContext(Dispatchers.IO) { api.generateReviewPlan(targetRole, days, hours, focus, _state.value.selectedResumeId) } }
                .onSuccess { id ->
                    _state.update { it.copy(busy = false, selectedReviewPlanId = id, reviewMessage = "计划已生成") }
                    loadReviewPlans()
                    loadLearningToday()
                }
                .onFailure { error -> _state.update { it.copy(busy = false, reviewMessage = "生成失败：${error.message}") } }
        }
    }

    fun checkinReview(minutes: Int, note: String) {
        val planId = _state.value.selectedReviewPlanId ?: return
        if (_state.value.busy) return
        _state.update { it.copy(busy = true, reviewMessage = "") }
        viewModelScope.launch {
            runCatching { withContext(Dispatchers.IO) { api.checkin(planId, minutes, note) } }
                .onSuccess { streak ->
                    _state.update { it.copy(busy = false, reviewMessage = "打卡成功，连续 $streak 天") }
                    loadLearningToday()
                }
                .onFailure { error -> _state.update { it.copy(busy = false, reviewMessage = "打卡失败：${error.message}") } }
        }
    }

    fun loadInterviewKits(append: Boolean = false) {
        if (_state.value.account == null) return
        if (!paging.add("kits") || (append && !_state.value.interviewKitsHasMore)) return
        viewModelScope.launch {
            runCatching { withContext(Dispatchers.IO) { api.listInterviewKits(offset = if (append) _state.value.interviewKits.size else 0) } }
                .onSuccess { kits -> _state.update { state -> state.copy(interviewKits = if (append) (state.interviewKits + kits).distinctBy { it.id } else kits, interviewKitsHasMore = kits.size == 20) } }
                .onFailure { error -> _state.update { it.copy(interviewerMessage = "加载面试题单失败：${error.message}") } }
            paging.remove("kits")
        }
    }

    fun createInterviewKit(targetRole: String, duration: Int, dimensions: List<String>) {
        if (!requireAccount("创建面试官题单前需要登录。") || _state.value.busy) return
        _state.update { it.copy(busy = true, interviewerMessage = "") }
        viewModelScope.launch {
            runCatching { withContext(Dispatchers.IO) { api.createInterviewKit(targetRole, duration, dimensions) } }
                .onSuccess { kit ->
                    _state.update { it.copy(busy = false, interviewKits = listOf(kit) + it.interviewKits, interviewerMessage = "面试题单已创建") }
                }
                .onFailure { error -> _state.update { it.copy(busy = false, interviewerMessage = "创建失败：${error.message}") } }
        }
    }

    fun recharge(amountCredits: String) {
        val current = _state.value
        if (current.account == null) {
            requireAccount("充值积分前需要先登录账号。")
            return
        }
        if (current.busy) return
        _state.update { it.copy(busy = true, accountMessage = "") }
        viewModelScope.launch {
            runCatching {
                withContext(Dispatchers.IO) { api.recharge(amountCredits) }
            }.onSuccess { account ->
                _state.update {
                    it.copy(
                        busy = false,
                        account = account,
                        accountMessage = "已充值 $amountCredits 积分"
                    )
                }
            }.onFailure { error ->
                _state.update {
                    it.copy(
                        busy = false,
                        accountMessage = "充值失败：${error.message}"
                    )
                }
            }
        }
    }

    fun dismissAuthPrompt() {
        _state.update { it.copy(authPrompt = null) }
    }

    fun selectIndustry(value: String) {
        _state.update { it.copy(selectedIndustry = value) }
    }

    fun updateResumeDraftName(value: String) {
        _state.update { it.copy(resumeDraftName = value) }
    }

    fun updateResumeDraftText(value: String) {
        _state.update { it.copy(resumeDraftText = value) }
    }

    fun updateInput(value: String) {
        _state.update { it.copy(input = value) }
    }

    fun loadPractice(append: Boolean = false) {
        if (_state.value.account == null) return
        if (!paging.add("practice") || (append && !_state.value.practiceHasMore)) return
        viewModelScope.launch {
            runCatching {
                withContext(Dispatchers.IO) {
                    val categories = api.listPracticeCategories()
                    val selected = _state.value.selectedPracticeCategory.takeIf { current ->
                        categories.any { it.value == current }
                    } ?: (categories.firstOrNull()?.value ?: "ai_application")
                    val questions = api.listPracticeQuestions(selected, offset = if (append) _state.value.practiceQuestions.size else 0)
                    Triple(categories, selected, questions)
                }
            }.onSuccess { (categories, selected, questions) ->
                practiceStartedAtMillis = System.currentTimeMillis()
                _state.update {
                    it.copy(
                        practiceCategories = categories,
                        selectedPracticeCategory = selected,
                        practiceQuestions = if (append) (it.practiceQuestions + questions.items).distinctBy { question -> question.id } else questions.items,
                        practiceHasMore = questions.hasMore,
                        currentPracticeIndex = it.activeLearningTarget?.questionId
                            ?.takeIf { questionId -> it.activeLearningTaskType == "practice" && questionId.isNotBlank() }
                            ?.let { questionId -> questions.items.indexOfFirst { question -> question.id == questionId } }
                            ?.takeIf { index -> index >= 0 } ?: 0,
                        practiceAnswer = "",
                        practiceResult = null
                    )
                }
            }.onFailure { error ->
                _state.update { it.copy(practiceMessage = "加载刷题失败：${error.message}") }
            }
            paging.remove("practice")
        }
    }

    fun selectPracticeCategory(value: String) {
        _state.update { it.copy(selectedPracticeCategory = value) }
        loadPractice()
    }

    fun updatePracticeAnswer(value: String) {
        _state.update { it.copy(practiceAnswer = value) }
    }

    fun choosePracticeOption(value: String) {
        updatePracticeAnswer(value)
    }

    fun nextPracticeQuestion() {
        val questions = _state.value.practiceQuestions
        if (questions.isEmpty()) return
        practiceStartedAtMillis = System.currentTimeMillis()
        _state.update {
            it.copy(
                currentPracticeIndex = (it.currentPracticeIndex + 1) % questions.size,
                practiceAnswer = "",
                practiceResult = null
            )
        }
        if (_state.value.currentPracticeIndex >= _state.value.practiceQuestions.size - 6) loadPractice(append = true)
    }

    fun seedPracticeQuestions() {
        if (!requireAccount("初始化练习样题前需要先登录账号。")) return
        viewModelScope.launch {
            runCatching {
                withContext(Dispatchers.IO) { api.seedPracticeQuestions() }
            }.onSuccess { result ->
                _state.update { it.copy(practiceMessage = "样题已初始化：${result.total} 道") }
                loadPractice()
            }.onFailure { error ->
                _state.update { it.copy(practiceMessage = "初始化样题失败：${error.message}") }
            }
        }
    }

    fun submitPracticeAnswer() {
        val question = currentPracticeQuestion ?: return
        if (!requireAccount("提交答案前需要先登录账号。") || _state.value.busy) return
        val answer = _state.value.practiceAnswer
        val elapsed = ((System.currentTimeMillis() - practiceStartedAtMillis) / 1000).toInt().coerceAtLeast(0)
        _state.update { it.copy(busy = true, practiceMessage = "") }
        viewModelScope.launch {
            runCatching {
                withContext(Dispatchers.IO) { api.submitPracticeAttempt(question.id, answer, elapsed) }
            }.onSuccess { result ->
                _state.update { it.copy(busy = false, practiceResult = result) }
            }.onFailure { error ->
                _state.update { it.copy(busy = false, practiceMessage = "提交答案失败：${error.message}") }
            }
        }
    }

    fun loadResumes(append: Boolean = false) {
        if (_state.value.account == null) return
        if (!paging.add("resumes") || (append && !_state.value.resumesHasMore)) return
        viewModelScope.launch {
            runCatching {
                withContext(Dispatchers.IO) { api.listResumes(offset = if (append) _state.value.resumes.size else 0) }
            }.onSuccess { resumes ->
                _state.update {
                    it.copy(
                        resumes = if (append) (it.resumes + resumes).distinctBy { resume -> resume.id } else resumes,
                        resumesHasMore = resumes.size == 20,
                        selectedResumeId = it.selectedResumeId ?: resumes.firstOrNull()?.id
                    )
                }
            }.onFailure { error ->
                _state.update { it.copy(resumeMessage = "加载简历失败：${error.message}") }
            }
            paging.remove("resumes")
        }
    }

    fun importResumeDraft() {
        val current = _state.value
        val text = current.resumeDraftText.trim()
        if (!requireAccount("上传和保存简历前需要先登录账号。") || text.isEmpty() || current.busy) return
        _state.update { it.copy(busy = true, resumeMessage = "") }
        viewModelScope.launch {
            runCatching {
                withContext(Dispatchers.IO) {
                    api.importResume(current.resumeDraftName.ifBlank { "resume.md" }, text)
                }
            }.onSuccess { resume ->
                _state.update {
                    it.copy(
                        busy = false,
                        selectedResumeId = resume.id,
                        resumeDraftText = "",
                        resumeMessage = "简历已保存"
                    )
                }
                loadResumes()
            }.onFailure { error ->
                _state.update { it.copy(busy = false, resumeMessage = "上传简历失败：${error.message}") }
            }
        }
    }

    fun selectResume(id: String) {
        _state.update { it.copy(selectedResumeId = id, resumeMessage = "已选择当前简历") }
    }

    fun deleteResume(id: String) {
        if (!requireAccount("删除简历前需要先登录账号。")) return
        viewModelScope.launch {
            runCatching {
                withContext(Dispatchers.IO) { api.deleteResume(id) }
            }.onSuccess {
                _state.update {
                    it.copy(
                        selectedResumeId = if (it.selectedResumeId == id) null else it.selectedResumeId,
                        resumeMessage = "简历已删除"
                    )
                }
                loadResumes()
            }.onFailure { error ->
                _state.update { it.copy(resumeMessage = "删除简历失败：${error.message}") }
            }
        }
    }

    fun loadSessions(append: Boolean = false) {
        if (_state.value.account == null) return
        if (!paging.add("sessions") || (append && !_state.value.sessionsHasMore)) return
        viewModelScope.launch {
            runCatching {
                withContext(Dispatchers.IO) { api.listSessions(offset = if (append) _state.value.sessions.size else 0) }
            }.onSuccess { sessions ->
                _state.update { it.copy(sessions = if (append) (it.sessions + sessions).distinctBy { session -> session.id } else sessions, sessionsHasMore = sessions.size == 20) }
            }.onFailure { error ->
                _state.update { it.copy(historyMessage = "加载历史失败：${error.message}") }
            }
            paging.remove("sessions")
        }
    }

    fun restoreSession(id: String) {
        if (!requireAccount("恢复历史会话前需要先登录账号。")) return
        _state.update { it.copy(busy = true, historyMessage = "") }
        viewModelScope.launch {
            runCatching {
                withContext(Dispatchers.IO) { api.getSession(id) }
            }.onSuccess { detail ->
                val summary = _state.value.sessions.firstOrNull { it.id == id }
                val messages = detail.turns.flatMap { turn ->
                    buildList {
                        turn.interviewer?.takeIf { it.isNotBlank() }?.let {
                            add(ChatMessage(ChatMessage.Role.Agent, it))
                        }
                        turn.candidate?.takeIf { it.isNotBlank() }?.let {
                            add(ChatMessage(ChatMessage.Role.User, it))
                        }
                    }
                }
                _state.update {
                    it.copy(
                        busy = false,
                        sessionId = detail.id,
                        selectedResumeId = summary?.resumeId ?: it.selectedResumeId,
                        selectedIndustry = summary?.industry ?: it.selectedIndustry,
                        messages = messages,
                        historyMessage = "会话已恢复"
                    )
                }
            }.onFailure { error ->
                _state.update { it.copy(busy = false, historyMessage = "恢复会话失败：${error.message}") }
            }
        }
    }

    fun deleteSession(id: String) {
        if (!requireAccount("删除历史会话前需要先登录账号。")) return
        viewModelScope.launch {
            runCatching {
                withContext(Dispatchers.IO) { api.deleteSession(id) }
            }.onSuccess {
                _state.update {
                    it.copy(
                        sessionId = if (it.sessionId == id) null else it.sessionId,
                        messages = if (it.sessionId == id) emptyList() else it.messages,
                        historyMessage = "历史会话已删除"
                    )
                }
                loadSessions()
            }.onFailure { error ->
                _state.update { it.copy(historyMessage = "删除历史失败：${error.message}") }
            }
        }
    }

    fun updateDefaultMode(mode: String) {
        if (!requireAccount("更新设置前需要先登录账号。")) return
        viewModelScope.launch {
            runCatching {
                withContext(Dispatchers.IO) { api.updateDefaultInterviewMode(mode) }
            }.onSuccess { settings ->
                _state.update { it.copy(settings = settings, accountMessage = "设置已保存") }
            }.onFailure { error ->
                _state.update { it.copy(accountMessage = "保存设置失败：${error.message}") }
            }
        }
    }

    fun startInterview() {
        val current = _state.value
        if (current.busy) return
        if (!requireAccount("开始面试前需要先登录，登录后会保存会话、简历和用量记录。")) return
        _state.update { it.copy(busy = true, messages = emptyList()) }
        viewModelScope.launch {
            runCatching {
                withContext(Dispatchers.IO) {
                    api.createSession(
                        CreateSessionRequest(
                            industry = current.selectedIndustry,
                            resumeId = current.selectedResumeId,
                            mode = current.activeLearningTarget?.mode?.takeIf { current.activeLearningTaskType == "interview" && it.isNotBlank() } ?: "interviewer",
                            interviewGoal = current.activeLearningTarget?.focus?.takeIf { current.activeLearningTaskType == "interview" && it.isNotBlank() }
                                ?: "请基于我的简历和 AI 项目经历进行真实面试。",
                            planTaskId = current.activeLearningTarget?.taskId?.takeIf { current.activeLearningTaskType == "interview" && it.isNotBlank() }
                        )
                    )
                }
            }.onSuccess { response ->
                refreshAccount()
                loadSessions()
                _state.update {
                    it.copy(
                        busy = false,
                        sessionId = response.sessionId,
                        messages = listOf(ChatMessage(ChatMessage.Role.Agent, response.message))
                    )
                }
            }.onFailure { error ->
                appendSystem("创建会话失败：${error.message}")
                _state.update { it.copy(busy = false) }
            }
        }
    }

    fun send() {
        val current = _state.value
        val message = current.input.trim()
        val sessionId = current.sessionId ?: return
        if (message.isEmpty() || current.busy) return
        if (!requireAccount("发送回答前需要先登录账号。")) return
        _state.update {
            it.copy(
                busy = true,
                input = "",
                messages = it.messages + ChatMessage(ChatMessage.Role.User, message)
            )
        }
        viewModelScope.launch {
            runCatching {
                withContext(Dispatchers.IO) { api.streamMessage(sessionId, message) }
            }.onSuccess { events ->
                val reply = events.lastOrNull { it.event == "message.done" }?.data?.get("message") as? String
                val streamError = events.lastOrNull { it.event == "message.error" }?.data?.get("message") as? String
                if (reply == null && streamError == null) {
                    runCatching {
                        withContext(Dispatchers.IO) { api.sendMessage(sessionId, message) }
                    }.onSuccess { response ->
                        _state.update {
                            it.copy(
                                busy = false,
                                messages = it.messages + ChatMessage(ChatMessage.Role.Agent, response.message)
                            )
                        }
                    }.onFailure { error ->
                        appendSystem("发送失败：${error.message}")
                        _state.update { it.copy(busy = false) }
                    }
                } else {
                    _state.update {
                        it.copy(
                            busy = false,
                            messages = it.messages + ChatMessage(
                                if (reply == null) ChatMessage.Role.System else ChatMessage.Role.Agent,
                                reply ?: "发送失败：$streamError"
                            )
                        )
                    }
                }
                refreshAccount()
                loadSessions()
            }.onFailure { error ->
                appendSystem("发送失败：${error.message}")
                _state.update { it.copy(busy = false) }
            }
        }
    }

    private fun appendSystem(text: String) {
        _state.update { it.copy(messages = it.messages + ChatMessage(ChatMessage.Role.System, text)) }
    }

    private fun requireAccount(message: String): Boolean {
        if (_state.value.account != null) return true
        _state.update { it.copy(authPrompt = message) }
        return false
    }
}

class ChatViewModelFactory(
    private val api: InterviewApiClient
) : ViewModelProvider.Factory {
    @Suppress("UNCHECKED_CAST")
    override fun <T : ViewModel> create(modelClass: Class<T>): T {
        return ChatViewModel(api) as T
    }
}
