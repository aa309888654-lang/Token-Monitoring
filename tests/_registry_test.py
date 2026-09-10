# -*- coding: utf-8 -*-
"""注册表接管 / 还原测试（用完立即还原，失败也还原）。"""
import os
import queue
import sys
import tempfile
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import tokenmon as tm   # noqa: E402

problems = []
orig_sys = tm.SystemProxy.read()
orig_env = tm.SystemProxy.read_env()
print("原始系统代理:", orig_sys)
print("原始环境变量:", {k: v for k, v in orig_env.items() if v})

tmp = tempfile.mkdtemp(prefix="tokenmon-reg-")
tm.APP_DIR = tmp
tm.PROXY_BACKUP_FILE = os.path.join(tmp, "backup.json")
tm.RESTORE_BAT = os.path.join(tmp, "restore.bat")
tm.CA_DIR = os.path.join(tmp, "ca")
tm.CA_CERT_FILE = os.path.join(tm.CA_DIR, "ca.pem")
tm.CA_KEY_FILE = os.path.join(tm.CA_DIR, "ca.key")
tm.LEAF_DIR = os.path.join(tm.CA_DIR, "leaf")

ca = tm.CertAuthority(ca_dir=tm.CA_DIR)
assert ca.ensure()
stats, meter = tm.Stats(), tm.SpeedMeter()
q = queue.Queue()
watcher = tm.Watcher(stats, meter, q)
app = tm.App(stats, meter, q, watcher, ca=ca)
app._proxy_port = 18907
ok, msg = app.start_proxy()
print("代理:", ok, msg)
if not ok:
    problems.append(msg)

try:
    app.apply_system_proxy()
    app.apply_env_proxy()
    time.sleep(0.3)
    now_sys = tm.SystemProxy.read()
    now_env = tm.SystemProxy.read_env()
    print("接管后系统代理:", {k: now_sys.get(k) for k in
                          ("ProxyEnable", "ProxyServer", "ProxyOverride")})
    print("接管后环境变量:", {k: now_env.get(k) for k in
                          ("HTTPS_PROXY", "NODE_EXTRA_CA_CERTS",
                           "NODE_USE_ENV_PROXY")})
    if not now_sys.get("ProxyEnable"):
        problems.append("ProxyEnable 未置 1")
    if str(app._proxy_port) not in str(now_sys.get("ProxyServer")):
        problems.append(f"ProxyServer 不对: {now_sys.get('ProxyServer')}")
    if "localhost" not in str(now_sys.get("ProxyOverride")):
        problems.append(f"ProxyOverride 未含 localhost: {now_sys.get('ProxyOverride')}")
    if not str(now_env.get("HTTPS_PROXY", "")).startswith("http://127.0.0.1"):
        problems.append(f"HTTPS_PROXY 未注入: {now_env.get('HTTPS_PROXY')}")
    if not str(now_env.get("NODE_EXTRA_CA_CERTS", "")).endswith("ca.pem"):
        problems.append(f"NODE_EXTRA_CA_CERTS 未注入: {now_env.get('NODE_EXTRA_CA_CERTS')}")
    if tm.load_proxy_backup() is None:
        problems.append("备份文件未写入")
    if not os.path.exists(tm.RESTORE_BAT):
        problems.append("一键还原脚本未生成")
    else:
        bat = open(tm.RESTORE_BAT, "rb").read()
        bat.decode("ascii")          # 必须是纯 ASCII，避免中文系统乱码
        print("还原脚本已生成，大小", len(bat))
finally:
    app.revert_system_proxy()
    app.stop_proxy()
    time.sleep(0.3)

back_sys = tm.SystemProxy.read()
back_env = tm.SystemProxy.read_env()
print("\n还原后系统代理:", back_sys)
print("还原后环境变量:", {k: v for k, v in back_env.items() if v})
for k in ("ProxyEnable", "ProxyServer", "ProxyOverride", "AutoConfigURL"):
    if back_sys.get(k) != orig_sys.get(k):
        problems.append(f"系统代理未还原 {k}: {orig_sys.get(k)} -> {back_sys.get(k)}")
for k in orig_env:
    if back_env.get(k) != orig_env.get(k):
        problems.append(f"环境变量未还原 {k}: {orig_env.get(k)} -> {back_env.get(k)}")
if tm.load_proxy_backup() is not None:
    problems.append("备份文件未清除")

app._on_close()
print("\n[结果] " + ("全部通过 ✔" if not problems else
                    "发现问题：\n  - " + "\n  - ".join(problems)))
sys.exit(1 if problems else 0)
