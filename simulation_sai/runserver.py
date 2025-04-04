import os
import sys
import threading
import time
import requests
from django.core.management import execute_from_command_line
from PyQt5 import QtWidgets, QtCore, QtWebEngineWidgets
import uuid
import socket
import subprocess



# # Allowed MAC and IP Address (Replace with your actual values)
# ALLOWED_MAC = "E0-69-95-B3-6D-7D"  # Wi-Fi MAC Address
# ALLOWED_IP = "192.168.8.199"         # IPv4 Address

# def get_mac_address():
#     """Fetch the system's MAC address using the correct method."""
#     try:
#         result = subprocess.check_output("getmac", shell=True).decode()
#         mac_addresses = [line.split()[0] for line in result.splitlines() if "-" in line]
#         if mac_addresses:
#             mac = mac_addresses[0]  # Use the first valid MAC
#             print("Your MAC address is:", mac)
#             return mac.upper()
#     except Exception as e:
#         print("Error retrieving MAC address:", e)
#         return None

# def get_ip_address():
#     """Fetch the system's correct IPv4 address."""
#     try:
#         ip = socket.gethostbyname(socket.gethostname())
#         print("Your IP address is:", ip)
#         return ip
#     except Exception as e:
#         print("Error retrieving IP address:", e)
#         return None

# # Get current system's MAC and IP
# current_mac = get_mac_address()
# current_ip = get_ip_address()

# # Validate the MAC and IP Address
# if current_mac != ALLOWED_MAC or current_ip != ALLOWED_IP:
#     print("Unauthorized system. Exiting...")
#     sys.exit(1)  # Exit the program

# print("Authorized system. Running application...")



# Global event to signal server to stop
stop_event = threading.Event()

class WebWindow(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        self.init_ui()

    def init_ui(self):
        self.setWindowTitle("MULTI CHANNEL WITH ANGLE")
        self.showFullScreen()

        # Create a QWebEngineView widget to display the web page
        self.browser = QtWebEngineWidgets.QWebEngineView(self)

        # Create a layout and add the browser
        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(self.browser)

        # Load the Django server URL
        self.browser.load(QtCore.QUrl("http://127.0.0.1:8000/"))

        # Add a Close button (initially hidden)
        self.close_button = QtWidgets.QPushButton("Close", self)
        self.close_button.clicked.connect(self.close)  # Connect to close event
        layout.addWidget(self.close_button)

        # Hide the close button initially
        self.close_button.setVisible(False)

        # Detect URL changes to control visibility of the Close button
        self.browser.urlChanged.connect(self.toggle_close_button)

        # Add a timer to periodically check if the screen is active
        self.inactivity_timer = QtCore.QTimer(self)
        self.inactivity_timer.timeout.connect(self.check_screen_status)
        self.inactivity_timer.start(1000)  # Check every second

        self.screen_on = True  # To track screen status

    def toggle_close_button(self, url):
        """ Show Close button only for the specific URL. """
        if url.toString() == "http://127.0.0.1:8000/":
            self.close_button.setVisible(True)  # Show button for this page
        else:
            self.close_button.setVisible(False)  # Hide button for other pages

    def closeEvent(self, event):
        # Send a POST request to the shutdown endpoint
        try:
            requests.post("http://127.0.0.1:8000/shutdown/")
        except Exception as e:
            print(f"Error sending shutdown request: {e}")
        finally:
            stop_event.set()
            event.accept()

    def check_screen_status(self):
        """ Check if the screen is turned on or off. """
        # Using Qt's screen to detect if the screen is turned off
        screen = QtWidgets.QApplication.primaryScreen()
        geometry = screen.geometry()
        
        # Check if the screen has changed in size (this usually happens when the screen turns on again)
        if geometry.isNull() or geometry.width() == 0 or geometry.height() == 0:
            if self.screen_on:
                self.screen_on = False
                print("Screen turned off.")
                # You can trigger actions here if necessary when the screen is off
        else:
            if not self.screen_on:
                self.screen_on = True
                print("Screen turned on.")
                # Refresh the PyQt window when screen is turned back on
                self.refresh_window()

    def refresh_window(self):
        """ Refresh or reinitialize the window when the screen is turned on again. """
        self.browser.reload()  # Reload the page in the browser view to ensure it resumes correctly.
        self.setWindowState(QtCore.Qt.WindowActive)  # Ensure the window is active and in focus.

def start_web_window():
    app = QtWidgets.QApplication(sys.argv)
    window = WebWindow()
    window.show()
    sys.exit(app.exec_())

def migrate_database():
    # Set the Django settings module environment variable
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "project_me.settings")
    
    # Run makemigrations
    sys.argv = ["manage.py", "makemigrations"]
    execute_from_command_line(sys.argv)
    
    # Run migrate
    sys.argv = ["manage.py", "migrate"]
    execute_from_command_line(sys.argv)



def start_django_server():

    # First, perform migrations
    migrate_database()
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "project_me.settings")
    sys.argv = ["manage.py", "runserver", "--noreload"]
    while not stop_event.is_set():
        try:
            execute_from_command_line(sys.argv)
        except SystemExit:
            # Handle SystemExit if Django server exits (e.g., when stop_event is set)
            break

def wait_for_server():
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
    # Start the Django server in a separate thread
    django_thread = threading.Thread(target=start_django_server)
    django_thread.daemon = True
    django_thread.start()

    # Wait for the Django server to start
    wait_for_server()

    # Start the PyQt5 window after the server starts
    start_web_window()
