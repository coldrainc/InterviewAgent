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

    MaterialTheme(colorScheme = BrandColorScheme) {
        Column(
            modifier = Modifier
                .fillMaxSize()
                .background(BrandColors.Background)
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
                } else if (selectedTab == AppTab.Practice) {
                    PracticeScreen(
                        state = state,
                        onSelectCategory = viewModel::selectPracticeCategory,
                        onAnswer = viewModel::updatePracticeAnswer,
                        onSeed = viewModel::seedPracticeQuestions,
                        onSubmit = viewModel::submitPracticeAnswer,
                        onNext = viewModel::nextPracticeQuestion
                    )
                } else if (selectedTab == AppTab.Resume) {
                    ResumeScreen(
                        state = state,
                        onNameChange = viewModel::updateResumeDraftName,
                        onTextChange = viewModel::updateResumeDraftText,
                        onImport = viewModel::importResumeDraft,
                        onRefresh = viewModel::loadResumes,
                        onSelect = viewModel::selectResume,
                        onDelete = viewModel::deleteResume
                    )
                } else if (selectedTab == AppTab.History) {
                    HistoryScreen(
                        state = state,
                        onRefresh = viewModel::loadSessions,
                        onRestore = {
                            viewModel.restoreSession(it)
                            selectedTab = AppTab.Chat
                        },
                        onDelete = viewModel::deleteSession
                    )
                } else {
                    ProfileScreen(
                        state = state,
                        onDevLogin = viewModel::devLogin,
                        onRefreshAccount = viewModel::refreshAccount,
                        onRecharge = viewModel::recharge,
                        onUpdateDefaultMode = viewModel::updateDefaultMode,
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
private fun BottomTabs(selected: AppTab, onSelect: (AppTab) -> Unit) {
    Card(modifier = Modifier.fillMaxWidth(), shape = RoundedCornerShape(10.dp)) {
        Row(modifier = Modifier.padding(6.dp), horizontalArrangement = Arrangement.spacedBy(6.dp)) {
            TabButton("面试", selected == AppTab.Chat, Modifier.weight(1f)) { onSelect(AppTab.Chat) }
            TabButton("刷题", selected == AppTab.Practice, Modifier.weight(1f)) { onSelect(AppTab.Practice) }
            TabButton("简历", selected == AppTab.Resume, Modifier.weight(1f)) { onSelect(AppTab.Resume) }
            TabButton("历史", selected == AppTab.History, Modifier.weight(1f)) { onSelect(AppTab.History) }
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
    Practice,
    Resume,
    History,
    Profile
}
