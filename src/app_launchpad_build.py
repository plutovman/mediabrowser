from PyInstaller.__main__ import run
import inspect, os
if __name__ == "__main__":
    current_file = inspect.getfile(inspect.currentframe())
    current_dir = os.path.dirname(os.path.abspath(current_file))
    spec_file = os.path.join(current_dir, "app_launchpad.spec")
    run([spec_file])