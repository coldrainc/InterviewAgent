package com.interviewagent.ui

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp

@Composable
fun MyWorkspaceScreen(viewModel: ChatViewModel, state: ChatUiState, onOpenInterview: () -> Unit) {
    var section by remember { mutableStateOf(MySection.Account) }
    Column(modifier = Modifier.fillMaxSize(), verticalArrangement = Arrangement.spacedBy(10.dp)) {
        Row(modifier = Modifier.fillMaxWidth()) {
            MySection.entries.forEach { item ->
                TextButton(onClick = { section = item }, modifier = Modifier.weight(1f)) {
                    Text(if (section == item) "● ${item.label}" else item.label)
                }
            }
        }
        when (section) {
            MySection.Account -> ProfileScreen(state, viewModel::refreshAccount, viewModel::updateDefaultMode, viewModel::logout)
            MySection.Resume -> ResumeScreen(state, viewModel::updateResumeDraftName, viewModel::updateResumeDraftText, viewModel::importResumeDraft, { viewModel.loadResumes(false) }, viewModel::selectResume, viewModel::deleteResume, { viewModel.loadResumes(true) })
            MySection.History -> HistoryScreen(state, { viewModel.loadSessions(false) }, { viewModel.restoreSession(it); onOpenInterview() }, viewModel::deleteSession, { viewModel.loadSessions(true) })
        }
    }
}

private enum class MySection(val label: String) { Account("账号"), Resume("简历"), History("历史") }
