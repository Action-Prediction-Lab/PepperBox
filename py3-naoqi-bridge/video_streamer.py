#!/usr/bin/env python
import sys
import os
import time
import zmq
import vision_definitions
from naoqi import ALProxy

# --- Configuration ---
ROBOT_IP = os.getenv("NAOQI_IP", "127.0.0.1")
ROBOT_PORT = int(os.getenv("NAOQI_PORT", 9559))
ZMQ_PORT = 5559
FPS = 10 # Target FPS

def main():
    print("Starting Video Streamer...")
    
    # Connect to NaoQi
    try:
        video_proxy = ALProxy("ALVideoDevice", ROBOT_IP, ROBOT_PORT)
    except Exception as e:
        print("Error connecting to ALVideoDevice: {}".format(e))
        sys.exit(1)
        
    # Setup ZMQ
    context = zmq.Context()
    socket = context.socket(zmq.PUB)
    socket.bind("tcp://*:{}".format(ZMQ_PORT))
    
    # Subscribe to Camera
    # Resolution: 2 = VGA (640x480), 1 = QVGA (320x240)
    # ColorSpace: 11 = RGB, 13 = BGR
    resolution = vision_definitions.kqvga 
    color_space = vision_definitions.kRGBColorSpace
    
    client_name = "zmq_streamer_{}".format(int(time.time()))
    print("Subscribing to camera as {}...".format(client_name))
    
    try:
        video_client = video_proxy.subscribeCamera(client_name, 0, resolution, color_space, FPS)
    except Exception as e:
        print("Error subscribing: {}".format(e))
        sys.exit(1)
        
    print("Streaming video on port TCP/{} at {} FPS...".format(ZMQ_PORT, FPS))
    
    try:
        while True:
            start_time = time.time()
            
            # Get Image
            # [width, height, layers, colorSpace, timeStamp, binaryImage, cameraID, leftAngle, topAngle, rightAngle, bottomAngle]
            nao_image = video_proxy.getImageRemote(video_client)
            
            if nao_image:
                img_data = nao_image[6]
                
                # Send via ZMQ
                # Topic: "video", Data: raw bytes
                socket.send_multipart(["video", img_data])
                
            # Sleep to maintain FPS
            elapsed = time.time() - start_time
            if elapsed < 1.0 / FPS:
                time.sleep((1.0 / FPS) - elapsed)
                
    except KeyboardInterrupt:
        print("Interrupted")
    finally:
        print("Unsubscribing...")
        video_proxy.unsubscribe(video_client)
        socket.close()
        context.term()

if __name__ == "__main__":
    main()
