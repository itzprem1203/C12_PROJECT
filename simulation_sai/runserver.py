import os
import sys
import threading
import time
import requests
import webview  # Import PyWebView
from django.core.management import execute_from_command_line

# Global event to signal server shutdown
stop_event = threading.Event()

class Api:
    def shutdown(self):
        """Shutdown Django server and close PyWebView."""
        print("Shutting down...")
        stop_event.set()
        os._exit(0)  # Forcefully exit the program

def migrate_database():
    """Run Django migrations before starting the server."""
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "project_me.settings")
    sys.argv = ["manage.py", "makemigrations"]
    execute_from_command_line(sys.argv)

    sys.argv = ["manage.py", "migrate"]
    execute_from_command_line(sys.argv)

def start_django_server():
    """Start Django server in a separate thread."""
    migrate_database()
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "project_me.settings")
    sys.argv = ["manage.py", "runserver", "--noreload"]

    while not stop_event.is_set():
        try:
            execute_from_command_line(sys.argv)
        except SystemExit:
            break  # Exit loop when stop_event is set

def wait_for_server():
    """Wait until Django server starts."""
    url = "http://127.0.0.1:8000/"
    print("Waiting for Django server to start...")

    while True:
        try:
            response = requests.get(url)
            if response.status_code == 200:
                print("Django server is running.")
                break
        except requests.ConnectionError:
            pass
        time.sleep(1)  # Retry every second

if __name__ == "__main__":
    # Start Django server in a separate thread
    django_thread = threading.Thread(target=start_django_server)
    django_thread.daemon = True
    django_thread.start()

    # Wait for the Django server to start
    wait_for_server()

    # Create API instance
    api = Api()

    # Open the webpage in Full-Screen Mode with API
    webview.create_window(
        "MULTI CHANNEL WITH ANGLE",
        "http://127.0.0.1:8000/",
        fullscreen=True,
        js_api=api  # Expose shutdown API to JavaScript
    )
    
    webview.start()