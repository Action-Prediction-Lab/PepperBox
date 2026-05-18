"""Sim shim HTTP entry point. Wire-compatible with the real-robot shim at
`py3-naoqi-bridge/shim_server.py`.

The `create_app` factory takes a module-adapter dict so tests can supply
mocked adapters without launching qibullet. The `__main__` block wires up
the real driver, task registry, and joint publisher."""

import os
import sys
import threading
import struct
import time
import zmq
from flask import Flask, request, jsonify
from dispatcher import Dispatcher

class JointPublisher(threading.Thread):
    """50Hz PUB of HeadYaw/HeadPitch on :5560 topic 'joints', wire-compatible
    with py3-naoqi-bridge/state_service.py."""

    def __init__(self, pepper, rate_hz=50.0, port=5560):
        super(JointPublisher, self).__init__()
        self.pepper = pepper
        self.dt = 1.0 / rate_hz
        self.port = port
        self.daemon = True

    def run(self):
        ctx = zmq.Context()
        sock = ctx.socket(zmq.PUB)
        sock.bind("tcp://*:{}".format(self.port))
        print("[JointPublisher] Bound ZMQ PUB on tcp://*:{}".format(self.port))
        while True:
            loop_start = time.time()
            try:
                angles = self.pepper.getAnglesPosition(["HeadYaw", "HeadPitch"])
                if angles and len(angles) == 2:
                    payload = struct.pack("dff", loop_start, angles[0], angles[1])
                    sock.send_multipart([b"joints", payload])
            except Exception as e:
                sys.stderr.write("[JointPublisher] Error: {}\n".format(e))
            elapsed = time.time() - loop_start
            if elapsed < self.dt:
                time.sleep(self.dt - elapsed)


# --- Flask app factory ---

def create_app(module_adapters):
    """Build the Flask app around a pre-built module-adapter dict."""
    app = Flask(__name__)
    dispatcher = Dispatcher(module_adapters)

    @app.route("/api/call", methods=["POST"])
    def call_naoqi_method():
        data = request.get_json(silent=True) or {}
        module = data.get("module")
        method = data.get("method")
        if not module or not method:
            return jsonify({"error": "Invalid request: missing 'module' or 'method'"}), 400

        args = data.get("args", [])
        kwargs = data.get("kwargs", {})

        try:
            result, is_stub = dispatcher.dispatch(module, method, args, kwargs)
        except AttributeError as e:
            sys.stderr.write("Error calling {}.{}: {}\n".format(module, method, e))
            return jsonify({"error": str(e)}), 500
        except Exception as e:
            sys.stderr.write("Adapter raised on {}.{}: {}\n".format(module, method, e))
            return jsonify({"error": str(e)}), 500

        response = jsonify({"result": result})
        if is_stub:
            response.headers["X-Sim-Stub"] = "1"
            sys.stderr.write("[SIM-STUB] {}.{}(args={!r}) -> {!r}\n".format(
                module, method, args, result
            ))
        return response

    return app


# --- main: spin up qibullet, build adapters, start app ---

if __name__ == "__main__":
    from driver import QiBulletDriver
    from post_tasks import TaskRegistry
    from adapters import build_module_adapters

    _gui = os.environ.get("QIBULLET_GUI", "false").lower() in ("1", "true", "yes")
    driver = QiBulletDriver(gui=_gui)
    task_registry = TaskRegistry()
    module_adapters = build_module_adapters(driver.pepper, task_registry)

    JointPublisher(driver.pepper).start()

    app = create_app(module_adapters)
    print("Starting Flask Shim Server on port 5000...")
    app.run(host="0.0.0.0", port=5000, debug=False, use_reloader=False, threaded=True)
