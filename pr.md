# Pull Request: Migration to qibullet Simulation Backend

## Summary
Replaces the Webots-based simulation stack with a lightweight, Python-native **qibullet** implementation. This ensures better compatibility, lower resource usage, and a fully controllable physics environment for the Pepper robot.

## Key Changes
*   **Backend Swap**: Removed Webots driver; implemented `src/shim_server.py` and `src/driver.py` using `qibullet`.
*   **Docker Environment**: 
    *   Downgraded to **Ubuntu 20.04** (Python 3.8) to satisfy `qibullet` dependency strictness.
    *   Configured persistent volume for proprietary assets (`.qibullet`).
*   **License Handling**: Added `src/setup_wizard.py` to automate the interactive license agreement and asset installation in a headless Docker environment.
*   **New Features**:
    *   **Odometry**: Exposed ground truth position via `ALMotion.getRobotPosition(True)`.
    *   **Lasers**: Exposed raw Lidar arrays and added visualization toggles (`ALLaser.show`).
    *   **Sonar Proxy**: Mapped Laser minimums to `ALMemory` Sonar keys for legacy support.
    *   **Motion**: Implemented `moveToward`, `stopMove`, and `goToPosture`.

## Usage
1.  Run `./run.sh`
2.  (First Time) Run `python3 src/setup_wizard.py`
3.  Start server: `python3 src/shim_server.py`

## Verification
Test scripts provided in `tests/` cover Motion, Sonar, and Odometry functionalities.
