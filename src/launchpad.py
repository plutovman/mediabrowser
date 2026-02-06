import os
import sys
import threading
import webbrowser
import time
import socket
#import multiprocessing
import customtkinter as ctk
from PIL import Image, ImageTk
import app_flask as flsk  # Import shared Flask app


ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("dark-blue")

logo_file = 'foxlito.png'
logo_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'resources', logo_file)

###############################################################################
###############################################################################
def port_number_available(host, port):
    """Check if a port is available on the given host"""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind((host, port))
            return True
    except OSError:
        return False

###############################################################################
###############################################################################
def port_find_available(host='127.0.0.1', start_port=5000, max_attempts=10):
    """Find next available port by checking sequential ports from start_port"""
    for port in range(start_port, start_port + max_attempts):
        if port_number_available(host, port):
            return port
    return None

###############################################################################
###############################################################################
def get_python_executable():
    """Get the appropriate Python executable
    
    When running as a PyInstaller frozen app, sys.executable points to the
    frozen executable itself, not Python. This causes recursive execution
    when trying to launch Python scripts. This function returns the system
    Python interpreter when frozen.
    """
    if getattr(sys, 'frozen', False):
        # Running as frozen executable - use system Python
        return 'python3'  # WSL/Linux default
    return sys.executable

class LaunchpadApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        # Timer settings
        self.app_close = 60*15  # seconds until auto-close
        self.time_remaining = self.app_close
        
        self.title(f"[{self.time_format(self.time_remaining)}] Launchpad")
        self.app_width = 350
        self.app_height = 400
        self.button_width = 200
        self.button_height = 20
        self.button_pady = 10
        self.button_padx = 20
        
        # Update window to get accurate screen dimensions
        #self.update_idletasks()
        
        # Position window at upper right corner of screen
        #screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        #x_position = screen_width - self.app_width - 10  # 10px margin from edge
        #y_position = 10  # 10px margin from top
        x_position = 5
        y_position = screen_height/2 - self.app_height/2 
        self.geometry(f"{self.app_width}x{self.app_height}+{x_position}+{y_position}")
        self.resizable(False, False)  # Prevent window resizing
        self.minsize(self.app_width, self.app_height)  # Set minimum size
        self.maxsize(self.app_width, self.app_height)  # Set maximum size
        
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
        
        # Bind window close event to ensure cleanup
        self.protocol("WM_DELETE_WINDOW", self.quit_app)

        # Logo at top
        if os.path.exists(logo_path):
            try:
                logo_image = Image.open(logo_path)
                # Resize logo maintaining aspect ratio
                original_width, original_height = logo_image.size
                max_height = 50
                aspect_ratio = original_width / original_height
                new_width = int(max_height * aspect_ratio)
                #logo_image = logo_image.resize((new_width, max_height), Image.Resampling.LANCZOS)
                #self.logo_photo = ImageTk.PhotoImage(logo_image)
                self.logo_photo = ctk.CTkImage(light_image=logo_image, dark_image=logo_image, size=(new_width, max_height))
                self.logo_label = ctk.CTkLabel(
                    self,
                    image=self.logo_photo,
                    text=""
                )
                self.logo_label.pack(pady=(10,10), anchor="e", padx=(0, 5))
            except Exception as e:
                print(f"Error loading logo: {e}")

        # Title
        self.label = ctk.CTkLabel(
            self, 
            text="LAUNCHPAD", 
            font=ctk.CTkFont(size=24, weight="bold")
        )
        self.label.pack(pady=(5, self.button_pady))

        # Info label
        '''
        self.label_info = ctk.CTkLabel(
            self,
            text="Launch Flask-based tools",
            font=ctk.CTkFont(size=12)
        )
        self.label_info.pack(pady=5)
        '''

        # Button frame to contain all buttons
        button_frame_width = self.button_width + 10  # 5px padding on each side
        button_frame = ctk.CTkFrame(self, fg_color="#2e2e2e")
        button_frame.pack(padx=50, pady=5)

        # Research button
        self.button_search = ctk.CTkButton(
            button_frame, 
            text="RESEARCH", 
            command=self.launch_search,
            width= self.button_width,
            height=self.button_height,
            state='disabled'  # Disabled until server starts
        )
        self.button_search.pack(padx=self.button_padx, pady=self.button_pady)

        # Archive button
        self.button_archive = ctk.CTkButton(
            button_frame, 
            text="ARCHIVE", 
            command=self.launch_archive,
            width= self.button_width,
            height=self.button_height,
            state='disabled'  # Disabled until server starts
        )
        self.button_archive.pack(pady=self.button_pady)
        
        # Production button
        self.button_production = ctk.CTkButton(
            button_frame, 
            text="PRODUCTION",
            command=self.launch_production, 
            width= self.button_width,
            height=self.button_height,
            state='disabled'  # Disabled until server starts
        )
        self.button_production.pack(pady=self.button_pady)

        # Status label
        #self.label_status = ctk.CTkLabel(
        self.label_status = ctk.CTkEntry(
            button_frame,
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
            button_frame, 
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
            # Start Flask in a daemon thread instead of subprocess
            flask_thread = threading.Thread(
                target=self.flask_run_server,
                daemon=True
            )
            flask_thread.start()
            
            self.status_update("Starting server...", "orange")
            
            # Start monitoring thread to check when server is ready
            monitor_thread = threading.Thread(
                target=self.flask_startup_monitor_http,
                daemon=True
            )
            monitor_thread.start()
            
        except Exception as e:
            self.status_update(f"Error starting server: {str(e)}", "red")
    
    def flask_run_server(self):
        """Run Flask server in thread"""
        try:
            # Configure Flask app from app_flask module
            flsk.app.config['SERVER_NAME'] = None  # Allow dynamic host/port
            
            # Run Flask server
            flsk.app.run(
                host=self.flask_host,
                port=self.flask_port,
                debug=False,  # Must be False for threaded operation
                use_reloader=False,  # Must be False in threads
                threaded=True
            )
        except Exception as e:
            print(f"Error running Flask server: {e}")
            self.after(0, lambda: self.status_update(f"Server error: {str(e)}", "red"))

    def flask_startup_monitor_http(self):
        """Monitor Flask server readiness via HTTP probe"""
        max_attempts = 30
        attempt = 0
        
        while attempt < max_attempts:
            try:
                # Try to connect to Flask server
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.settimeout(1)
                    result = s.connect_ex((self.flask_host, self.flask_port))
                    if result == 0:
                        # Server is accepting connections
                        time.sleep(0.5)  # Give it a moment to fully initialize
                        self.server_ready = True
                        self.after(0, self.buttons_enable)
                        self.after(0, lambda: self.status_update("Server ready", "green"))
                        return
            except Exception as e:
                pass
            
            attempt += 1
            time.sleep(0.5)
        
        # Timeout reached
        self.after(0, lambda: self.status_update("Server startup timeout", "red"))

    def buttons_enable(self):
        """Enable buttons once server is ready"""
        self.button_search.configure(state='normal')
        self.button_archive.configure(state='normal')
        self.button_production.configure(state='normal')

    def launch_search(self):
        """Open browser to search page"""

        if self.server_ready:
            url = f"{self.flask_url}/index"
            flsk.browser_open(url)
            self.status_update("Opened Search in browser", "green")
            self.time_countdown_reset()
        else:
            self.status_update("Server not ready yet...", "orange")

    def launch_archive(self):
        """Open browser to archive page"""
        if self.server_ready:
            url = f"{self.flask_url}/archive"
            flsk.browser_open(url)
            self.status_update("Opened Archive in browser", "green")
            self.time_countdown_reset()
        else:
            self.status_update("Server not ready yet...", "orange")

    def launch_production(self):
        """Open browser to archive page"""
        if self.server_ready:
            url = f"{self.flask_url}/production"
            flsk.browser_open(url)
            self.status_update("Opened Production in browser", "green")
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
        """Quit the application"""
        # Flask runs in daemon thread, will terminate automatically
        print(f"Closing application (Flask server on port {self.flask_port} will stop)")
        self.destroy()


def main():
    #multiprocessing.freeze_support()  # Required for PyInstaller frozen apps
    app = LaunchpadApp()
    app.mainloop()


if __name__ == "__main__":
    main()