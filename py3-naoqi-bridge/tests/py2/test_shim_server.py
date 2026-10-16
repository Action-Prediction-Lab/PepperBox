"""Unit tests for the physical-robot shim, with the naoqi SDK stubbed.

Covers the REST contract and the Py2 unicode marshalling; connecting to a real broker still needs hardware.
"""
import sys
import types
import unittest

# Stub the proprietary SDK before importing the module under test.
if "naoqi" not in sys.modules:
    _naoqi = types.ModuleType("naoqi")
    _naoqi.ALProxy = lambda *a, **k: None
    sys.modules["naoqi"] = _naoqi

import shim_server  # noqa: E402


class _FakePost(object):
    """ALProxy.post is a distinct object whose methods dispatch asynchronously."""

    def __init__(self, parent):
        self._parent = parent

    def echo(self, *args):
        self._parent.calls.append(("post.echo", args))
        return 99  # NAOqi returns a task id, not the result


class _FakeProxy(object):
    """Stands in for ALProxy: records calls and echoes arguments back."""

    def __init__(self, name="ALMotion"):
        self.name = name
        self.calls = []
        self.post = _FakePost(self)

    def echo(self, *args):
        self.calls.append(("echo", args))
        return list(args)

    def boom(self, *args):
        self.calls.append(("boom", args))
        raise RuntimeError("naoqi exploded")


class ShimTestCase(unittest.TestCase):
    def setUp(self):
        shim_server.PROXY_CACHE.clear()
        self.proxy = _FakeProxy()
        shim_server.PROXY_CACHE["ALMotion"] = self.proxy
        shim_server.app.config["TESTING"] = True
        self.client = shim_server.app.test_client()

    def post(self, payload):
        import json
        return self.client.post("/api/call", data=json.dumps(payload),
                                content_type="application/json")


class TestEncoding(unittest.TestCase):
    def test_unicode_becomes_utf8_str(self):
        out = shim_server._deep_encode_to_str(u"Bonjour")
        self.assertIsInstance(out, str)
        self.assertEqual(out, "Bonjour")

    def test_encoding_recurses_into_containers(self):
        out = shim_server._deep_encode_to_str([u"a", (u"b",), {u"k": u"v"}])
        self.assertEqual(out, ["a", ("b",), {"k": "v"}])
        self.assertIsInstance(out[2].keys()[0], str)

    def test_non_strings_pass_through(self):
        self.assertEqual(shim_server._deep_encode_to_str([1, 2.5, True, None]),
                         [1, 2.5, True, None])

    def test_decoding_returns_unicode(self):
        out = shim_server._deep_decode_to_unicode(["a", {"k": "v"}])
        self.assertIsInstance(out[0], unicode)  # noqa: F821
        self.assertIsInstance(out[1].keys()[0], unicode)  # noqa: F821

    def test_undecodable_bytes_pass_through(self):
        raw = b"\xff\xfe"
        self.assertEqual(shim_server._deep_decode_to_unicode(raw), raw)


class TestProxyCache(ShimTestCase):
    def test_proxy_is_reused_across_calls(self):
        first = shim_server.get_proxy("ALMotion")
        second = shim_server.get_proxy("ALMotion")
        self.assertIs(first, second)

    def test_a_failed_call_drops_the_cached_proxy(self):
        """A failed call removes the proxy from the cache."""
        self.post({"module": "ALMotion", "method": "boom"})
        self.assertNotIn("ALMotion", shim_server.PROXY_CACHE)

    def test_a_failed_call_is_not_retried(self):
        """The shim does not retry a failed call."""
        self.post({"module": "ALMotion", "method": "boom"})
        self.assertEqual([name for name, _ in self.proxy.calls], ["boom"])


class TestRoute(ShimTestCase):
    def test_missing_module_is_rejected(self):
        self.assertEqual(self.post({"method": "echo"}).status_code, 400)

    def test_missing_method_is_rejected(self):
        self.assertEqual(self.post({"module": "ALMotion"}).status_code, 400)

    def test_empty_body_is_rejected(self):
        response = self.client.post("/api/call", data="", content_type="application/json")
        self.assertEqual(response.status_code, 400)

    def test_call_returns_result(self):
        response = self.post({"module": "ALMotion", "method": "echo", "args": [1, 2]})
        self.assertEqual(response.status_code, 200)
        import json
        self.assertEqual(json.loads(response.data)["result"], [1, 2])

    def test_args_default_to_empty(self):
        response = self.post({"module": "ALMotion", "method": "echo"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.proxy.calls[-1], ("echo", ()))

    def test_raising_method_returns_500_with_message(self):
        response = self.post({"module": "ALMotion", "method": "boom"})
        self.assertEqual(response.status_code, 500)
        import json
        self.assertIn("naoqi exploded", json.loads(response.data)["error"])

    def test_post_dispatches_through_the_post_object(self):
        response = self.post({"module": "ALMotion", "method": "post", "args": ["echo", 7]})
        self.assertEqual(response.status_code, 200)
        # Must go via proxy.post.echo, not proxy.echo, or the call is synchronous.
        self.assertEqual(self.proxy.calls[-1], ("post.echo", (7,)))
        import json
        self.assertEqual(json.loads(response.data)["result"], 99)

    def test_post_without_a_target_is_an_error(self):
        response = self.post({"module": "ALMotion", "method": "post", "args": []})
        self.assertEqual(response.status_code, 500)


if __name__ == "__main__":
    unittest.main()
