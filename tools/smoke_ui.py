# -*- coding: utf-8 -*-
"""桌面 UI 冒烟测试：不开事件循环，验证 KV 加载、专属文件夹导入/导出、
键盘录入、搜索跳转、自动保存。"""

import os
import shutil
import sys
import tempfile

tmp = tempfile.mkdtemp()
os.environ["MOISTURE_APP_DIR"] = os.path.join(tmp, u"田间水分采集")  # 测试隔离

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from kivy.base import EventLoop
EventLoop.ensure_window()          # 只建窗口上下文，不跑主循环

import main as appmod
from kivy.core.window import Window

sample = os.path.join(tmp, "s.xlsx")
src_sample = os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), "sample_田间水分.xlsx")
shutil.copyfile(src_sample, sample)

app = appmod.MoistureApp()
app.build()
scr = app.sm.get_screen("main")

# 1. 导入（自动复制进专属文件夹，工作副本在文件夹内）
scr.load_excel(sample)
assert len(scr.rows) == 15, scr.rows
assert scr.excel_path == os.path.join(os.environ["MOISTURE_APP_DIR"], "s.xlsx"), \
    scr.excel_path
assert os.path.isfile(scr.excel_path), "应已复制进专属文件夹"
assert scr.rows[0]["code"] == "T001"
assert "variety" in scr.rows[0]
print("PASS: 导入 15 行 → 自动复制进专属文件夹")

# 2. 键盘录入 12.5 → 自动保存应立即落盘到专属文件夹的工作副本
kp = appmod.KeypadPopup(0, scr.rows[0], scr._confirm_value)
kp.dismiss = lambda *a, **k: None          # 未 open 的 Popup 不能真 dismiss
for ch in ["1", "2", ".", "5"]:
    kp.press(ch)
assert kp.value == "12.5"
kp.confirm()
assert scr.rows[0]["moisture"] == "12.5"
assert scr.dirty is False, "自动保存后 dirty 应复位"
from excel_io import load_rows
rows_now, _ = load_rows(scr.excel_path)
assert rows_now[0]["moisture"] == "12.5", "录入后应已自动写盘"
assert u"已自动保存" in scr.save_status
print("PASS: 小键盘录入 + 全局自动保存落盘")

# 3. 连续录入：确认后应自动弹下一行（T002）的小键盘
assert scr.active_index == 1, scr.active_index
opened = [w for w in Window.children if isinstance(w, appmod.KeypadPopup)]
assert opened and opened[-1].row["code"] == "T002", \
    "应自动弹出 T002 的键盘, %s" % opened
kp2 = opened[-1]
kp2.dismiss = lambda *a, **k: None
kp2.press("8")
kp2.confirm()
assert scr.rows[1]["moisture"] == "8"
assert scr.filled_count == u"2 / 15", scr.filled_count
print("PASS: 连续录入自动跳 T002；计数 2/15")

# 4. 搜索：按条码关键字 / 排+区
assert scr.search_row("T005", "", "") == 4
assert scr.search_row("", "2", "3") == 7
assert scr.search_row("T999", "", "") is None
scr.jump_to_row(7)
assert scr.active_index == 7
hint = scr.ids.current_hint.text
assert u"已定位" in hint, hint
print("PASS: 搜索定位 + 常亮高亮")

# 5. 扫码结果落位（模拟扫码回调，桌面无 jnius，直接调 jump_to_code）
scr.jump_to_code("T010")
assert scr.active_index == 9
scr.jump_to_code("NOPE")   # 未找到只弹提示，不崩
print("PASS: 扫码条码跳转定位")

# 6. 切后台/退出保存
scr.rows[2]["moisture"] = "9.9"
scr.dirty = True
scr.flush_save()
rows_now, _ = load_rows(scr.excel_path)
assert rows_now[2]["moisture"] == "9.9"
print("PASS: flush_save（切后台/退出兜底）")

# 7. 小数点/前导零防呆
kp3 = appmod.KeypadPopup(3, scr.rows[3], scr._confirm_value)
for ch in ["0", "5"]:
    kp3.press(ch)
assert kp3.value == "5", kp3.value      # 前导零自动吞掉
kp3.press(".")
kp3.press(".")
assert kp3.value == "5.", kp3.value     # 重复小数点只进一个
print("PASS: 前导零与重复小数点防呆")

# 8. 导出数据 → 专属文件夹/导出/原名_已填写_时间戳.xlsx
scr.do_save(copy_only=True)
export_dir = os.path.join(os.environ["MOISTURE_APP_DIR"], u"导出")
exports = os.listdir(export_dir)
assert len(exports) == 1 and exports[0].startswith(u"s_已填写_"), exports
rows_exp, _ = load_rows(os.path.join(export_dir, exports[0]))
assert rows_exp[0]["moisture"] == "12.5", "导出副本应含最新数据"
print("PASS: 导出数据 → 导出/ 子文件夹（时间戳命名，含最新数据）")

print("ALL UI SMOKE TESTS PASSED")
