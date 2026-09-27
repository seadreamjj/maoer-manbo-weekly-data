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
# ============================================================

def file_date(path):

    name = os.path.basename(path)

    match = re.fullmatch(
        r"猫耳周数据(\d{4})\.xlsx",
        name
    )

    if not match:
        return None

    return match.group(1)


# ============================================================
# 4. 找到所有原始周数据
#
# 只匹配：
#
# 猫耳周数据0925.xlsx
#
# 不匹配：
#
# 猫耳周数据对比版0925.xlsx
# ============================================================

def find_raw_files():

    paths = []

    if not os.path.exists(
        OUTPUT_DIR
    ):
        return paths

    for name in os.listdir(
        OUTPUT_DIR
    ):

        path = os.path.join(
            OUTPUT_DIR,
            name
        )

        if not os.path.isfile(path):
            continue

        if re.fullmatch(
            r"猫耳周数据\d{4}\.xlsx",
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
# 6. 主程序
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

    current_date = now.strftime(
        "%m%d"
    )


    current_path = os.path.join(
        OUTPUT_DIR,
        f"猫耳周数据{current_date}.xlsx"
    )


    if not os.path.exists(
        current_path
    ):

        raise FileNotFoundError(
            f"找不到本周猫耳原始数据："
            f"{current_path}"
        )


    # ========================================================
    # 找所有原始文件
    # ========================================================

    raw_files = find_raw_files()


    if not raw_files:

        raise FileNotFoundError(
            "output 中没有找到猫耳周数据原始文件。"
        )


    print()
    print("=" * 70)
    print("猫耳周增数据计算")
    print("=" * 70)

    print("\n找到的原始文件：")

    for path in raw_files:

        print(
            f"  - {os.path.basename(path)}"
        )


    # ========================================================
    # 找“当前文件之前”的最近一期
    #
    # 不直接使用 previous_files[-1]
    # 防止仓库里存在未来日期文件。
    # ========================================================

    current_date_code = file_date(
        current_path
    )


    previous_files = [
        p
        for p in raw_files
        if (
            os.path.abspath(p)
            != os.path.abspath(current_path)
            and file_date(p) is not None
            and file_date(p) < current_date_code
        )
    ]


    # ========================================================
    # 第一周
    # ========================================================

    if not previous_files:

        print()
        print(
            "没有找到本周之前的历史数据。"
        )

        print(
            "本周作为第一期，"
            "不计算周增。"
        )

        return


    # 最近的一期历史数据
    previous_path = previous_files[-1]


    print()
    print(
        f"本周："
        f"{os.path.basename(current_path)}"
    )

    print(
        f"上期："
        f"{os.path.basename(previous_path)}"
    )


    # ========================================================
    # 读取
    # ========================================================

    current_df = pd.read_excel(
        current_path
    )

    previous_df = pd.read_excel(
        previous_path
    )


    # ========================================================
    # 选择匹配键
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
            "当前周和上一周没有共同的 "
            "url / id 匹配字段。"
        )


    print(
        f"匹配字段：{key}"
    )


    # ========================================================
    # 清理 key
    # ========================================================

    current_df[key] = (
        current_df[key]
        .astype(str)
        .str.strip()
        .str.replace(
            r"\.0$",
            "",
            regex=True
        )
    )


    previous_df[key] = (
        previous_df[key]
        .astype(str)
        .str.strip()
        .str.replace(
            r"\.0$",
            "",
            regex=True
        )
    )


    # ========================================================
    # 删除当前数据中可能残留的旧计算字段
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
    # 检查必要字段
    # ========================================================

    missing_current = [
        c
        for c in CURRENT_COLUMNS
        if c not in current_df.columns
    ]

    missing_previous = [
        c
        for c in CURRENT_COLUMNS
        if c not in previous_df.columns
    ]


    if missing_current:

        raise ValueError(
            "本周文件缺少字段："
            + ", ".join(
                missing_current
            )
        )


    if missing_previous:

        raise ValueError(
            "上周文件缺少字段："
            + ", ".join(
                missing_previous
            )
        )


    # ========================================================
    # 上周数据
    #
    # 注意：
    # 这里主动改成 *_prev
    #
    # 防止 merge 后出现：
    #
    # id
    # id_上周
    #
    # 导致逻辑混乱。
    # ========================================================

    previous_small = previous_df[
        [
            key
        ] + CURRENT_COLUMNS
    ].copy()


    # 同一个 url 如果出现多次，
    # 保留最后一条
    previous_small = (
        previous_small
        .drop_duplicates(
            subset=[key],
            keep="last"
        )
    )


    # 重命名成明确的上周字段

    previous_small = previous_small.rename(
        columns={
            "id": "id_prev",
            "总弹幕": "总弹幕_prev",
            "追剧人数": "追剧人数_prev",
            "播放量": "播放量_prev",
        }
    )


    # ========================================================
    # Merge
    # ========================================================

    compare_df = current_df.merge(
        previous_small,
        on=key,
        how="left"
    )


    # ========================================================
    # 非常重要：
    #
    # 现在：
    #
    # id          = 本周
    # id_prev     = 上周
    #
    # 所以：
    #
    # id2         = 本周
    # id          = 上周
    #
    # 也就是说，先把本周复制到 *_2，
    # 再把 id 等字段替换成上周。
    # ========================================================


    # --------------------------------------------------------
    # 本周数据 → *_2
    # --------------------------------------------------------

    compare_df["id2"] = (
        compare_df["id"]
    )

    compare_df["总弹幕2"] = (
        compare_df["总弹幕"]
    )

    compare_df["追剧人数2"] = (
        compare_df["追剧人数"]
    )

    compare_df["播放量2"] = (
        compare_df["播放量"]
    )


    # --------------------------------------------------------
    # 上周数据 → 原字段
    # --------------------------------------------------------

    compare_df["id"] = (
        compare_df["id_prev"]
    )

    compare_df["总弹幕"] = (
        compare_df["总弹幕_prev"]
    )

    compare_df["追剧人数"] = (
        compare_df["追剧人数_prev"]
    )

    compare_df["播放量"] = (
        compare_df["播放量_prev"]
    )


    # ========================================================
    # 周增
    #
    # 本周 - 上周
    # ========================================================

    compare_df["ID周增"] = (
        safe_numeric(
            compare_df["id2"]
        )
        -
        safe_numeric(
            compare_df["id"]
        )
    )


    compare_df["总弹幕周增"] = (
        safe_numeric(
            compare_df["总弹幕2"]
        )
        -
        safe_numeric(
            compare_df["总弹幕"]
        )
    )


    compare_df["追剧周增"] = (
        safe_numeric(
            compare_df["追剧人数2"]
        )
        -
        safe_numeric(
            compare_df["追剧人数"]
        )
    )


    compare_df["播放周增"] = (
        safe_numeric(
            compare_df["播放量2"]
        )
        -
        safe_numeric(
            compare_df["播放量"]
        )
    )


    # ========================================================
    # 周增率
    #
    # （本周 - 上周） / 上周
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
    # 比例差
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
    # 本周 ID 活跃比
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
    # 删除内部辅助字段
    # ========================================================

    compare_df = compare_df.drop(
        columns=[
            "id_prev",
            "总弹幕_prev",
            "追剧人数_prev",
            "播放量_prev",
        ],
        errors="ignore"
    )


    # ========================================================
    # 列顺序
    # ========================================================

    preferred = []


    # 先保留原始字段
    for col in current_df.columns:

        if col in compare_df.columns:

            preferred.append(col)


    # 再放核心比较字段
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


    preferred = list(
        dict.fromkeys(
            c
            for c in preferred
            if c in compare_df.columns
        )
    )


    remaining = [
        c
        for c in compare_df.columns
        if c not in preferred
    ]


    compare_df = compare_df[
        preferred + remaining
    ]


    # ========================================================
    # 保存
    # ========================================================

    output_path = os.path.join(
        OUTPUT_DIR,
        f"猫耳周数据对比版{current_date}.xlsx"
    )


    compare_df.to_excel(
        output_path,
        index=False
    )


    # ========================================================
    # 输出统计
    # ========================================================

    matched_count = (
        compare_df["id"]
        .notna()
        .sum()
    )


    print()
    print("=" * 70)
    print("✅ 猫耳周增计算完成")
    print("=" * 70)

    print(
        f"本周："
        f"{os.path.basename(current_path)}"
    )

    print(
        f"上期："
        f"{os.path.basename(previous_path)}"
    )

    print(
        f"匹配字段：{key}"
    )

    print(
        f"本周剧数："
        f"{len(current_df)}"
    )

    print(
        f"匹配到上期："
        f"{matched_count}"
    )

    print(
        f"未匹配："
        f"{len(compare_df) - matched_count}"
    )

    print(
        f"输出：{output_path}"
    )

    print("=" * 70)


    # ========================================================
    # 简单检查前几行
    # ========================================================

    check_columns = [
        key,
        "id",
        "id2",
        "ID周增",
        "追剧人数",
        "追剧人数2",
        "追剧周增",
        "播放量",
        "播放量2",
        "播放周增",
    ]

    check_columns = [
        c
        for c in check_columns
        if c in compare_df.columns
    ]


    print()
    print("前 5 行周增检查：")
    print(
        compare_df[
            check_columns
        ].head(5).to_string(
            index=False
        )
    )


if __name__ == "__main__":
    main()
