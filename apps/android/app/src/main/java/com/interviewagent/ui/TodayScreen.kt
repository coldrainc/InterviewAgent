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
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import com.interviewagent.data.LearningTask

@Composable
fun TodayScreen(
    state: ChatUiState,
    onRefresh: () -> Unit,
    onTaskAction: (LearningTask) -> Unit,
    onOpenTask: (LearningTask) -> Unit,
    onStartInterview: () -> Unit
) {
    val today = state.learningToday
    LazyColumn(modifier = Modifier.fillMaxSize(), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        item {
            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                Text("今天，向目标再近一点", style = MaterialTheme.typography.headlineSmall)
                Text(today.nextActionTitle.ifBlank { "完成今日关键任务，保持稳定节奏" }, color = BrandColors.Muted)
            }
        }
        item {
            Card(modifier = Modifier.fillMaxWidth(), shape = RoundedCornerShape(14.dp)) {
                Column(modifier = Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
                    Row(horizontalArrangement = Arrangement.spacedBy(10.dp), modifier = Modifier.fillMaxWidth()) {
                        MetricBox("今日完成", "${today.done}/${today.total}", Modifier.weight(1f))
                        MetricBox("连续打卡", "${today.streak} 天", Modifier.weight(1f))
                    }
                    LinearProgressIndicator(
                        progress = { if (today.total == 0) 0f else today.done.toFloat() / today.total },
                        modifier = Modifier.fillMaxWidth()
                    )
                    if (today.advice.isNotBlank()) Text(today.advice, color = BrandColors.Muted)
                }
            }
        }
        if (today.tasks.isEmpty()) {
            item {
                Card(modifier = Modifier.fillMaxWidth(), shape = RoundedCornerShape(14.dp)) {
                    Column(modifier = Modifier.padding(20.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
                        Text("今天还没有任务", style = MaterialTheme.typography.titleMedium)
                        Text("可以先做一次轻量模拟，或到复习页生成计划。", color = BrandColors.Muted)
                        Button(onClick = onStartInterview) { Text("开始模拟面试") }
                    }
                }
            }
        }
        items(today.tasks, key = { it.id }) { task ->
            Card(
                onClick = { onOpenTask(task) },
                modifier = Modifier.fillMaxWidth(),
                shape = RoundedCornerShape(12.dp)
            ) {
                Row(modifier = Modifier.padding(16.dp), horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                    Column(modifier = Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(5.dp)) {
                        Text(task.title, style = MaterialTheme.typography.titleMedium)
                        Text(task.taskType.uppercase() + " · " + task.status, style = MaterialTheme.typography.labelSmall, color = BrandColors.Muted)
                    }
                    Button(onClick = { onTaskAction(task) }, enabled = !state.busy) { Text(if (task.done) "重开" else task.actionLabel) }
                }
            }
        }
        item {
            OutlinedButton(onClick = onRefresh, modifier = Modifier.fillMaxWidth()) { Text("刷新今日进度") }
            if (state.learningMessage.isNotBlank()) Text(state.learningMessage, color = BrandColors.Muted, modifier = Modifier.padding(top = 8.dp))
        }
    }
}
