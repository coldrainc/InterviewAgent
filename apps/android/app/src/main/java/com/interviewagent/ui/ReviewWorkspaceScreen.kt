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
fun ReviewWorkspaceScreen(
    state: ChatUiState,
    onGenerate: (String, Int, Double, String) -> Unit,
    onCheckin: (Int, String) -> Unit,
    onRefresh: () -> Unit,
    onLoadMore: () -> Unit
) {
    var generator by remember { mutableStateOf(false) }
    var role by remember { mutableStateOf("AI 应用工程师") }
    var focus by remember { mutableStateOf("RAG、Agent、系统设计") }
    var days by remember { mutableIntStateOf(14) }
    var minutes by remember { mutableIntStateOf(60) }
    var note by remember { mutableStateOf("") }
    LazyColumn(modifier = Modifier.fillMaxSize(), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        item {
            Row(modifier = Modifier.fillMaxWidth()) {
                TextButton(onClick = { generator = false }, modifier = Modifier.weight(1f)) { Text(if (!generator) "● 复习计划" else "复习计划") }
                TextButton(onClick = { generator = true }, modifier = Modifier.weight(1f)) { Text(if (generator) "● 计划生成" else "计划生成") }
            }
        }
        if (generator) {
            item {
                Text("制定可执行的复习节奏", style = MaterialTheme.typography.headlineSmall)
                Text("计划会结合当前简历与历史薄弱项。", color = BrandColors.Muted)
            }
            item {
                Card(modifier = Modifier.fillMaxWidth(), shape = RoundedCornerShape(14.dp)) {
                    Column(modifier = Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
                        OutlinedTextField(role, { role = it }, label = { Text("目标岗位") }, modifier = Modifier.fillMaxWidth())
                        OutlinedTextField(focus, { focus = it }, label = { Text("重点方向") }, modifier = Modifier.fillMaxWidth())
                        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                            listOf(7, 14, 30).forEach { value ->
                                OutlinedButton(onClick = { days = value }, modifier = Modifier.weight(1f)) { Text(if (days == value) "● $value 天" else "$value 天") }
                            }
                        }
                        Button(onClick = { onGenerate(role, days, 1.5, focus) }, enabled = !state.busy, modifier = Modifier.fillMaxWidth()) { Text("生成计划") }
                    }
                }
            }
        } else {
            state.activeLearningTarget?.let { target ->
                if (target.taskId.isNotBlank()) {
                    item {
                        Card(modifier = Modifier.fillMaxWidth(), shape = RoundedCornerShape(12.dp)) {
                            Column(modifier = Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                                Text("当前任务", style = MaterialTheme.typography.labelMedium, color = BrandColors.Teal)
                                Text("已定位到今日复习安排", style = MaterialTheme.typography.titleMedium)
                                Text("完成内容后可返回今日页更新状态。", color = BrandColors.Muted)
                            }
                        }
                    }
                }
            }
            item {
                Text("复习站", style = MaterialTheme.typography.headlineSmall)
                Text("计划、执行和打卡在一个地方完成。", color = BrandColors.Muted)
            }
            items(state.reviewPlans.size, key = { state.reviewPlans[it].id }) { index ->
                val plan = state.reviewPlans[index]
                if (index >= state.reviewPlans.size - 6 && state.reviewPlansHasMore) LaunchedEffect(state.reviewPlans.size) { onLoadMore() }
                Card(modifier = Modifier.fillMaxWidth(), shape = RoundedCornerShape(12.dp)) {
                    Column(modifier = Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                        Text(plan.title, style = MaterialTheme.typography.titleMedium)
                        Text("${plan.status} · ${plan.completedTasks}/${plan.totalTasks} 项完成", color = BrandColors.Muted)
                    }
                }
            }
            item {
                Card(modifier = Modifier.fillMaxWidth(), shape = RoundedCornerShape(14.dp)) {
                    Column(modifier = Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
                        Text("今日打卡", style = MaterialTheme.typography.titleMedium)
                        OutlinedTextField(minutes.toString(), { minutes = it.toIntOrNull()?.coerceIn(0, 720) ?: 0 }, label = { Text("学习分钟") }, modifier = Modifier.fillMaxWidth())
                        OutlinedTextField(note, { note = it }, label = { Text("复盘一句话") }, modifier = Modifier.fillMaxWidth())
                        Button(onClick = { onCheckin(minutes, note) }, enabled = state.selectedReviewPlanId != null && !state.busy, modifier = Modifier.fillMaxWidth()) { Text("完成打卡") }
                    }
                }
            }
        }
        item {
            OutlinedButton(onClick = onRefresh, modifier = Modifier.fillMaxWidth()) { Text("刷新复习数据") }
            if (state.reviewMessage.isNotBlank()) Text(state.reviewMessage, color = BrandColors.Muted, modifier = Modifier.padding(top = 8.dp))
        }
    }
}
