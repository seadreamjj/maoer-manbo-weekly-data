import os
import re
from datetime import datetime

import pandas as pd
import pytz


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_DIR = os.path.join(ROOT, "output")

TZ = pytz.timezone("Asia/Shanghai")


# 本周和上周都需要保存的主要数值字段
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


def find_raw_files():
    paths = []

    if not os.path.exists(OUTPUT_DIR):
        return paths

    for name in os.listdir(OUTPUT_DIR):
        if re.fullmatch(
            r"漫播周数据\d{4}\.xlsx",
            name
        ):
            paths.append(
                os.path.join(
                    OUTPUT_DIR,
                    name
                )
            )

    def sort_key(path):
        name = os.path.basename(path)
        match = re.search(
            r"漫播周数据(\d{4})\.xlsx$",
            name
        )

        if match:
            return (
                match.group(1),
                os.path.getmtime(path)
            )

        return (
            "",
            os.path.getmtime(path)
        )

    return sorted(
        paths,
        key=sort_key
    )


def numeric(series):
    return pd.to_numeric(
        series,
        errors="coerce"
    )


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    now = datetime.now(TZ)
    current_date = now.strftime("%m%d")

    current_path = os.path.join(
        OUTPUT_DIR,
        f"漫播周数据{current_date}.xlsx"
    )

    if not os.path.exists(current_path):
        raise FileNotFoundError(
            f"找不到本周漫播原始数据：{current_path}"
        )

    raw_files = find_raw_files()

    previous_files = [
        p for p in raw_files
        if os.path.abspath(p)
        != os.path.abspath(current_path)
    ]

    if not previous_files:
        print("没有找到上一周漫播原始数据。")
        print("本周作为第一期，只保留原始数据。")
        return

    previous_path = previous_files[-1]

    print(f"本周：{current_path}")
    print(f"上周：{previous_path}")

    current_df = pd.read_excel(
        current_path
    )

    previous_df = pd.read_excel(
        previous_path
    )

    if "url" not in current_df.columns:
        raise ValueError(
            "本周漫播数据没有 url 列。"
        )

    if "url" not in previous_df.columns:
        raise ValueError(
            "上周漫播数据没有 url 列。"
        )

    current_df["url"] = (
        current_df["url"]
        .astype(str)
        .str.strip()
    )

    previous_df["url"] = (
        previous_df["url"]
        .astype(str)
        .str.strip()
    )

    previous_small_cols = [
        "url"
    ] + [
        c for c in NUMERIC_COLUMNS
        if c in previous_df.columns
    ]

    previous_small = previous_df[
        previous_small_cols
    ].drop_duplicates(
        subset=["url"],
        keep="last"
    )

    # 避免本周文件已有旧的 *_2 / 周增字段
    drop_cols = []

    for col in current_df.columns:
        if (
            col.endswith("2")
            or col.endswith("周增")
            or col.endswith("周增率")
        ):
            drop_cols.append(col)

    current_df = current_df.drop(
        columns=drop_cols,
        errors="ignore"
    )

    compare_df = current_df.merge(
        previous_small,
        on="url",
        how="left",
        suffixes=("", "_上周")
    )

    # --------------------------------------------------------
    # 本周字段复制为 *_2
    # 上周原值保留原名
    # --------------------------------------------------------

    for col in NUMERIC_COLUMNS:
        if col in compare_df.columns:
            compare_df[f"{col}2"] = compare_df[col]

    # --------------------------------------------------------
    # 周增
    # --------------------------------------------------------

    for col in NUMERIC_COLUMNS:
        current_col = f"{col}2"

        if (
            col in compare_df.columns
            and current_col in compare_df.columns
        ):
            compare_df[f"{col}周增"] = (
                numeric(compare_df[current_col])
                - numeric(compare_df[col])
            )

            previous_value = numeric(
                compare_df[col]
            ).replace(0, pd.NA)

            compare_df[f"{col}周增率"] = (
                compare_df[f"{col}周增"]
                / previous_value
            )

    # --------------------------------------------------------
    # 输出列顺序
    # --------------------------------------------------------

    original_cols = list(
        current_df.columns
    )

    generated_cols = []

    for col in NUMERIC_COLUMNS:
        for suffix in [
            "2",
            "周增",
            "周增率",
        ]:
            generated = f"{col}{suffix}"

            if generated in compare_df.columns:
                generated_cols.append(generated)

    # 去掉 merge 后意外残留的上周辅助列
    remaining = [
        c for c in compare_df.columns
        if c not in original_cols
        and c not in generated_cols
        and not c.endswith("_上周")
    ]

    final_cols = [
        c for c in original_cols
        if c in compare_df.columns
    ]

    final_cols += generated_cols
    final_cols += remaining

    final_cols = list(
        dict.fromkeys(final_cols)
    )

    compare_df = compare_df[
        final_cols
    ]

    output_path = os.path.join(
        OUTPUT_DIR,
        f"漫播周数据对比版{current_date}.xlsx"
    )

    compare_df.to_excel(
        output_path,
        index=False
    )

    print("\n" + "=" * 70)
    print("漫播周增计算完成")
    print("=" * 70)
    print(f"匹配字段：url")
    print(f"本周：{current_path}")
    print(f"上周：{previous_path}")
    print(f"输出：{output_path}")
    print(f"本周剧数：{len(current_df)}")

    # 以 UID 为例报告匹配情况
    if "UID数量" in compare_df.columns:
        print(
            "匹配到上周："
            f"{compare_df['UID数量'].notna().sum()}"
        )


if __name__ == "__main__":
    main()
