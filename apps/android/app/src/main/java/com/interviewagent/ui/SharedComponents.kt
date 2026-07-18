package com.interviewagent.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Button
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.unit.dp
import com.interviewagent.data.ChatMessage

@Composable
fun MetricBox(title: String, value: String, modifier: Modifier = Modifier) {
    Column(
        modifier = modifier
            .background(BrandColors.SurfaceSoft, RoundedCornerShape(10.dp))
            .padding(12.dp)
    ) {
        Text(title, style = MaterialTheme.typography.labelSmall, color = BrandColors.Muted)
        Spacer(Modifier.height(6.dp))
        Text(value, style = MaterialTheme.typography.titleLarge, color = BrandColors.Teal)
    }
}

@Composable
fun InfoRow(label: String, value: String) {
    Row(modifier = Modifier.fillMaxWidth()) {
        Text(label, color = BrandColors.Muted, modifier = Modifier.weight(1f))
        Text(value, color = BrandColors.Text, modifier = Modifier.weight(2f))
    }
}

@Composable
fun MessageBubble(message: ChatMessage) {
    val isUser = message.role == ChatMessage.Role.User
    val label = when (message.role) {
        ChatMessage.Role.User -> "我"
        ChatMessage.Role.Agent -> "面试官"
        ChatMessage.Role.System -> "系统"
    }
    Column(
        modifier = Modifier.fillMaxWidth(),
        horizontalAlignment = if (isUser) Alignment.End else Alignment.Start
    ) {
        Text(label, style = MaterialTheme.typography.labelSmall, color = BrandColors.Muted)
        Spacer(Modifier.height(4.dp))
        Text(
            text = message.text,
            color = if (isUser) Color.White else BrandColors.Text,
            modifier = Modifier
                .background(
                    if (isUser) BrandColors.Primary else Color.White,
                    RoundedCornerShape(10.dp)
                )
                .padding(12.dp)
        )
    }
}

@Composable
fun Composer(
    input: String,
    busy: Boolean,
    enabled: Boolean,
    onInput: (String) -> Unit,
    onSend: () -> Unit
) {
    Row(
        modifier = Modifier.fillMaxWidth(),
        verticalAlignment = Alignment.Bottom,
        horizontalArrangement = Arrangement.spacedBy(8.dp)
    ) {
        OutlinedTextField(
            value = input,
            onValueChange = onInput,
            placeholder = { Text("输入你的回答") },
            maxLines = 5,
            modifier = Modifier.weight(1f)
        )
        Button(
            onClick = onSend,
            enabled = enabled && !busy && input.trim().isNotEmpty()
        ) {
            Text("发送")
        }
    }
}
