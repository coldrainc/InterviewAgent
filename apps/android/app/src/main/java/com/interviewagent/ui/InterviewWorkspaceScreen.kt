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
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp

@Composable
fun InterviewWorkspaceScreen(
    state: ChatUiState,
    onSelectIndustry: (String) -> Unit,
    onStart: () -> Unit,
    onInput: (String) -> Unit,
    onSend: () -> Unit,
    onCreateKit: (String, Int, List<String>) -> Unit,
    onRefreshKits: () -> Unit,
    onLoadMoreKits: () -> Unit
) {
    var interviewerMode by remember { mutableStateOf(false) }
    Column(modifier = Modifier.fillMaxSize(), verticalArrangement = Arrangement.spacedBy(10.dp)) {
        Row(modifier = Modifier.fillMaxWidth()) {
            TextButton(onClick = { interviewerMode = false }, modifier = Modifier.weight(1f)) { Text(if (!interviewerMode) "● 作为面试者" else "作为面试者") }
            TextButton(onClick = { interviewerMode = true }, modifier = Modifier.weight(1f)) { Text(if (interviewerMode) "● 作为面试官" else "作为面试官") }
        }
        if (interviewerMode) {
            InterviewerKitWorkspace(state, onCreateKit, onRefreshKits, onLoadMoreKits)
        } else {
            ChatScreen(state, onSelectIndustry, onStart, onInput, onSend)
        }
    }
}

@Composable
private fun InterviewerKitWorkspace(state: ChatUiState, onCreate: (String, Int, List<String>) -> Unit, onRefresh: () -> Unit, onLoadMore: () -> Unit) {
    var role by remember { mutableStateOf("AI 应用工程师") }
    var duration by remember { mutableIntStateOf(45) }
    LazyColumn(modifier = Modifier.fillMaxSize(), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        item {
            Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {
                Text("面试官工作台", style = MaterialTheme.typography.headlineSmall)
                Text("先定义岗位与评价维度，再进入结构化面试。", color = BrandColors.Muted)
            }
        }
        item {
            Card(modifier = Modifier.fillMaxWidth(), shape = RoundedCornerShape(14.dp)) {
                Column(modifier = Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
                    OutlinedTextField(role, { role = it }, label = { Text("目标岗位") }, modifier = Modifier.fillMaxWidth())
                    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        listOf(30, 45, 60).forEach { value ->
                            TextButton(onClick = { duration = value }, modifier = Modifier.weight(1f)) { Text(if (duration == value) "● $value 分钟" else "$value 分钟") }
                        }
                    }
                    Button(
                        onClick = { onCreate(role, duration, listOf("技术深度", "系统设计", "表达与协作")) },
                        enabled = !state.busy && role.isNotBlank(),
                        modifier = Modifier.fillMaxWidth()
                    ) { Text("创建结构化题单") }
                }
            }
        }
        items(state.interviewKits.size, key = { state.interviewKits[it].id }) { index ->
            val kit = state.interviewKits[index]
            if (index >= state.interviewKits.size - 6 && state.interviewKitsHasMore) LaunchedEffect(state.interviewKits.size) { onLoadMore() }
            Card(modifier = Modifier.fillMaxWidth(), shape = RoundedCornerShape(12.dp)) {
                Column(modifier = Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(5.dp)) {
                    Text(kit.title, style = MaterialTheme.typography.titleMedium)
                    Text("${kit.targetRole} · ${kit.durationMinutes} 分钟 · ${kit.questionCount} 题", color = BrandColors.Muted)
                }
            }
        }
        item {
            TextButton(onClick = onRefresh, modifier = Modifier.fillMaxWidth()) { Text("刷新题单") }
            if (state.interviewerMessage.isNotBlank()) Text(state.interviewerMessage, color = BrandColors.Muted)
        }
    }
}
