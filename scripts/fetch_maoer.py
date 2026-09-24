import os
import re
import time
from datetime import datetime

import pandas as pd
import pytz
import requests


# ============================================================
# 路径
# ============================================================

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

INPUT_FILE = os.path.join(
    ROOT,
    "data",
    "猫耳在播剧id（跑程序版）.xlsx"
)

OUTPUT_DIR = os.path.join(ROOT, "output")

# ============================================================
# 基础设置
# ============================================================

TZ = pytz.timezone("Asia/Shanghai")

COOKIE = os.environ.get("MISSEVAN_COOKIE", "").strip()

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/150.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
}

if COOKIE:
    HEADERS["Cookie"] = COOKIE


session = requests.Session()
session.headers.update(HEADERS)


# ============================================================
# 工具函数
# ============================================================

def clean_number(value):
    """把 API 中可能出现的数字字符串转成数值。"""
    if value is None:
        return None

    if isinstance(value, bool):
        return int(value)

    if isinstance(value, (int, float)):
        return value

    text = str(value).replace(",", "").strip()

    if not text:
        return None

    try:
        if "." in text:
            return float(text)
        return int(text)
    except Exception:
        return value


def first_value(obj, keys):
    """在一个 dict 中按候选 key 顺序寻找值。"""
    if not isinstance(obj, dict):
        return None

    for key in keys:
        if key in obj and obj[key] is not None:
            return obj[key]

    return None


def find_dict_with_keys(obj, wanted_keys):
    """
    在未知层级的 JSON 中寻找包含指定 key 的 dict。
    用于兼容接口返回层级变化。
    """
    if isinstance(obj, dict):
        if any(k in obj for k in wanted_keys):
            return obj

        for value in obj.values():
            found = find_dict_with_keys(value, wanted_keys)
            if found is not None:
                return found

    elif isinstance(obj, list):
        for item in obj:
            found = find_dict_with_keys(item, wanted_keys)
            if found is not None:
                return found

    return None


def extract_id_from_url(url):
    if not isinstance(url, str):
        return None

    patterns = [
        r"drama[_-]?id[=/](\d+)",
        r"/drama/(\d+)",
        r"[?&]id=(\d+)",
    ]

    for pattern in patterns:
        match = re.search(pattern, url, flags=re.I)
        if match:
            return match.group(1)

    return None


def get_drama_id(row):
    # ===== 1. 优先检查常见 ID 列 =====
    for col in ["id", "剧id", "剧集id", "drama_id", "dramaId"]:
        if col in row.index:
            value = row[col]

            if pd.notna(value):
                text = str(value).strip()

                # Excel 数字可能读成 85974.0
                match = re.search(r"(\d+)", text)

                if match:
                    return match.group(1)

    # ===== 2. 你的 Excel 实际上是：
    # url 列 = drama_id
    # 例如 85974.0
    # =====
    for col in ["url", "URL", "链接"]:
        if col in row.index:
            value = row[col]

            if pd.notna(value):
                text = str(value).strip()

                # 直接处理数字 ID
                match = re.fullmatch(r"(\d+)(?:\.0+)?", text)

                if match:
                    return match.group(1)

                # 如果以后 url 列真的变成完整 URL，也兼容
                drama_id = extract_id_from_url(text)

                if drama_id:
                    return str(drama_id)

    return None


def request_json(url, timeout=20, retries=3):
    last_error = None

    for attempt in range(retries):
        try:
            response = session.get(
                url,
                timeout=timeout
            )
            response.raise_for_status()
            return response.json()

        except Exception as exc:
            last_error = exc
            wait = min(2 ** attempt, 8)
            print(
                f"  请求失败 {attempt + 1}/{retries}: "
                f"{url}\n  {exc}"
            )
            if attempt < retries - 1:
                time.sleep(wait)

    raise RuntimeError(str(last_error))


def extract_drama_payload(data):
    """
    猫耳 getdrama 返回结构在不同时间可能略有差异。
    优先寻找包含 drama/name 的对象。
    """
    if isinstance(data, dict):
        if isinstance(data.get("info"), dict):
            info = data["info"]
            if isinstance(info.get("drama"), dict):
                return info["drama"]

        if isinstance(data.get("drama"), dict):
            return data["drama"]

        found = find_dict_with_keys(
            data,
            {
                "name",
                "view_count",
                "sub_count",
                "sounds",
            }
        )
        if found:
            return found

    return {}


def extract_sound_ids(sound_data):
    """
    从 getdramabysound 返回的 JSON 中尽量提取 sound_id。
    """
    ids = []

    def walk(obj):
        if isinstance(obj, dict):
            for key, value in obj.items():
                key_lower = str(key).lower()

                if key_lower in {
                    "sound_id",
                    "soundid",
                    "soundId",
                }:
                    if value is not None:
                        match = re.search(r"\d+", str(value))
                        if match:
                            ids.append(match.group(0))

                walk(value)

        elif isinstance(obj, list):
            for item in obj:
                walk(item)

    walk(sound_data)

    # 保持顺序去重
    return list(dict.fromkeys(ids))


def extract_pay_flags(sound_data):
    """
    从 getdramabysound 中寻找 need_pay。
    """
    values = []

    def walk(obj):
        if isinstance(obj, dict):
            for key, value in obj.items():
                key_lower = str(key).lower()

                if key_lower in {
                    "need_pay",
                    "needpay",
                    "needPay",
                }:
                    values.append(value)

                walk(value)

        elif isinstance(obj, list):
            for item in obj:
                walk(item)

    walk(sound_data)
    return values


def get_uid_from_p_field(p):
    """
    猫耳 getdm 的 p 字段通常是逗号分隔结构。
    当前统计逻辑沿用原程序：第 7 个字段作为 UID。
    """
    if p is None:
        return None

    parts = str(p).split(",")

    if len(parts) > 6:
        uid = parts[6].strip()
        return uid or None

    return None


def extract_danmaku_uids(data):
    """
    尽量兼容 getdm 返回的多种结构。
    """
    uids = []

    def walk(obj):
        if isinstance(obj, dict):
            if "p" in obj:
                uid = get_uid_from_p_field(obj.get("p"))
                if uid:
                    uids.append(uid)

            for value in obj.values():
                walk(value)

        elif isinstance(obj, list):
            for item in obj:
                walk(item)

    walk(data)

    return uids


# ============================================================
# 单剧抓取
# ============================================================

def fetch_one_drama(drama_id):
    print(f"\n{'=' * 70}")
    print(f"处理 drama_id={drama_id}")
    print(f"{'=' * 70}")

    result = {
        "更新集数": None,
        "id": None,
        "总弹幕": None,
        "播放量": None,
        "追剧人数": None,
        "抓取错误": "",
    }

    try:
        drama_url = (
            "https://www.missevan.com/"
            f"dramaapi/getdrama?drama_id={drama_id}"
        )

        drama_json = request_json(drama_url)

        drama = extract_drama_payload(drama_json)

        name = first_value(
            drama,
            ["name", "title", "drama_name"]
        )

        result["id"] = drama_id

        result["播放量"] = clean_number(
            first_value(
                drama,
                [
                    "view_count",
                    "viewCount",
                    "views",
                    "play_count",
                    "playCount",
                ],
            )
        )

        result["追剧人数"] = clean_number(
            first_value(
                drama,
                [
                    "sub_count",
                    "subCount",
                    "subscribe_count",
                    "subscribeCount",
                    "follow_count",
                    "followCount",
                ],
            )
        )

        print(f"剧名：{name or '未知'}")
        print(f"播放量：{result['播放量']}")
        print(f"追剧人数：{result['追剧人数']}")

        # ----------------------------------------------------
        # 获取声音/剧集列表
        # ----------------------------------------------------

        sounds_url = (
            "https://www.missevan.com/"
            f"dramaapi/getdramabysound?drama_id={drama_id}"
        )

        sounds_json = request_json(sounds_url)

        sound_ids = extract_sound_ids(sounds_json)
        pay_flags = extract_pay_flags(sounds_json)

        # 如果接口中没有找到 sound_id，则尝试从 drama JSON 中提取
        if not sound_ids:
            sound_ids = extract_sound_ids(drama_json)

        print(f"检测到剧集数：{len(sound_ids)}")

        # ----------------------------------------------------
        # 判断付费集
        # ----------------------------------------------------
        #
        # 这里保持与原有统计口径一致：
        # 第一集不计入付费 ID 的范围；
        # 第 2 集以后 need_pay != 0 的集计入。
        #
        # 由于不同版本接口可能存在 need_pay 长度差异，
        # 优先按 sound_id 和 flag 的位置匹配。
        # ----------------------------------------------------

        paid_sound_ids = []

        if sound_ids and pay_flags:
            usable = min(len(sound_ids), len(pay_flags))

            pairs = list(
                zip(
                    sound_ids[:usable],
                    pay_flags[:usable]
                )
            )

            for index, (sid, pay) in enumerate(pairs):
                if index == 0:
                    continue

                if str(pay).lower() not in {
                    "0",
                    "false",
                    "none",
                    "",
                }:
                    paid_sound_ids.append(sid)

        # 如果没有拿到 pay_flags，则不凭空判断
        print(f"付费集数：{len(paid_sound_ids)}")

        result["更新集数"] = len(sound_ids)

        # ----------------------------------------------------
        # 获取总弹幕 UID
        # ----------------------------------------------------

        all_uids = set()

        for index, sound_id in enumerate(sound_ids, start=1):
            print(
                f"弹幕：{index}/{len(sound_ids)}",
                end="\r"
            )

            dm_url = (
                "http://www.missevan.com/"
                f"sound/getdm?soundid={sound_id}"
            )

            try:
                dm_json = request_json(
                    dm_url,
                    timeout=15,
                    retries=2
                )

                all_uids.update(
                    extract_danmaku_uids(dm_json)
                )

            except Exception as exc:
                print(
                    f"\n  弹幕请求失败 sound_id={sound_id}: "
                    f"{exc}"
                )

        print()

        result["总弹幕"] = len(all_uids)

        print(f"总弹幕 UID：{result['总弹幕']}")

        return result

    except Exception as exc:
        result["抓取错误"] = str(exc)
        print(f"❌ drama_id={drama_id} 失败：{exc}")
        return result


# ============================================================
# 主程序
# ============================================================

def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    if not os.path.exists(INPUT_FILE):
        raise FileNotFoundError(
            f"找不到输入文件：{INPUT_FILE}\n"
            "请把「猫耳在播剧id（跑程序版）.xlsx」放进 data/"
        )

    df = pd.read_excel(INPUT_FILE)

    print("\n========== Excel 列名 ==========")
    print(df.columns.tolist())
    print("================================\n")

    print("前 3 行数据：")
    print(df.head(3).to_string())
    print("================================\n")
    print("\n========== 测试 drama_id ==========")
    for i, row in df.head(5).iterrows():
        print(
            f"第 {i + 1} 行："
            f"剧名={row.get('剧名')}, "
            f"url={row.get('url')}, "
            f"drama_id={get_drama_id(row)}"
        )

     print("====================================\n")


    rows = []

    for index, row in df.iterrows():
        drama_id = get_drama_id(row)

        if not drama_id:
            print(
                f"\n⚠️ 第 {index + 1} 行无法识别 drama_id，"
                "保留原行并标记错误。"
            )

            result = {
                "更新集数": None,
                "id": None,
                "总弹幕": None,
                "播放量": None,
                "追剧人数": None,
                "抓取错误": "无法从当前行识别 drama_id",
            }
        else:
            result = fetch_one_drama(drama_id)

        output_row = row.to_dict()
        output_row.update(result)
        rows.append(output_row)

    out_df = pd.DataFrame(rows)

    now = datetime.now(TZ)
    date_str = now.strftime("%m%d")

    output_path = os.path.join(
        OUTPUT_DIR,
        f"猫耳周数据{date_str}.xlsx"
    )

    out_df.to_excel(
        output_path,
        index=False
    )

    print("\n" + "=" * 70)
    print("猫耳本周数据抓取完成")
    print("=" * 70)
    print(f"总数：{len(out_df)}")
    print(
        f"成功：{sum(out_df['抓取错误'].fillna('').eq(''))}"
    )
    print(
        f"失败：{sum(out_df['抓取错误'].fillna('').ne(''))}"
    )
    print(f"文件：{output_path}")


if __name__ == "__main__":
    main()
