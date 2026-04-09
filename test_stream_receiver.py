import zmq
import cv2
import numpy as np
import time
import sys

def main():
    context = zmq.Context()
    socket = context.socket(zmq.SUB)
    
    # Connect to PepperBox (running on host network or exposed port)
    uri = "tcp://localhost:5559"
    print(f"Connecting to video stream at {uri}...")
    socket.connect(uri)
    socket.setsockopt_string(zmq.SUBSCRIBE, "video")
    
    print("Waiting for frames...")
    
    count = 0
    start_time = time.time()
    headless = "--headless" in sys.argv
    
    # Parse timeout
    timeout = None
    for arg in sys.argv:
        if arg.startswith("--timeout="):
            try:
                timeout = float(arg.split("=")[1])
            except:
                pass
    
    while True:
        try:
            # Check timeout
            if timeout and (time.time() - start_time > timeout):
                print(f"Timeout of {timeout}s reached. Exiting.")
                break

            # Receive multipart: [topic, data]
            # Use NOBLOCK to check for exit conditions easier? No, blocking is fine.
            topic, msg = socket.recv_multipart()
            
            if len(msg) == 230400:
                h, w = 240, 320
            elif len(msg) == 921600:
                h, w = 480, 640
            else:
                print(f"Unknown frame size: {len(msg)}")
                continue
                
            frame = np.frombuffer(msg, dtype=np.uint8).reshape((h, w, 3))
            
            if not headless:
                # BGR for OpenCV display
                frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
                cv2.imshow("PepperBox Stream Test", frame)
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    break
            
            count += 1
            if count % 10 == 0:
                fps = count / (time.time() - start_time)
                print(f"SUCCESS: Receiving at {fps:.2f} FPS. Resolution: {w}x{h}")
                if headless and count >= 30:
                    print("Test Verification Complete. Exiting.")
                    break
                
        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"Error: {e}")
            break
            
    if not headless:
        cv2.destroyAllWindows()
    context.term()

if __name__ == "__main__":
    main()
