package com.interviewagent.data

import android.util.Base64
import org.json.JSONArray
import org.json.JSONObject
import java.io.BufferedReader
import java.io.InputStreamReader
import java.net.HttpURLConnection
import java.net.URL
import java.net.URLEncoder
import java.nio.charset.StandardCharsets

class InterviewApiClient(
    private val baseUrl: String,
    private var token: String?
) {
    fun devLogin(userId: String = "android-dev-user"): AuthTokenResponse {
        val body = JSONObject()
            .put("user_id", userId)
            .put("display_name", "Android 开发用户")
            .put("platform", "android")
        val json = JSONObject(request("/auth/dev-login", "POST", body.toString()))
        val accessToken = json.getString("access_token")
        token = accessToken
        return AuthTokenResponse(
            accessToken = accessToken,
            expiresAt = json.optLong("expires_at"),
            tenantId = json.optString("tenant_id"),
            userId = json.optString("user_id"),
            platform = json.optString("platform"),
            displayName = json.optString("display_name"),
            trialUsesRemaining = json.optInt("trial_uses_remaining"),
            creditBalance = json.optString("credit_balance", "0")
        )
    }

    fun logout() {
        token = null
    }

    fun account(): AccountResponse {
        return parseAccount(request("/account"))
    }

    fun settings(): UserSettingsResponse {
        val json = JSONObject(request("/settings"))
        return UserSettingsResponse(defaultInterviewMode = json.optString("default_interview_mode", "interviewer"))
    }

    fun updateDefaultInterviewMode(mode: String): UserSettingsResponse {
        val body = JSONObject().put("default_interview_mode", mode)
        val json = JSONObject(request("/settings", "PUT", body.toString()))
        return UserSettingsResponse(defaultInterviewMode = json.optString("default_interview_mode", mode))
    }

    fun recharge(amountCredits: String): AccountResponse {
        val body = JSONObject()
            .put("amount_credits", amountCredits)
            .put("payment_provider", "android-mock")
            .put("external_order_id", "android-${System.currentTimeMillis()}")
        return parseAccount(request("/account/recharge", "POST", body.toString()))
    }

    fun health(): String {
        val payload = request("/health")
        return JSONObject(payload).optString("status", "unknown")
    }

    fun listIndustries(targetRole: String = "AI 应用工程师"): List<IndustryOption> {
        val encoded = URLEncoder.encode(targetRole, StandardCharsets.UTF_8.name())
        val payload = request("/metadata/industries?target_role=$encoded")
        val array = JSONArray(payload)
        return (0 until array.length()).map { index ->
            val item = array.getJSONObject(index)
            IndustryOption(
                value = item.getString("value"),
                label = item.getString("label"),
                description = item.optString("description"),
                productionSignals = item.optJSONArray("production_signals").toStringList(),
                recommendedFocusAreas = item.optJSONArray("recommended_focus_areas").toStringList()
            )
        }
    }

    fun listPracticeCategories(): List<PracticeCategory> {
        val array = JSONArray(request("/practice/categories"))
        return (0 until array.length()).map { index ->
            val item = array.getJSONObject(index)
            PracticeCategory(
                value = item.optString("value"),
                label = item.optString("label"),
                description = item.optString("description"),
                subjects = item.optJSONArray("subjects").toStringList()
            )
        }
    }

    fun listPracticeQuestions(category: String, limit: Int = 50): PracticeQuestionListResponse {
        val encoded = URLEncoder.encode(category, StandardCharsets.UTF_8.name())
        val json = JSONObject(request("/practice/questions?category=$encoded&limit=$limit"))
        val items = json.optJSONArray("items")
        return PracticeQuestionListResponse(
            items = (0 until (items?.length() ?: 0)).map { index -> parsePracticeQuestion(items?.getJSONObject(index) ?: JSONObject()) },
            total = json.optInt("total"),
            limit = json.optInt("limit"),
            offset = json.optInt("offset")
        )
    }

    fun seedPracticeQuestions(): ImportResultResponse {
        val json = JSONObject(request("/practice/questions/seed", "POST"))
        return ImportResultResponse(
            created = json.optInt("created"),
            updated = json.optInt("updated"),
            total = json.optInt("total")
        )
    }

    fun submitPracticeAttempt(questionId: String, answer: String, elapsedSeconds: Int): PracticeAttemptResponse {
        val body = JSONObject()
            .put("question_id", questionId)
            .put("answer", answer)
            .put("elapsed_seconds", elapsedSeconds)
        val json = JSONObject(request("/practice/attempt", "POST", body.toString()))
        return PracticeAttemptResponse(
            questionId = json.optString("question_id"),
            correct = if (json.isNull("correct")) null else json.optBoolean("correct"),
            score = json.optInt("score"),
            feedback = json.optString("feedback"),
            referenceAnswer = json.optString("reference_answer"),
            explanation = json.optString("explanation"),
            suggestions = json.optJSONArray("suggestions").toStringList(),
            elapsedSeconds = if (json.isNull("elapsed_seconds")) null else json.optInt("elapsed_seconds")
        )
    }

    fun createSession(request: CreateSessionRequest): ChatResponse {
        val body = JSONObject()
            .put("offline", request.offline)
            .put("web_search", request.webSearch)
            .put("mode", request.mode)
            .put("industry", request.industry)
            .put("target_role", request.targetRole)
            .put("seniority", request.seniority)
            .put("interview_goal", request.interviewGoal)
            .put("focus_areas", JSONArray(request.focusAreas))
        if (!request.resumeId.isNullOrBlank()) {
            body.put("resume_id", request.resumeId)
        }
        return parseChatResponse(request("/sessions", "POST", body.toString()))
    }

    fun listResumes(): List<ResumeRecord> {
        val array = JSONArray(request("/resumes"))
        return (0 until array.length()).map { index -> parseResume(array.getJSONObject(index)) }
    }

    fun importResume(filename: String, text: String): ResumeRecord {
        val encoded = Base64.encodeToString(text.toByteArray(StandardCharsets.UTF_8), Base64.NO_WRAP)
        val body = JSONObject()
            .put("filename", filename)
            .put("content_base64", encoded)
        return parseResume(JSONObject(request("/resumes", "POST", body.toString())))
    }

    fun deleteResume(id: String): Boolean {
        return JSONObject(request("/resumes/$id", "DELETE")).optBoolean("deleted")
    }

    fun listSessions(limit: Int = 50): List<SessionSummary> {
        val array = JSONArray(request("/sessions?limit=$limit"))
        return (0 until array.length()).map { index ->
            val item = array.getJSONObject(index)
            SessionSummary(
                id = item.getString("id"),
                resumeId = item.optString("resume_id").ifBlank { null },
                mode = item.optString("mode"),
                industry = item.optString("industry"),
                candidateName = item.optString("candidate_name"),
                targetRole = item.optString("target_role"),
                seniority = item.optString("seniority"),
                status = item.optString("status"),
                createdAt = item.optString("created_at"),
                updatedAt = item.optString("updated_at")
            )
        }
    }

    fun getSession(id: String): SessionDetail {
        val json = JSONObject(request("/sessions/$id"))
        val turns = json.optJSONArray("turns")
        return SessionDetail(
            id = json.getString("id"),
            turns = (0 until (turns?.length() ?: 0)).map { index ->
                val item = turns?.getJSONObject(index) ?: JSONObject()
                TurnPayload(
                    interviewer = item.optString("interviewer").ifBlank { null },
                    candidate = item.optString("candidate").ifBlank { null }
                )
            }
        )
    }

    fun deleteSession(id: String): Boolean {
        return JSONObject(request("/sessions/$id", "DELETE")).optBoolean("deleted")
    }

    fun sendMessage(sessionId: String, message: String): ChatResponse {
        val body = JSONObject().put("message", message)
        return parseChatResponse(request("/sessions/$sessionId/messages", "POST", body.toString()))
    }

    fun streamMessage(sessionId: String, message: String): List<StreamEvent> {
        val body = JSONObject().put("message", message)
        return parseSse(request("/sessions/$sessionId/stream", "POST", body.toString()))
    }

    private fun parseChatResponse(payload: String): ChatResponse {
        val json = JSONObject(payload)
        return ChatResponse(
            sessionId = json.getString("session_id"),
            message = json.getString("message"),
            completed = json.optBoolean("completed"),
            fallbackUsed = json.optBoolean("fallback_used"),
            guardrails = json.optJSONArray("guardrails").toStringList()
        )
    }

    private fun parseAccount(payload: String): AccountResponse {
        val json = JSONObject(payload)
        return AccountResponse(
            tenantId = json.optString("tenant_id"),
            userId = json.optString("user_id"),
            displayName = json.optString("display_name"),
            email = json.optString("email").ifBlank { null },
            platform = json.optString("platform"),
            trialUsesRemaining = json.optInt("trial_uses_remaining"),
            creditBalance = json.optString("credit_balance", "0"),
            creditBalanceMicros = json.optLong("credit_balance_micros")
        )
    }

    private fun parseResume(json: JSONObject): ResumeRecord {
        return ResumeRecord(
            id = json.getString("id"),
            filename = json.optString("filename"),
            fileType = json.optString("file_type"),
            summary = json.optString("summary"),
            text = json.optString("text"),
            truncated = json.optBoolean("truncated"),
            createdAt = json.optString("created_at"),
            updatedAt = json.optString("updated_at")
        )
    }

    private fun parsePracticeQuestion(json: JSONObject): PracticeQuestion {
        return PracticeQuestion(
            id = json.optString("id"),
            practiceCategory = json.optString("practice_category"),
            examYear = json.optInt("exam_year"),
            examName = json.optString("exam_name"),
            subject = json.optString("subject"),
            questionType = json.optString("question_type"),
            prompt = json.optString("prompt"),
            choices = json.optJSONArray("choices").toStringList(),
            answer = json.optString("answer").ifBlank { null },
            explanation = json.optString("explanation").ifBlank { null },
            difficulty = json.optString("difficulty")
        )
    }

    private fun request(path: String, method: String = "GET", body: String? = null): String {
        val connection = URL("$baseUrl$path").openConnection() as HttpURLConnection
        connection.requestMethod = method
        connection.setRequestProperty("Content-Type", "application/json")
        if (!token.isNullOrBlank()) {
            connection.setRequestProperty("Authorization", "Bearer $token")
        }
        if (body != null) {
            connection.doOutput = true
            connection.outputStream.use { stream ->
                stream.write(body.toByteArray(StandardCharsets.UTF_8))
            }
        }

        val status = connection.responseCode
        val stream = if (status in 200..299) connection.inputStream else connection.errorStream
        val text = stream?.let {
            BufferedReader(InputStreamReader(it, StandardCharsets.UTF_8)).use { reader ->
                reader.readText()
            }
        }.orEmpty()
        if (status !in 200..299) {
            val detail = runCatching { JSONObject(text).optString("detail") }.getOrDefault("")
            throw IllegalStateException(detail.ifBlank { "HTTP $status" })
        }
        return text
    }

    private fun parseSse(text: String): List<StreamEvent> {
        return text.split("\n\n")
            .map { it.trim() }
            .filter { it.isNotBlank() }
            .map { block ->
                val lines = block.lines()
                val event = lines.firstOrNull { it.startsWith("event:") }
                    ?.removePrefix("event:")
                    ?.trim()
                    ?: "message"
                val dataText = lines.firstOrNull { it.startsWith("data:") }
                    ?.removePrefix("data:")
                    ?.trim()
                    ?: "{}"
                StreamEvent(event = event, data = JSONObject(dataText).toMap())
            }
    }
}

private fun JSONArray?.toStringList(): List<String> {
    if (this == null) return emptyList()
    return (0 until length()).map { index -> optString(index) }
}

private fun JSONObject.toMap(): Map<String, Any?> {
    return keys().asSequence().associateWith { key ->
        when (val value = get(key)) {
            is JSONObject -> value.toMap()
            is JSONArray -> value.toStringList()
            else -> value
        }
    }
}
