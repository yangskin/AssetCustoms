"""sp_remote.py 单元测试。

测试范围（🤖 自动化）：
- 1.1 encode_script() base64 编码
- 1.2 RemotePainter.execute() HTTP POST 封装（mock）
- 1.3 连接检测 + 错误处理
"""
import base64
import json
import http.client
from unittest.mock import MagicMock, patch

import pytest

from unreal_integration.sp_remote import (
    encode_script,
    build_request_body,
    parse_response,
    RemotePainter,
    ConnectionError,
    ExecuteScriptError,
    DEFAULT_PORT,
    PAINTER_ROUTE,
)


# ---------------------------------------------------------------------------
# 1.1 encode_script
# ---------------------------------------------------------------------------
class TestEncodeScript:
    def test_basic_string(self):
        result = encode_script("print('hello')")
        decoded = base64.b64decode(result).decode("utf-8")
        assert decoded == "print('hello')"

    def test_empty_string(self):
        result = encode_script("")
        decoded = base64.b64decode(result).decode("utf-8")
        assert decoded == ""

    def test_unicode(self):
        script = "print('你好世界')"
        result = encode_script(script)
        decoded = base64.b64decode(result).decode("utf-8")
        assert decoded == script

    def test_multiline(self):
        script = "import os\nprint(os.getcwd())"
        result = encode_script(script)
        decoded = base64.b64decode(result).decode("utf-8")
        assert decoded == script


# ---------------------------------------------------------------------------
# build_request_body
# ---------------------------------------------------------------------------
class TestBuildRequestBody:
    def test_returns_bytes(self):
        body = build_request_body("1+1")
        assert isinstance(body, bytes)

    def test_json_structure(self):
        body = build_request_body("print(42)")
        data = json.loads(body)
        assert "python" in data
        decoded = base64.b64decode(data["python"]).decode("utf-8")
        assert decoded == "print(42)"

    def test_roundtrip(self):
        script = "import substance_painter\nprint('ok')"
        body = build_request_body(script)
        data = json.loads(body)
        decoded = base64.b64decode(data["python"]).decode("utf-8")
        assert decoded == script


# ---------------------------------------------------------------------------
# parse_response
# ---------------------------------------------------------------------------
class TestParseResponse:
    def test_plain_text(self):
        result = parse_response(b"hello world")
        assert result == "hello world"

    def test_strips_trailing_whitespace(self):
        result = parse_response(b"ok  \n\n")
        assert result == "ok"

    def test_empty_response(self):
        result = parse_response(b"")
        assert result == ""

    def test_error_json_raises(self):
        error_data = json.dumps({"error": "NameError: name 'x' is not defined"}).encode()
        with pytest.raises(ExecuteScriptError, match="NameError"):
            parse_response(error_data)

    def test_non_error_json_passthrough(self):
        data = json.dumps({"result": "ok"}).encode()
        result = parse_response(data)
        assert '"result"' in result

    def test_binary_decode_failure(self):
        result = parse_response(b"\xff\xfe")
        assert result == ""


# ---------------------------------------------------------------------------
# 1.2 RemotePainter.execute (mock HTTP)
# ---------------------------------------------------------------------------
class TestRemotePainterExecute:
    @patch("unreal_integration.sp_remote.http.client.HTTPConnection")
    def test_execute_success(self, mock_conn_cls):
        mock_conn = MagicMock()
        mock_response = MagicMock()
        mock_response.read.return_value = b"42"
        mock_conn.getresponse.return_value = mock_response
        mock_conn_cls.return_value = mock_conn

        painter = RemotePainter()
        result = painter.execute("print(42)")

        assert result == "42"
        mock_conn.request.assert_called_once()
        args = mock_conn.request.call_args
        assert args[0][0] == "POST"
        assert args[0][1] == PAINTER_ROUTE

    @patch("unreal_integration.sp_remote.http.client.HTTPConnection")
    def test_execute_sends_correct_body(self, mock_conn_cls):
        mock_conn = MagicMock()
        mock_response = MagicMock()
        mock_response.read.return_value = b""
        mock_conn.getresponse.return_value = mock_response
        mock_conn_cls.return_value = mock_conn

        painter = RemotePainter()
        painter.execute("x = 1")

        body = mock_conn.request.call_args[0][2]
        data = json.loads(body)
        decoded = base64.b64decode(data["python"]).decode("utf-8")
        assert decoded == "x = 1"

    @patch("unreal_integration.sp_remote.http.client.HTTPConnection")
    def test_execute_sp_error_raises(self, mock_conn_cls):
        mock_conn = MagicMock()
        mock_response = MagicMock()
        error_body = json.dumps({"error": "SyntaxError"}).encode()
        mock_response.read.return_value = error_body
        mock_conn.getresponse.return_value = mock_response
        mock_conn_cls.return_value = mock_conn

        painter = RemotePainter()
        with pytest.raises(ExecuteScriptError, match="SyntaxError"):
            painter.execute("invalid python")


# ---------------------------------------------------------------------------
# 1.3 连接检测 + 错误处理
# ---------------------------------------------------------------------------
class TestRemotePainterConnection:
    @patch("unreal_integration.sp_remote.http.client.HTTPConnection")
    def test_is_connected_true(self, mock_conn_cls):
        mock_conn = MagicMock()
        mock_conn_cls.return_value = mock_conn

        painter = RemotePainter()
        assert painter.is_connected() is True
        mock_conn.connect.assert_called_once()

    @patch("unreal_integration.sp_remote.http.client.HTTPConnection")
    def test_is_connected_refused(self, mock_conn_cls):
        mock_conn = MagicMock()
        mock_conn.connect.side_effect = OSError("Connection refused")
        mock_conn_cls.return_value = mock_conn

        painter = RemotePainter()
        assert painter.is_connected() is False

    @patch("unreal_integration.sp_remote.http.client.HTTPConnection")
    def test_is_connected_timeout(self, mock_conn_cls):
        mock_conn = MagicMock()
        mock_conn.connect.side_effect = OSError("timed out")
        mock_conn_cls.return_value = mock_conn

        painter = RemotePainter()
        assert painter.is_connected() is False

    @patch("unreal_integration.sp_remote.http.client.HTTPConnection")
    def test_execute_connection_refused_raises(self, mock_conn_cls):
        mock_conn = MagicMock()
        mock_conn.request.side_effect = OSError("Connection refused")
        mock_conn_cls.return_value = mock_conn

        painter = RemotePainter()
        with pytest.raises(ConnectionError, match="Substance Painter"):
            painter.execute("print(1)")

    def test_custom_host_port(self):
        painter = RemotePainter(host="192.168.1.100", port=12345)
        assert painter._host == "192.168.1.100"
        assert painter._port == 12345


# ---------------------------------------------------------------------------
# 1.4 is_ready — SP 插件就绪检测
# ---------------------------------------------------------------------------
class TestRemotePainterIsReady:
    @patch("unreal_integration.sp_remote.http.client.HTTPConnection")
    def test_ready_when_script_executes(self, mock_conn_cls):
        mock_conn = MagicMock()
        mock_response = MagicMock()
        mock_response.read.return_value = b"__sp_ready__"
        mock_conn.getresponse.return_value = mock_response
        mock_conn_cls.return_value = mock_conn

        painter = RemotePainter()
        assert painter.is_ready() is True

    @patch("unreal_integration.sp_remote.http.client.HTTPConnection")
    def test_not_ready_when_connection_fails(self, mock_conn_cls):
        mock_conn = MagicMock()
        mock_conn.request.side_effect = OSError("Connection refused")
        mock_conn_cls.return_value = mock_conn

        painter = RemotePainter()
        assert painter.is_ready() is False

    @patch("unreal_integration.sp_remote.http.client.HTTPConnection")
    def test_not_ready_when_sp_returns_error(self, mock_conn_cls):
        mock_conn = MagicMock()
        mock_response = MagicMock()
        error_body = json.dumps({"error": "not ready"}).encode()
        mock_response.read.return_value = error_body
        mock_conn.getresponse.return_value = mock_response
        mock_conn_cls.return_value = mock_conn

        painter = RemotePainter()
        assert painter.is_ready() is False

    @patch("unreal_integration.sp_remote.http.client.HTTPConnection")
    def test_uses_connection_timeout(self, mock_conn_cls):
        """is_ready 使用 CONNECTION_TIMEOUT 而非 EXEC_TIMEOUT，避免长阻塞。"""
        from unreal_integration.sp_remote import CONNECTION_TIMEOUT
        mock_conn = MagicMock()
        mock_response = MagicMock()
        mock_response.read.return_value = b"__sp_ready__"
        mock_conn.getresponse.return_value = mock_response
        mock_conn_cls.return_value = mock_conn

        painter = RemotePainter()
        painter.is_ready()

        call_args = mock_conn_cls.call_args
        assert call_args[1].get("timeout") == CONNECTION_TIMEOUT


# ---------------------------------------------------------------------------
# 1.5 execute_fire_and_forget — 非阻塞发送
# ---------------------------------------------------------------------------
class TestExecuteFireAndForget:
    @patch("unreal_integration.sp_remote.http.client.HTTPConnection")
    def test_returns_response_on_success(self, mock_conn_cls):
        mock_conn = MagicMock()
        mock_response = MagicMock()
        mock_response.read.return_value = b"__sp_script_dispatched__"
        mock_conn.getresponse.return_value = mock_response
        mock_conn_cls.return_value = mock_conn

        painter = RemotePainter()
        result = painter.execute_fire_and_forget("print('hi')")
        assert "__sp_script_dispatched__" in result

    @patch("unreal_integration.sp_remote.http.client.HTTPConnection")
    def test_returns_empty_on_timeout(self, mock_conn_cls):
        mock_conn = MagicMock()
        mock_conn.request.side_effect = OSError("timed out")
        mock_conn_cls.return_value = mock_conn

        painter = RemotePainter()
        result = painter.execute_fire_and_forget("long_running()")
        assert result == ""

    @patch("unreal_integration.sp_remote.http.client.HTTPConnection")
    def test_uses_short_timeout(self, mock_conn_cls):
        from unreal_integration.sp_remote import FIRE_AND_FORGET_TIMEOUT
        mock_conn = MagicMock()
        mock_response = MagicMock()
        mock_response.read.return_value = b""
        mock_conn.getresponse.return_value = mock_response
        mock_conn_cls.return_value = mock_conn

        painter = RemotePainter()
        painter.execute_fire_and_forget("x = 1")

        # 验证使用短超时
        call_kwargs = mock_conn_cls.call_args
        assert call_kwargs[1].get("timeout", call_kwargs[0][2] if len(call_kwargs[0]) > 2 else None) == FIRE_AND_FORGET_TIMEOUT
