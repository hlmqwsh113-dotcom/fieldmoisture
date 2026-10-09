# -*- coding: utf-8 -*-
"""运行 App 并抓取界面预览图：列表页 / 搜索弹窗 / 数字键盘。"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from kivy.base import EventLoop
EventLoop.ensure_window()
import main as appmod
from kivy.clock import Clock
from kivy.core.window import Window

app = appmod.MoistureApp()
app.build()
Window.size = (420, 760)
scr = app.sm.get_screen("main")
scr.load_excel(os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), "sample_田间水分.xlsx"))
scr.jump_to_row(4)

stage = {"n": 0}


def snap(dt):
    stage["n"] += 1
    Window.screenshot(name="preview_%d.png" % stage["n"])
    if stage["n"] == 1:
        scr.open_search()
    elif stage["n"] == 2:
        for w in list(Window.children):
            if isinstance(w, appmod.SearchPopup):
                w.dismiss()
        scr.open_keypad(4)
    else:
        Clock.schedule_once(lambda *_: app.stop(), 0.2)


Clock.schedule_once(snap, 1.5)
Clock.schedule_interval(snap, 1.5)
app.run()
print("screenshots done")
