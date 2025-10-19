from naoqi_proxy import NaoqiClient, NaoqiProxyError

try:
    client = NaoqiClient()
    client.ALTextToSpeech.say("Hello, world!")
    print("Successfully made the robot say 'Hello, world!' via Python 3 proxy.")
except NaoqiProxyError as e:
    print(f"NAOqi Proxy Error: {e}")
except Exception as e:
    print(f"An unexpected error occurred: {e}")