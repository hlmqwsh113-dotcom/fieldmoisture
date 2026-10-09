# -*- coding: utf-8 -*-
"""田间水分采集 App（Kivy，可打包安卓 APK）v3

- 全局明亮模式：白色背景 + 深色文字（覆盖 Kivy 默认深色主题）
- 顶部左侧汉堡菜单（导入表格 / 导出数据 / 退出）
- 表格 Excel 风格：实线网格、行间无间距
- 数字小键盘同为表格风格：键间无间距、实线分隔
- 搜索/扫码定位、连续录入、全局自动保存（同 v2）
"""

import datetime
import os
import shutil

from kivy.app import App
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.core.text import LabelBase
from kivy.lang import Builder
from kivy.metrics import dp
from kivy.properties import (BooleanProperty, ListProperty, NumericProperty,
                             ObjectProperty, StringProperty)
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.modalview import ModalView
from kivy.uix.popup import Popup
from kivy.uix.screenmanager import Screen, ScreenManager

from excel_io import load_rows, save_rows
from app_paths import get_app_dir, get_export_dir, request_android_permissions

# ---------------------------------------------------------------- 全局明亮主题
# 主题默认值一律用 kv 规则（见 MAIN_KV 中的 <Label>/<Button>/<Popup>），
# 不要用 Label.color = ... 这类类属性赋值——那会破坏 Kivy 属性系统。
Window.clearcolor = (0.97, 0.97, 0.97, 1)
Window.softinput_mode = "below_target"

SCAN_REQUEST_CODE = 0x5C4  # 扫码 startActivityForResult 的请求码


# ---------------------------------------------------------------- 中文字体
def _find_cjk_font():
    import os
    here = os.path.dirname(os.path.abspath(__file__))
    candidates = [
        os.path.join(here, "assets", "SimHei.ttf"),
        "/system/fonts/DroidSansFallback.ttf",      # 安卓系统字体兜底
        "/system/fonts/NotoSansCJK-Regular.ttc",
        "/system/fonts/NotoSansSC-Regular.otf",
    ]
    for p in candidates:
        if os.path.exists(p):
            return p
    return None


_font = _find_cjk_font()
if _font:
    LabelBase.register(name="CJK", fn_regular=_font)
    Label.font_name = "CJK"  # Label/Button 全局默认


# ---------------------------------------------------------------- 基础控件
class LightPopup(Popup):
    """白底弹窗基类（Kivy 默认弹窗是深色底）。"""


class GridCell(Label):
    """Excel 风格单元格：背景色 + 右/下实线边框。"""
    row_color = ListProperty([1, 1, 1, 1])


class MenuPanel(ModalView):
    """左上角汉堡菜单面板：导入表格 / 导出数据 / 退出。"""
    screen = ObjectProperty(None, allownone=True)

    def _align_center(self, *args):
        pass  # ModalView 默认强制居中，菜单改为固定在按钮下方

    def open_at(self, btn):
        self.open()
        wx, wy = btn.to_window(btn.x, btn.top)
        self.pos = (wx, max(wy - self.height, 0))


# ---------------------------------------------------------------- 数字小键盘
class KeypadPopup(LightPopup):
    """自定义数字小键盘：0-9、小数点、删除、清空、确定（实线表格风格）。"""

    value = StringProperty("")
    title_text = StringProperty("")

    def __init__(self, row_index, row, on_confirm, **kw):
        self.row_index = row_index
        self.row = row
        self.on_confirm = on_confirm
        sub = u"（排%s 区%s %s）" % (row["pai"] or "-",
                                    row["qu"] or "-", row["variety"] or "")
        self.title_text = u"录入水分：%s%s" % (row["code"] or "-", sub)
        self.value = row["moisture"]
        super(KeypadPopup, self).__init__(**kw)

    def press(self, ch):
        if ch == "back":
            self.value = self.value[:-1]
        elif ch == "clear":
            self.value = ""
        elif ch == ".":
            if "." not in self.value:
                self.value = (self.value or "0") + "."
        else:  # 数字
            if self.value == "0":
                self.value = ch
            elif len(self.value.replace(".", "")) < 8:
                self.value += ch

    def confirm(self):
        v = self.value
        if v in ("", ".") or v.endswith("."):
            self.ids.hint.text = u"请输入有效数值"
            return
        self.dismiss()
        self.on_confirm(self.row_index, v)


# ---------------------------------------------------------------- 搜索弹窗
class SearchPopup(LightPopup):
    """按田间条码关键字，或 排+区 定位数据行。"""

    def __init__(self, screen, **kw):
        self.screen = screen
        super(SearchPopup, self).__init__(**kw)

    def do_search(self):
        code_kw = self.ids.code_kw.text.strip()
        pai = self.ids.pai.text.strip()
        qu = self.ids.qu.text.strip()
        if not (code_kw or pai or qu):
            self.ids.msg.text = u"请输入条码或排/区号"
            return
        idx = self.screen.search_row(code_kw, pai, qu)
        if idx is None:
            self.ids.msg.text = u"未找到匹配行，请检查输入"
            return
        self.dismiss()
        self.screen.jump_to_row(idx)


# ---------------------------------------------------------------- 数据行控件
class DataRow(GridLayout):
    code = StringProperty("")
    variety = StringProperty("")
    pai = StringProperty("")
    qu = StringProperty("")
    moisture = StringProperty("")
    filled = BooleanProperty(False)
    active = BooleanProperty(False)
    row_color = ListProperty([1, 1, 1, 1])
    parent_row_tap = ObjectProperty(None, allownone=True)
    index = NumericProperty(0)

    def on_touch_down(self, touch):
        if self.collide_point(*touch.pos):
            if self.parent_row_tap is not None:
                self.parent_row_tap(self.index)
            return True
        return super(DataRow, self).on_touch_down(touch)


# ---------------------------------------------------------------- 主界面
class MainScreen(Screen):
    rows = ListProperty([])
    filled_count = StringProperty(u"0 / 0")
    excel_path = ObjectProperty(None, allownone=True)
    active_index = NumericProperty(-1)
    auto_next = BooleanProperty(True)
    dirty = BooleanProperty(False)          # 有未落盘的修改
    save_status = StringProperty("")

    def load_excel(self, path):
        try:
            rows, missing = load_rows(path)
        except Exception as e:
            self._alert(u"导入失败", u"无法读取该文件：\n%s" % e)
            return
        code_missing = [h for h in missing if h in (u"田间条码", u"田间编号")]
        if code_missing:
            self._alert(u"导入失败", u"表中未找到表头：田间条码（或旧表头 田间编号）")
            return
        work_path = self._into_app_dir(path)
        if work_path is None:
            return
        self.excel_path = work_path
        self.rows = rows
        self.dirty = False
        self._refresh()
        if self.manager is not None:
            self.manager.current = "main"
        tip = u"已导入 %d 行 → %s" % (len(rows), work_path)
        other_missing = [h for h in missing if h not in code_missing]
        if other_missing:
            tip += u"（缺少表头：%s，保存时自动补）" % u"、".join(other_missing)
        self.ids.status.text = tip
        Clock.schedule_interval(self._autosave_tick, 30)  # 30 秒兜底保存

    def _into_app_dir(self, src):
        """把导入的文件复制进 App 专属文件夹集中管理；已在文件夹内则直接用。"""
        app_dir = get_app_dir()
        src_abs = os.path.abspath(src)
        if os.path.dirname(src_abs) == os.path.abspath(app_dir):
            return src_abs
        dst = os.path.join(app_dir, os.path.basename(src))
        try:
            if os.path.abspath(dst) != src_abs:
                shutil.copyfile(src_abs, dst)
            return dst
        except Exception as e:
            self._alert(u"导入失败", u"无法复制到数据文件夹：\n%s" % e)
            return None

    # ------------------------------------------------------------- 列表刷新
    def _refresh(self):
        n_filled = sum(1 for r in self.rows if r["moisture"] != "")
        self.filled_count = u"%d / %d" % (n_filled, len(self.rows))
        self._rebuild_list()

    def _rebuild_list(self):
        box = self.ids.rows_box
        box.clear_widgets()
        for i, r in enumerate(self.rows):
            if r["moisture"] != "":
                bg = (0.80, 0.92, 0.80, 1)          # 已填：浅绿
            elif i == self.active_index:
                bg = (0.98, 0.78, 0.35, 1)          # 定位/当前行：橙
            else:
                bg = (1, 1, 1, 1)
            item = DataRow(
                code=r["code"], variety=r.get("variety", ""),
                pai=r["pai"], qu=r["qu"],
                moisture=r["moisture"] or u"待录入",
                filled=(r["moisture"] != ""),
                active=(i == self.active_index),
                row_color=bg,
                parent_row_tap=self.open_keypad,
                size_hint_y=None, height=dp(52))
            item.index = i
            box.add_widget(item)
        nxt = self._next_unfilled()
        if nxt is None:
            self.ids.current_hint.text = u"全部填写完成 √"
        else:
            self.ids.current_hint.text = u"下一行：%s" % (
                self.rows[nxt]["code"] or str(nxt + 1))

    def _next_unfilled(self, start=0):
        for i in range(start, len(self.rows)):
            if self.rows[i]["moisture"] == "":
                return i
        for i in range(start):  # 回绕
            if self.rows[i]["moisture"] == "":
                return i
        return None

    def _scroll_to_index(self, i):
        sv = self.ids.rows_scroll
        row_total = dp(52)
        content_h = len(self.rows) * row_total
        if content_h <= sv.height:
            return
        target = i * row_total + row_total / 2.0
        sv.scroll_y = max(0.0, min(1.0,
                           1.0 - (target - sv.height / 2.0) / (content_h - sv.height)))

    # ------------------------------------------------------------- 汉堡菜单
    def open_menu(self):
        MenuPanel(screen=self).open_at(self.ids.menu_btn)

    def menu_action(self, name):
        if name == "import":
            if self.manager is not None:
                self.manager.current = "files"
        elif name == "export":
            self.do_save(copy_only=True)
        elif name == "exit":
            self.flush_save()
            App.get_running_app().stop()

    # ------------------------------------------------------------- 录入
    def open_keypad(self, index):
        self.active_index = index
        self._rebuild_list()
        pop = KeypadPopup(index, self.rows[index], self._confirm_value)
        pop.open()

    def _confirm_value(self, i, value):
        self.rows[i]["moisture"] = value
        self.dirty = True         # 标记待落盘
        self.active_index = i     # 保持当前行常亮
        self._refresh()
        self.autosave()           # 全局自动保存：每次录入立即落盘
        if self.auto_next:
            nxt = self._next_unfilled(i + 1)
            if nxt is not None:
                self.open_keypad(nxt)
                return
        self.active_index = -1
        self._rebuild_list()

    # ------------------------------------------------------------- 搜索 / 扫码
    def search_row(self, code_kw, pai, qu):
        """按 条码关键字 + 排 + 区 查找，返回行号或 None。"""
        for i, r in enumerate(self.rows):
            if code_kw and code_kw not in r["code"]:
                continue
            if pai and pai != r["pai"]:
                continue
            if qu and qu != r["qu"]:
                continue
            return i
        return None

    def jump_to_row(self, index):
        """跳转并常亮高亮目标行。"""
        self.active_index = index
        self._rebuild_list()
        self._scroll_to_index(index)
        r = self.rows[index]
        self.ids.current_hint.text = u"已定位：%s（排%s 区%s %s）" % (
            r["code"] or "-", r["pai"] or "-", r["qu"] or "-",
            r.get("variety", "") or "")

    def jump_to_code(self, code):
        idx = self.search_row(code, "", "")
        if idx is None:
            self._alert(u"扫码结果", u"条码 %s 在表中未找到" % code)
            return
        self.jump_to_row(idx)

    def open_search(self):
        SearchPopup(self).open()

    def start_scan(self):
        """调起 ZXing 兼容条码扫描器（安卓）；桌面端提示不可用。"""
        try:
            from jnius import autoclass  # noqa
            from android import activity as android_activity
        except ImportError:
            self._alert(u"扫码", u"扫码功能需在安卓手机上使用。\n"
                                 u"电脑端请使用“搜索”功能。")
            return
        if not getattr(self, "_scan_bound", False):
            android_activity.bind(on_activity_result=self._on_scan_result)
            self._scan_bound = True
        Intent = autoclass("android.content.Intent")
        PythonActivity = autoclass("org.kivy.android.PythonActivity")
        intent = Intent("com.google.zxing.client.android.SCAN")
        intent.putExtra("SCAN_MODE", "ONE_D_MODE")
        intent.putExtra("SCAN_FORMATS",
                        "CODE_128,CODE_39,CODE_93,EAN_13,EAN_8,UPC_A,ITF,QR_CODE")
        try:
            PythonActivity.mActivity.startActivityForResult(
                intent, SCAN_REQUEST_CODE)
        except Exception:
            self._alert(u"扫码失败",
                        u"未找到条码扫描器应用。\n请安装 ZXing 兼容扫码App"
                        u"（如“条码扫描器”）后重试，\n或改用“搜索”功能。")

    def _on_scan_result(self, request_code, result_code, intent):
        if request_code != SCAN_REQUEST_CODE:
            return
        if result_code != -1:  # RESULT_OK = -1，其他为取消
            return
        try:
            text = intent.getStringExtra("SCAN_RESULT") or ""
        except Exception:
            text = ""
        text = text.strip()
        if text:
            self.jump_to_code(text)

    # ------------------------------------------------------------- 保存
    def autosave(self):
        """录入后立即自动保存（静默，不打扰操作）。"""
        if not self.dirty or not self.excel_path or not self.rows:
            return
        try:
            save_rows(self.excel_path, self.rows)
            self.dirty = False
            self.save_status = u"已自动保存 %s" % (
                datetime.datetime.now().strftime("%H:%M:%S"))
        except Exception as e:
            # 保存失败不清 dirty，30 秒兜底定时器会重试
            self.save_status = u"自动保存失败，将重试：%s" % e

    def _autosave_tick(self, dt):
        self.autosave()

    def flush_save(self):
        """切后台 / 退出前强制落盘。"""
        self.autosave()

    def do_save(self, copy_only=False):
        if not self.excel_path or not self.rows:
            self._alert(u"提示", u"请先导入 Excel")
            return
        if copy_only:
            # 导出副本 → 专属文件夹/导出/原名_已填写_时间戳.xlsx
            stem = os.path.splitext(os.path.basename(self.excel_path))[0]
            stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            target = os.path.join(get_export_dir(),
                                  u"%s_已填写_%s.xlsx" % (stem, stamp))
        else:
            target = self.excel_path
        try:
            if copy_only:
                shutil.copyfile(self.excel_path, target)
            save_rows(target, self.rows)
            self.dirty = False
            self.save_status = u"已自动保存 %s" % (
                datetime.datetime.now().strftime("%H:%M:%S"))
        except Exception as e:
            self._alert(u"保存失败", str(e))
            return
        self.ids.status.text = u"已保存到：%s" % target
        if copy_only:
            self._alert(u"导出成功", target)

    def _alert(self, title, msg):
        LightPopup(title=title,
                   content=Label(text=msg, text_size=(dp(280), None),
                                 halign="left", color=(0.12, 0.12, 0.12, 1)),
                   size_hint=(0.85, None), size=(dp(320), dp(200))).open()


class FileScreen(Screen):
    def on_pre_enter(self, *args):
        # 默认定位到 App 专属文件夹（表格统一放这里）
        try:
            self.ids.chooser.path = get_app_dir()
        except Exception:
            pass

    def pick(self, selection):
        if selection:
            self.manager.get_screen("main").load_excel(selection[0])


class MoistureApp(App):
    title = u"田间水分采集"

    def build(self):
        self.sm = ScreenManager()
        self.sm.add_widget(MainScreen(name="main"))
        self.sm.add_widget(FileScreen(name="files"))
        return self.sm

    def on_start(self):
        # 安卓端申请存储权限；确保专属文件夹存在并在状态行显示
        request_android_permissions()
        try:
            app_dir = get_app_dir()
            self._main().ids.status.text = u"数据文件夹：%s" % app_dir
        except Exception:
            pass

    def _main(self):
        return self.sm.get_screen("main")

    def on_pause(self):
        self._main().flush_save()  # 切后台先落盘再暂停
        return True

    def on_stop(self):
        self._main().flush_save()  # 退出前落盘


MAIN_KV = """
# 全局明亮主题：深色文字 + 扁平浅色按钮 + 浅色弹窗标题
<Label>:
    color: 0.12, 0.12, 0.12, 1
<Button>:
    background_normal: ''
    background_down: ''
    background_color: 0.93, 0.93, 0.93, 1
    color: 0.12, 0.12, 0.12, 1
<Popup>:
    title_color: 0.1, 0.1, 0.1, 1

<LightPopup>:
    background: ''
    separator_color: 0.7, 0.7, 0.7, 1
    title_color: 0.1, 0.1, 0.1, 1
    canvas.before:
        Color:
            rgba: 1, 1, 1, 1
        Rectangle:
            pos: self.pos
            size: self.size

<GridCell>:
    font_size: dp(13)
    color: 0.12, 0.12, 0.12, 1
    canvas.before:
        Color:
            rgba: self.row_color
        Rectangle:
            pos: self.pos
            size: self.size
    canvas.after:
        Color:
            rgba: 0.55, 0.55, 0.55, 1
        Line:
            points: self.x, self.y, self.x + self.width, self.y
        Line:
            points: self.x + self.width, self.y, self.x + self.width, self.y + self.height

<LightButton@Button>:
    background_normal: ''
    background_down: ''
    background_color: 1, 1, 1, 1
    color: 0.12, 0.12, 0.12, 1
    canvas.before:
        Color:
            rgba: (0.85, 0.85, 0.85, 1) if self.state == 'down' else (1, 1, 1, 1)
        Rectangle:
            pos: self.pos
            size: self.size
    canvas.after:
        Color:
            rgba: 0.6, 0.6, 0.6, 1
        Line:
            points: self.x + self.width, self.y, self.x + self.width, self.y + self.height
        Line:
            points: self.x, self.y, self.x + self.width, self.y

<AccentButton@Button>:
    background_normal: ''
    background_down: ''
    background_color: 0.15, 0.55, 0.25, 1
    color: 1, 1, 1, 1
    canvas.after:
        Color:
            rgba: 0.1, 0.4, 0.2, 1
        Line:
            rectangle: self.x, self.y, self.width, self.height

<MenuPanel>:
    size_hint: None, None
    size: dp(200), dp(168)
    background: ''
    canvas.before:
        Color:
            rgba: 1, 1, 1, 1
        Rectangle:
            pos: self.pos
            size: self.size
        Color:
            rgba: 0.5, 0.5, 0.5, 1
        Line:
            rectangle: self.x, self.y, self.width, self.height
    BoxLayout:
        orientation: 'vertical'
        spacing: 0
        LightButton:
            text: '导入表格'
            font_size: dp(16)
            on_release: root.dismiss(); root.screen.menu_action('import')
        LightButton:
            text: '导出数据'
            font_size: dp(16)
            on_release: root.dismiss(); root.screen.menu_action('export')
        LightButton:
            text: '退出'
            font_size: dp(16)
            on_release: root.dismiss(); root.screen.menu_action('exit')

<MainScreen>:
    canvas.before:
        Color:
            rgba: 0.97, 0.97, 0.97, 1
        Rectangle:
            pos: self.pos
            size: self.size
    BoxLayout:
        orientation: 'vertical'
        padding: dp(6)
        spacing: dp(4)

        # 顶栏：汉堡菜单 / 搜索 / 扫码 / 进度
        BoxLayout:
            size_hint_y: None
            height: dp(48)
            spacing: dp(4)
            Button:
                id: menu_btn
                size_hint_x: 0.28
                background_normal: ''
                background_down: ''
                background_color: 1, 1, 1, 1
                on_release: root.open_menu()
                canvas.before:
                    Color:
                        rgba: (0.85, 0.85, 0.85, 1) if self.state == 'down' else (1, 1, 1, 1)
                    Rectangle:
                        pos: self.pos
                        size: self.size
                canvas.after:
                    Color:
                        rgba: 0.15, 0.15, 0.15, 1
                    Line:
                        points:
                            (self.x + self.width * 0.26, self.y + self.height * 0.70,
                            self.x + self.width * 0.74, self.y + self.height * 0.70)
                        width: 1.4
                    Line:
                        points:
                            (self.x + self.width * 0.26, self.y + self.height * 0.50,
                            self.x + self.width * 0.74, self.y + self.height * 0.50)
                        width: 1.4
                    Line:
                        points:
                            (self.x + self.width * 0.26, self.y + self.height * 0.30,
                            self.x + self.width * 0.74, self.y + self.height * 0.30)
                        width: 1.4
                    Color:
                        rgba: 0.6, 0.6, 0.6, 1
                    Line:
                        rectangle: self.x, self.y, self.width, self.height
            LightButton:
                text: '搜索'
                on_release: root.open_search()
            LightButton:
                text: '扫码'
                on_release: root.start_scan()
            Label:
                text: root.filled_count
                bold: True
                font_size: dp(18)
                color: 0.1, 0.3, 0.7, 1

        # 状态行
        BoxLayout:
            size_hint_y: None
            height: dp(22)
            Label:
                id: status
                text: '菜单中“导入表格”选择 .xlsx 文件'
                color: 0.35, 0.35, 0.35, 1
                font_size: dp(12)
                text_size: self.size
                halign: 'left'
                valign: 'middle'
            Label:
                id: save_state
                text: root.save_status
                font_size: dp(11)
                color: 0.2, 0.55, 0.25, 1
                size_hint_x: 0.6
                text_size: self.size
                halign: 'right'
                valign: 'middle'

        Label:
            id: current_hint
            text: ''
            size_hint_y: None
            height: dp(24)
            bold: True
            color: 0.1, 0.4, 0.8, 1

        # 表头（实线网格）
        GridLayout:
            cols: 5
            spacing: 0
            size_hint_y: None
            height: dp(34)
            GridCell:
                text: '田间条码'
                bold: True
                size_hint_x: 1.25
                row_color: 0.88, 0.9, 0.96, 1
            GridCell:
                text: '排'
                bold: True
                size_hint_x: 0.45
                row_color: 0.88, 0.9, 0.96, 1
            GridCell:
                text: '区'
                bold: True
                size_hint_x: 0.45
                row_color: 0.88, 0.9, 0.96, 1
            GridCell:
                text: '品种名称'
                bold: True
                size_hint_x: 1.25
                row_color: 0.88, 0.9, 0.96, 1
            GridCell:
                text: '水分'
                bold: True
                size_hint_x: 1.0
                row_color: 0.88, 0.9, 0.96, 1

        ScrollView:
            id: rows_scroll
            GridLayout:
                id: rows_box
                cols: 1
                spacing: 0
                size_hint_y: None
                height: self.minimum_height

<DataRow>:
    cols: 5
    spacing: 0
    GridCell:
        text: root.code
        bold: root.active
        size_hint_x: 1.25
        row_color: root.row_color
    GridCell:
        text: root.pai
        size_hint_x: 0.45
        row_color: root.row_color
    GridCell:
        text: root.qu
        size_hint_x: 0.45
        row_color: root.row_color
    GridCell:
        text: root.variety
        size_hint_x: 1.25
        row_color: root.row_color
    GridCell:
        text: root.moisture
        size_hint_x: 1.0
        bold: True
        row_color: root.row_color
        color:
            (0, 0.5, 0, 1) if root.filled else (0.5, 0.5, 0.5, 1)

<FileScreen>:
    canvas.before:
        Color:
            rgba: 0.97, 0.97, 0.97, 1
        Rectangle:
            pos: self.pos
            size: self.size
    BoxLayout:
        orientation: 'vertical'
        padding: dp(6)
        spacing: dp(6)
        BoxLayout:
            size_hint_y: None
            height: dp(48)
            spacing: dp(6)
            LightButton:
                text: '< 返回'
                size_hint_x: 0.3
                on_release: root.manager.current = 'main'
            Label:
                text: '选择 .xlsx 文件'
                bold: True
                color: 0.12, 0.12, 0.12, 1
        FileChooserListView:
            id: chooser
            filters: ['*.xlsx']
            on_submit: root.pick(args[1])
        LightButton:
            size_hint_y: None
            height: dp(52)
            text: '导入选中的文件'
            on_release: root.pick(chooser.selection)

<SearchPopup>:
    title: '搜索定位'
    size_hint: (0.92, None)
    height: dp(320)
    BoxLayout:
        orientation: 'vertical'
        spacing: dp(10)
        padding: dp(8)
        Label:
            text: '田间条码（支持部分匹配）'
            color: 0.35, 0.35, 0.35, 1
            size_hint_y: None
            height: dp(22)
            font_size: dp(13)
            text_size: self.size
            halign: 'left'
        TextInput:
            id: code_kw
            multiline: False
            font_size: dp(18)
            size_hint_y: None
            height: dp(44)
        BoxLayout:
            size_hint_y: None
            height: dp(44)
            spacing: dp(6)
            Label:
                text: '排'
                size_hint_x: 0.2
                color: 0.35, 0.35, 0.35, 1
            TextInput:
                id: pai
                multiline: False
                font_size: dp(18)
                size_hint_x: 0.8
            Label:
                text: '区'
                size_hint_x: 0.2
                color: 0.35, 0.35, 0.35, 1
            TextInput:
                id: qu
                multiline: False
                font_size: dp(18)
                size_hint_x: 0.8
        Label:
            id: msg
            text: ''
            color: 0.8, 0.2, 0.2, 1
            size_hint_y: None
            height: dp(22)
            font_size: dp(13)
        BoxLayout:
            size_hint_y: None
            height: dp(50)
            spacing: dp(6)
            LightButton:
                text: '取消'
                on_release: root.dismiss()
            AccentButton:
                text: '搜索定位'
                bold: True
                on_release: root.do_search()

<KeypadPopup>:
    title: root.title_text
    size_hint: (0.92, None)
    height: dp(430)
    auto_dismiss: False
    BoxLayout:
        orientation: 'vertical'
        spacing: dp(6)
        padding: dp(4)

        GridCell:
            id: display
            text: root.value if root.value else '—'
            font_size: dp(32)
            bold: True
            row_color: 0.95, 0.96, 1, 1
            size_hint_y: None
            height: dp(62)

        Label:
            id: hint
            text: ''
            color: 0.8, 0.2, 0.2, 1
            size_hint_y: None
            height: dp(20)
            font_size: dp(12)

        # 数字键区：无间距、实线分隔（同表格样式）
        GridLayout:
            cols: 3
            spacing: 0
            size_hint_y: 1
            LightButton:
                text: '7'
                font_size: dp(24)
                on_release: root.press('7')
            LightButton:
                text: '8'
                font_size: dp(24)
                on_release: root.press('8')
            LightButton:
                text: '9'
                font_size: dp(24)
                on_release: root.press('9')
            LightButton:
                text: '4'
                font_size: dp(24)
                on_release: root.press('4')
            LightButton:
                text: '5'
                font_size: dp(24)
                on_release: root.press('5')
            LightButton:
                text: '6'
                font_size: dp(24)
                on_release: root.press('6')
            LightButton:
                text: '1'
                font_size: dp(24)
                on_release: root.press('1')
            LightButton:
                text: '2'
                font_size: dp(24)
                on_release: root.press('2')
            LightButton:
                text: '3'
                font_size: dp(24)
                on_release: root.press('3')
            LightButton:
                text: '.'
                font_size: dp(24)
                on_release: root.press('.')
            LightButton:
                text: '0'
                font_size: dp(24)
                on_release: root.press('0')
            LightButton:
                text: '删除'
                font_size: dp(20)
                on_release: root.press('back')

        BoxLayout:
            size_hint_y: None
            height: dp(56)
            spacing: 0
            LightButton:
                text: '清空'
                on_release: root.press('clear')
            AccentButton:
                text: '确定 √'
                bold: True
                on_release: root.confirm()
"""

Builder.load_string(MAIN_KV)

if __name__ == "__main__":
    MoistureApp().run()
