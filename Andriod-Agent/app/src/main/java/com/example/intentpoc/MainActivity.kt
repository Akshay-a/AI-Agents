package com.example.intentpoc

import android.app.Activity
import android.os.Bundle
import android.view.ViewGroup
import android.widget.Button
import android.widget.EditText
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.TextView

class MainActivity : Activity() {
    private lateinit var input: EditText
    private lateinit var log: TextView

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        input = EditText(this).apply {
            setText(defaultAlarmJson)
            minLines = 12
            gravity = android.view.Gravity.TOP
            setHorizontallyScrolling(false)
        }

        val executeButton = Button(this).apply {
            text = "Execute"
            setOnClickListener { executeJson() }
        }

        log = TextView(this).apply {
            text = "Ready."
            textSize = 16f
            setPadding(0, 24, 0, 0)
        }

        val content = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(32, 32, 32, 32)
            addView(TextView(context).apply {
                text = "Raw Intent JSON"
                textSize = 18f
            })
            addView(input, LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT,
                0,
                1f,
            ))
            addView(executeButton, LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT,
                ViewGroup.LayoutParams.WRAP_CONTENT,
            ))
            addView(log, LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT,
                ViewGroup.LayoutParams.WRAP_CONTENT,
            ))
        }

        setContentView(ScrollView(this).apply { addView(content) })
    }

    private fun executeJson() {
        log.text = when (val parseResult = IntentJsonParser.parse(input.text.toString())) {
            is ParseResult.Failure -> "Parse error: ${parseResult.message}"
            is ParseResult.Success -> when (val executionResult = IntentExecutor(this).execute(parseResult.parsedIntent)) {
                is ExecutionResult.Failure -> "Execution error: ${executionResult.message}"
                is ExecutionResult.Success -> executionResult.message
            }
        }
    }

    private companion object {
        private val defaultAlarmJson = """
            {
              "type": "android_intent",
              "intent": {
                "action": "android.intent.action.VIEW",
                "data": "https://www.google.com",
                "flags": ["FLAG_ACTIVITY_NEW_TASK"]
              },
              "safety": {
                "requires_confirmation": false,
                "risk": "low"
              }
            }
        """.trimIndent()
    }
}
