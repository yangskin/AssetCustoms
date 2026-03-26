"""Substance Painter Remote Scripting 客户端。

通过 HTTP POST 将 Python 脚本发送到 SP Remote Scripting 端口执行。
迁移自 Reference/lib_remote.py，适配 AssetCustoms 插件架构。

通信协议：
  POST http://localhost:60041/run.json
  Body: {"python": "<base64 encoded script>"}
"""
import base64
import json
import http.client
from typing import Optional


# SP Remote Scripting 默认配置
DEFAULT_HOST = "localhost"
DEFAULT_PORT = 60041
PAINTER_ROUTE = "/run.json"
HEADERS = {"Content-type": "application/json", "Accept": "application/json"}
CONNECTION_TIMEOUT = 10  # 连接检测超时（秒）
EXEC_TIMEOUT = 3600  # 脚本执行超时（秒）
FIRE_AND_FORGET_TIMEOUT = 30  # 异步发送超时（秒）— 只等 SP 接收确认


class PainterError(Exception):
    """Substance Painter 通信基础异常。"""


class ConnectionError(PainterError):
    """无法连接到 Substance Painter。"""


class ExecuteScriptError(PainterError):
    """SP 端脚本执行报错。"""

    def __init__(self, error_data: str):
        super().__init__(f"SP script execution error: {error_data}")
        self.error_data = error_data


def encode_script(script: str) -> str:
    """将 Python 脚本 base64 编码为 SP Remote Scripting 接受的字符串。

    >>> encode_script("print('hello')")
    'cHJpbnQoJ2hlbGxvJyk='
    """
    return base64.b64encode(script.encode("utf-8")).decode("utf-8")


def build_request_body(script: str) -> bytes:
    """构建 HTTP POST 请求体。

    Args:
        script: 要执行的 Python 脚本源码。

    Returns:
        JSON 编码的请求体字节串。

    >>> body = build_request_body("print(1)")
    >>> data = json.loads(body)
    >>> 'python' in data
    True
    """
    encoded = encode_script(script)
    payload = json.dumps({"python": encoded})
    return payload.encode("utf-8")


def parse_response(data: bytes) -> str:
    """解析 SP 返回的响应数据。

    Args:
        data: HTTP 响应体原始字节。

    Returns:
        解码后的响应文本。

    Raises:
        ExecuteScriptError: SP 端返回错误。
    """
    try:
        text = data.decode("utf-8").rstrip()
    except UnicodeDecodeError:
        return ""

    # SP 可能返回 JSON 错误对象
    try:
        obj = json.loads(text)
        if isinstance(obj, dict) and "error" in obj:
            raise ExecuteScriptError(obj["error"])
    except json.JSONDecodeError:
        pass

    return text


class RemotePainter:
    """Substance Painter Remote Scripting HTTP 客户端。

    Usage:
        painter = RemotePainter()
        if painter.is_connected():
            result = painter.execute("import substance_painter; print('ok')")
    """

    def __init__(self, host: str = DEFAULT_HOST, port: int = DEFAULT_PORT):
        self._host = host
        self._port = port

    def is_connected(self) -> bool:
        """检测 SP Remote Scripting 是否可达。"""
        try:
            conn = http.client.HTTPConnection(
                self._host, self._port, timeout=CONNECTION_TIMEOUT
            )
            conn.connect()
            conn.close()
            return True
        except (OSError, http.client.HTTPException):
            return False

    def execute(self, script: str) -> str:
        """发送 Python 脚本到 SP 执行。

        Args:
            script: Python 脚本源码。

        Returns:
            SP 返回的文本响应。

        Raises:
            ConnectionError: SP 不可达。
            ExecuteScriptError: SP 端脚本执行出错。
        """
        body = build_request_body(script)
        conn = http.client.HTTPConnection(
            self._host, self._port, timeout=EXEC_TIMEOUT
        )
        try:
            conn.request("POST", PAINTER_ROUTE, body, HEADERS)
            response = conn.getresponse()
            data = response.read()
        except (OSError, http.client.HTTPException) as exc:
            raise ConnectionError(
                f"无法连接到 Substance Painter ({self._host}:{self._port})。"
                f"请确认 SP 已启动并使用 --enable-remote-scripting 参数。"
            ) from exc
        finally:
            conn.close()

        return parse_response(data)

    def is_ready(self) -> bool:
        """验证 SP Remote Scripting 可执行脚本（非仅 TCP 通）。

        发送一个简单表达式确认 SP Python 环境已就绪。
        比 is_connected() 更可靠：SP 启动后 TCP 端口先于脚本引擎就绪。

        注意：SP Remote Scripting Python 模式返回的是表达式求值结果，
        不是 stdout。因此使用字符串字面量而非 print()。
        """
        body = build_request_body("'__sp_ready__'")
        conn = http.client.HTTPConnection(
            self._host, self._port, timeout=CONNECTION_TIMEOUT
        )
        try:
            conn.request("POST", PAINTER_ROUTE, body, HEADERS)
            response = conn.getresponse()
            data = response.read()
            result = parse_response(data)
            return "__sp_ready__" in result
        except (OSError, http.client.HTTPException, PainterError):
            return False
        finally:
            conn.close()

    def execute_fire_and_forget(self, script: str) -> str:
        """发送脚本到 SP 执行，使用短超时。

        SP Remote Scripting 会在脚本执行完后才返回 HTTP 响应。
        对于耗时操作（创建项目、导入资源），使用短超时避免阻塞调用方。
        SP 端脚本会继续在后台执行。

        Args:
            script: Python 脚本（应自带 try/except 以免 SP 端崩溃）。

        Returns:
            SP 返回的文本响应（如果在超时内完成）。

        Note:
            超时不意味着失败 — SP 仍在执行脚本。
        """
        body = build_request_body(script)
        conn = http.client.HTTPConnection(
            self._host, self._port, timeout=FIRE_AND_FORGET_TIMEOUT
        )
        try:
            conn.request("POST", PAINTER_ROUTE, body, HEADERS)
            response = conn.getresponse()
            data = response.read()
            return parse_response(data)
        except (OSError, http.client.HTTPException):
            # 超时或断开 — SP 侧脚本仍在运行，不视为错误
            return ""
        finally:
            conn.close()
