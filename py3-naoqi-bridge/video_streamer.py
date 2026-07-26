import os
import sys
import time
import zmq
import struct
import vision_definitions
from naoqi import ALProxy

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
    
    try:
        video_proxy = ALProxy("ALVideoDevice", ROBOT_IP, ROBOT_PORT)
        # motion_proxy is never used again; it exits early if ALMotion is unreachable.
        motion_proxy = ALProxy("ALMotion", ROBOT_IP, ROBOT_PORT)
    except Exception as e:
        print("Error connecting to Proxies: {}".format(e))
        sys.exit(1)
        
    context = zmq.Context()
    socket = context.socket(zmq.PUB)
    socket.bind("tcp://*:{}".format(ZMQ_PORT))
    
    # Resolution: 2 = VGA (640x480), 1 = QVGA (320x240). ColorSpace: 11 = RGB, 13 = BGR, 0 = Yuv.
    resolution = vision_definitions.kQVGA 
    # YUV so only the Y (greyscale) channel travels: 1 byte/pixel instead of 3.
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
            
            # [width, height, layers, colorSpace, timeStamp, binaryImage, cameraID, leftAngle, topAngle, rightAngle, bottomAngle]
            nao_image = video_proxy.getImageRemote(video_client)
            
            # Debug FPS counter; the source is hardware-limited to ~4-5 FPS.
            frame_count += 1
            if frame_count % 30 == 0:
                now = time.time()
                actual_fps = 30.0 / (now - last_report_time)
                print("Source FPS: {:.2f}".format(actual_fps))
                sys.stdout.flush()
                last_report_time = now
            
            if nao_image:
                # kYuvColorSpace (0) yields interleaved YUV422 at 2 bytes/pixel.
                
                img_data = nao_image[6]
                
                # Extract Y only: 153600 = QVGA YUYV, 76800 = already greyscale.
                if len(img_data) == 153600:
                    # YUYV (2 bytes/px) -> Extract Y (Index 0, 2...)
                    y_channel = img_data[0::2]
                elif len(img_data) == 76800:
                    # Already 1 byte/px (Y-only or similar) -> Send as is
                    y_channel = img_data
                elif len(img_data) == 38400:
                     # QQVGA YUYV (160x120 * 2) -> Extract Y
                     y_channel = img_data[0::2]
                elif len(img_data) == 19200:
                     # QQVGA Y-only -> Send as is
                     y_channel = img_data
                else:
                    # Fallback
                    y_channel = img_data
                
                # Wire format: topic "video", header (d), then image bytes.
                
                # NaoQi stamps uptime (nao_image[4:6]); system time replaces it to match proprioception.
                timestamp = time.time()
                
                # Header: timestamp (double)
                header = struct.pack('d', timestamp)
                
                socket.send_multipart(["video", header, y_channel])
                
            elapsed = time.time() - start_time
            if elapsed < 1.0 / FPS:
                time.sleep((1.0 / FPS) - elapsed)
                
            if frame_count % 30 == 0:
                print("Streamer FPS: {:.1f}".format(30.0 / (time.time() - last_report_time)))
                last_report_time = time.time()
                
    except KeyboardInterrupt:
        print("Interrupted")
    finally:
        print("Unsubscribing...")
        video_proxy.unsubscribe(video_client)
        socket.close()
        context.term()

if __name__ == "__main__":
    main()
