package com.interviewagent.ui

import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.viewModelScope
import com.interviewagent.data.AccountResponse
import com.interviewagent.data.ChatMessage
import com.interviewagent.data.CreateSessionRequest
import com.interviewagent.data.IndustryOption
import com.interviewagent.data.InterviewApiClient
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
    val authPrompt: String? = null
)

class ChatViewModel(
    private val api: InterviewApiClient
) : ViewModel() {
    private val _state = MutableStateFlow(ChatUiState())
    val state: StateFlow<ChatUiState> = _state

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
                        selectedIndustry = industries.firstOrNull()?.value ?: "internet"
                    )
                }
            }
        }
    }

    fun devLogin() {
        if (_state.value.busy) return
        _state.update { it.copy(busy = true, accountMessage = "") }
        viewModelScope.launch {
            runCatching {
                withContext(Dispatchers.IO) {
                    api.devLogin()
                    api.account()
                }
            }.onSuccess { account ->
                _state.update {
                    it.copy(
                        busy = false,
                        account = account,
                        accountMessage = "已登录开发账号",
                        authPrompt = null
                    )
                }
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
                messages = emptyList()
            )
        }
    }

    fun refreshAccount() {
        viewModelScope.launch {
            runCatching {
                withContext(Dispatchers.IO) { api.account() }
            }.onSuccess { account ->
                _state.update { it.copy(account = account) }
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

    fun updateInput(value: String) {
        _state.update { it.copy(input = value) }
    }

    fun startInterview() {
        val current = _state.value
        if (current.busy) return
        if (!requireAccount("开始面试前需要先登录，登录后会保存会话、简历和用量记录。")) return
        _state.update { it.copy(busy = true, messages = emptyList()) }
        viewModelScope.launch {
            runCatching {
                withContext(Dispatchers.IO) {
                    api.createSession(CreateSessionRequest(industry = current.selectedIndustry))
                }
            }.onSuccess { response ->
                refreshAccount()
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
                refreshAccount()
                _state.update {
                    it.copy(
                        busy = false,
                        messages = it.messages + ChatMessage(ChatMessage.Role.Agent, reply ?: "流式响应结束，但未返回消息。")
                    )
                }
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
