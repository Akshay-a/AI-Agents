#!/usr/bin/env python3
"""
Launch script for the AI Code Generator Streamlit UI.
"""

import sys
import subprocess
import os

def main():
    """Launch the Streamlit application."""
    # Ensure we're in the correct directory
    script_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(script_dir)
    
    print("🤖 Starting AI Code Generator UI...")
    print("📁 Working directory:", script_dir)
    print("🌐 The app will open in your default browser")
    print("⏹️  Press Ctrl+C to stop the server")
    print("-" * 50)
    
    try:
        # Launch Streamlit
        subprocess.run([
            sys.executable, "-m", "streamlit", "run", 
            "streamlit_app.py",
            "--server.port", "8501",
            "--server.address", "localhost",
            "--browser.gatherUsageStats", "false"
        ])
    except KeyboardInterrupt:
        print("\n👋 Shutting down AI Code Generator UI...")
    except Exception as e:
        print(f"❌ Error launching Streamlit: {e}")
        print("💡 Make sure Streamlit is installed: pip install streamlit")
        sys.exit(1)

if __name__ == "__main__":
    main() 