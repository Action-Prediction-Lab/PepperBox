import os
import sys
import time
import zmq
import struct
from naoqi import ALProxy

# --- Configuration Loader ---
import argparse

RATE = 50 # 50Hz

def get_config():
    parser = argparse.ArgumentParser(description="Pepper Proprioception Service")
    parser.add_argument("--ip", type=str, default=os.getenv("NAOQI_IP"), help="Robot IP (or set NAOQI_IP env)")
    parser.add_argument("--port", type=int, default=int(os.getenv("NAOQI_PORT", 9559)), help="Robot Port (or set NAOQI_PORT env)")
    parser.add_argument("--zmq_port", type=int, default=5560, help="ZMQ PUB Port")
    args = parser.parse_args()
    
    if not args.ip:
        raise ValueError("Robot IP must be provided via --ip or NAOQI_IP environment variable.")
        
    return args

def main():
    args = get_config()
    print("Starting Proprioception Service on {}:{} -> ZMQ:{}...".format(args.ip, args.port, args.zmq_port))
    
    # Connect to NaoQi
    try:
        motion_proxy = ALProxy("ALMotion", args.ip, args.port)
    except Exception as e:
        print("Error connecting to ALMotion: {}".format(e))
        sys.exit(1)
        
    # Setup ZMQ
    context = zmq.Context()
    socket = context.socket(zmq.PUB)
    socket.bind("tcp://*:{}".format(args.zmq_port))
    
    print("Publishing joint states on port TCP/{} at {} Hz...".format(args.zmq_port, RATE))
    
    try:
        while True:
            start_time = time.time()
            
            # Get Angles
            # useSensors = True ensures we get encoder values, not command values
            try:
                # 20ms blocking call roughly? No, ALMotion is fast.
                names = ["HeadYaw", "HeadPitch"]
                angles = motion_proxy.getAngles(names, True)
                
                if angles and len(angles) == 2:
                    current_time = time.time()
                    # Format: Timestamp (double), HeadYaw (float), HeadPitch (float)
                    # using 'dff' struct format
                    # Message matches: [topic, binary_data]
                    # Topic: "joints"
                    data = struct.pack('dff', current_time, angles[0], angles[1])
                    socket.send_multipart(["joints", data])
                    
            except Exception as e:
                print("Error reading joints: {}".format(e))
                
            # Sleep to maintain Rate
            elapsed = time.time() - start_time
            if elapsed < 1.0 / RATE:
                time.sleep((1.0 / RATE) - elapsed)
                
    except KeyboardInterrupt:
        print("Interrupted")
    finally:
        socket.close()
        context.term()

if __name__ == "__main__":
    main()
