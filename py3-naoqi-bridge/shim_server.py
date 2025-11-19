#!/usr/bin/env python
import sys
import os
from flask import Flask, request, jsonify
from naoqi import ALProxy

# Load environment variables from robot.env file
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
    print("robot.env file not found at {}. Using default or existing environment variables.".format(env_file_path))

def _deep_encode_to_str(obj):
    """
    Recursively traverses a data structure and encodes unicode strings to utf-8 byte strings (str).
    This is necessary before passing data to the Naoqi C++ bindings.
    """
    if isinstance(obj, unicode):
        return obj.encode('utf-8')
    if isinstance(obj, list):
        return [_deep_encode_to_str(elem) for elem in obj]
    if isinstance(obj, tuple):
        return tuple(_deep_encode_to_str(elem) for elem in obj)
    if isinstance(obj, dict):
        return {
            _deep_encode_to_str(key): _deep_encode_to_str(value)
            for key, value in obj.items()
        }
    return obj

def _deep_decode_to_unicode(obj):
    """
    Recursively traverses a data structure and decodes byte strings (str) to unicode strings.
    This is necessary for correct JSON serialization of the result.
    """
    if isinstance(obj, str):
        try:
            return obj.decode('utf-8')
        except UnicodeDecodeError:
            # If it's not valid utf-8, return the original string.
            # This can happen with binary data.
            return obj
    if isinstance(obj, list):
        return [_deep_decode_to_unicode(elem) for elem in obj]
    if isinstance(obj, tuple):
        return tuple(_deep_decode_to_unicode(elem) for elem in obj)
    if isinstance(obj, dict):
        return {
            _deep_decode_to_unicode(key): _deep_decode_to_unicode(value)
            for key, value in obj.items()
        }
    return obj

app = Flask(__name__)

# Read IP and Port from environment variables, with defaults
ROBOT_IP = os.getenv("NAOQI_IP", "127.0.0.1")
ROBOT_PORT = int(os.getenv("NAOQI_PORT", 9559))

@app.route("/api/call", methods=["POST"])
def call_naoqi_method():
    print("---")
    print("Received request at /api/call")
    data = request.get_json()
    print("Request data: {}".format(data))

    if not all(k in data for k in ["module", "method"]):
        print("Invalid request payload")
        return jsonify({"error": "Invalid request payload, 'module' and 'method' are required."}), 400

    module_name = data["module"]
    method_name = data["method"]
    args = data.get("args", [])
    kwargs = data.get("kwargs", {})

    # Naoqi's C++ bindings expect byte strings (str), not unicode.
    py2_module_name = module_name.encode('utf-8')
    py2_robot_ip = str(ROBOT_IP)

    print("Attempting to connect to naoqi module '{}' at {}:{}".format(py2_module_name, py2_robot_ip, ROBOT_PORT))

    try:
        proxy = ALProxy(py2_module_name, py2_robot_ip, ROBOT_PORT)
        print("Successfully created proxy to '{}'".format(module_name))

        method_to_call = getattr(proxy, method_name)

        # Recursively encode all unicode strings in args and kwargs to byte strings (str)
        encoded_args = _deep_encode_to_str(args)
        encoded_kwargs = _deep_encode_to_str(kwargs)

        print("Calling method '{}' with encoded args: {} and kwargs: {}".format(method_name, encoded_args, encoded_kwargs))

        result = method_to_call(*encoded_args, **encoded_kwargs)
        print("Method call successful. Result: {}".format(result))

        # Recursively decode the result back to unicode for proper JSON serialization
        json_compatible_result = _deep_decode_to_unicode(result)
        return jsonify({"result": json_compatible_result})

    except Exception as e:
        # Log the full exception to stderr for debugging
        sys.stderr.write("!!! An exception occurred: {} !!!\n".format(e))
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
