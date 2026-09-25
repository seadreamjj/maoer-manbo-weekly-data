import os
import re
from datetime import datetime

import pandas as pd
import pytz


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_DIR = os.path.join(ROOT, "output")
TZ = pytz.timezone("Asia/Shanghai")


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


def file_date(path):
    name = os.path.basename(path)
    match = re.search(r"猫耳周数据(\d{4})\.csv$", name)

    if not match:
        return None

    return match.group(1)


def find_raw_files():
    paths = []

    if not os.path.exists(OUTPUT_DIR):
        return paths

    for name in os.listdir(OUTPUT_DIR):
        path = os.path.join(OUTPUT_DIR, name)

        if not os.path.isfile(path):
            continue

        if re.fullmatch(r"猫耳周数据\d{4}\.csv", name):
            paths.append(path)

    return sorted(
        paths,
        key=lambda p: (
            file_date(p) or "",
            os.path.getmtime(p)
        )
    )


def safe_numeric(series):
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
        f"猫耳周数据{current_date}.csv"
    )

    if not os.path.exists(current_path):
        raise FileNotFoundError(
            f"找不到本周猫耳原始数据：{current_path}"
        )

    raw_files = find_raw_files()

    previous_files = [
        p for p in raw_files
        if os.path.abspath(p) != os.path.abspath(current_path)
    ]

    if not previous_files:
        print("没有找到上一周猫耳原始数据。")
        print("本周作为第一期，只保留原始数据，不计算周增。")
        return

    previous_path = previous_files[-1]

    print(f"本周：{current_path}")
    print(f"上周：{previous_path}")

    current_df = pd.read_excel(current_path)
    previous_df = pd.read_excel(previous_path)

    # --------------------------------------------------------
    # 选择匹配键
    # --------------------------------------------------------

    if "url" in current_df.columns and "url" in previous_df.columns:
        key = "url"
    elif "id" in current_df.columns and "id" in previous_df.columns:
        key = "id"
    else:
        raise ValueError(
            "当前周和上一周没有共同的 url / id 匹配字段。"
        )

    # --------------------------------------------------------
    # 删除可能残留的旧计算列
    # --------------------------------------------------------

    current_df = current_df.drop(
        columns=[
            c for c in DERIVED_COLUMNS
            if c in current_df.columns
        ],
        errors="ignore"
    )

    previous_small = previous_df[
        [c for c in [key] + CURRENT_COLUMNS if c in previous_df.columns]
    ].copy()

    previous_small = previous_small.drop_duplicates(
        subset=[key],
        keep="last"
    )

    # --------------------------------------------------------
    # 统一 key
    # --------------------------------------------------------

    current_df[key] = current_df[key].astype(str).str.strip()
    previous_small[key] = previous_small[key].astype(str).str.strip()

    # --------------------------------------------------------
    # 保存上周数值
    # --------------------------------------------------------

    rename_previous = {
        "id": "id",
        "总弹幕": "总弹幕",
        "追剧人数": "追剧人数",
        "播放量": "播放量",
    }

    previous_small = previous_small.rename(
        columns=rename_previous
    )

    compare_df = current_df.merge(
        previous_small,
        on=key,
        how="left",
        suffixes=("", "_上周")
    )

    # --------------------------------------------------------
    # 当前周字段 → *_2
    # 上周字段保留原名
    # --------------------------------------------------------

    for col in CURRENT_COLUMNS:
        if col in compare_df.columns:
            compare_df[f"{col}2"] = compare_df[col]

    # --------------------------------------------------------
    # 计算周增
    # --------------------------------------------------------

    compare_df["ID周增"] = (
        safe_numeric(compare_df["id2"])
        - safe_numeric(compare_df["id"])
    )

    compare_df["总弹幕周增"] = (
        safe_numeric(compare_df["总弹幕2"])
        - safe_numeric(compare_df["总弹幕"])
    )

    compare_df["追剧周增"] = (
        safe_numeric(compare_df["追剧人数2"])
        - safe_numeric(compare_df["追剧人数"])
    )

    compare_df["播放周增"] = (
        safe_numeric(compare_df["播放量2"])
        - safe_numeric(compare_df["播放量"])
    )

    # --------------------------------------------------------
    # 周增率
    # --------------------------------------------------------

    previous_follow = safe_numeric(
        compare_df["追剧人数"]
    )

    previous_play = safe_numeric(
        compare_df["播放量"]
    )

    compare_df["追剧周增率"] = (
        compare_df["追剧周增"]
        / previous_follow.replace(0, pd.NA)
    )

    compare_df["播放周增率"] = (
        compare_df["播放周增"]
        / previous_play.replace(0, pd.NA)
    )

    # --------------------------------------------------------
    # 播放增长 / 追剧增长
    # --------------------------------------------------------

    compare_df["比例差"] = (
        compare_df["播放周增率"]
        / compare_df["追剧周增率"].replace(0, pd.NA)
    )

    # --------------------------------------------------------
    # 本周 ID / 追剧人数
    # --------------------------------------------------------

    compare_df["本周ID活跃比"] = (
        safe_numeric(compare_df["id2"])
        / safe_numeric(
            compare_df["追剧人数2"]
        ).replace(0, pd.NA)
    )

    # --------------------------------------------------------
    # 列顺序
    # --------------------------------------------------------

    preferred = []

    for col in current_df.columns:
        if col in compare_df.columns:
            preferred.append(col)

    preferred += [
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

    preferred = list(dict.fromkeys(
        c for c in preferred
        if c in compare_df.columns
    ))

    remaining = [
        c for c in compare_df.columns
        if c not in preferred
        and not c.endswith("_上周")
    ]

    compare_df = compare_df[
        preferred + remaining
    ]

    # --------------------------------------------------------
    # 保存
    # --------------------------------------------------------

    output_path = os.path.join(
        OUTPUT_DIR,
        f"猫耳周数据对比版{current_date}.csv"
    )

    compare_df.to_csv(
        output_path,
        index=False
    )

    print("\n" + "=" * 70)
    print("猫耳周增计算完成")
    print("=" * 70)
    print(f"匹配字段：{key}")
    print(f"本周：{current_path}")
    print(f"上周：{previous_path}")
    print(f"输出：{output_path}")
    print(f"本周剧数：{len(current_df)}")
    print(
        f"匹配到上周："
        f"{compare_df['id'].notna().sum()}"
    )


if __name__ == "__main__":
    main()
