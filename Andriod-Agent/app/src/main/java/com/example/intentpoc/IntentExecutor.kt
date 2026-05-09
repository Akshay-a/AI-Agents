package com.example.intentpoc

import android.app.Activity
import android.content.ActivityNotFoundException
import android.content.Intent

sealed class ExecutionResult {
    data class Success(val message: String) : ExecutionResult()
    data class Failure(val message: String) : ExecutionResult()
}

class IntentExecutor(private val activity: Activity) {
    fun execute(parsedIntent: ParsedIntent): ExecutionResult {
        val intent = Intent(parsedIntent.action)

        parsedIntent.data?.let(intent::setData)
        parsedIntent.packageName?.let(intent::setPackage)
        parsedIntent.flags.forEach(intent::addFlags)

        for ((key, value) in parsedIntent.extras) {
            when (value) {
                is ExtraValue.BooleanValue -> intent.putExtra(key, value.value)
                is ExtraValue.DoubleValue -> intent.putExtra(key, value.value)
                is ExtraValue.IntValue -> intent.putExtra(key, value.value)
                is ExtraValue.LongValue -> intent.putExtra(key, value.value)
                is ExtraValue.StringValue -> intent.putExtra(key, value.value)
            }
        }

        return try {
            activity.startActivity(intent)
            ExecutionResult.Success("LAUNCHED: Android accepted native Intent '${parsedIntent.action}'. Verify the visible target app behavior.")
        } catch (error: ActivityNotFoundException) {
            ExecutionResult.Failure(
                "NO_HANDLER: No activity can handle action '${parsedIntent.action}'" +
                    packageSuffix(parsedIntent) +
                    ". Install/enable a compatible app or change the JSON intent."
            )
        } catch (error: SecurityException) {
            ExecutionResult.Failure(
                "PERMISSION_DENIED: Android blocked this intent. Check manifest permissions and target app policy. ${error.message}"
            )
        } catch (error: RuntimeException) {
            ExecutionResult.Failure("LAUNCH_FAILED: ${error.javaClass.simpleName}: ${error.message}")
        }
    }

    private fun packageSuffix(parsedIntent: ParsedIntent): String {
        val packageName = parsedIntent.packageName ?: return ""
        return " for package '${packageName}'"
    }
}
