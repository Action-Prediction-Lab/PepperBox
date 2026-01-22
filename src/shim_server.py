from flask import Flask, request, jsonify
import sys
import threading
from driver import QiBulletDriver

# --- Initialization ---
# We launch the simulation on import/startup
driver = QiBulletDriver(gui=True)

app = Flask(__name__)

@app.route("/api/call", methods=["POST"])
def call_naoqi_method():
    data = request.get_json()
    module = data.get("module")
    method = data.get("method")
    args = data.get("args", [])
    
    print(f"Received call: {module}.{method} with args {args}")
    
    try:
        result = None
        
        # --- API MAPPING ---
        if module == "ALTextToSpeech" and method == "say":
            driver.say(args[0])
            
        elif module == "ALMotion":
            if method == "move":
                # args: x, y, theta
                # Ensure we cast to float, as JSON might pass them as strings or ints
                x = float(args[0])
                y = float(args[1])
                theta = float(args[2])
                print(f"[Shim] Executing Move: x={x}, y={y}, theta={theta}")
                driver.move(x, y, theta)
            elif method == "moveToward":
                 # Naoqi: moveToward(vx, vy, vth) -> Velocity control
                 x = float(args[0])
                 y = float(args[1])
                 theta = float(args[2])
                 # print(f"[Shim] Executing moveToward: x={x}, y={y}, theta={theta}")
                 driver.move(x, y, theta)

            elif method == "stopMove":
                print("[Shim] Executing stopMove")
                driver.stop_motion()

            elif method == "stopMove":
                print("[Shim] Executing stopMove")
                driver.stop_motion()
            
            elif method == "getRobotPosition":
                # args: useSensors (bool) - ignored in shim, we give ground truth
                # Returns [x, y, theta]
                result = driver.get_position()

            elif method == "moveTo":
                # Fallback to move(0,0,0) or warn
                print("WARNING: moveTo called (blocking), treating as move(0,0,0) or ignored for async shim")

        elif module == "ALRobotPosture":
            if method == "goToPosture":
                 # args: posture_name, speed
                 p_name = args[0]
                 speed = 0.5
                 if len(args) > 1:
                     speed = float(args[1])
                 driver.set_posture(p_name, speed)
                 result = True

        elif module == "ALAnimationPlayer":
            # Stub for animations
            print(f"[Shim] ALAnimationPlayer.{method} called (Not Implemented in qibullet). Ignored.")
            result = None
            
        elif module == "ALLaser":
            if method == "show":
                # Custom method to toggle debug lines
                # args: [True/False]
                state = True
                if len(args) > 0:
                    state = bool(args[0])
                driver.show_lasers(state)
                result = True

        elif module == "ALAutonomousLife":
            # Stub for life
            print(f"[Shim] ALAutonomousLife.{method} called (Not Implemented). Ignored.")
            result = "disabled"

        elif module == "ALBasicAwareness":
             print(f"[Shim] ALBasicAwareness.{method} called. Ignored.")
             result = None
             
        elif module == "ALMemory":
            if method == "getData":
                key = args[0]
                # print(f"[Shim] ALMemory.getData: {key}")
                
                if key == "Device/SubDeviceList/Platform/Front/Sonar/Sensor/Value":
                    result = driver.get_front_sonar()
                elif key == "Device/SubDeviceList/Platform/Back/Sonar/Sensor/Value":
                    result = driver.get_back_sonar()
                elif key == "Device/SubDeviceList/Platform/Laser/Front/Sensor/Value":
                     # Non-standard key, but exposing the raw array
                    result = driver.get_front_laser()
                else:
                    # Generic fallback
                    result = None
                    
        # TODO: Add more modules (ALVideoDevice, ALMemory, etc.)
        
        return jsonify({"result": result})
        
    except Exception as e:
        sys.stderr.write(f"Error handling request: {e}\n")
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    # Start Flask
    # Note: PyBullet GUI needs the main thread usually? 
    # qibullet spawns its own thread for physics. 
    # Flask can run on main thread IF qibullet is happy backgrounded.
    # Actually qibullet examples usually run script on main thread.
    
    print("Starting Flask Shim Server on port 5000...")
    app.run(host="0.0.0.0", port=5000, debug=False, use_reloader=False)
