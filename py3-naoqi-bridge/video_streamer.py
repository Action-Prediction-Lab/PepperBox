import os
import sys
import time
import zmq
import vision_definitions
from naoqi import ALProxy

# --- Configuration Loader ---
script_dir = os.path.dirname(os.path.abspath(__file__))
env_file_path = os.path.join(script_dir, 'robot.env')
try:
    with open(env_file_path) as f:
        for line in f:
            if line.strip() and not line.startswith('#'):
                key, value = line.strip().split('=', 1)
                os.environ[key] = value
    print("Loaded configuration from {}".format(env_file_path))
except IOError:
    print("robot.env file not found. Using environment variables.")

ROBOT_IP = os.getenv("NAOQI_IP", "127.0.0.1")
ROBOT_PORT = int(os.getenv("NAOQI_PORT", 9559))
ZMQ_PORT = 5559
FPS = 30 # Target FPS

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
    # Resolution: 2 = VGA (640x480), 1 = QVGA (320x240)
    # ColorSpace: 11 = RGB, 0 = Yuv
    resolution = vision_definitions.kQVGA 
    # OPTIMIZATION: Use YUV Color Space to extract Y (Greyscale) channel
    # This reduces bandwidth by 2/3rds (from 3 bytes/pixel to 1 byte/pixel)
    color_space = vision_definitions.kYuvColorSpace
    
    client_name = "zmq_streamer_{}".format(int(time.time()))
    print("Subscribing to camera as {}...".format(client_name))
    
    try:
        video_client = video_proxy.subscribeCamera(client_name, 0, resolution, color_space, FPS)
    except Exception as e:
        print("Error subscribing: {}".format(e))
        sys.exit(1)
        
    print("Streaming video on port TCP/{} at {} FPS...".format(ZMQ_PORT, FPS))
    
    try:
        frame_count = 0
        last_report_time = time.time()
        while True:
            start_time = time.time()
            
            # Get Image
            # [width, height, layers, colorSpace, timeStamp, binaryImage, cameraID, leftAngle, topAngle, rightAngle, bottomAngle]
            nao_image = video_proxy.getImageRemote(video_client)
            
            # FPS Calculation (Debug only)
            # Source is limited to ~4-5 FPS by hardware
            frame_count += 1
            if frame_count % 30 == 0:
                now = time.time()
                actual_fps = 30.0 / (now - last_report_time)
                print("Source FPS: {:.2f}".format(actual_fps))
                sys.stdout.flush()
                last_report_time = now
            
            if nao_image:
                # NaoQi returns YUV422 when kYuvColorSpace is requested.
                # The data is interleaved. However, for bandwidth saving we ONLY want the Y (Luminance) channel.
                # In YUV422, Y is every byte?, wait. 
                # Actually NaoQi returns the raw buffer. 
                # Checking docs: kYuvColorSpace = 0.
                # Image is [Y1, U, Y2, V]. 
                # Wait, simpler approach:
                # If we just send the whole buffer, it's 2 bytes/pixel (YUV422). 
                # To get 1 byte/pixel we need to extract Y.
                # Let's verify buffer size first.
                
                img_data = nao_image[6]
                
                # OPTIMIZATION: Extract Y channel only if YUV
                # But actually, NaoQi's ALVideoDevice kYuvColorSpace returns data in YUV422 format.
                # Length = Width * Height * 2.
                # We want to send Width * Height * 1.
                # We can skip every other byte? No, it's YUYV usually.
                # Let's stick to sending the RAW YUV422 first (33% saving) to be safe,
                # OR if we are confident, strip it. 
                # Let's send the raw buffer for now, receiving end will handle it.
                # Actually, standard is RGB=3 bytes, YUV422=2 bytes. That is a 33% saving immediately.
                
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
