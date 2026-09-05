package com.interviewagent.ui

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.ExposedDropdownMenuBox
import androidx.compose.material3.ExposedDropdownMenuDefaults
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun PracticeScreen(
    state: ChatUiState,
    onSelectCategory: (String) -> Unit,
    onAnswer: (String) -> Unit,
    onSeed: () -> Unit,
    onSubmit: () -> Unit,
    onNext: () -> Unit
) {
    val question = state.practiceQuestions.getOrNull(state.currentPracticeIndex)
    var expanded by remember { mutableStateOf(false) }
    val selected = state.practiceCategories.firstOrNull { it.value == state.selectedPracticeCategory }

    LazyColumn(
        modifier = Modifier.fillMaxSize(),
        verticalArrangement = Arrangement.spacedBy(12.dp)
    ) {
        item {
            Card(modifier = Modifier.fillMaxWidth(), shape = RoundedCornerShape(10.dp)) {
                Column(modifier = Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
                    Text("刷题训练", style = MaterialTheme.typography.titleMedium)
                    ExposedDropdownMenuBox(expanded = expanded, onExpandedChange = { expanded = !expanded }) {
                        OutlinedTextField(
                            value = selected?.label ?: state.selectedPracticeCategory,
                            onValueChange = {},
                            readOnly = true,
                            label = { Text("训练类型") },
                            trailingIcon = { ExposedDropdownMenuDefaults.TrailingIcon(expanded = expanded) },
                            modifier = Modifier
                                .menuAnchor()
                                .fillMaxWidth()
                        )
                        ExposedDropdownMenu(expanded = expanded, onDismissRequest = { expanded = false }) {
                            state.practiceCategories.forEach { category ->
                                DropdownMenuItem(
                                    text = { Text(category.label) },
                                    onClick = {
                                        onSelectCategory(category.value)
                                        expanded = false
                                    }
                                )
                            }
                        }
                    }
                    Row(horizontalArrangement = Arrangement.spacedBy(8.dp), modifier = Modifier.fillMaxWidth()) {
                        OutlinedButton(onClick = onSeed, modifier = Modifier.weight(1f)) {
                            Text("初始化样题")
                        }
                        OutlinedButton(onClick = onNext, enabled = question != null, modifier = Modifier.weight(1f)) {
                            Text("下一题")
                        }
                    }
                    if (state.practiceMessage.isNotBlank()) {
                        Text(
                            state.practiceMessage,
                            style = MaterialTheme.typography.bodySmall,
                            color = if (state.practiceMessage.contains("失败")) BrandColors.Danger else BrandColors.Success
                        )
                    }
                }
            }
        }

        item {
            if (question == null) {
                Card(modifier = Modifier.fillMaxWidth(), shape = RoundedCornerShape(10.dp)) {
                    Text("暂无题目，可以初始化样题。", modifier = Modifier.padding(16.dp), color = BrandColors.Muted)
                }
            } else {
                Card(modifier = Modifier.fillMaxWidth(), shape = RoundedCornerShape(10.dp)) {
                    Column(modifier = Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
                        Text("${question.examYear} · ${question.subject} · ${question.questionType}", style = MaterialTheme.typography.labelSmall, color = BrandColors.Muted)
                        Text(question.prompt, style = MaterialTheme.typography.titleSmall)
                        if (question.choices.isEmpty()) {
                            OutlinedTextField(
                                value = state.practiceAnswer,
                                onValueChange = onAnswer,
                                label = { Text("我的答案") },
                                minLines = 4,
                                maxLines = 8,
                                modifier = Modifier.fillMaxWidth()
                            )
                        } else {
                            question.choices.forEachIndexed { index, choice ->
                                val key = ('A'.code + index).toChar().toString()
                                OutlinedButton(onClick = { onAnswer(key) }, modifier = Modifier.fillMaxWidth()) {
                                    Text("$key. $choice")
                                }
                            }
                        }
                        Button(onClick = onSubmit, enabled = !state.busy, modifier = Modifier.fillMaxWidth()) {
                            Text("提交答案")
                        }
                    }
                }
            }
        }

        state.practiceResult?.let { result ->
            item {
                Card(modifier = Modifier.fillMaxWidth(), shape = RoundedCornerShape(10.dp)) {
                    Column(modifier = Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                        Text("${result.score} 分", style = MaterialTheme.typography.headlineMedium, color = BrandColors.Teal)
                        Text(result.feedback)
                        InfoRow("参考答案", result.referenceAnswer)
                        Text("解析", style = MaterialTheme.typography.titleSmall)
                        Text(result.explanation, style = MaterialTheme.typography.bodySmall, color = BrandColors.Muted)
                        Text("复盘建议", style = MaterialTheme.typography.titleSmall)
                        result.suggestions.forEach { suggestion ->
                            Text("- $suggestion", style = MaterialTheme.typography.bodySmall)
                        }
                    }
                }
            }
        }
    }
}
