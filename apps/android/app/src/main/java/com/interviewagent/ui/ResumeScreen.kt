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
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp

@Composable
fun ResumeScreen(
    state: ChatUiState,
    onNameChange: (String) -> Unit,
    onTextChange: (String) -> Unit,
    onImport: () -> Unit,
    onRefresh: () -> Unit,
    onSelect: (String) -> Unit,
    onDelete: (String) -> Unit
) {
    LazyColumn(
        modifier = Modifier.fillMaxSize(),
        verticalArrangement = Arrangement.spacedBy(12.dp)
    ) {
        item {
            Card(modifier = Modifier.fillMaxWidth(), shape = RoundedCornerShape(10.dp)) {
                Column(modifier = Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
                    Text("导入简历", style = MaterialTheme.typography.titleMedium)
                    OutlinedTextField(
                        value = state.resumeDraftName,
                        onValueChange = onNameChange,
                        label = { Text("文件名") },
                        modifier = Modifier.fillMaxWidth()
                    )
                    OutlinedTextField(
                        value = state.resumeDraftText,
                        onValueChange = onTextChange,
                        label = { Text("粘贴 Markdown / 文本简历") },
                        minLines = 5,
                        maxLines = 10,
                        modifier = Modifier.fillMaxWidth()
                    )
                    Button(
                        onClick = onImport,
                        enabled = !state.busy && state.resumeDraftText.trim().isNotEmpty(),
                        modifier = Modifier.fillMaxWidth()
                    ) {
                        Text("保存简历")
                    }
                    if (state.resumeMessage.isNotBlank()) {
                        Text(
                            state.resumeMessage,
                            style = MaterialTheme.typography.bodySmall,
                            color = if (state.resumeMessage.contains("失败")) BrandColors.Danger else BrandColors.Success
                        )
                    }
                }
            }
        }

        item {
            Card(modifier = Modifier.fillMaxWidth(), shape = RoundedCornerShape(10.dp)) {
                Column(modifier = Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    Text("当前简历", style = MaterialTheme.typography.titleMedium)
                    Text(
                        state.resumes.firstOrNull { it.id == state.selectedResumeId }?.filename ?: "暂未选择",
                        color = BrandColors.Muted
                    )
                    OutlinedButton(onClick = onRefresh, modifier = Modifier.fillMaxWidth()) {
                        Text("刷新简历库")
                    }
                }
            }
        }

        items(state.resumes) { resume ->
            Card(modifier = Modifier.fillMaxWidth(), shape = RoundedCornerShape(10.dp)) {
                Column(modifier = Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                        Text(resume.filename, style = MaterialTheme.typography.titleSmall)
                        if (resume.id == state.selectedResumeId) {
                            Text("当前", style = MaterialTheme.typography.labelSmall, color = BrandColors.Success)
                        }
                    }
                    Text(
                        resume.summary.ifBlank { "暂无摘要" },
                        style = MaterialTheme.typography.bodySmall,
                        color = BrandColors.Muted
                    )
                    Row(horizontalArrangement = Arrangement.spacedBy(8.dp), modifier = Modifier.fillMaxWidth()) {
                        OutlinedButton(onClick = { onSelect(resume.id) }, modifier = Modifier.weight(1f)) {
                            Text("选择")
                        }
                        OutlinedButton(onClick = { onDelete(resume.id) }, modifier = Modifier.weight(1f)) {
                            Text("删除")
                        }
                    }
                }
            }
        }
    }
}
