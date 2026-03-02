from PyInstaller.__main__ import run
import inspect, os
if __name__ == "__main__":
    current_file = inspect.getfile(inspect.currentframe())
    current_dir = os.path.dirname(os.path.abspath(current_file))
    spec_file = os.path.join(current_dir, "app_launchpad.spec")
    dist_dir = os.path.join(current_dir, "dist")
    build_dir = os.path.join(current_dir, "build")
    run([
        "--log-level=DEBUG",
        "--distpath", dist_dir,
        "--workpath", build_dir,
        spec_file,
    ])