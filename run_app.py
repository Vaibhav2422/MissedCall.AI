import subprocess
import threading
import time
import webbrowser
import os

def run_backend():
    """Run the FastAPI backend server"""
    os.system("uvicorn backend.main:app --reload --port 8000")

def run_frontend():
    """Run the Streamlit frontend"""
    time.sleep(3)  # Wait for backend to start
    os.system("streamlit run frontend/app.py")

if __name__ == "__main__":
    print("Starting MissedCall.AI...")
    print("Starting backend server on http://localhost:8000")
    print("Starting frontend on http://localhost:8001 (auto-opened by Streamlit)")
    
    # Start backend in a separate thread
    backend_thread = threading.Thread(target=run_backend)
    backend_thread.daemon = True
    backend_thread.start()
    
    # Start frontend in main thread
    run_frontend()