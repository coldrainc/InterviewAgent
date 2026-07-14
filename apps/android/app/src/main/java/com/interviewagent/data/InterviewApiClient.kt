package com.interviewagent.data

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
        return parseChatResponse(request("/sessions", "POST", body.toString()))
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
        val text = BufferedReader(InputStreamReader(stream, StandardCharsets.UTF_8)).use { reader ->
            reader.readText()
        }
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
