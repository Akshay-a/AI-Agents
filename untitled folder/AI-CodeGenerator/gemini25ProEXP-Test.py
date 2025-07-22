import google.generativeai as genai
import os
from dotenv import load_dotenv
import json # Optional: for pretty printing the history

# --- Configuration ---
MODEL_NAME = "gemini-2.5-pro-exp-03-25" # Use the specific model requested

# --- Load API Key ---
print("Loading API key from .env file...")
load_dotenv()
api_key = os.getenv("GOOGLE_API_KEY")

if not api_key:
    print("\n--- ERROR ---")
    print("Google API Key not found.")
    print("The .env file should contain the line: GOOGLE_API_KEY='YOUR_API_KEY'")
    print("-------------")
    exit() # Stop execution if key is missing
else:
    print("API Key loaded successfully.")

# --- Configure the Generative AI Client ---
try:
    genai.configure(api_key=api_key)
    print(f"Google Generative AI configured using model: {MODEL_NAME}")
except Exception as e:
    print(f"Error configuring Google Generative AI: {e}")
    exit()

# --- Prepare the Conversation History ---
# Note: The Gemini API uses 'model' for the assistant role,
# and expects content under 'parts' which is a list.
conversation_history = [
    {
        "role": "user",
        "parts": ["What's the highest mountain in the world?"]
    },
    {
        "role": "model", # Use 'model' role for Gemini
        "parts": ["The highest mountain in the world is Mount Everest."]
    },
    {
        "role": "user",
        "parts": ["What is the capital of India?"] #2nd question
    }
]

print("\n--- Conversation History Sent to Gemini ---")
# Optional: Pretty print the history being sent
# print(json.dumps(conversation_history, indent=2))
print("[User]: What's the highest mountain in the world?")
print("[Gemini]: The highest mountain in the world is Mount Everest.")
print("[User]: What is the capital of India?")
print("------------------------------------------")


# --- Initialize the Model ---
try:
    model = genai.GenerativeModel(MODEL_NAME)
except Exception as e:
    print(f"\n--- ERROR ---")
    print(f"Error creating GenerativeModel instance: {e}")
    print("Make sure the model name '{MODEL_NAME}' is correct and available.")
    print("-------------")
    exit()

# --- Send the request and get the response ---
print("\nAsking Gemini...")
try:
    # Pass the entire history for conversational context
    response = model.generate_content(conversation_history)

    print("\n--- Gemini's Response ---")
    # Check if response has text part (might be blocked due to safety)
    if response.parts:
        print(response.text)
    else:
        print("Received an empty or blocked response.")
        # You can print feedback if needed: print(response.prompt_feedback)

except Exception as e:
    print(f"\n--- ERROR ---")
    print(f"An error occurred while generating content: {e}")
    print("Check your API key, internet connection, and model access.")
    print("-------------")

print("\n--- Script Finished ---")