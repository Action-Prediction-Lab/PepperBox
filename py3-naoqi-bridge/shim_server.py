#!/usr/bin/env python
import sys
import os
import threading
from flask import Flask, request, jsonify
from naoqi import ALProxy

# --- Thread-Safety Fix ---
# A lock to make the global PROXY_CACHE thread-safe
PROXY_LOCK = threading.Lock()

# --- Configuration ---
script_dir = os.path.dirname(os.path.abspath(__file__))
env_file_path = os.path.join(script_dir, 'robot.env')
try:
    with open(env_file_path) as f:
        for line in f:
            if line.strip() and not line.startswith('#'):
                key, value = line.strip().split('=', 1)
                # Only load from file if NOT already set in environment (Docker priority)
                if key not in os.environ:
                    os.environ[key] = value
    print("Loaded configuration from {}".format(env_file_path))
except IOError:
    print("robot.env file not found. Using defaults.")

app = Flask(__name__)

ROBOT_IP = os.getenv("NAOQI_IP", "127.0.0.1")
ROBOT_PORT = int(os.getenv("NAOQI_PORT", 9559))

# --- PERFORMANCE FIX: Global Proxy Cache ---
# This prevents re-connecting 1000 times per second
PROXY_CACHE = {}

def get_proxy(module_name):
    with PROXY_LOCK:
        global PROXY_CACHE
        if module_name in PROXY_CACHE:
            return PROXY_CACHE[module_name]
        
        # Create new connection only if needed
        py2_module_name = module_name.encode('utf-8')
        py2_robot_ip = str(ROBOT_IP)
        
        print("Creating new ALProxy connection to '{}'...".format(py2_module_name))
        try:
            proxy = ALProxy(py2_module_name, py2_robot_ip, ROBOT_PORT)
            PROXY_CACHE[module_name] = proxy
            return proxy
        except Exception as e:
            print("Failed to create proxy: {}".format(e))
            raise e

def _deep_encode_to_str(obj):
    if isinstance(obj, unicode): return obj.encode('utf-8')
    if isinstance(obj, list): return [_deep_encode_to_str(e) for e in obj]
    if isinstance(obj, tuple): return tuple(_deep_encode_to_str(e) for e in obj)
    if isinstance(obj, dict): return {_deep_encode_to_str(k): _deep_encode_to_str(v) for k, v in obj.items()}
    return obj

def _deep_decode_to_unicode(obj):
    if isinstance(obj, str):
        try: return obj.decode('utf-8')
        except: return obj
    if isinstance(obj, list): return [_deep_decode_to_unicode(e) for e in obj]
    if isinstance(obj, tuple): return tuple(_deep_decode_to_unicode(e) for e in obj)
    if isinstance(obj, dict): return {_deep_decode_to_unicode(k): _deep_decode_to_unicode(v) for k, v in obj.items()}
    return obj

@app.route("/api/call", methods=["POST"])
def call_naoqi_method():
    data = request.get_json()
    if not data or "module" not in data or "method" not in data:
        return jsonify({"error": "Invalid request"}), 400

    module_name = data["module"]
    method_name = data["method"]
    args = data.get("args", [])
    kwargs = data.get("kwargs", {})

    try:
        # 1. Get Cached Proxy (Fast!)
        proxy = get_proxy(module_name)

        # 2. Handle 'post' or standard calls
        if method_name == "post":
            if not args:
                raise ValueError("post requires method name as first arg")
            
            target_method = args[0]
            if isinstance(target_method, unicode): target_method = target_method.encode('utf-8')
            
            real_args = args[1:]
            
            post_proxy = getattr(proxy, "post")
            method_to_call = getattr(post_proxy, target_method)
            encoded_args = _deep_encode_to_str(real_args)
            
            result = method_to_call(*encoded_args, **_deep_encode_to_str(kwargs))
        
        else:
            method_to_call = getattr(proxy, method_name)
            encoded_args = _deep_encode_to_str(args)
            result = method_to_call(*encoded_args, **_deep_encode_to_str(kwargs))

        return jsonify({"result": _deep_decode_to_unicode(result)})

    except Exception as e:
        sys.stderr.write("Error calling {}.{}: {}\n".format(module_name, method_name, e))
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    # threaded=True is required for concurrent requests
    app.run(host="0.0.0.0", port=5000, threaded=True)

