"""
MediaBrowser Flask Application Launcher
========================================
CLI standalone launcher for the MediaBrowser Flask application.
Initializes Flask app and registers routes from mediabrowser and projectbrowser modules.

Can be run directly: python app_flask.py
For GUI launcher with buttons, use launchpad.py instead.

Environment Requirements:
- DEPOT_ALL: Base depot directory path
- MEDIA_SQLITE_KEY (optional): Password for database modifications
"""

import socket
import webbrowser
import os
from threading import Timer
from flask import Flask, send_from_directory

# ============================================================================
# CONFIGURATION & GLOBALS
# ============================================================================

depot_local = os.getenv('DEPOT_ALL')
if not depot_local:
    raise EnvironmentError("DEPOT_ALL environment variable must be set")

# ============================================================================
# FLASK APP INITIALIZATION
# ============================================================================

# Get absolute path to templates directory
template_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates')

app = Flask(__name__, 
            static_folder=None,  # Disable automatic static route
            template_folder=template_dir)
app.secret_key = 'your_secret_key_here'  # Set secret key for sessions
app.config['TEMPLATES_AUTO_RELOAD'] = True  # Force template reloading

# ============================================================================
# COMMON RESOURCE ROUTES
# ============================================================================

@app.route('/resources/<path:filename>')
def serve_resources(filename):
    """Serve common resources (favicon, icons) for all modules"""
    resources_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'resources')
    return send_from_directory(resources_dir, filename)

# Manually create static route for depot media files
@app.route('/static/<path:filename>')
def static(filename):
    """Serve media files from depot"""
    return send_from_directory(depot_local, filename)

# ============================================================================
# PORT MANAGEMENT UTILITIES
# ============================================================================

def browser_open(url):
    """Open a URL in the default web browser, with WSL support"""
    
    try:
        # Check if running in WSL (Windows Subsystem for Linux)
        is_wsl = 'microsoft' in os.uname().release.lower() or 'wsl' in os.uname().release.lower()
        
        if is_wsl:
            # Use Windows command to open browser from WSL
            import subprocess
            subprocess.run(['cmd.exe', '/c', 'start', url], check=False)
        else:
            # Use standard webbrowser module for native environments
            webbrowser.open(url)
    except Exception as e:
        print(f"Error opening browser: {e}")


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

# ============================================================================
# ROUTE REGISTRATION
# ============================================================================

def register_routes_mediabrowser():
    """Register mediabrowser routes if module is available"""
    try:
        import mediabrowser as mb
        if hasattr(mb, 'register_routes'):
            mb.register_routes(app)
    except ImportError:
        print("⚠ mediabrowser module not found, search/archive/cart routes not registered")
    except Exception as e:
        print(f"⚠ Error registering mediabrowser routes: {e}")


def register_routes_projectbrowser():
    """Register projectbrowser routes if module is available"""
    try:
        import projectbrowser as pb
        if hasattr(pb, 'register_routes'):
            pb.register_routes(app)
    except ImportError:
        print("ℹ projectbrowser module not found, skipping route registration")
    except Exception as e:
        print(f"⚠ Error registering projectbrowser routes: {e}")


# Attempt to register routes on module load

register_routes_mediabrowser()
register_routes_projectbrowser()

# ============================================================================
# MAIN CLI LAUNCHER
# ============================================================================

def main(debug=True, host='127.0.0.1', port=5000, browser_open_on_start=True):
    """
    Main entry point for the MediaBrowser application.
    
    Args:
        debug (bool): Enable Flask debug mode. Default is True.
        host (str): Host to bind to. Default is '127.0.0.1' (accessible from WSL/Windows).
        port (int): Port to bind to. Default is 5000.
        browser_open_on_start (bool): Automatically open browser. Default is True.
    """
    # Find an available port if the requested one is in use
    if not port_number_available(host, port):
        print(f"Port {port} is already in use, searching for available port...")
        available_port = port_find_available(host, port, max_attempts=10)
        if available_port:
            port = available_port
            print(f"Using port {port} instead")
        else:
            print(f"Could not find an available port in range {port}-{port+9}")
            return
    
    # Build the URL for browser (0.0.0.0 is not browsable, use 127.0.0.1)
    browser_host = '127.0.0.1' if host == '0.0.0.0' else host
    url = f"http://{browser_host}:{port}"
    print(f"Starting MediaBrowser at {url}")
    print("Available interfaces:")
    print(f"  • Search:     {url}/search")
    print(f"  • Archive:    {url}/archive")
    print(f"  • Production: {url}/production")
    print(f"  • Cart:       {url}/cart")
    
    # Open browser after a delay to allow Flask to start
    if browser_open_on_start:
        delay = 3.0 if debug else 1.5
        Timer(delay, lambda: browser_open(url)).start()
    
    app.run(debug=debug, host=host, port=port, use_reloader=False)


if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='MediaBrowser - Flask-based media management')
    parser.add_argument('--port', type=int, default=5000, help='Port to run on (default: 5000)')
    parser.add_argument('--host', default='127.0.0.1', help='Host to bind to (default: 127.0.0.1)')
    parser.add_argument('--debug', action='store_true', default=True, help='Enable debug mode')
    parser.add_argument('--no-browser', action='store_true', help='Do not open browser automatically')
    
    args = parser.parse_args()
    
    # Convert --no-browser flag to positive browser_open flag
    should_open_browser = not args.no_browser
    
    main(debug=args.debug, host=args.host, port=args.port, browser_open_on_start=should_open_browser)
