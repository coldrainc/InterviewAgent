package com.interviewagent.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.unit.dp

@Composable
fun AuthGateScreen(
    state: ChatUiState,
    onLogin: (String, String) -> Unit,
    onRegister: (String, String, String) -> Unit
) {
    var register by remember { mutableStateOf(false) }
    var name by remember { mutableStateOf("") }
    var email by remember { mutableStateOf("") }
    var password by remember { mutableStateOf("") }
    Column(
        modifier = Modifier.fillMaxSize().background(BrandColors.Background).padding(24.dp),
        verticalArrangement = Arrangement.Center,
        horizontalAlignment = Alignment.CenterHorizontally
    ) {
        Column(modifier = Modifier.fillMaxWidth()) {
            Text("Interview Agent", style = MaterialTheme.typography.headlineMedium, color = BrandColors.Text)
            Spacer(Modifier.height(8.dp))
            Text("把面试、刷题和复习计划收进同一条成长路径", color = BrandColors.Muted)
        }
        Spacer(Modifier.height(28.dp))
        Card(modifier = Modifier.fillMaxWidth(), shape = RoundedCornerShape(16.dp)) {
            Column(modifier = Modifier.padding(20.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
                Text(if (register) "创建账号" else "欢迎回来", style = MaterialTheme.typography.titleLarge)
                if (register) {
                    OutlinedTextField(name, { name = it }, label = { Text("昵称") }, modifier = Modifier.fillMaxWidth())
                }
                OutlinedTextField(email, { email = it }, label = { Text("邮箱") }, modifier = Modifier.fillMaxWidth())
                OutlinedTextField(
                    password,
                    { password = it },
                    label = { Text("密码") },
                    visualTransformation = PasswordVisualTransformation(),
                    modifier = Modifier.fillMaxWidth()
                )
                Button(
                    onClick = { if (register) onRegister(email, password, name) else onLogin(email, password) },
                    enabled = !state.busy && email.isNotBlank() && password.length >= 8 && (!register || name.isNotBlank()),
                    modifier = Modifier.fillMaxWidth()
                ) { Text(if (register) "注册并开始" else "登录") }
                TextButton(onClick = { register = !register }, modifier = Modifier.align(Alignment.CenterHorizontally)) {
                    Text(if (register) "已有账号，直接登录" else "第一次使用？创建账号")
                }
                if (state.accountMessage.isNotBlank()) {
                    Text(state.accountMessage, color = if (state.accountMessage.contains("失败")) BrandColors.Danger else BrandColors.Success)
                }
            }
        }
        Spacer(Modifier.height(16.dp))
        Text("你的简历、面试记录与学习数据仅对当前账号可见", style = MaterialTheme.typography.bodySmall, color = Color(0xFF708079))
    }
}
