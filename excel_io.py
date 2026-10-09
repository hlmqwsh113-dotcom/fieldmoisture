# -*- coding: utf-8 -*-
"""Excel 读写模块（与界面解耦，便于在电脑上单独测试）。

表格表头约定：田间条码（兼容旧表头"田间编号"）、排、区、品种名称、水分
- 列位置按表头名查找，不依赖固定列序；
- "水分"列不存在时会在保存时自动追加到表头行末尾；
- 保存时保留原工作簿（其他 sheet、格式不受影响），只写水分值。
"""

import os

from openpyxl import load_workbook

# 田间条码列可接受的新旧表头
CODE_HEADERS = (u"田间条码", u"田间编号")
OTHER_HEADERS = (u"排", u"区", u"品种名称", u"水分")


def _cell_text(v):
    if v is None:
        return ""
    if isinstance(v, float) and v == int(v):
        return str(int(v))
    return str(v).strip()


def load_rows(path):
    """读取表格，返回 (rows, missing_headers)。

    rows: [{'code':田间条码, 'pai':排, 'qu':区, 'variety':品种名称,
            'moisture':水分(str, ''=未填)}]
    missing_headers: 缺失的表头名列表（"水分"/"品种名称"缺失不算致命）。
    """
    wb = load_workbook(path, data_only=True)
    ws = wb.active

    header_cells = next(ws.iter_rows(min_row=1, max_row=1))
    header = [_cell_text(c.value) for c in header_cells]

    idx = {}
    missing = []
    for key in OTHER_HEADERS:
        found = None
        for i, h in enumerate(header):
            if h == key:
                found = i
                break
        if found is None:
            missing.append(key)
        else:
            idx[key] = found

    code_idx = None
    for alias in CODE_HEADERS:
        if alias in header:
            code_idx = header.index(alias)
            break
    if code_idx is None:
        missing.append(u"田间条码")

    rows = []
    for r in ws.iter_rows(min_row=2):
        def val(i):
            if i is None or i >= len(r):
                return ""
            return _cell_text(r[i].value)

        code = val(code_idx)
        pai = val(idx.get(u"排"))
        qu = val(idx.get(u"区"))
        variety = val(idx.get(u"品种名称"))
        moisture = val(idx.get(u"水分"))
        if not (code or pai or qu or variety or moisture):
            continue  # 整行为空，跳过
        rows.append({"code": code, "pai": pai, "qu": qu,
                     "variety": variety, "moisture": moisture})

    wb.close()
    return rows, missing


def _as_number(text):
    """纯数字字符串转 int/float，其余原样返回（方便 Excel 后续公式统计）。"""
    if text is None or text == "":
        return None
    try:
        f = float(text)
        return int(f) if f == int(f) and "." not in str(text) else f
    except (TypeError, ValueError):
        return text


def save_rows(path, rows):
    """把 rows 中的水分值写回 xlsx（按行序对应）。返回保存路径。"""
    wb = load_workbook(path, data_only=False)
    ws = wb.active

    header_cells = next(ws.iter_rows(min_row=1, max_row=1))
    header = [_cell_text(c.value) for c in header_cells]

    # 定位水分列，没有则在第一个空列追加
    mcol = None
    for i, h in enumerate(header):
        if h == u"水分":
            mcol = i + 1
            break
    if mcol is None:
        mcol = len(header) + 1
        ws.cell(row=1, column=mcol, value=u"水分")

    for offset, row in enumerate(rows):
        r = offset + 2  # 数据从第 2 行开始，与 load_rows 的跳空行逻辑一致
        ws.cell(row=r, column=mcol, value=_as_number(row["moisture"]))

    wb.save(path)
    wb.close()
    return path


def default_output_path(src_path):
    """导出副本路径：原文件名_已填写.xlsx，放在原文件同目录。"""
    base, ext = os.path.splitext(src_path)
    return base + "_已填写" + (ext or ".xlsx")
