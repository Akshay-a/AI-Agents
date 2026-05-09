package com.example.intentpoc

import android.content.Intent
import android.net.Uri
import org.json.JSONArray
import org.json.JSONException
import org.json.JSONObject

data class ParsedIntent(
    val action: String,
    val data: Uri?,
    val packageName: String?,
    val extras: Map<String, ExtraValue>,
    val flags: List<Int>,
)

sealed class ExtraValue {
    data class BooleanValue(val value: Boolean) : ExtraValue()
    data class DoubleValue(val value: Double) : ExtraValue()
    data class IntValue(val value: Int) : ExtraValue()
    data class LongValue(val value: Long) : ExtraValue()
    data class StringValue(val value: String) : ExtraValue()
}

sealed class ParseResult {
    data class Success(val parsedIntent: ParsedIntent) : ParseResult()
    data class Failure(val message: String) : ParseResult()
}

object IntentJsonParser {
    private val supportedFlags = mapOf(
        "FLAG_ACTIVITY_NEW_TASK" to Intent.FLAG_ACTIVITY_NEW_TASK,
        "FLAG_ACTIVITY_CLEAR_TOP" to Intent.FLAG_ACTIVITY_CLEAR_TOP,
        "FLAG_ACTIVITY_SINGLE_TOP" to Intent.FLAG_ACTIVITY_SINGLE_TOP,
        "FLAG_ACTIVITY_NO_HISTORY" to Intent.FLAG_ACTIVITY_NO_HISTORY,
        "FLAG_ACTIVITY_EXCLUDE_FROM_RECENTS" to Intent.FLAG_ACTIVITY_EXCLUDE_FROM_RECENTS,
    )

    fun parse(rawJson: String): ParseResult {
        val root = try {
            JSONObject(rawJson)
        } catch (error: JSONException) {
            return ParseResult.Failure("Malformed JSON: ${error.message}")
        }

        if (root.has("type") && !root.isNull("type") && root.opt("type") !is String) {
            return ParseResult.Failure("Invalid field: type must be a string.")
        }
        val type = if (root.has("type") && !root.isNull("type")) root.getString("type") else null
        if (type != "android_intent") {
            return ParseResult.Failure("Invalid type: expected 'android_intent'.")
        }

        validateSafety(root)?.let { return ParseResult.Failure(it) }

        val intentObject = root.optJSONObject("intent")
            ?: return ParseResult.Failure("Missing object: intent.")

        if (intentObject.has("action") && !intentObject.isNull("action") && intentObject.opt("action") !is String) {
            return ParseResult.Failure("Invalid field: intent.action must be a string.")
        }
        val action = if (intentObject.has("action") && !intentObject.isNull("action")) intentObject.getString("action") else null
        if (action.isNullOrBlank()) {
            return ParseResult.Failure("Missing string: intent.action.")
        }

        val data = when {
            !intentObject.has("data") || intentObject.isNull("data") -> null
            intentObject.opt("data") is String -> Uri.parse(intentObject.getString("data"))
            else -> return ParseResult.Failure("Invalid field: intent.data must be a string.")
        }

        val packageName = when {
            !intentObject.has("package") || intentObject.isNull("package") -> null
            intentObject.opt("package") is String -> intentObject.getString("package")
            else -> return ParseResult.Failure("Invalid field: intent.package must be a string.")
        }

        val extras = when {
            !intentObject.has("extras") || intentObject.isNull("extras") -> ParsedExtras.Success(emptyMap())
            intentObject.opt("extras") is JSONObject -> parseExtras(intentObject.getJSONObject("extras"))
            else -> return ParseResult.Failure("Invalid field: intent.extras must be an object.")
        }
        if (extras is ParsedExtras.Failure) {
            return ParseResult.Failure(extras.message)
        }

        val flags = when {
            !intentObject.has("flags") || intentObject.isNull("flags") -> ParsedFlags.Success(emptyList())
            intentObject.opt("flags") is JSONArray -> parseFlags(intentObject.getJSONArray("flags"))
            else -> return ParseResult.Failure("Invalid field: intent.flags must be an array.")
        }
        if (flags is ParsedFlags.Failure) {
            return ParseResult.Failure(flags.message)
        }

        return ParseResult.Success(
            ParsedIntent(
                action = action,
                data = data,
                packageName = packageName,
                extras = (extras as ParsedExtras.Success).extras,
                flags = (flags as ParsedFlags.Success).flags,
            )
        )
    }

    private fun parseExtras(jsonObject: JSONObject): ParsedExtras {
        val extras = linkedMapOf<String, ExtraValue>()
        val keys = jsonObject.keys()

        while (keys.hasNext()) {
            val key = keys.next()
            val value = jsonObject.opt(key)
            extras[key] = when (value) {
                is Boolean -> ExtraValue.BooleanValue(value)
                is Int -> ExtraValue.IntValue(value)
                is Long -> ExtraValue.LongValue(value)
                is Double -> ExtraValue.DoubleValue(value)
                is String -> ExtraValue.StringValue(value)
                else -> return ParsedExtras.Failure(
                    "Unsupported extra '${key}': only string, boolean, int, long, and double values are supported."
                )
            }
        }

        return ParsedExtras.Success(extras)
    }

    private fun validateSafety(root: JSONObject): String? {
        if (!root.has("safety") || root.isNull("safety")) return null

        val safety = root.optJSONObject("safety")
            ?: return "Invalid field: safety must be an object when present."

        if (
            safety.has("requires_confirmation") &&
            !safety.isNull("requires_confirmation") &&
            safety.opt("requires_confirmation") !is Boolean
        ) {
            return "Invalid field: safety.requires_confirmation must be a boolean."
        }

        if (safety.has("risk") && !safety.isNull("risk") && safety.opt("risk") !is String) {
            return "Invalid field: safety.risk must be a string."
        }

        return null
    }

    private fun parseFlags(jsonArray: JSONArray): ParsedFlags {
        val flags = mutableListOf<Int>()
        for (index in 0 until jsonArray.length()) {
            val rawFlag = jsonArray.opt(index)
            val flag = when (rawFlag) {
                is Int -> rawFlag
                is String -> supportedFlags[rawFlag]
                    ?: return ParsedFlags.Failure(
                        "Unsupported flag '${rawFlag}'. Supported names: ${supportedFlags.keys.joinToString()}."
                    )
                else -> return ParsedFlags.Failure("Invalid flag at index ${index}: use a supported string name or integer.")
            }
            flags += flag
        }
        return ParsedFlags.Success(flags)
    }

    private sealed class ParsedExtras {
        data class Success(val extras: Map<String, ExtraValue>) : ParsedExtras()
        data class Failure(val message: String) : ParsedExtras()
    }

    private sealed class ParsedFlags {
        data class Success(val flags: List<Int>) : ParsedFlags()
        data class Failure(val message: String) : ParsedFlags()
    }
}
