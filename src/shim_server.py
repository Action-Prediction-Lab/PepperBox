"""Sim shim HTTP entry point, wire-compatible with `py3-naoqi-bridge/shim_server.py`.

`create_app` takes a module-adapter dict so tests can mock without qibullet; `__main__` wires the real driver, task registry and joint publisher."""

import os
import sys
from flask import Flask, request, jsonify
from dispatcher import Dispatcher


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


if __name__ == "__main__":
    import signal

    from driver import QiBulletDriver
    from post_tasks import TaskRegistry
    from adapters import build_module_adapters
    from joint_publisher import JointPublisher

    _gui = os.environ.get("QIBULLET_GUI", "false").lower() in ("1", "true", "yes")
    driver = QiBulletDriver(gui=_gui)

    def _shutdown(signum, _frame):
        print("[ShimServer] Signal {}; stopping simulation.".format(signum))
        driver.stop()
        sys.exit(0)

    signal.signal(signal.SIGTERM, _shutdown)
    signal.signal(signal.SIGINT, _shutdown)
    task_registry = TaskRegistry()
    module_adapters = build_module_adapters(driver.pepper, task_registry)

    JointPublisher(driver.pepper).start()

    app = create_app(module_adapters)
    print("Starting Flask Shim Server on port 5000...")
    app.run(host="0.0.0.0", port=5000, debug=False, use_reloader=False, threaded=True)
