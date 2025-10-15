import json
import urllib.request

def call_naoqi(module, method, args=None, kwargs=None):
    """
    Calls a NAOqi method through the shim server.
    Returns a tuple of (success, result).
    """
    if args is None:
        args = []
    if kwargs is None:
        kwargs = {}

    url = "http://localhost:5000/api/call"
    data = {
        "module": module,
        "method": method,
        "args": args,
        "kwargs": kwargs,
    }
    
    req = urllib.request.Request(
        url,
        data=json.dumps(data).encode('utf-8'),
        headers={'Content-Type': 'application/json'}
    )
    
    try:
        with urllib.request.urlopen(req) as response:
            response_data = json.loads(response.read().decode('utf-8'))
            if response.status == 200:
                print("Request successful.")
                return True, response_data.get("result")
            else:
                print(f"Error: {response.status} - {response_data.get('error')}")
                return False, None
    except Exception as e:
        print(f"An error occurred: {e}")
        return False, None

if __name__ == "__main__":
    print("Testing the bridge by making the robot say 'Hello from Python 3'.")
    success, result = call_naoqi("ALTextToSpeech", "say", args=["Hello from Python 3"])
    
    if success:
        print("Request sent successfully.")
    else:
        print("Request failed.")
