import os
import sys
import subprocess
import threading
import webbrowser
import time
import socket
import customtkinter as ctk


ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("dark-blue")

def port_number_available(host, port):
    """Check if a port is available on the given host"""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind((host, port))
            return True
    except OSError:
        return False

def port_find_available(host='127.0.0.1', start_port=5000, max_attempts=10):
    """Find next available port by checking sequential ports from start_port"""
    for port in range(start_port, start_port + max_attempts):
        if port_number_available(host, port):
            return port
    return None

class LaunchpadApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        # Timer settings
        self.app_close = 10  # seconds until auto-close
        self.time_remaining = self.app_close
        
        self.title(f"[{self.time_format(self.time_remaining)}] Launchpad")
        self.app_width = 220
        self.app_height = 230
        self.button_width = 200
        self.button_height = 20
        self.button_pady = 10
        self.geometry(f"{self.app_width}x{self.app_height}")
        
        # Flask server settings
        self.flask_process = None
        self.flask_host = '127.0.0.1'
        self.flask_port = self.flask_port_find()
        self.flask_url = f"http://{self.flask_host}:{self.flask_port}"
        self.server_ready = False
        
        self.monitoring_active = False
        
        # Bind any mouse/keyboard interaction to reset timer
        self.bind('<Motion>', lambda e: self.time_countdown_reset())
        self.bind('<Button>', lambda e: self.time_countdown_reset())
        self.bind('<Key>', lambda e: self.time_countdown_reset())

        # Title
        self.label = ctk.CTkLabel(
            self, 
            text="LAUNCHPAD", 
            font=ctk.CTkFont(size=24, weight="bold")
        )
        self.label.pack(pady=self.button_pady)

        # Info label
        '''
        self.label_info = ctk.CTkLabel(
            self,
            text="Launch Flask-based tools",
            font=ctk.CTkFont(size=12)
        )
        self.label_info.pack(pady=5)
        '''

        # Archive button
        self.button_archive = ctk.CTkButton(
            self, 
            text="ARCHIVE", 
            command=self.launch_archive,
            width= self.button_width,
            height=self.button_height,
            state='disabled'  # Disabled until server starts
        )
        self.button_archive.pack(pady=self.button_pady)
        
        # Search button
        self.button_search = ctk.CTkButton(
            self, 
            text="SEARCH", 
            command=self.launch_search,
            width= self.button_width,
            height=self.button_height,
            state='disabled'  # Disabled until server starts
        )
        self.button_search.pack(pady=self.button_pady)

        # Status label
        #self.label_status = ctk.CTkLabel(
        self.label_status = ctk.CTkEntry(
            self,
            font=ctk.CTkFont(size=11),
            state='disabled',
            text_color="gray",
            justify='center',
            width=self.button_width,
            height=self.button_height
        )
        self.label_status.pack(pady=self.button_pady)
        
        # Start Flask server first
        self.flask_server_start()
        
        # Start countdown timer
        self.time_countdown_start()

        # Exit button
        self.button_quit = ctk.CTkButton(
            self, 
            text="EXIT", 
            command=self.quit_app,
            fg_color="darkred",
            hover_color="red",
            width=self.button_width,
            height=self.button_height
        )
        self.button_quit.pack(pady=self.button_pady)

    def flask_port_find(self, start_port=5000):
        """Find an available port for Flask server"""
        if port_number_available(self.flask_host if hasattr(self, 'flask_host') else '127.0.0.1', start_port):
            return start_port
        
        print(f"Port {start_port} is already in use, searching for available port...")
        available_port = port_find_available(self.flask_host if hasattr(self, 'flask_host') else '127.0.0.1', start_port, max_attempts=10)
        
        if available_port:
            print(f"Using port {available_port} instead")
            return available_port
        else:
            print(f"Could not find an available port in range {start_port}-{start_port+9}")
            return start_port  # Fallback to requested port (will likely fail)

    def flask_server_start(self):
        """Start MediaBrowser Flask server on initialization"""
        try:
            script_dir = os.path.dirname(os.path.abspath(__file__))
            mediabrowser_path = os.path.join(script_dir, 'mediabrowser.py')
            
            if not os.path.exists(mediabrowser_path):
                self.status_update("Error: mediabrowser.py not found", "red")
                return
            
            # Launch Flask server as subprocess with custom port and no auto-browser
            self.flask_process = subprocess.Popen(
                [sys.executable, mediabrowser_path, '--port', str(self.flask_port), '--no-browser'],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=script_dir,
                text=True,
                bufsize=1
            )
            
            self.status_update("Starting server...", "orange")
            
            # Start monitoring thread
            monitor_thread = threading.Thread(
                target=self.flask_startup_monitor,
                daemon=True
            )
            monitor_thread.start()
            
        except Exception as e:
            self.status_update(f"Error starting server: {str(e)}", "red")

    def flask_startup_monitor(self):
        """Monitor Flask server output until ready"""
        try:
            for line in iter(self.flask_process.stderr.readline, ''):
                if not line:
                    break
                
                # Detect Flask startup message
                if 'Running on' in line or 'WARNING' in line:
                    time.sleep(1)  # Give server a moment to fully initialize
                    self.server_ready = True
                    self.after(0, self.buttons_enable)
                    self.after(0, lambda: self.status_update("Server ready", "green"))
                
                # Monitor for HTTP activity to reset timer
                if any(method in line for method in ['GET', 'POST', 'PUT', 'DELETE', 'PATCH']):
                    if 'HTTP' in line:
                        self.after(0, self.time_countdown_reset)
                        
        except Exception as e:
            print(f"Error monitoring Flask: {e}")

    def buttons_enable(self):
        """Enable buttons once server is ready"""
        self.button_search.configure(state='normal')
        self.button_archive.configure(state='normal')

    def launch_search(self):
        """Open browser to search page"""
        if self.server_ready:
            webbrowser.open(f"{self.flask_url}/search")
            self.status_update("Opened Search in browser", "green")
            self.time_countdown_reset()
        else:
            self.status_update("Server not ready yet...", "orange")

    def launch_archive(self):
        """Open browser to archive page"""
        if self.server_ready:
            webbrowser.open(f"{self.flask_url}/archive")
            self.status_update("Opened Archive in browser", "green")
            self.time_countdown_reset()
        else:
            self.status_update("Server not ready yet...", "orange")

    def status_update(self, message, color="gray"):
        """Update the status label"""
        self.label_status.configure(state='normal')
        self.label_status.delete(0, 'end')
        self.label_status.insert(0, message)
        self.label_status.configure(state='disabled', text_color=color)
    
    def time_format(self, seconds):
        """Format seconds as HH:MM:SS"""
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        secs = seconds % 60
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    
    def time_countdown_start(self):
        """Start the countdown timer"""
        self.time_countdown_update()
    
    def time_countdown_update(self):
        """Update countdown timer display and handle auto-close"""
        if self.time_remaining > 0:
            self.title(f"[{self.time_format(self.time_remaining)}] Launchpad")
            self.time_remaining -= 1
            # Schedule next update in 1000ms (1 second)
            self.after(1000, self.time_countdown_update)
        else:
            self.title("[Closing...] Launchpad")
            # Close the app after showing "Closing..." briefly
            self.after(500, self.quit_app)

    def time_countdown_reset(self):
        """Reset the countdown timer to initial value"""
        self.time_remaining = self.app_close
    
    def quit_app(self):
        """Quit the application and terminate Flask server"""
        if self.flask_process and self.flask_process.poll() is None:
            print("Terminating Flask server...")
            self.flask_process.terminate()
            try:
                self.flask_process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self.flask_process.kill()
        
        self.quit()


def main():
    app = LaunchpadApp()
    app.mainloop()


if __name__ == "__main__":
    main()