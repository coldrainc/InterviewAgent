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
        setContent {
            val viewModel: ChatViewModel = viewModel(
                factory = ChatViewModelFactory(
                    InterviewApiClient(baseUrl = BuildConfig.INTERVIEW_API_BASE_URL, token = null)
                )
            )
            InterviewApp(viewModel = viewModel)
        }
    }
}
