#!/usr/bin/env python
import sys
import os
from flask import Flask, request, jsonify
from naoqi import ALProxy
import json

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

    # Naoqi's C++ bindings expect byte strings (str), not unicode. Convert before calling.
    py2_module_name = module_name.encode('utf-8')
    py2_robot_ip = str(ROBOT_IP)

    print("Attempting to connect to naoqi module '{}' at {}:{}".format(py2_module_name, py2_robot_ip, ROBOT_PORT))

    try:
        proxy = ALProxy(py2_module_name, py2_robot_ip, ROBOT_PORT)
        print("Successfully created proxy to '{}'".format(module_name))

        method_to_call = getattr(proxy, method_name)
        print("Calling method '{}' with args: {} and kwargs: {}".format(method_name, args, kwargs))

        # The naoqi C++ library expects byte strings (str) for arguments, not unicode.
        # We encode any unicode strings in the args list before calling the method.
        encoded_args = [arg.encode('utf-8') if isinstance(arg, unicode) else arg for arg in args]
        result = method_to_call(*encoded_args, **kwargs)
        print("Method call successful. Result: {}".format(result))

        return jsonify({"result": result})

    except Exception as e:
        # Log the full exception to stderr for debugging
        sys.stderr.write("!!! An exception occurred: {} !!!\n".format(e))
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
