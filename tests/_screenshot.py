# -*- coding: utf-8 -*-
"""截取主窗口与直采控制台。

    python tests\\_screenshot.py          # 合成数据（外观回归用）
    python tests\\_screenshot.py --real   # 扫描本机真实日志（看真实数字）

数据全部落在临时目录，不会碰真实统计。
"""
import os
import queue
import sys
import tempfile
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import tokenmon as tm   # noqa: E402

try:
    import ctypes
    ctypes.windll.shcore.SetProcessDpiAwareness(1)
except Exception:
    pass
from PIL import ImageGrab   # noqa: E402

REAL = "--real" in sys.argv
OUT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

tmp = tempfile.mkdtemp(prefix="tokenmon-shot-")
tm.APP_DIR = tmp
tm.CONFIG_FILE = os.path.join(tmp, "config.json")
tm.STATE_FILE = os.path.join(tmp, "state.json")
tm.LOG_FILE = os.path.join(tmp, "records.jsonl")
tm.CA_DIR = os.path.join(tmp, "ca")
tm.CA_CERT_FILE = os.path.join(tm.CA_DIR, "ca.pem")
tm.CA_KEY_FILE = os.path.join(tm.CA_DIR, "ca.key")
tm.LEAF_DIR = os.path.join(tm.CA_DIR, "leaf")

stats, meter, q = tm.Stats(), tm.SpeedMeter(), queue.Queue()
watcher = tm.Watcher(stats, meter, q)

if REAL:
    print("扫描真实日志…")
    watcher.poll()
else:
    for i, (model, inp, out, cr, dur) in enumerate([
            ("claude-sonnet-4-5", 18240, 3520, 15000, 12.4),
            ("gpt-5.2-codex", 9120, 2180, 7000, 7.1),
            ("gemini-2.5-pro", 4380, 640, 3200, 2.6),
            ("deepseek-v4-pro", 2260, 1180, 0, 4.8),
            ("glm-5.3-flash", 1560, 470, 1200, 1.9)]):
        pat = "proxy" if i % 2 == 0 else "zcode"
        watcher._emit({"ts": time.time() - i * 7, "source": pat,
                       "provider": tm.guess_provider(model), "model": model,
                       "inp": inp, "out": out, "cache_r": cr, "cache_w": 0,
                       "dur": dur, "key": f"shot-{i}", "session": None})
for _ in range(120):
    meter.tick(stats)
    time.sleep(0.012)

app = tm.App(stats, meter, q, watcher, ca=tm.CertAuthority(ca_dir=tm.CA_DIR))
app.attributes("-topmost", True)
app.lift()
app.focus_force()
# 切到「累计」视图，看清全部模型
app._view = "all"
app._set_view("all")
for _ in range(60):
    app.update()
    time.sleep(0.02)
time.sleep(0.5)
app.update()


def shot(widget, path, pad_title=0):
    widget.update_idletasks()
    x = widget.winfo_rootx()
    y = widget.winfo_rooty() - pad_title
    w = widget.winfo_width()
    h = widget.winfo_height() + pad_title
    img = ImageGrab.grab(bbox=(x, y, x + w, y + h))
    img.save(path)
    print("已保存", path, img.size)


shot(app, os.path.join(OUT, "shot_main.png"), pad_title=31)

# 直采控制台
app.start_proxy()
rows = [
    ("claude-sonnet-4-5", 18240, 3520, 12.4, False, "api.anthropic.com"),
    ("gpt-5.2-codex", 9120, 2180, 7.1, False, "api.openai.com"),
    ("gemini-2.5-pro", 4380, 640, 2.6, False, "api.googleapis.com"),
    ("deepseek-v4-pro", 2260, 1180, 4.8, True, "api.deepseek.com"),
    ("glm-5.3-flash", 1560, 470, 1.9, False, "bigmodel.cn"),
]
for i, (model, inp, out, dur, est, host) in enumerate(rows):
    app.proxy.recent.append({
        "ts": time.time() - i * 5, "model": model,
        "provider": tm.guess_provider(model), "inp": inp, "out": out,
        "dur": dur, "est": est, "status": 200, "host": host})
app.proxy.sniffed = 37
app._proxy_center()
for _ in range(40):
    app.update()
    time.sleep(0.02)
time.sleep(0.3)
app.update()
shot(app._pwin, os.path.join(OUT, "shot_proxy.png"), pad_title=31)

app.stop_proxy()
app._on_close()
import shutil   # noqa: E402
shutil.rmtree(tmp, ignore_errors=True)
print("done")
