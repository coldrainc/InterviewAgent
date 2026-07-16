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
fun ProfileScreen(
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
