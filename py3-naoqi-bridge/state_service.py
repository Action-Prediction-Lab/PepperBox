#!/usr/bin/env python2
import os
import sys
import time
import zmq
import struct
import json
import math
from naoqi import ALProxy

# --- Configuration Loader ---
import argparse

RATE_JOINTS = 50.0  # 50Hz for control loop
RATE_PROXIMITY = 15.0 # 15Hz for visualization
PROXIMITY_DIVIDER = int(RATE_JOINTS / RATE_PROXIMITY) # Poll proximity every N cycles

def get_config():
    parser = argparse.ArgumentParser(description="Pepper State Service (Unified)")
    parser.add_argument("--ip", type=str, default=os.getenv("NAOQI_IP"), help="Robot IP (or set NAOQI_IP env)")
    parser.add_argument("--port", type=int, default=int(os.getenv("NAOQI_PORT", 9559)), help="Robot Port (or set NAOQI_PORT env)")
    parser.add_argument("--zmq_port", type=int, default=5560, help="ZMQ PUB Port")
    args = parser.parse_args()
    
    if not args.ip:
        raise ValueError("Robot IP must be provided via --ip or NAOQI_IP environment variable.")
        
    return args

def get_proximity_keys():
    # --- 1. Sonar ---
    # Try Modern 2.5 keys first, then Platform fallback
    sonar_keys = [
        "Device/SubDeviceList/US/FrontLeft/Sensor/Value",
        "Device/SubDeviceList/US/FrontRight/Sensor/Value",
        "Device/SubDeviceList/US/BackLeft/Sensor/Value",
        "Device/SubDeviceList/US/BackRight/Sensor/Value"
    ]
    sonar_fallback = [
        "Device/SubDeviceList/Platform/Front/Sonar/Sensor/Value",
        "Device/SubDeviceList/Platform/Back/Sonar/Sensor/Value"
    ]
    
    # --- 2. Lasers ---
    # Traditional Laser
    laser_keys = []
    for loc in ["Front", "Left", "Right"]:
        for i in range(15):
            laser_keys.append("Device/SubDeviceList/Laser/{}/Horizontal/Sensor/Value{}".format(loc, i))
    
    # Platform Segment Laser (Found on some specific firmwares)
    laser_platform_keys = []
    for loc in ["Front", "Left", "Right"]:
        for i in range(1, 16):
            laser_platform_keys.append("Device/SubDeviceList/Platform/LaserSensor/{}/Horizontal/Seg{:02d}/X/Sensor/Value".format(loc, i))
            laser_platform_keys.append("Device/SubDeviceList/Platform/LaserSensor/{}/Horizontal/Seg{:02d}/Y/Sensor/Value".format(loc, i))

    # --- 3. Bumpers ---
    bumper_keys = [
        "Device/SubDeviceList/Platform/FrontLeft/Bumper/Sensor/Value",
        "Device/SubDeviceList/Platform/FrontRight/Bumper/Sensor/Value",
        "Device/SubDeviceList/Platform/Back/Bumper/Sensor/Value"
    ]
    
    return sonar_keys, sonar_fallback, laser_keys, laser_platform_keys, bumper_keys

def main():
    args = get_config()
    
    # Connect to NaoQi
    try:
        motion_proxy = ALProxy("ALMotion", args.ip, args.port)
        memory_proxy = ALProxy("ALMemory", args.ip, args.port)
    except Exception as e:
        print("Error connecting to Naoqi: {}".format(e))
        sys.exit(1)
        
    # Setup ZMQ
    context = zmq.Context()
    socket = context.socket(zmq.PUB)
    socket.bind("tcp://*:{}".format(args.zmq_port))
    
    prox_sonar_keys, prox_sonar_fallback, prox_laser_keys, prox_laser_platform, prox_bumper_keys = get_proximity_keys()
    
    loop_count = 0
    dt_joints = 1.0 / RATE_JOINTS
    
    try:
        while True:
            start_loop = time.time()
            loop_count += 1
            
            # --- 1. JOINT DATA (50Hz) ---
            try:
                names = ["HeadYaw", "HeadPitch"]
                angles = motion_proxy.getAngles(names, True)
                if angles and len(angles) == 2:
                    # Maintain exact legacy format for TrackingOrchestrator
                    data = struct.pack('dff', start_loop, angles[0], angles[1])
                    socket.send_multipart(["joints", data])
            except Exception as e:
                print("Joints Error: {}".format(e))

            # --- 2. PROXIMITY DATA (~15Hz) ---
            if loop_count % PROXIMITY_DIVIDER == 0:
                payload = {"timestamp": start_loop, "sonar": {}, "lasers": {}, "bumpers": {}}
                
                # A. SONAR
                try:
                    s_vals = memory_proxy.getListData(prox_sonar_keys)
                    if s_vals and s_vals[0] is not None:
                        payload["sonar"] = {
                            "front_left": s_vals[0], "front_right": s_vals[1],
                            "back_left": s_vals[2], "back_right": s_vals[3]
                        }
                    else:
                        # Try fallback
                        s_vals = memory_proxy.getListData(prox_sonar_fallback)
                        if s_vals and s_vals[0] is not None:
                            # Map 2 sonars to 4 fields (approx)
                            payload["sonar"] = {
                                "front_left": s_vals[0], "front_right": s_vals[0],
                                "back_left": s_vals[1], "back_right": s_vals[1]
                            }
                except Exception:
                    pass

                # B. LASERS
                try:
                    l_vals = memory_proxy.getListData(prox_laser_keys)
                    if l_vals and l_vals[0] is not None:
                        payload["lasers"] = {
                            "front": l_vals[0:15], "left": l_vals[15:30], "right": l_vals[30:45]
                        }
                    else:
                        # Try Platform/Segment laser
                        l_vals = memory_proxy.getListData(prox_laser_platform)
                        if l_vals and l_vals[0] is not None:
                            # We have X,Y pairs for each segment. Convert to distance.
                            # l_vals format: [F1X, F1Y, F2X, F2Y, ..., L1X, L1Y, ..., R1X, R1Y, ...]
                            def compute_dists(start_idx):
                                dists = []
                                for i in range(15):
                                    x = l_vals[start_idx + i*2]
                                    y = l_vals[start_idx + i*2 + 1]
                                    dists.append(math.sqrt(x**2 + y**2))
                                return dists
                            
                            payload["lasers"] = {
                                "front": compute_dists(0),
                                "left": compute_dists(30),
                                "right": compute_dists(60)
                            }
                except Exception as e:
                    if loop_count % 300 == 0:
                        sys.stderr.write("Laser Error: {}\n".format(e))
                        sys.stderr.flush()

                # C. BUMPERS
                try:
                    b_vals = memory_proxy.getListData(prox_bumper_keys)
                    if b_vals:
                        payload["bumpers"] = {
                            "front_left": b_vals[0], "front_right": b_vals[1],
                            "back": b_vals[2]
                        }
                except Exception:
                    pass

                # Publish what we have
                socket.send_multipart(["proximity", json.dumps(payload)])

            # --- Sleep to maintain rate ---
            elapsed = time.time() - start_loop
            if elapsed < dt_joints:
                time.sleep(dt_joints - elapsed)
                
    except KeyboardInterrupt:
        print("Interrupted")
    finally:
        socket.close()
        context.term()

if __name__ == "__main__":
    main()
