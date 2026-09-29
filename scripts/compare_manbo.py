
# ============================================================
# 漫播每周数据对比
# GitHub Actions 版本
#
# 功能：
# 1. 自动读取 output/漫播周数据MMDD.csv
# 2. 自动寻找当前周之前最近的一份原始漫播周数据 CSV
# 3. 计算：
#       各项2
#       各项周增
#       各项周增率
# 4. 空行保留，不参与计算
# 5. 输出：
#       output/漫播周数据对比版MMDD.csv
#
# 数据逻辑：
#
#   UID数量       = 上周
#   UID数量2      = 本周
#   UID数量周增    = 本周 - 上周
#
#   其他数值字段同理。
# ============================================================


import os
import re
from datetime import datetime

import pandas as pd
import pytz


# ============================================================
# 1. 路径
# ============================================================

ROOT = os.path.dirname(
    os.path.dirname(
        os.path.abspath(__file__)
    )
)

OUTPUT_DIR = os.path.join(
    ROOT,
    "output"
)

TZ = pytz.timezone(
    "Asia/Shanghai"
)


# ============================================================
# 2. 需要进行周对比的数值字段
# ============================================================

NUMERIC_COLUMNS = [
    "付费集数",
    "UID数量",
    "弹幕ID_source1+4",
    "播放量",
    "收藏数",
    "评论数",
    "投喂数",
    "实际付费人数",
]


# ============================================================
# 3. 从文件名提取日期
#
# 例如：
#
# 漫播周数据0929.csv
#
# 返回：
#
# 0929
# ============================================================

def file_date(path):

    name = os.path.basename(path)

    match = re.fullmatch(
        r"漫播周数据(\d{4})\.csv",
        name
    )

    if not match:
        return None

    return match.group(1)


# ============================================================
# 4. 找到所有原始漫播 CSV
#
# 只匹配：
#
#   漫播周数据0929.csv
#
# 不匹配：
#
#   漫播周数据对比版0929.csv
# ============================================================

def find_raw_files():

    paths = []

    if not os.path.exists(OUTPUT_DIR):
        return paths

    for name in os.listdir(OUTPUT_DIR):

        if not re.fullmatch(
            r"漫播周数据\d{4}\.csv",
            name
        ):
            continue

        paths.append(
            os.path.join(
                OUTPUT_DIR,
                name
            )
        )

    def sort_key(path):

        date_code = file_date(path)

        return (
            date_code or "",
            os.path.getmtime(path)
        )

    return sorted(
        paths,
        key=sort_key
    )


# ============================================================
# 5. 数值转换
# ============================================================

def numeric(series):

    return pd.to_numeric(
        series,
        errors="coerce"
    )


# ============================================================
# 6. 清理 url
# ============================================================

def normalize_url(series):

    return (
        series
        .astype("string")
        .str.strip()
    )


# ============================================================
# 7. 主程序
# ============================================================

def main():

    os.makedirs(
        OUTPUT_DIR,
        exist_ok=True
    )


    # ========================================================
    # 当前北京时间
    # ========================================================

    now = datetime.now(TZ)

    current_date = now.strftime(
        "%m%d"
    )


    current_filename = (
        f"漫播周数据{current_date}.csv"
    )

    current_path = os.path.join(
        OUTPUT_DIR,
        current_filename
    )


    print()
    print("=" * 70)
    print("📊 漫播每周数据对比")
    print("=" * 70)

    print(
        f"📅 当前北京时间："
        f"{now.strftime('%Y-%m-%d %H:%M:%S')}"
    )

    print(
        f"📄 本周文件："
        f"{current_filename}"
    )


    # ========================================================
    # 8. 检查本周文件
    # ========================================================

    if not os.path.exists(
        current_path
    ):

        raise FileNotFoundError(
            f"\n❌ 找不到本周漫播原始数据：\n"
            f"{current_path}\n\n"
            f"请先运行 fetch_manbo.py。"
        )


    # ========================================================
    # 9. 找到所有原始文件
    # ========================================================

    raw_files = find_raw_files()

    print()
    print(
        f"📚 找到 {len(raw_files)} "
        f"个原始漫播周数据文件"
    )


    # ========================================================
    # 10. 找当前日期之前最近的一份
    #
    # 例如：
    #
    # 当前：0929
    #
    # 0905
    # 0912
    # 0919
    # 0926
    # 0929
    #
    # 选择：
    #
    # 0926
    # ========================================================

    historical_files = []

    for path in raw_files:

        date_code = file_date(path)

        if not date_code:
            continue

        if date_code < current_date:

            historical_files.append(
                path
            )


    if not historical_files:

        print()
        print(
            "ℹ️ 没有找到本周之前的"
            "漫播历史数据。"
        )

        print(
            "ℹ️ 本周作为第一期，"
            "不计算周增。"
        )

        return


    previous_path = historical_files[-1]


    print(
        f"📄 上周文件："
        f"{os.path.basename(previous_path)}"
    )


    # ========================================================
    # 11. 读取 CSV
    # ========================================================

    print()
    print("📖 正在读取本周数据...")

    current_df = pd.read_csv(
        current_path,
        dtype=object
    )

    print(
        f"✅ 本周读取："
        f"{len(current_df)} 行"
    )


    print(
        "📖 正在读取上周数据..."
    )

    previous_df = pd.read_csv(
        previous_path,
        dtype=object
    )

    print(
        f"✅ 上周读取："
        f"{len(previous_df)} 行"
    )


    # ========================================================
    # 12. 检查 url
    # ========================================================

    if "url" not in current_df.columns:

        raise ValueError(
            "❌ 本周漫播数据没有 url 列。"
        )


    if "url" not in previous_df.columns:

        raise ValueError(
            "❌ 上周漫播数据没有 url 列。"
        )


    # ========================================================
    # 13. 清理 url
    # ========================================================

    current_df["url"] = normalize_url(
        current_df["url"]
    )

    previous_df["url"] = normalize_url(
        previous_df["url"]
    )


    # ========================================================
    # 14. 删除当前文件中已有的旧计算字段
    #
    # 防止重复运行 compare_manbo.py
    # 时把旧结果再次参与计算。
    # ========================================================

    drop_cols = []

    for col in current_df.columns:

        if (
            col.endswith("2")
            or col.endswith("周增")
            or col.endswith("周增率")
        ):

            drop_cols.append(
                col
            )


    current_df = current_df.drop(
        columns=drop_cols,
        errors="ignore"
    )


    # ========================================================
    # 15. 保留当前数据原始顺序
    #
    # 空行也属于当前文件结构，
    # 后面不删除。
    # ========================================================

    current_df["_original_order"] = range(
        len(current_df)
    )


    # ========================================================
    # 16. 准备上周数据
    # ========================================================

    previous_small_cols = [
        "url"
    ] + [
        col
        for col in NUMERIC_COLUMNS
        if col in previous_df.columns
    ]


    previous_small = previous_df[
        previous_small_cols
    ].copy()


    # ========================================================
    # 17. 上周重复 URL 只保留最后一条
    # ========================================================

    previous_small = (
        previous_small
        .drop_duplicates(
            subset=["url"],
            keep="last"
        )
    )


    # ========================================================
    # 18. 上周字段改名为 _prev
    #
    # 这样 merge 后不会把本周和上周
    # 混在一起。
    # ========================================================

    rename_previous = {}

    for col in NUMERIC_COLUMNS:

        if col in previous_small.columns:

            rename_previous[col] = (
                f"{col}_prev"
            )


    previous_small = previous_small.rename(
        columns=rename_previous
    )


    # ========================================================
    # 19. 合并
    #
    # 以本周数据为主。
    #
    # 新出现的剧：
    # 上周数值为空。
    #
    # 本周没有的剧：
    # 不出现在本周对比文件中。
    # ========================================================

    compare_df = current_df.merge(
        previous_small,
        on="url",
        how="left"
    )


    # ========================================================
    # 20. 本周值 -> *_2
    #
    # 例如：
    #
    # UID数量2 = 本周 UID
    # 播放量2 = 本周播放量
    # ========================================================

    for col in NUMERIC_COLUMNS:

        if col in compare_df.columns:

            compare_df[
                f"{col}2"
            ] = compare_df[col]


    # ========================================================
    # 21. 原字段改成上周值
    #
    # 例如：
    #
    # UID数量  = 上周
    # UID数量2 = 本周
    # ========================================================

    for col in NUMERIC_COLUMNS:

        previous_col = (
            f"{col}_prev"
        )

        if previous_col in compare_df.columns:

            compare_df[col] = (
                compare_df[
                    previous_col
                ]
            )

        else:

            # 没有上周数据时保持为空
            compare_df[col] = pd.NA


    # ========================================================
    # 22. 计算周增和周增率
    #
    # 周增：
    #
    #     本周 - 上周
    #
    # 周增率：
    #
    #     周增 / 上周
    # ========================================================

    for col in NUMERIC_COLUMNS:

        current_col = (
            f"{col}2"
        )

        increase_col = (
            f"{col}周增"
        )

        rate_col = (
            f"{col}周增率"
        )


        if (
            col not in compare_df.columns
            or
            current_col not in compare_df.columns
        ):

            continue


        previous_values = numeric(
            compare_df[col]
        )

        current_values = numeric(
            compare_df[current_col]
        )


        # ----------------------------------------------------
        # 周增
        # ----------------------------------------------------

        compare_df[increase_col] = (
            current_values
            -
            previous_values
        )


        # ----------------------------------------------------
        # 周增率
        # ----------------------------------------------------

        denominator = (
            previous_values
            .replace(
                0,
                pd.NA
            )
        )


        compare_df[rate_col] = (
            compare_df[increase_col]
            /
            denominator
        )


    # ========================================================
    # 23. 删除辅助字段
    # ========================================================

    helper_columns = [
        "_original_order"
    ] + [
        f"{col}_prev"
        for col in NUMERIC_COLUMNS
    ]


    compare_df = compare_df.drop(
        columns=[
            col
            for col in helper_columns
            if col in compare_df.columns
        ],
        errors="ignore"
    )


    # ========================================================
    # 24. 调整列顺序
    # ========================================================

    original_cols = [
        col
        for col in current_df.columns
        if col != "_original_order"
    ]


    generated_cols = []


    for col in NUMERIC_COLUMNS:

        for suffix in [
            "2",
            "周增",
            "周增率",
        ]:

            generated = (
                f"{col}{suffix}"
            )

            if generated in compare_df.columns:

                generated_cols.append(
                    generated
                )


    # ========================================================
    # 25. 剩余字段
    # ========================================================

    remaining = [
        col
        for col in compare_df.columns
        if col not in original_cols
        and col not in generated_cols
        and not col.endswith("_prev")
    ]


    final_cols = [
        col
        for col in original_cols
        if col in compare_df.columns
    ]


    final_cols += generated_cols
    final_cols += remaining


    final_cols = list(
        dict.fromkeys(
            final_cols
        )
    )


    compare_df = compare_df[
        final_cols
    ]


    # ========================================================
    # 26. 输出 CSV
    # ========================================================

    output_filename = (
        f"漫播周数据对比版"
        f"{current_date}.csv"
    )


    output_path = os.path.join(
        OUTPUT_DIR,
        output_filename
    )


    compare_df.to_csv(
        output_path,
        index=False,
        encoding="utf-8-sig"
    )


    # ========================================================
    # 27. 输出统计
    # ========================================================

    print()
    print("=" * 70)
    print("📊 漫播周增计算完成")
    print("=" * 70)

    print(
        f"🔑 匹配字段：url"
    )

    print(
        f"📄 本周："
        f"{os.path.basename(current_path)}"
    )

    print(
        f"📄 上周："
        f"{os.path.basename(previous_path)}"
    )

    print(
        f"📄 输出："
        f"{output_filename}"
    )

    print(
        f"📊 本周行数："
        f"{len(current_df)}"
    )

    print(
        f"📊 上周行数："
        f"{len(previous_df)}"
    )


    # ========================================================
    # 28. 匹配统计
    # ========================================================

    if "UID数量" in compare_df.columns:

        matched_count = (
            numeric(
                compare_df["UID数量"]
            )
            .notna()
            .sum()
        )

        print(
            f"🔗 匹配到上周："
            f"{matched_count}"
        )


    # ========================================================
    # 29. 新剧数量
    # ========================================================

    if "UID数量" in compare_df.columns:

        new_count = (
            numeric(
                compare_df["UID数量"]
            )
            .isna()
            &
            numeric(
                compare_df["UID数量2"]
            ).notna()
        ).sum()

        print(
            f"🆕 本周新出现："
            f"{new_count}"
        )


    # ========================================================
    # 30. 输出几个样本
    # ========================================================

    debug_columns = [
        "剧名",
        "url",
        "UID数量",
        "UID数量2",
        "UID数量周增",
        "播放量",
        "播放量2",
        "播放量周增",
        "收藏数",
        "收藏数2",
        "收藏数周增",
        "实际付费人数",
        "实际付费人数2",
        "实际付费人数周增",
    ]


    debug_columns = [
        col
        for col in debug_columns
        if col in compare_df.columns
    ]


    print()
    print("🔎 前 5 行对比结果：")
    print("-" * 70)


    if debug_columns:

        print(
            compare_df[
                debug_columns
            ]
            .head(5)
            .to_string(
                index=False
            )
        )


    print()
    print("=" * 70)
    print("✅ 全部完成")
    print("=" * 70)


# ============================================================
# Entry point
# ============================================================

if __name__ == "__main__":

    main()
