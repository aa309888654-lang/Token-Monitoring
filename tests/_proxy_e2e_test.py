# -*- coding: utf-8 -*-
"""网络直采端到端测试：本地假 AI 服务 + 真证书 + 真代理链路。"""
import http.server
import json
import os
import shutil
import socket
import ssl
import sys
import tempfile
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import tokenmon as tm   # noqa: E402

TMP = tempfile.mkdtemp(prefix="tokenmon-test-")
tm.CA_DIR = os.path.join(TMP, "ca")
tm.CA_CERT_FILE = os.path.join(tm.CA_DIR, "ca.pem")
tm.CA_KEY_FILE = os.path.join(tm.CA_DIR, "ca.key")
tm.LEAF_DIR = os.path.join(tm.CA_DIR, "leaf")
tm.PROXY_BACKUP_FILE = os.path.join(TMP, "backup.json")
os.environ["SSL_CERT_FILE"] = tm.CA_CERT_FILE     # 让上游校验信任测试 CA

RECORDS = []


def emit(rec):
    RECORDS.append(rec)


# ---------------------------------------------------------------- 假 AI 服务

class Handler(http.server.BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *a):
        pass

    def _read(self):
        n = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(n) if n else b""
        try:
            return json.loads(raw.decode("utf-8"))
        except ValueError:
            return {}

    def _sse(self, chunks):
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "close")
        self.end_headers()
        for c in chunks:
            self.wfile.write(("data: " + json.dumps(c, ensure_ascii=False) +
                              "\n\n").encode("utf-8"))
            self.wfile.flush()
            time.sleep(0.04)
        self.wfile.write(b"data: [DONE]\n\n")
        self.wfile.flush()

    def _json(self, obj):
        data = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _chunked_sse(self, chunks):
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Transfer-Encoding", "chunked")
        self.send_header("Connection", "close")
        self.end_headers()
        for c in chunks:
            payload = ("data: " + json.dumps(c, ensure_ascii=False) +
                       "\n\n").encode("utf-8")
            self.wfile.write(b"%x\r\n" % len(payload) + payload + b"\r\n")
            self.wfile.flush()
            time.sleep(0.03)
        self.wfile.write(b"0\r\n\r\n")
        self.wfile.flush()

    def do_POST(self):
        req = self._read()
        path = self.path.split("?")[0]

        if req.get("_chunked_no_usage"):            # 无 usage + chunked，走估算
            self._chunked_sse([
                {"id": "c9", "model": "deepseek-chat",
                 "choices": [{"index": 0,
                              "delta": {"content": "这是一段没有 usage 的中文回复，"
                                                   "用来验证字符估算是否合理。"}}]},
            ])
            return

        if path.endswith("/messages"):                       # Anthropic 流式
            self._sse([
                {"type": "message_start", "message": {
                    "id": "msg_1", "model": "claude-sonnet-4-5-20250929",
                    "usage": {"input_tokens": 1000, "output_tokens": 1,
                              "cache_read_input_tokens": 900,
                              "cache_creation_input_tokens": 50}}},
                {"type": "content_block_delta",
                 "delta": {"type": "text_delta", "text": "你好世界"}},
                {"type": "message_delta", "delta": {"stop_reason": "end_turn"},
                 "usage": {"output_tokens": 200}},
                {"type": "message_stop"},
            ])
            return

        if path.endswith("/chat/completions") and req.get("stream"):
            self._sse([
                {"id": "c1", "object": "chat.completion.chunk",
                 "model": "gpt-4o-2024-08-06",
                 "choices": [{"index": 0, "delta": {"content": "Hello"}}]},
                {"id": "c1", "object": "chat.completion.chunk",
                 "model": "gpt-4o-2024-08-06",
                 "choices": [{"index": 0,
                              "delta": {"content": " world, 这是一个测试"}}]},
                {"id": "c1", "object": "chat.completion.chunk",
                 "model": "gpt-4o-2024-08-06", "choices": [],
                 "usage": {"prompt_tokens": 30, "completion_tokens": 12,
                           "total_tokens": 42,
                           "prompt_tokens_details": {"cached_tokens": 10}}},
            ])
            return

        if path.endswith("/chat/completions"):               # OpenAI 非流式
            self._json({
                "id": "c2", "model": "gpt-4o-2024-08-06",
                "choices": [{"message": {"role": "assistant",
                                         "content": "hi " * 60}}],
                "usage": {"prompt_tokens": 100, "completion_tokens": 80,
                          "total_tokens": 180,
                          "prompt_tokens_details": {"cached_tokens": 40}},
            })
            return

        if "generativelanguage" in (self.headers.get("Host") or "") or \
                path.endswith(":generateContent"):
            self._json({
                "candidates": [{"content": {"parts": [{"text": "gemini 回答"}]}}],
                "usageMetadata": {"promptTokenCount": 200,
                                  "candidatesTokenCount": 50,
                                  "cachedContentTokenCount": 120},
                "modelVersion": "gemini-2.5-pro",
            })
            return

        self.send_response(404)
        self.send_header("Content-Length", "0")
        self.end_headers()


def start_https(cert_p, key_p):
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.load_cert_chain(cert_p, key_p)
    ctx.set_alpn_protocols(["http/1.1"])
    srv.socket = ctx.wrap_socket(srv.socket, server_side=True)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, srv.server_address[1]


# ---------------------------------------------------------------- 客户端

def run_case(proxy_port, up_port, path, payload, host="localhost"):
    c = socket.create_connection(("127.0.0.1", proxy_port), timeout=15)
    c.sendall(f"CONNECT {host}:{up_port} HTTP/1.1\r\n"
              f"Host: {host}:{up_port}\r\n\r\n".encode())
    buf = b""
    while b"\r\n\r\n" not in buf:
        d = c.recv(4096)
        if not d:
            raise RuntimeError("代理未响应 CONNECT")
        buf += d
    if b" 200 " not in buf.split(b"\r\n")[0]:
        raise RuntimeError(f"CONNECT 失败: {buf[:80]}")
    tls = ssl.create_default_context(cafile=tm.CA_CERT_FILE)
    tc = tls.wrap_socket(c, server_hostname=host)
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    tc.sendall(f"POST {path} HTTP/1.1\r\nHost: {host}:{up_port}\r\n"
               f"Content-Type: application/json\r\n"
               f"Content-Length: {len(body)}\r\nConnection: close\r\n\r\n"
               .encode() + body)
    data = b""
    while True:
        try:
            d = tc.recv(65536)
        except (OSError, ssl.SSLError):
            break
        if not d:
            break
        data += d
    tc.close()
    return data


def main():
    ca = tm.CertAuthority(ca_dir=tm.CA_DIR)
    if not ca.ensure():
        raise SystemExit(f"CA 生成失败: {ca.error}")
    pair = ca.leaf_for("localhost")
    if not pair:
        raise SystemExit(f"签发站点证书失败: {ca.error}")
    srv, up_port = start_https(*pair)

    stats, meter = tm.Stats(), tm.SpeedMeter()
    q = __import__("queue").Queue()

    def emit(rec):
        RECORDS.append(rec)

    proxy = tm.MitmProxy(emit, q, ca, meter=meter, port=0, mitm_all=True)
    proxy.port = _free_port()
    proxy.addr = f"127.0.0.1:{proxy.port}"
    proxy.start()
    for _ in range(60):
        if proxy.running or proxy.error:
            break
        time.sleep(0.05)
    assert proxy.running, proxy.error
    print(f"[测试] 代理已启动 {proxy.addr}；上游 127.0.0.1:{up_port}")

    cases = [
        ("OpenAI 流式", "/v1/chat/completions",
         {"model": "gpt-4o", "stream": True,
          "messages": [{"role": "user", "content": "你好"}]}),
        ("OpenAI 非流式", "/v1/chat/completions",
         {"model": "gpt-4o", "messages": [{"role": "user", "content": "hi"}]}),
        ("Claude 流式", "/v1/messages",
         {"model": "claude-sonnet-4-5", "stream": True, "max_tokens": 100,
          "messages": [{"role": "user", "content": "hello"}]}),
        ("Gemini", "/v1beta/models/gemini-2.5-pro:generateContent",
         {"contents": [{"parts": [{"text": "hi"}]}]}),
        ("chunked 无 usage（估算）", "/v1/chat/completions",
         {"model": "deepseek-chat", "stream": True,
          "_chunked_no_usage": True,
          "messages": [{"role": "user", "content": "讲个故事"}]}),
    ]
    for name, path, payload in cases:
        before = len(RECORDS)
        resp = run_case(proxy.port, up_port, path, payload)
        got = resp.split(b"\r\n\r\n", 1)[-1]
        ok_http = resp.startswith(b"HTTP/1.1 200")
        time.sleep(0.35)
        new = RECORDS[before:]
        print(f"\n=== {name} ===  HTTP200={ok_http} 响应字节={len(got)}")
        if not new:
            print("  !! 没有产出记录")
            continue
        for r in new:
            print(f"  模型={r['model']:<22} 厂商={r['provider']:<10} "
                  f"输入={r['inp']:<6} 输出={r['out']:<6} "
                  f"缓存读={r['cache_r']:<6} 缓存写={r['cache_w']:<5} "
                  f"耗时={r['dur']:.2f}s")

    print("\n--- 统计汇总 ---")
    for (src, prov, model), a in sorted(stats.snapshot_cumulative().items()):
        print(f"  {model:<24} {prov:<10} 请求{a['requests']} "
              f"输入{ a['inp']} 输出{a['out']} 缓存读{a['cache_r']} "
              f"写{a['cache_w']} 均速"
              f"{a['out'] / a['gen_s'] if a['gen_s'] else 0:.1f} tok/s  [{src}]")
    print("  totals:", stats.totals())

    # ---- 断言
    exp = {
        "gpt-4o": (2, 20, 60, 12, 80),      # 请求数 / 首次输入 / 二次输入 / 首次输出 / 二次输出
    }
    recs = {r["key"]: r for r in RECORDS}
    problems = []
    gpt_stream = [r for r in RECORDS if r["model"] == "gpt-4o" and r["out"] == 12]
    gpt_json = [r for r in RECORDS if r["model"] == "gpt-4o" and r["out"] == 80]
    claude = [r for r in RECORDS if r["model"] == "claude-sonnet-4-5"]
    gemini = [r for r in RECORDS if r["model"] == "gemini-2.5-pro"]
    if not gpt_stream:
        problems.append("GPT 流式记录缺失或输出 token 不是 12")
    elif gpt_stream[0]["inp"] != 20 or gpt_stream[0]["cache_r"] != 10:
        problems.append(f"GPT 流式输入/缓存拆分错误: {gpt_stream[0]}")
    if not gpt_json:
        problems.append("GPT 非流式记录缺失或输出 token 不是 80")
    elif gpt_json[0]["inp"] != 60 or gpt_json[0]["cache_r"] != 40:
        problems.append(f"GPT 非流式输入/缓存拆分错误: {gpt_json[0]}")
    if not claude:
        problems.append("Claude 记录缺失")
    elif (claude[0]["inp"], claude[0]["out"], claude[0]["cache_r"],
          claude[0]["cache_w"]) != (1000, 200, 900, 50):
        problems.append(f"Claude 用量解析错误: {claude[0]}")
    if not gemini:
        problems.append("Gemini 记录缺失")
    elif (gemini[0]["inp"], gemini[0]["out"], gemini[0]["cache_r"]) != \
            (80, 50, 120):
        problems.append(f"Gemini 用量解析错误: {gemini[0]}")
    elif gemini[0]["model"] != "gemini-2.5-pro":
        problems.append(f"Gemini 模型名识别错误: {gemini[0]['model']}")
    ds = [r for r in RECORDS if r["model"] == "deepseek-chat"]
    if not ds:
        problems.append("chunked/无 usage 场景没有产出记录")
    elif ds[0]["out"] < 10:
        problems.append(f"字符估算输出偏小: {ds[0]}")

    # ---- 直通（非 AI 域名不解密、不统计）验证
    proxy.mitm_all = False
    proxy.extra_hosts = []
    before = len(RECORDS)
    resp = run_case(proxy.port, up_port, "/v1/chat/completions",
                    {"model": "gpt-4o",
                     "messages": [{"role": "user", "content": "hi"}]})
    time.sleep(0.2)
    print(f"\n=== 直通（非 AI 域名）=== HTTP200="
          f"{resp.startswith(b'HTTP/1.1 200')} 直通计数={proxy.passthru} "
          f"新增记录={len(RECORDS) - before}")
    if not resp.startswith(b"HTTP/1.1 200"):
        problems.append("直通模式下请求失败")
    if len(RECORDS) != before:
        problems.append("直通模式下不应产生统计记录")

    print("\n[断言] " + ("全部通过 ✔" if not problems else
                        "发现问题：" + " | ".join(problems)))
    proxy.stop()
    srv.shutdown()
    shutil.rmtree(TMP, ignore_errors=True)
    return 1 if problems else 0


def _free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


if __name__ == "__main__":
    sys.exit(main())
