from naoqi_proxy import NaoqiClient, NaoqiProxyError

if __name__ == "__main__":
    print("Testing the bridge by making the robot say 'Hello from Python 3' using the NaoqiClient proxy.")
    
    client = NaoqiClient()
    
    try:
        # Example: Make the robot say something
        client.ALTextToSpeech.say("Hello from Python 3")
        print("Request sent successfully.")

    except NaoqiProxyError as e:
        print(f"NAOqi Proxy Error: {e}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
