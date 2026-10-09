# -*- coding: utf-8 -*-
"""抓取明亮模式界面：列表(定位高亮) / 汉堡菜单 / 数字键盘。"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from kivy.base import EventLoop
EventLoop.ensure_window()
import main as appmod
from kivy.clock import Clock
from kivy.core.window import Window

app = appmod.MoistureApp()
stage = {"n": 0}

def setup(dt):
    Window.size = (420, 760)
    scr = app.root.get_screen("main")
    scr.load_excel(os.path.join(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))), "sample_田间水分.xlsx"))
    scr.jump_to_row(4)
    stage["scr"] = scr

def snap1(dt):
    Window.screenshot(name="preview_main.png")
    stage["scr"].open_menu()

def snap2(dt):
    Window.screenshot(name="preview_menu.png")
    from kivy.uix.modalview import ModalView
    for w in list(Window.children):
        if isinstance(w, ModalView):
            w.dismiss()
    stage["scr"].open_keypad(4)

def snap3(dt):
    Window.screenshot(name="preview_keypad.png")
    Clock.schedule_once(lambda *_: app.stop(), 0.3)

Clock.schedule_once(setup, 0.6)
Clock.schedule_once(snap1, 2.5)
Clock.schedule_once(snap2, 4.0)
Clock.schedule_once(snap3, 5.5)
app.run()
print("done")
