# -*- coding: utf-8 -*-
"""生成一份示例田间表格（sample_田间水分.xlsx），供桌面/手机测试导入。
注意：该文件在腾讯文档编辑器中打开时由编辑器管理，重新生成前请先关闭预览。
"""

from openpyxl import Workbook

wb = Workbook()
ws = wb.active
ws.title = "田间数据"
ws.append(["田间条码", "品种名称", "排", "区", "水分"])

varieties = ["先玉335", "郑单958", "京科968", "登海605", "沃玉3号"]

n = 0
for pai in range(1, 4):          # 3 排
    for qu in range(1, 6):       # 每排 5 个小区
        n += 1
        ws.append(["T%03d" % n, varieties[(n - 1) % len(varieties)], pai, qu, None])

wb.save("sample_田间水分.xlsx")
print("已生成 sample_田间水分.xlsx，共 %d 行" % n)
