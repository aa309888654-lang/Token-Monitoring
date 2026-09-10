# -*- coding: utf-8 -*-
"""界面 + 统计管线冒烟测试（使用临时目录，不改动系统代理设置）。"""
import os
import queue
import shutil
import sys
import tempfile
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import tokenmon as tm   # noqa: E402

TMP = tempfile.mkdtemp(prefix="tokenmon-ui-")
tm.APP_DIR = TMP
tm.STATE_FILE = os.path.join(TMP, "state.json")
tm.LOG_FILE = os.path.join(TMP, "records.jsonl")
tm.CONFIG_FILE = os.path.join(TMP, "config.json")
tm.CA_DIR = os.path.join(TMP, "ca")
tm.CA_CERT_FILE = os.path.join(tm.CA_DIR, "ca.pem")
tm.CA_KEY_FILE = os.path.join(tm.CA_DIR, "ca.key")
tm.LEAF_DIR = os.path.join(tm.CA_DIR, "leaf")
tm.PROXY_BACKUP_FILE = os.path.join(TMP, "backup.json")
tm.RESTORE_BAT = os.path.join(TMP, "restore.bat")

problems = []

# ------------------------------------------------ 1. 模型 / 厂商识别
expect = {
    "claude-sonnet-4-5": "Anthropic", "gpt-4o": "OpenAI", "o3-mini": "OpenAI",
    "gpt-5.2-codex": "OpenAI", "gemini-2.5-pro": "Google",
    "deepseek-chat": "DeepSeek", "deepseek-r1": "DeepSeek",
    "glm-4.7": "智谱GLM", "GLM-5.3-Flash": "智谱GLM",
    "qwen3-max": "阿里通义", "kimi-k2-0905": "月之暗面",
    "doubao-seed-1.6": "字节豆包", "grok-4": "xAI",
    "mistral-large-latest": "Mistral", "hunyuan-turbos": "腾讯混元",
    "ernie-4.5": "百度文心", "step-3.7-flash": "阶跃星辰",
    "MiniMax-M2": "MiniMax", "mimo-7b": "小米",
    "llama-3.3-70b": "Meta", "command-r-plus": "Cohere",
}
for model, want in expect.items():
    got = tm.guess_provider(model)
    if got != want:
        problems.append(f"厂商识别 {model}: 期望 {want} 得到 {got}")
print(f"[1] 厂商识别：{len(expect)} 个模型检查完成")

# ------------------------------------------------ 2. usage 提取（各家格式）
cases = [
    ({"usage": {"prompt_tokens": 100, "completion_tokens": 20,
                "prompt_tokens_details": {"cached_tokens": 60}}},
     {"inp": 40, "out": 20, "cache_r": 60, "cache_w": 0}, "OpenAI"),
    ({"usage": {"input_tokens": 100, "output_tokens": 20,
                "cache_read_input_tokens": 60,
                "cache_creation_input_tokens": 5}},
     {"inp": 100, "out": 20, "cache_r": 60, "cache_w": 5}, "Anthropic"),
    ({"usageMetadata": {"promptTokenCount": 100, "candidatesTokenCount": 20,
                        "cachedContentTokenCount": 60, "thoughtsTokenCount": 7}},
     {"inp": 40, "out": 27, "cache_r": 60, "cache_w": 0}, "Gemini"),
    ({"data": {"tokenUsage": {"inputTokens": 50, "outputTokens": 9}}},
     {"inp": 50, "out": 9, "cache_r": 0, "cache_w": 0}, "中转站嵌套"),
    ({"choices": [{"message": {"content": "x"}}]},
     {"inp": 0, "out": 0, "cache_r": 0, "cache_w": 0}, "无 usage"),
]
for node, want, name in cases:
    u = tm.extract_usage(node)
    got = tm.normalize_usage(u)
    if got != want:
        problems.append(f"usage 提取 {name}: 期望 {want} 得到 {got}")
print(f"[2] usage 提取：{len(cases)} 种格式检查完成")

# ------------------------------------------------ 3. 统计 / 表格管线
stats, meter = tm.Stats(), tm.SpeedMeter()
q = queue.Queue()
watcher = tm.Watcher(stats, meter, q)

ca = tm.CertAuthority(ca_dir=tm.CA_DIR)
assert ca.ensure(), ca.error

app = tm.App(stats, meter, q, watcher, ca=ca)
app._proxy_port = 18899

# 造几条直采记录，走真实 _emit 管线
for i, (model, inp, out, cr, cw, dur) in enumerate([
        ("claude-sonnet-4-5", 1200, 350, 1000, 0, 4.0),
        ("gpt-4o", 800, 220, 300, 0, 3.0),
        ("deepseek-chat", 400, 900, 0, 0, 6.0)]):
    watcher._emit({"ts": time.time() - i, "source": "proxy",
                   "provider": tm.guess_provider(model), "model": model,
                   "inp": inp, "out": out, "cache_r": cr, "cache_w": cw,
                   "dur": dur, "key": f"ui-test-{i}", "session": None})
meter.tick(stats)
rows = app._rows()
print(f"[3] 表格行数={len(rows)} 累计={stats.totals()}")
if len(rows) != 3:
    problems.append(f"表格应有 3 行，实际 {len(rows)}")
names = {r[0][0] for r in rows}
if "claude-sonnet-4-5" not in names or "gpt-4o" not in names:
    problems.append(f"表格缺少模型: {names}")
vendors = {r[0][1] for r in rows}
if "Anthropic" not in vendors:
    problems.append(f"厂商列未显示: {vendors}")

# ------------------------------------------------ 4. 代理启停 + 面板
ok, msg = app.start_proxy()
print(f"[4] 启动代理: ok={ok} msg={msg}")
if not ok:
    problems.append(f"代理启动失败: {msg}")
else:
    st = app.proxy.status()
    if not st["running"]:
        problems.append("代理未处于运行状态")
    app._proxy_center()                      # 打开直采控制台
    app._proxy_refresh()
    for _ in range(12):
        app.update()
        time.sleep(0.03)
    if not app._p_lbls["svc"].cget("text").startswith("●"):
        problems.append(f"面板状态未显示运行中: {app._p_lbls['svc'].cget('text')}")

# 面板交互（只读/不落系统设置）
app._toggle_mitm_all()
app._p_hosts.set("my-relay.example.com, api.test.cn")
app._apply_extra_hosts()
if app.proxy.extra_hosts != ["my-relay.example.com", "api.test.cn"]:
    problems.append(f"额外域名未生效: {app.proxy.extra_hosts}")

# ------------------------------------------------ 5. 状态栏 / 主循环 tick
app._update_status()
for _ in range(20):
    app.update()
    time.sleep(0.02)
if not app._active_snapshot() == []:
    problems.append("空闲时应无生成中请求")

app.stop_proxy()
if app.proxy is not None and app.proxy.running:
    problems.append("代理未停止")
print(f"[5] 面板与状态栏渲染完成；文件统计={app._file_stats}")

# 确认没有污染系统代理（本测试不应写注册表）
if app._applied_sys is not None or app._applied_env is not None:
    problems.append("测试过程中意外改动了系统代理设置")

app._on_close()
shutil.rmtree(TMP, ignore_errors=True)
print("\n[结果] " + ("全部通过 ✔" if not problems else
                    "发现问题：\n  - " + "\n  - ".join(problems)))
sys.exit(1 if problems else 0)
