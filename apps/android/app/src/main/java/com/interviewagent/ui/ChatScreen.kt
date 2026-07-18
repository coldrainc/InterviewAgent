package com.interviewagent.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.Image
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
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.unit.dp
import com.interviewagent.R
import com.interviewagent.data.ChatMessage

@Composable
fun ChatScreen(
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
        Row(
            modifier = Modifier.padding(16.dp),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(12.dp)
        ) {
            Image(
                painter = painterResource(id = R.drawable.app_icon),
                contentDescription = null,
                modifier = Modifier.size(44.dp)
            )
            Column(modifier = Modifier.weight(1f)) {
                Text("Interview Agent", style = MaterialTheme.typography.titleLarge)
                Spacer(Modifier.height(4.dp))
                Text(healthText, style = MaterialTheme.typography.bodySmall, color = BrandColors.Muted)
            }
            Text(accountText, style = MaterialTheme.typography.labelMedium, color = BrandColors.Teal)
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
