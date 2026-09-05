package com.interviewagent.ui

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp

@Composable
fun HistoryScreen(
    state: ChatUiState,
    onRefresh: () -> Unit,
    onRestore: (String) -> Unit,
    onDelete: (String) -> Unit
) {
    LazyColumn(
        modifier = Modifier.fillMaxSize(),
        verticalArrangement = Arrangement.spacedBy(12.dp)
    ) {
        item {
            Card(modifier = Modifier.fillMaxWidth(), shape = RoundedCornerShape(10.dp)) {
                Column(modifier = Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    Text("历史会话", style = MaterialTheme.typography.titleMedium)
                    Text(
                        state.historyMessage.ifBlank { "可恢复最近的面试上下文继续对话。" },
                        style = MaterialTheme.typography.bodySmall,
                        color = if (state.historyMessage.contains("失败")) BrandColors.Danger else BrandColors.Muted
                    )
                    OutlinedButton(onClick = onRefresh, modifier = Modifier.fillMaxWidth()) {
                        Text("刷新历史")
                    }
                }
            }
        }

        items(state.sessions) { session ->
            Card(modifier = Modifier.fillMaxWidth(), shape = RoundedCornerShape(10.dp)) {
                Column(modifier = Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                        Text(session.targetRole, style = MaterialTheme.typography.titleSmall)
                        Text(session.status, style = MaterialTheme.typography.labelSmall, color = BrandColors.Muted)
                    }
                    Text(
                        "${if (session.mode == "candidate") "Agent 回答我" else "Agent 面试我"} · ${session.seniority} · ${session.updatedAt}",
                        style = MaterialTheme.typography.bodySmall,
                        color = BrandColors.Muted
                    )
                    Row(horizontalArrangement = Arrangement.spacedBy(8.dp), modifier = Modifier.fillMaxWidth()) {
                        Button(onClick = { onRestore(session.id) }, modifier = Modifier.weight(1f)) {
                            Text("恢复")
                        }
                        OutlinedButton(onClick = { onDelete(session.id) }, modifier = Modifier.weight(1f)) {
                            Text("删除")
                        }
                    }
                }
            }
        }
    }
}
