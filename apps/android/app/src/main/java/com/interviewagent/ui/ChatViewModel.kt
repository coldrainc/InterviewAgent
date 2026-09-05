package com.interviewagent.ui

import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.viewModelScope
import com.interviewagent.data.AccountResponse
import com.interviewagent.data.ChatMessage
import com.interviewagent.data.CreateSessionRequest
import com.interviewagent.data.IndustryOption
import com.interviewagent.data.InterviewApiClient
import com.interviewagent.data.PracticeAttemptResponse
import com.interviewagent.data.PracticeCategory
import com.interviewagent.data.PracticeQuestion
import com.interviewagent.data.ResumeRecord
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
    val practiceMessage: String = ""
)

class ChatViewModel(
    private val api: InterviewApiClient
) : ViewModel() {
    private val _state = MutableStateFlow(ChatUiState())
    val state: StateFlow<ChatUiState> = _state
    private var practiceStartedAtMillis: Long = System.currentTimeMillis()

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

    fun devLogin() {
        if (_state.value.busy) return
        _state.update { it.copy(busy = true, accountMessage = "") }
        viewModelScope.launch {
            runCatching {
                withContext(Dispatchers.IO) {
                    api.devLogin()
                    val account = api.account()
                    val settings = runCatching { api.settings() }.getOrNull()
                    account to settings
                }
            }.onSuccess { (account, settings) ->
                _state.update {
                    it.copy(
                        busy = false,
                        account = account,
                        settings = settings,
                        accountMessage = "已登录开发账号",
                        authPrompt = null
                    )
                }
                loadResumes()
                loadSessions()
                loadPractice()
            }.onFailure { error ->
                _state.update {
                    it.copy(
                        busy = false,
                        accountMessage = "开发登录失败：${error.message}"
                    )
                }
            }
        }
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
                practiceResult = null
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
                loadResumes()
                loadSessions()
                loadPractice()
            }.onFailure {
                _state.update { it.copy(account = null) }
            }
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

    fun loadPractice() {
        if (_state.value.account == null) return
        viewModelScope.launch {
            runCatching {
                withContext(Dispatchers.IO) {
                    val categories = api.listPracticeCategories()
                    val selected = _state.value.selectedPracticeCategory.takeIf { current ->
                        categories.any { it.value == current }
                    } ?: (categories.firstOrNull()?.value ?: "ai_application")
                    val questions = api.listPracticeQuestions(selected)
                    Triple(categories, selected, questions)
                }
            }.onSuccess { (categories, selected, questions) ->
                practiceStartedAtMillis = System.currentTimeMillis()
                _state.update {
                    it.copy(
                        practiceCategories = categories,
                        selectedPracticeCategory = selected,
                        practiceQuestions = questions.items,
                        currentPracticeIndex = 0,
                        practiceAnswer = "",
                        practiceResult = null
                    )
                }
            }.onFailure { error ->
                _state.update { it.copy(practiceMessage = "加载刷题失败：${error.message}") }
            }
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

    fun loadResumes() {
        if (_state.value.account == null) return
        viewModelScope.launch {
            runCatching {
                withContext(Dispatchers.IO) { api.listResumes() }
            }.onSuccess { resumes ->
                _state.update {
                    it.copy(
                        resumes = resumes,
                        selectedResumeId = it.selectedResumeId ?: resumes.firstOrNull()?.id
                    )
                }
            }.onFailure { error ->
                _state.update { it.copy(resumeMessage = "加载简历失败：${error.message}") }
            }
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

    fun loadSessions() {
        if (_state.value.account == null) return
        viewModelScope.launch {
            runCatching {
                withContext(Dispatchers.IO) { api.listSessions() }
            }.onSuccess { sessions ->
                _state.update { it.copy(sessions = sessions) }
            }.onFailure { error ->
                _state.update { it.copy(historyMessage = "加载历史失败：${error.message}") }
            }
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
                            resumeId = current.selectedResumeId
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
