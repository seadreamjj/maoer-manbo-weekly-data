
# ============================================================
# 猫耳每周数据对比
# GitHub Actions 版本
#
# 功能：
# 1. 自动读取 output/猫耳周数据MMDD.csv
# 2. 自动寻找当前周之前最近的一份原始猫耳周数据 CSV
# 3. 计算：
#       ID周增
#       总弹幕周增
#       追剧周增
#       播放周增
#       追剧周增率
#       播放周增率
#       比例差
#       本周ID活跃比
# 4. 空行保留，不参与计算
# 5. 输出：
#       output/猫耳周数据对比版MMDD.csv
#
# 数据逻辑：
#
#   id       = 上周 UID
#   id2      = 本周 UID
#
#   总弹幕   = 上周总弹幕
#   总弹幕2  = 本周总弹幕
#
#   追剧人数   = 上周追剧人数
#   追剧人数2  = 本周追剧人数
#
#   播放量   = 上周播放量
#   播放量2  = 本周播放量
#
#   周增 = 本周 - 上周
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
# 2. 字段
# ============================================================

CURRENT_COLUMNS = [
    "id",
    "总弹幕",
    "追剧人数",
    "播放量",
]


DERIVED_COLUMNS = [
    "id2",
    "总弹幕2",
    "追剧人数2",
    "播放量2",
    "ID周增",
    "总弹幕周增",
    "追剧周增",
    "播放周增",
    "追剧周增率",
    "播放周增率",
    "比例差",
    "本周ID活跃比",
]


# ============================================================
# 3. 从文件名获取日期
#
# 例如：
#
# 猫耳周数据0929.csv
#
# 返回：
#
# 0929
# ============================================================

def file_date(path):

    name = os.path.basename(path)

    match = re.fullmatch(
        r"猫耳周数据(\d{4})\.csv",
        name
    )

    if not match:
        return None

    return match.group(1)


# ============================================================
# 4. 找到所有“原始周数据 CSV”
#
# 注意：
#
# 这里只匹配：
#
#   猫耳周数据0929.csv
#
# 不会匹配：
#
#   猫耳周数据对比版0929.csv
# ============================================================

def find_raw_files():

    paths = []

    if not os.path.exists(OUTPUT_DIR):
        return paths

    for name in os.listdir(OUTPUT_DIR):

        path = os.path.join(
            OUTPUT_DIR,
            name
        )

        if not os.path.isfile(path):
            continue

        if re.fullmatch(
            r"猫耳周数据\d{4}\.csv",
            name
        ):
            paths.append(path)

    return sorted(
        paths,
        key=lambda p: (
            file_date(p) or "",
            os.path.getmtime(p)
        )
    )


# ============================================================
# 5. 数值转换
# ============================================================

def safe_numeric(series):

    return pd.to_numeric(
        series,
        errors="coerce"
    )


# ============================================================
# 6. 清理匹配键
#
# 支持：
#
# 85974
# 85974.0
# "85974"
# "85974.0"
# ============================================================

def normalize_key(series):

    return (
        series
        .astype("string")
        .str.strip()
        .str.replace(
            r"\.0$",
            "",
            regex=True
        )
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
    # 当前日期
    # ========================================================

    now = datetime.now(TZ)

    current_date_code = now.strftime(
        "%m%d"
    )


    current_filename = (
        f"猫耳周数据{current_date_code}.csv"
    )

    current_path = os.path.join(
        OUTPUT_DIR,
        current_filename
    )


    print()
    print("=" * 70)
    print("📊 猫耳每周数据对比")
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

    if not os.path.exists(current_path):

        raise FileNotFoundError(
            f"\n❌ 找不到本周猫耳数据：\n"
            f"{current_path}\n\n"
            f"请先运行 fetch_maoer.py。"
        )


    # ========================================================
    # 9. 找到所有历史原始 CSV
    # ========================================================

    raw_files = find_raw_files()

    print()
    print(
        f"📚 找到 {len(raw_files)} 个原始周数据文件"
    )


    if not raw_files:

        print(
            "⚠️ 没有找到任何历史原始数据。"
        )

        return


    # ========================================================
    # 10. 寻找“当前日期之前最近的一份”
    #
    # 非常重要：
    #
    # 例如当前：
    #
    # 0929
    #
    # 文件：
    #
    # 猫耳周数据0905.csv
    # 猫耳周数据0912.csv
    # 猫耳周数据0919.csv
    # 猫耳周数据0926.csv
    # 猫耳周数据0929.csv
    #
    # 会选择：
    #
    # 猫耳周数据0926.csv
    #
    # 而不会选择未来日期文件。
    # ========================================================

    historical_files = []

    for path in raw_files:

        date_code = file_date(path)

        if not date_code:
            continue

        if date_code < current_date_code:

            historical_files.append(path)


    if not historical_files:

        print()
        print(
            "ℹ️ 没有找到本周之前的历史数据。"
        )

        print(
            "ℹ️ 本周作为第一期，不计算周增。"
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
    # 12. 确定匹配字段
    #
    # 优先使用 url
    #
    # 因为 url 实际上就是 drama_id。
    #
    # 如果没有 url，
    # 再尝试 id。
    # ========================================================

    if (
        "url" in current_df.columns
        and
        "url" in previous_df.columns
    ):

        key = "url"

    elif (
        "id" in current_df.columns
        and
        "id" in previous_df.columns
    ):

        key = "id"

    else:

        raise ValueError(
            "❌ 当前周和上周没有共同的 "
            "url / id 匹配字段。"
        )


    print(
        f"🔑 匹配字段：{key}"
    )


    # ========================================================
    # 13. 删除旧的计算字段
    #
    # 防止重复运行 compare_maoer.py
    # 时产生旧数据。
    # ========================================================

    current_df = current_df.drop(
        columns=[
            c
            for c in DERIVED_COLUMNS
            if c in current_df.columns
        ],
        errors="ignore"
    )


    # ========================================================
    # 14. 保存原始顺序
    #
    # 特别注意：
    #
    # 空行也属于当前 CSV 的结构。
    #
    # 因此后面不直接 drop 空行。
    # ========================================================

    current_df["_original_order"] = range(
        len(current_df)
    )


    # ========================================================
    # 15. 准备上周数据
    # ========================================================

    previous_columns = [
        key
    ] + [
        col
        for col in CURRENT_COLUMNS
        if col in previous_df.columns
    ]


    previous_small = previous_df[
        previous_columns
    ].copy()


    # ========================================================
    # 16. 清理匹配字段
    # ========================================================

    current_df[key] = normalize_key(
        current_df[key]
    )

    previous_small[key] = normalize_key(
        previous_small[key]
    )


    # ========================================================
    # 17. 上周重复剧只保留最后一条
    # ========================================================

    previous_small = previous_small.drop_duplicates(
        subset=[key],
        keep="last"
    )


    # ========================================================
    # 18. 上周字段改成 _prev
    #
    # 防止 merge 后 current / previous
    # 混在一起。
    # ========================================================

    rename_previous = {
        "id": "id_prev",
        "总弹幕": "总弹幕_prev",
        "追剧人数": "追剧人数_prev",
        "播放量": "播放量_prev",
    }


    previous_small = previous_small.rename(
        columns=rename_previous
    )


    # ========================================================
    # 19. 合并
    #
    # how="left"
    #
    # 以本周剧目为主。
    #
    # 新上榜的剧：
    # 上周数据为空。
    #
    # 这非常重要。
    # ========================================================

    compare_df = current_df.merge(
        previous_small,
        on=key,
        how="left"
    )


    # ========================================================
    # 20. 本周数据 -> 2
    #
    # id2 = 本周
    # 总弹幕2 = 本周
    # ...
    # ========================================================

    for col in CURRENT_COLUMNS:

        if col in compare_df.columns:

            compare_df[
                f"{col}2"
            ] = compare_df[col]


    # ========================================================
    # 21. 原字段改成“上周”
    #
    # 最终：
    #
    # id  = 上周
    # id2 = 本周
    #
    # 总弹幕  = 上周
    # 总弹幕2 = 本周
    #
    # ...
    # ========================================================

    previous_mapping = {
        "id": "id_prev",
        "总弹幕": "总弹幕_prev",
        "追剧人数": "追剧人数_prev",
        "播放量": "播放量_prev",
    }


    for current_col, previous_col in previous_mapping.items():

        if previous_col in compare_df.columns:

            compare_df[current_col] = (
                compare_df[previous_col]
            )


    # ========================================================
    # 22. 周增
    #
    # 本周 - 上周
    # ========================================================

    compare_df["ID周增"] = (
        safe_numeric(compare_df["id2"])
        -
        safe_numeric(compare_df["id"])
    )


    compare_df["总弹幕周增"] = (
        safe_numeric(compare_df["总弹幕2"])
        -
        safe_numeric(compare_df["总弹幕"])
    )


    compare_df["追剧周增"] = (
        safe_numeric(compare_df["追剧人数2"])
        -
        safe_numeric(compare_df["追剧人数"])
    )


    compare_df["播放周增"] = (
        safe_numeric(compare_df["播放量2"])
        -
        safe_numeric(compare_df["播放量"])
    )


    # ========================================================
    # 23. 周增率
    #
    # 基数 = 上周
    # ========================================================

    previous_follow = safe_numeric(
        compare_df["追剧人数"]
    )

    previous_play = safe_numeric(
        compare_df["播放量"]
    )


    compare_df["追剧周增率"] = (
        compare_df["追剧周增"]
        /
        previous_follow.replace(
            0,
            pd.NA
        )
    )


    compare_df["播放周增率"] = (
        compare_df["播放周增"]
        /
        previous_play.replace(
            0,
            pd.NA
        )
    )


    # ========================================================
    # 24. 比例差
    #
    # 播放增长率 / 追剧增长率
    # ========================================================

    compare_df["比例差"] = (
        compare_df["播放周增率"]
        /
        compare_df[
            "追剧周增率"
        ].replace(
            0,
            pd.NA
        )
    )


    # ========================================================
    # 25. 本周 ID 活跃比
    #
    # 本周 UID / 本周追剧人数
    # ========================================================

    compare_df["本周ID活跃比"] = (
        safe_numeric(
            compare_df["id2"]
        )
        /
        safe_numeric(
            compare_df["追剧人数2"]
        ).replace(
            0,
            pd.NA
        )
    )


    # ========================================================
    # 26. 删除辅助字段
    # ========================================================

    helper_columns = [
        "id_prev",
        "总弹幕_prev",
        "追剧人数_prev",
        "播放量_prev",
        "_original_order",
    ]


    compare_df = compare_df.drop(
        columns=[
            c
            for c in helper_columns
            if c in compare_df.columns
        ],
        errors="ignore"
    )


    # ========================================================
    # 27. 调整列顺序
    # ========================================================

    preferred = []


    # 原始字段首先保留
    original_first = [
        "剧名",
        "url",
        "更新集数",
        "付费集数",
    ]


    for col in original_first:

        if col in compare_df.columns:

            preferred.append(col)


    # 上周 / 本周核心数据
    preferred += [
        "id",
        "id2",
        "总弹幕",
        "总弹幕2",
        "追剧人数",
        "追剧人数2",
        "播放量",
        "播放量2",
    ]


    # 周增
    preferred += [
        "ID周增",
        "总弹幕周增",
        "追剧周增",
        "播放周增",
        "追剧周增率",
        "播放周增率",
        "比例差",
        "本周ID活跃比",
    ]


    # 抓取错误放最后
    if "抓取错误" in compare_df.columns:

        preferred.append(
            "抓取错误"
        )


    # 去重
    preferred = list(
        dict.fromkeys(
            preferred
        )
    )


    # 剩余字段
    remaining = [
        col
        for col in compare_df.columns
        if col not in preferred
    ]


    compare_df = compare_df[
        preferred + remaining
    ]

    # 整数型字段去掉 .0
    for col in compare_df.columns:
        if (
            col.endswith("2")
            or col.endswith("周增")
        ):
            compare_df[col] = pd.to_numeric(
                compare_df[col],
                errors="coerce"
            ).round().astype("Int64")


    # ========================================================
    # 28. 输出文件
    # ========================================================

    output_filename = (
        f"猫耳周数据对比版"
        f"{current_date_code}.csv"
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
    # 29. 调试输出
    # ========================================================

    print()
    print("=" * 70)
    print("📊 猫耳周增计算完成")
    print("=" * 70)

    print(
        f"🔑 匹配字段：{key}"
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
    # 30. 匹配统计
    # ========================================================

    if key in compare_df.columns:

        key_values = (
            compare_df[key]
            .astype("string")
            .str.strip()
        )

        matched_count = (
            key_values.notna()
            &
            key_values.ne("")
        ).sum()

        print(
            f"🔗 有效匹配键："
            f"{matched_count}"
        )


    # ========================================================
    # 31. 输出几个样本
    # ========================================================

    debug_columns = [
        "剧名",
        key,
        "id",
        "id2",
        "ID周增",
        "总弹幕",
        "总弹幕2",
        "总弹幕周增",
        "追剧人数",
        "追剧人数2",
        "追剧周增",
        "播放量",
        "播放量2",
        "播放周增",
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
            ].head(5).to_string(
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
