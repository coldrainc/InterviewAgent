package com.interviewagent.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.ExposedDropdownMenuBox
import androidx.compose.material3.ExposedDropdownMenuDefaults
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.unit.dp
import com.interviewagent.data.ChatMessage

@Composable
fun InterviewApp(viewModel: ChatViewModel) {
    val state by viewModel.state.collectAsState()
    var selectedTab by remember { mutableStateOf(AppTab.Chat) }

    MaterialTheme {
        Column(
            modifier = Modifier
                .fillMaxSize()
                .background(Color(0xFFEDF1F7))
                .padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp)
        ) {
            Box(modifier = Modifier.weight(1f)) {
                if (selectedTab == AppTab.Chat) {
                    ChatScreen(
                        state = state,
                        onSelectIndustry = viewModel::selectIndustry,
                        onStart = viewModel::startInterview,
                        onInput = viewModel::updateInput,
                        onSend = viewModel::send
                    )
                } else {
                    ProfileScreen(
                        state = state,
                        onDevLogin = viewModel::devLogin,
                        onRefreshAccount = viewModel::refreshAccount,
                        onRecharge = viewModel::recharge,
                        onLogout = viewModel::logout
                    )
                }
            }
            BottomTabs(selected = selectedTab, onSelect = { selectedTab = it })
        }

        state.authPrompt?.let { prompt ->
            AlertDialog(
                onDismissRequest = viewModel::dismissAuthPrompt,
                title = { Text("需要登录") },
                text = { Text(prompt) },
                confirmButton = {
                    TextButton(
                        onClick = {
                            viewModel.dismissAuthPrompt()
                            selectedTab = AppTab.Profile
                        }
                    ) {
                        Text("去我的")
                    }
                },
                dismissButton = {
                    TextButton(onClick = viewModel::dismissAuthPrompt) {
                        Text("稍后")
                    }
                }
            )
        }
    }
}

@Composable
private fun ChatScreen(
    state: ChatUiState,
    onSelectIndustry: (String) -> Unit,
    onStart: () -> Unit,
    onInput: (String) -> Unit,
    onSend: () -> Unit
) {
    Column(
        modifier = Modifier.fillMaxSize(),
        verticalArrangement = Arrangement.spacedBy(12.dp)
    ) {
        Header(healthText = state.healthText, accountText = state.account?.creditBalance?.let { "$it 积分" } ?: "未登录")
        Controls(
            state = state,
            onSelectIndustry = onSelectIndustry,
            onStart = onStart
        )
        LazyColumn(
            modifier = Modifier
                .weight(1f)
                .fillMaxWidth(),
            verticalArrangement = Arrangement.spacedBy(10.dp)
        ) {
            items(state.messages) { message ->
                MessageBubble(message)
            }
        }
        Composer(
            input = state.input,
            busy = state.busy,
            enabled = state.sessionId != null,
            onInput = onInput,
            onSend = onSend
        )
    }
}

@Composable
private fun Header(healthText: String, accountText: String) {
    Card(modifier = Modifier.fillMaxWidth(), shape = RoundedCornerShape(10.dp)) {
        Row(modifier = Modifier.padding(16.dp), verticalAlignment = Alignment.CenterVertically) {
            Column(modifier = Modifier.weight(1f)) {
                Text("Interview Agent", style = MaterialTheme.typography.titleLarge)
                Spacer(Modifier.height(4.dp))
                Text(healthText, style = MaterialTheme.typography.bodySmall, color = Color(0xFF687386))
            }
            Text(accountText, style = MaterialTheme.typography.labelMedium, color = Color(0xFF0F4D63))
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun Controls(
    state: ChatUiState,
    onSelectIndustry: (String) -> Unit,
    onStart: () -> Unit
) {
    var expanded by remember { mutableStateOf(false) }
    val selected = state.industries.firstOrNull { it.value == state.selectedIndustry }

    Card(modifier = Modifier.fillMaxWidth(), shape = RoundedCornerShape(10.dp)) {
        Column(modifier = Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
            ExposedDropdownMenuBox(expanded = expanded, onExpandedChange = { expanded = !expanded }) {
                OutlinedTextField(
                    value = selected?.label ?: "互联网行业",
                    onValueChange = {},
                    readOnly = true,
                    label = { Text("行业") },
                    trailingIcon = { ExposedDropdownMenuDefaults.TrailingIcon(expanded = expanded) },
                    modifier = Modifier
                        .menuAnchor()
                        .fillMaxWidth()
                )
                ExposedDropdownMenu(expanded = expanded, onDismissRequest = { expanded = false }) {
                    state.industries.forEach { industry ->
                        DropdownMenuItem(
                            text = { Text(industry.label) },
                            onClick = {
                                onSelectIndustry(industry.value)
                                expanded = false
                            }
                        )
                    }
                }
            }
            Button(onClick = onStart, enabled = !state.busy, modifier = Modifier.fillMaxWidth()) {
                Text("开始面试")
            }
        }
    }
}

@Composable
private fun ProfileScreen(
    state: ChatUiState,
    onDevLogin: () -> Unit,
    onRefreshAccount: () -> Unit,
    onRecharge: (String) -> Unit,
    onLogout: () -> Unit
) {
    LazyColumn(
        modifier = Modifier.fillMaxSize(),
        verticalArrangement = Arrangement.spacedBy(12.dp)
    ) {
        item {
            Card(modifier = Modifier.fillMaxWidth(), shape = RoundedCornerShape(10.dp)) {
                Row(
                    modifier = Modifier.padding(16.dp),
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.spacedBy(14.dp)
                ) {
                    Box(
                        modifier = Modifier
                            .size(58.dp)
                            .background(Color(0xFF2563EB), RoundedCornerShape(12.dp)),
                        contentAlignment = Alignment.Center
                    ) {
                        Text(if (state.account == null) "未" else "我", color = Color.White)
                    }
                    Column(modifier = Modifier.weight(1f)) {
                        Text(state.account?.displayName ?: "未登录", style = MaterialTheme.typography.titleLarge)
                        Text(
                            state.account?.email ?: state.account?.userId ?: "登录后保存简历、会话和用量记录",
                            style = MaterialTheme.typography.bodySmall,
                            color = Color(0xFF687386)
                        )
                    }
                }
            }
        }

        item {
            Card(modifier = Modifier.fillMaxWidth(), shape = RoundedCornerShape(10.dp)) {
                Column(modifier = Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
                    Text("权益", style = MaterialTheme.typography.titleMedium)
                    Row(horizontalArrangement = Arrangement.spacedBy(10.dp), modifier = Modifier.fillMaxWidth()) {
                        MetricBox("剩余试用", state.account?.trialUsesRemaining?.toString() ?: "-", Modifier.weight(1f))
                        MetricBox("积分余额", state.account?.creditBalance ?: "-", Modifier.weight(1f))
                    }
                    Row(horizontalArrangement = Arrangement.spacedBy(8.dp), modifier = Modifier.fillMaxWidth()) {
                        listOf("10", "50", "100").forEach { amount ->
                            OutlinedButton(
                                onClick = { onRecharge(amount) },
                                enabled = state.account != null && !state.busy,
                                modifier = Modifier.weight(1f)
                            ) {
                                Text("充 $amount")
                            }
                        }
                    }
                    if (state.accountMessage.isNotBlank()) {
                        Text(
                            state.accountMessage,
                            style = MaterialTheme.typography.bodySmall,
                            color = if (state.accountMessage.contains("失败")) Color(0xFFB91C1C) else Color(0xFF166534)
                        )
                    }
                }
            }
        }

        item {
            Card(modifier = Modifier.fillMaxWidth(), shape = RoundedCornerShape(10.dp)) {
                Column(modifier = Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    Text("账号信息", style = MaterialTheme.typography.titleMedium)
                    InfoRow("租户", state.account?.tenantId ?: "-")
                    InfoRow("用户", state.account?.userId ?: "-")
                    InfoRow("平台", state.account?.platform ?: "-")
                    InfoRow("服务", state.healthText)
                }
            }
        }

        item {
            Card(modifier = Modifier.fillMaxWidth(), shape = RoundedCornerShape(10.dp)) {
                Column(modifier = Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
                    Button(
                        onClick = if (state.account == null) onDevLogin else onRefreshAccount,
                        enabled = !state.busy,
                        modifier = Modifier.fillMaxWidth()
                    ) {
                        Text(if (state.account == null) "开发登录" else "刷新账户")
                    }
                    if (state.account != null) {
                        OutlinedButton(onClick = onLogout, modifier = Modifier.fillMaxWidth()) {
                            Text("退出登录")
                        }
                    }
                }
            }
        }
    }
}

@Composable
private fun MetricBox(title: String, value: String, modifier: Modifier = Modifier) {
    Column(
        modifier = modifier
            .background(Color(0xFFF8FAFC), RoundedCornerShape(10.dp))
            .padding(12.dp)
    ) {
        Text(title, style = MaterialTheme.typography.labelSmall, color = Color(0xFF687386))
        Spacer(Modifier.height(6.dp))
        Text(value, style = MaterialTheme.typography.titleLarge, color = Color(0xFF0F4D63))
    }
}

@Composable
private fun InfoRow(label: String, value: String) {
    Row(modifier = Modifier.fillMaxWidth()) {
        Text(label, color = Color(0xFF687386), modifier = Modifier.weight(1f))
        Text(value, color = Color(0xFF162033), modifier = Modifier.weight(2f))
    }
}

@Composable
private fun BottomTabs(selected: AppTab, onSelect: (AppTab) -> Unit) {
    Card(modifier = Modifier.fillMaxWidth(), shape = RoundedCornerShape(10.dp)) {
        Row(modifier = Modifier.padding(6.dp), horizontalArrangement = Arrangement.spacedBy(6.dp)) {
            TabButton("面试", selected == AppTab.Chat, Modifier.weight(1f)) { onSelect(AppTab.Chat) }
            TabButton("我的", selected == AppTab.Profile, Modifier.weight(1f)) { onSelect(AppTab.Profile) }
        }
    }
}

@Composable
private fun TabButton(text: String, active: Boolean, modifier: Modifier = Modifier, onClick: () -> Unit) {
    if (active) {
        Button(onClick = onClick, modifier = modifier) {
            Text(text)
        }
    } else {
        TextButton(onClick = onClick, modifier = modifier) {
            Text(text)
        }
    }
}

private enum class AppTab {
    Chat,
    Profile
}

@Composable
private fun MessageBubble(message: ChatMessage) {
    val isUser = message.role == ChatMessage.Role.User
    Row(
        modifier = Modifier.fillMaxWidth(),
        horizontalArrangement = if (isUser) Arrangement.End else Arrangement.Start
    ) {
        Column(
            modifier = Modifier
                .fillMaxWidth(0.86f)
                .background(
                    if (isUser) Color(0xFF2563EB) else Color.White,
                    RoundedCornerShape(10.dp)
                )
                .padding(12.dp)
        ) {
            Text(
                text = when (message.role) {
                    ChatMessage.Role.User -> "我"
                    ChatMessage.Role.Agent -> "面试官"
                    ChatMessage.Role.System -> "系统"
                },
                style = MaterialTheme.typography.labelSmall,
                color = if (isUser) Color.White.copy(alpha = 0.78f) else Color(0xFF687386)
            )
            Spacer(Modifier.height(4.dp))
            Text(message.text, color = if (isUser) Color.White else Color(0xFF162033))
        }
    }
}

@Composable
private fun Composer(
    input: String,
    busy: Boolean,
    enabled: Boolean,
    onInput: (String) -> Unit,
    onSend: () -> Unit
) {
    Card(modifier = Modifier.fillMaxWidth(), shape = RoundedCornerShape(10.dp)) {
        Row(
            modifier = Modifier.padding(12.dp),
            verticalAlignment = Alignment.Bottom,
            horizontalArrangement = Arrangement.spacedBy(8.dp)
        ) {
            OutlinedTextField(
                value = input,
                onValueChange = onInput,
                modifier = Modifier.weight(1f),
                minLines = 1,
                maxLines = 5,
                placeholder = { Text("输入你的回答") }
            )
            Button(onClick = onSend, enabled = enabled && !busy && input.isNotBlank()) {
                Text("发送")
            }
        }
    }
}
