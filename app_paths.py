# -*- coding: utf-8 -*-
"""App 专属文件夹管理：导入的表格与导出的数据统一存放在独立文件夹。

优先级：
1. 安卓共享存储根目录下的"田间水分采集"文件夹（文件管理器里直接可见）
2. 应用私有外部目录 Android/data/<包名>/files/田间水分采集（免权限）
3. 桌面端：用户文档目录/田间水分采集
"""

import os

APP_DIR_NAME = u"田间水分采集"
EXPORT_DIR_NAME = u"导出"


def is_android():
    try:
        from jnius import autoclass  # noqa: F401
        return True
    except ImportError:
        return False


def request_android_permissions():
    """安卓端启动时申请存储权限（安卓 10 及以下需要；11+ 失败时自动回退私有目录）。"""
    if not is_android():
        return
    try:
        from android.permissions import Permission, request_permissions
        request_permissions([Permission.WRITE_EXTERNAL_STORAGE,
                             Permission.READ_EXTERNAL_STORAGE])
    except Exception:
        pass


def _mkdir(path):
    if not os.path.isdir(path):
        os.makedirs(path)
    return path


def _external_root():
    try:
        from android.storage import primary_external_storage_path
        return primary_external_storage_path()
    except Exception:
        return None


def _app_external_dir():
    """应用私有外部目录（/storage/emulated/0/Android/data/<pkg>/files）。"""
    try:
        from jnius import autoclass
        activity = autoclass("org.kivy.android.PythonActivity").mActivity
        d = activity.getExternalFilesDir(None)
        if d is not None:
            return d.getAbsolutePath()
    except Exception:
        pass
    return None


def get_app_dir():
    """返回（不存在则创建）App 专属文件夹的绝对路径。

    可用环境变量 MOISTURE_APP_DIR 覆盖（测试用）。
    """
    override = os.environ.get("MOISTURE_APP_DIR")
    if override:
        return _mkdir(override)
    if is_android():
        # 1) 共享存储根目录下的专属文件夹（首选，用户可直接拷贝文件进去）
        root = _external_root()
        if root:
            try:
                return _mkdir(os.path.join(root, APP_DIR_NAME))
            except OSError:
                pass
        # 2) 应用私有外部目录（免权限，文件管理器可见）
        ext = _app_external_dir()
        if ext:
            try:
                return _mkdir(os.path.join(ext, APP_DIR_NAME))
            except OSError:
                return _mkdir(ext)
    # 桌面端
    docs = os.path.join(os.path.expanduser("~"), "Documents")
    base = docs if os.path.isdir(docs) else os.path.expanduser("~")
    return _mkdir(os.path.join(base, APP_DIR_NAME))


def get_export_dir():
    """导出文件专用子文件夹：<专属文件夹>/导出。"""
    return _mkdir(os.path.join(get_app_dir(), EXPORT_DIR_NAME))
