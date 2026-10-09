[app]
title = 田间水分采集
package.name = fieldmoisture
package.domain = org.field
source.dir = .
source.include_exts = py,xlsx,ttf
version = 1.0

requirements = python3,kivy==2.3.0,openpyxl

orientation = portrait
fullscreen = 0

android.api = 34
android.minapi = 23
android.ndk = 25b
android.archs = arm64-v8a,armeabi-v7a
# 文件选择器需要读取手机存储里的 Excel
android.permissions = READ_EXTERNAL_STORAGE,WRITE_EXTERNAL_STORAGE

# 调试期保留按键唤醒，避免田间作业中途锁屏（可选，去掉注释生效）
# android.wakelock = True

[buildozer]
log_level = 2
warn_on_root = 1
