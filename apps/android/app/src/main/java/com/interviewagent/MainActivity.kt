package com.interviewagent

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.lifecycle.viewmodel.compose.viewModel
import com.interviewagent.data.InterviewApiClient
import com.interviewagent.ui.ChatViewModel
import com.interviewagent.ui.ChatViewModelFactory
import com.interviewagent.ui.InterviewApp

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val tokenStore = getSharedPreferences("interview-agent-auth", MODE_PRIVATE)
        setContent {
            val viewModel: ChatViewModel = viewModel(
                factory = ChatViewModelFactory(
                    InterviewApiClient(
                        baseUrl = BuildConfig.INTERVIEW_API_BASE_URL,
                        token = tokenStore.getString("access-token", null),
                        onTokenChanged = { token ->
                            tokenStore.edit().apply {
                                if (token == null) remove("access-token") else putString("access-token", token)
                            }.apply()
                        }
                    )
                )
            )
            InterviewApp(viewModel = viewModel)
        }
    }
}
