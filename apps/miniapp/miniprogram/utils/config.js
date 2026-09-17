const config = {
  apiBaseUrl: "http://127.0.0.1:8020",
  clientVersion: "0.1.0",
  apiToken: "",
  refreshToken: "",
  tenantId: "default",
  userId: "anonymous",
  storageKeys: {
    token: "interview_agent_token",
    refreshToken: "interview_agent_refresh_token",
    tenantId: "interview_agent_tenant_id",
    userId: "interview_agent_user_id",
    learningTodayCache: "interview_agent_learning_today",
    learningSyncCursor: "interview_agent_learning_sync_cursor",
    learningTaskTarget: "interview_agent_learning_task_target",
    selectedResumeId: "interview_agent_selected_resume_id",
    interviewSetup: "interview_agent_interview_setup",
    userProfile: "interview_agent_user_profile"
  }
};

module.exports = { config };
