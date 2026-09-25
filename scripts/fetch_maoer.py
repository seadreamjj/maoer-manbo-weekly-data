# ============================================================
# 猫耳每周数据抓取
# GitHub Actions 版本
#
# 输入：
#   data/猫耳在播剧id（跑程序版）.xlsx
#
# 输出：
#   output/猫耳周数据MMDD.xlsx
#
# 数据字段：
#   剧名
#   url
#   更新集数
#   付费集数
#   id              -> 去重 UID 数量
#   总弹幕          -> 弹幕总条数
#   播放量
#   追剧人数
#   抓取错误
#
# Cookie：
#   GitHub Actions Secret:
#   MISSEVAN_COOKIE
# ============================================================

import os
import re
import time
import json
from datetime import datetime

import pandas as pd
import pytz
import requests
import urllib3


# ============================================================
# 1. 路径设置
# ============================================================

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

DATA_DIR = os.path.join(ROOT, "data")
OUTPUT_DIR = os.path.join(ROOT, "output")

INPUT_FILE = os.path.join(
    DATA_DIR,
    "猫耳在播剧id（跑程序版）.xlsx"
)

os.makedirs(OUTPUT_DIR, exist_ok=True)


# ============================================================
# 2. 北京时间
# ============================================================

TZ = pytz.timezone("Asia/Shanghai")

NOW = datetime.now(TZ)

OUTPUT_NAME = f"猫耳周数据{NOW.strftime('%m%d')}.xlsx"
OUTPUT_FILE = os.path.join(OUTPUT_DIR, OUTPUT_NAME)


# ============================================================
# 3. GitHub Secret Cookie
# ============================================================

COOKIE = os.environ.get("MISSEVAN_COOKIE", "").strip()

if not COOKIE:
    print("⚠️ 未检测到 MISSEVAN_COOKIE")
    print("请确认 GitHub → Settings → Secrets and variables → Actions")
    print("已经添加名为 MISSEVAN_COOKIE 的 Secret。")
else:
    print("✅ 已读取 MISSEVAN_COOKIE")


# ============================================================
# 4. HTTP Session
# ============================================================

session = requests.Session()

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/150.0.0.0 Safari/537.36"
    ),
    "Accept": "*/*",
    "Referer": "https://www.missevan.com/",
}

if COOKIE:
    HEADERS["Cookie"] = COOKIE


# 猫耳部分接口偶尔存在证书问题。
# 正常情况下优先 verify=True。
urllib3.disable_warnings(
    urllib3.exceptions.InsecureRequestWarning
)


# ============================================================
# 5. HTTP 请求函数
# ============================================================

def request_text(
    url,
    timeout=30,
    retries=3,
    sleep_seconds=2,
):
    """
    获取普通文本响应。

    特别用于：
        sound/getdm

    因为这个接口返回的不是 JSON，
    所以不能调用 response.json()。
    """

    last_error = None

    for attempt in range(1, retries + 1):

        try:
            response = session.get(
                url,
                headers=HEADERS,
                timeout=timeout,
                verify=True,
            )

            response.raise_for_status()

            return response.text

        except Exception as e:

            last_error = e

            # 某些环境 SSL 有问题，再尝试 verify=False
            try:

                response = session.get(
                    url,
                    headers=HEADERS,
                    timeout=timeout,
                    verify=False,
                )

                response.raise_for_status()

                return response.text

            except Exception as e2:

                last_error = e2

                if attempt < retries:
                    print(
                        f"   ⚠️ 请求失败，第 {attempt}/{retries} 次重试："
                        f"{type(last_error).__name__}: {last_error}"
                    )
                    time.sleep(sleep_seconds)

    raise RuntimeError(
        f"请求失败：{url}\n"
        f"最后错误：{last_error}"
    )


def request_json(
    url,
    timeout=30,
    retries=3,
    sleep_seconds=2,
):
    """
    获取 JSON 接口。
    """

    last_error = None

    for attempt in range(1, retries + 1):

        try:

            response = session.get(
                url,
                headers=HEADERS,
                timeout=timeout,
                verify=True,
            )

            response.raise_for_status()

            return response.json()

        except Exception as e:

            last_error = e

            # SSL fallback
            try:

                response = session.get(
                    url,
                    headers=HEADERS,
                    timeout=timeout,
                    verify=False,
                )

                response.raise_for_status()

                return response.json()

            except Exception as e2:

                last_error = e2

                if attempt < retries:
                    print(
                        f"   ⚠️ JSON 请求失败，第 "
                        f"{attempt}/{retries} 次重试："
                        f"{type(last_error).__name__}: {last_error}"
                    )
                    time.sleep(sleep_seconds)

    raise RuntimeError(
        f"JSON 请求失败：{url}\n"
        f"最后错误：{last_error}"
    )


# ============================================================
# 6. 从 URL / ID 中提取 drama_id
# ============================================================

def extract_id_from_url(value):
    """
    支持：

    85974
    85974.0
    "85974"
    "85974.0"
    https://www.missevan.com/drama/85974
    https://www.missevan.com/drama/85974/
    """

    if pd.isna(value):
        return None

    s = str(value).strip()

    if not s:
        return None

    # ----------------------------
    # 纯数字，例如 85974
    # ----------------------------

    m = re.fullmatch(r"(\d+)(?:\.0+)?", s)

    if m:
        return m.group(1)

    # ----------------------------
    # URL
    # ----------------------------

    m = re.search(r"/(\d+)(?:/?(?:\?.*)?)?$", s)

    if m:
        return m.group(1)

    # ----------------------------
    # URL 中任意位置寻找 ID
    # ----------------------------

    m = re.search(r"(\d+)(?:\.0+)?", s)

    if m:
        return m.group(1)

    return None


def get_drama_id(row):
    """
    优先检查常见 ID 列。
    然后检查 url。
    """

    possible_columns = [
        "drama_id",
        "id",
        "剧id",
        "剧ID",
        "ID",
    ]

    for col in possible_columns:

        if col not in row.index:
            continue

        value = row[col]

        drama_id = extract_id_from_url(value)

        if drama_id:
            return drama_id

    # 最后从 url 获取
    if "url" in row.index:

        drama_id = extract_id_from_url(row["url"])

        if drama_id:
            return drama_id

    return None


# ============================================================
# 7. 递归寻找字段
# ============================================================

def recursive_find_values(obj, target_key):
    """
    在 JSON 中递归寻找某个 key 的所有值。
    """

    result = []

    if isinstance(obj, dict):

        for key, value in obj.items():

            if key == target_key:
                result.append(value)

            result.extend(
                recursive_find_values(
                    value,
                    target_key
                )
            )

    elif isinstance(obj, list):

        for item in obj:

            result.extend(
                recursive_find_values(
                    item,
                    target_key
                )
            )

    return result


# ============================================================
# 8. 提取 sound_id + need_pay
# ============================================================

def extract_sound_pay_pairs_from_json(data):
    """
    优先从 JSON 对象本身寻找：

        sound_id
        need_pay

    如果 API 返回结构发生变化，
    再使用兼容性 fallback。
    """

    pairs = []

    def walk(obj):

        if isinstance(obj, dict):

            if "sound_id" in obj and "need_pay" in obj:

                sid = obj.get("sound_id")
                pay = obj.get("need_pay")

                try:
                    sid = str(int(float(sid)))
                except Exception:
                    sid = str(sid).strip()

                try:
                    pay = str(int(float(pay)))
                except Exception:
                    pay = str(pay).strip()

                if sid and sid != "None":
                    pairs.append((sid, pay))

            for value in obj.values():
                walk(value)

        elif isinstance(obj, list):

            for item in obj:
                walk(item)

    walk(data)

    # 去重，保持原顺序
    unique_pairs = []
    seen = set()

    for sid, pay in pairs:

        if sid in seen:
            continue

        seen.add(sid)
        unique_pairs.append((sid, pay))

    return unique_pairs


def extract_sound_pay_pairs_fallback(raw_text):
    """
    兼容原始代码的正则提取方式。

    原代码：
        sound_id
        need_pay

    如果 JSON 结构无法直接对应，
    使用这个方法。
    """

    sound_ids = re.findall(
        r'"sound_id"\s*:\s*(\d+)',
        raw_text
    )

    pay_flags = re.findall(
        r'"need_pay"\s*:\s*(\d+)',
        raw_text
    )

    pairs = []

    for sid, pay in zip(sound_ids, pay_flags):

        pairs.append(
            (
                str(sid),
                str(pay)
            )
        )

    return pairs


# ============================================================
# 9. 提取 sound_id
# ============================================================

def extract_sound_ids(data):
    values = recursive_find_values(
        data,
        "sound_id"
    )

    result = []

    seen = set()

    for value in values:

        try:
            sid = str(int(float(value)))
        except Exception:
            sid = str(value).strip()

        if not sid:
            continue

        if sid in seen:
            continue

        seen.add(sid)
        result.append(sid)

    return result


# ============================================================
# 10. 获取单个剧的数据
# ============================================================

def fetch_one_drama(drama_id):

    result = {
        "更新集数": None,
        "付费集数": None,
        "id": None,
        "总弹幕": None,
        "播放量": None,
        "追剧人数": None,
        "抓取错误": "",
    }

    errors = []

    print()
    print("=" * 70)
    print(f"🎙️ drama_id = {drama_id}")
    print("=" * 70)

    # ========================================================
    # A. getdrama
    # ========================================================

    drama_url = (
        "https://www.missevan.com/"
        f"dramaapi/getdrama?drama_id={drama_id}"
    )

    try:

        drama_data = request_json(drama_url)

    except Exception as e:

        error = f"getdrama失败: {e}"

        print("❌", error)

        result["抓取错误"] = error

        return result


    # ========================================================
    # B. 检查 drama 信息
    # ========================================================

    try:

        info = drama_data.get("info", {})

        drama_info = info.get("drama", {})

        drama_name = drama_info.get("name")

        if drama_name:
            print(f"📖 剧名：{drama_name}")

    except Exception:

        drama_name = None


    # ========================================================
    # C. 提取 sound_id
    # ========================================================

    sound_ids = extract_sound_ids(
        drama_data
    )

    # 如果递归没有找到，
    # 尝试直接从文本中找
    if not sound_ids:

        try:

            raw_json = json.dumps(
                drama_data,
                ensure_ascii=False
            )

            sound_ids = list(
                dict.fromkeys(
                    re.findall(
                        r'"sound_id"\s*:\s*(\d+)',
                        raw_json
                    )
                )
            )

        except Exception:
            pass


    if not sound_ids:

        error = "没有找到 sound_id"

        print("❌", error)

        result["抓取错误"] = error

        return result


    print(
        f"🔊 找到 {len(sound_ids)} 个 sound_id"
    )

    print(
        f"   第一集 sound_id = {sound_ids[0]}"
    )


    # ========================================================
    # D. 提取 sound_id + need_pay
    # ========================================================

    pairs = extract_sound_pay_pairs_from_json(
        drama_data
    )

    # 如果结构没有正确提取，使用 fallback
    if not pairs:

        try:

            raw_json = json.dumps(
                drama_data,
                ensure_ascii=False
            )

            pairs = extract_sound_pay_pairs_fallback(
                raw_json
            )

        except Exception:
            pairs = []


    # ========================================================
    # E. 如果 pairs 数量与 sound_ids 不一致
    # 尝试根据独立数组恢复
    # ========================================================

    if len(pairs) != len(sound_ids):

        pay_flags = recursive_find_values(
            drama_data,
            "need_pay"
        )

        cleaned_pay_flags = []

        for pay in pay_flags:

            try:
                pay = str(int(float(pay)))
            except Exception:
                pay = str(pay).strip()

            cleaned_pay_flags.append(pay)

        if len(cleaned_pay_flags) >= len(sound_ids):

            pairs = list(
                zip(
                    sound_ids,
                    cleaned_pay_flags
                )
            )


    # ========================================================
    # F. 计算付费集
    #
    # 保留原始程序的业务规则：
    #
    # 第一集不纳入付费集统计。
    #
    # 即：
    # sound_ids[0] 不参与付费集数/付费弹幕统计
    # ========================================================

    paid_sound_ids = []

    if pairs:

        # 保证使用 sound_ids 的原始顺序
        pair_map = {}

        for sid, pay in pairs:

            if sid not in pair_map:
                pair_map[sid] = pay

        ordered_pairs = []

        for sid in sound_ids:

            if sid in pair_map:

                ordered_pairs.append(
                    (
                        sid,
                        pair_map[sid]
                    )
                )

        # 如果 API 的结构没有完全对应，
        # fallback 到 pairs 自己
        if not ordered_pairs:

            ordered_pairs = pairs


        # 第一集不计入
        for index, (sid, pay) in enumerate(
            ordered_pairs
        ):

            if index == 0:
                continue

            if str(pay) != "0":
                paid_sound_ids.append(
                    sid
                )

    else:

        print(
            "⚠️ 没有成功提取 need_pay，"
            "无法判断付费集"
        )


    # 去重
    paid_sound_ids = list(
        dict.fromkeys(
            paid_sound_ids
        )
    )


    result["付费集数"] = len(
        paid_sound_ids
    )


    print(
        f"💰 付费集数：{len(paid_sound_ids)}"
    )


    # ========================================================
    # G. getdramabysound
    #
    # 原程序这里使用：
    #
    # https://www.missevan.com/dramaapi/
    # getdramabysound?sound_id=第一集sound_id
    #
    # 而不是 drama_id
    # ========================================================

    first_sound_id = sound_ids[0]

    drama_info_url = (
        "https://www.missevan.com/"
        "dramaapi/getdramabysound"
        f"?sound_id={first_sound_id}"
    )

    try:

        data_info = request_json(
            drama_info_url
        )

        if data_info.get("success"):

            info = (
                data_info
                .get("info", {})
                .get("drama", {})
            )

            # ----------------------------------------------
            # 追剧人数
            # ----------------------------------------------

            result["追剧人数"] = (
                info.get("subscription_num")
            )

            # ----------------------------------------------
            # 播放量
            # ----------------------------------------------

            result["播放量"] = (
                info.get("view_count")
            )

            # ----------------------------------------------
            # 更新集数
            # ----------------------------------------------

            result["更新集数"] = (
                info.get("newest")
            )

            print(
                f"👥 追剧人数："
                f"{result['追剧人数']}"
            )

            print(
                f"▶️ 播放量："
                f"{result['播放量']}"
            )

            print(
                f"📚 更新集数："
                f"{result['更新集数']}"
            )

        else:

            error = (
                "getdramabysound 返回 "
                "success=False"
            )

            print("⚠️", error)

            errors.append(error)

    except Exception as e:

        error = (
            f"getdramabysound失败: {e}"
        )

        print("❌", error)

        errors.append(error)


    # ========================================================
    # H. 如果 newest 没有拿到
    # 使用 sound_id 数量作为 fallback
    # ========================================================

    if result["更新集数"] is None:

        result["更新集数"] = len(
            sound_ids
        )

        print(
            f"⚠️ newest 未获取，"
            f"使用 sound_id 数量："
            f"{len(sound_ids)}"
        )


    # ========================================================
    # I. 没有付费集
    # ========================================================

    if not paid_sound_ids:

        result["id"] = 0
        result["总弹幕"] = 0

        print(
            "📭 没有付费集，"
            "UID / 总弹幕 = 0"
        )

        result["抓取错误"] = (
            "；".join(errors)
        )

        return result


    # ========================================================
    # J. 获取付费集弹幕
    #
    # 原接口：
    #
    # http://www.missevan.com/sound/getdm?soundid=
    #
    # 这里使用 HTTPS。
    #
    # 注意：
    # getdm 返回的是文本，不是 JSON。
    # ========================================================

    all_uids = set()

    total_dm_count = 0

    successful_sounds = 0

    failed_sounds = 0


    for i, sound_id in enumerate(
        paid_sound_ids,
        start=1
    ):

        dm_url = (
            "https://www.missevan.com/"
            f"sound/getdm?soundid={sound_id}"
        )

        print(
            f"   💬 弹幕 {i}/"
            f"{len(paid_sound_ids)}"
            f"  sound_id={sound_id}"
        )

        try:

            sound_text = request_text(
                dm_url,
                timeout=30,
                retries=3,
            )

            if not sound_text:

                print(
                    "      ⚠️ 返回内容为空"
                )

                failed_sounds += 1

                continue


            # ----------------------------------------------
            # 从文本中提取：
            #
            # p="xxx,xxx,...,UID,..."
            # ----------------------------------------------

            dms = re.findall(
                r'p="(.+?)"',
                sound_text
            )


            if not dms:

                print(
                    "      ⚠️ 未找到弹幕 p 字段"
                )

                # 调试信息：只打印少量
                preview = (
                    sound_text[:200]
                    .replace("\n", " ")
                    .replace("\r", " ")
                )

                print(
                    f"      返回内容前200字符："
                    f"{preview}"
                )

                continue


            successful_sounds += 1

            # 总弹幕条数
            total_dm_count += len(dms)


            # ----------------------------------------------
            # UID
            #
            # p 字段按逗号分割：
            #
            # parts[6]
            #
            # 即原程序使用的 UID 字段
            # ----------------------------------------------

            for d in dms:

                parts = d.split(",")

                if len(parts) >= 7:

                    uid = parts[6].strip()

                    if uid:

                        all_uids.add(uid)


            print(
                f"      弹幕：{len(dms)}"
                f"；累计弹幕：{total_dm_count}"
                f"；累计UID：{len(all_uids)}"
            )


        except Exception as e:

            failed_sounds += 1

            error = (
                f"sound_id={sound_id}"
                f"弹幕请求失败: {e}"
            )

            print(
                f"      ❌ {error}"
            )

            errors.append(error)


    # ========================================================
    # K. 写入最终结果
    # ========================================================

    result["id"] = len(
        all_uids
    )

    result["总弹幕"] = (
        total_dm_count
    )


    # ========================================================
    # L. 输出日志
    # ========================================================

    print()
    print("📊 本剧结果")
    print("-" * 50)

    print(
        f"   更新集数：{result['更新集数']}"
    )

    print(
        f"   付费集数：{result['付费集数']}"
    )

    print(
        f"   播放量：{result['播放量']}"
    )

    print(
        f"   追剧人数：{result['追剧人数']}"
    )

    print(
        f"   总弹幕：{result['总弹幕']}"
    )

    print(
        f"   UID：{result['id']}"
    )

    print(
        f"   成功获取弹幕集数："
        f"{successful_sounds}"
    )

    print(
        f"   失败弹幕集数："
        f"{failed_sounds}"
    )


    # 如果部分弹幕接口失败，记录下来
    if failed_sounds > 0:

        errors.append(
            f"{failed_sounds} 个付费集弹幕获取失败"
        )


    result["抓取错误"] = (
        "；".join(errors)
    )

    return result


# ============================================================
# 11. 主程序
# ============================================================

def main():

    print()
    print("=" * 70)
    print("🎙️ 猫耳每周数据抓取")
    print("=" * 70)

    print(
        f"📅 当前北京时间："
        f"{NOW.strftime('%Y-%m-%d %H:%M:%S')}"
    )

    print(
        f"📁 输入文件："
        f"{INPUT_FILE}"
    )

    print(
        f"📁 输出文件："
        f"{OUTPUT_FILE}"
    )

    print("=" * 70)


    # ========================================================
    # A. 检查输入文件
    # ========================================================

    if not os.path.exists(INPUT_FILE):

        raise FileNotFoundError(
            f"\n❌ 找不到输入文件：\n"
            f"{INPUT_FILE}\n\n"
            f"请把：\n"
            f"猫耳在播剧id（跑程序版）.xlsx\n"
            f"放到仓库的 data/ 目录。"
        )


    # ========================================================
    # B. 读取 Excel
    # ========================================================

    print()
    print("📖 正在读取 Excel...")

    df = pd.read_excel(
        INPUT_FILE
    )

    print(
        f"✅ 共读取 {len(df)} 行"
    )

    print(
        f"📋 列名："
        f"{list(df.columns)}"
    )


    # ========================================================
    # C. 检查 url 列
    # ========================================================

    if "url" not in df.columns:

        raise ValueError(
            "❌ Excel 中没有找到 url 列。"
        )


    # ========================================================
    # D. 清理 url
    #
    # 例如：
    #
    # 85974.0
    #
    # 转成：
    #
    # 85974
    # ========================================================

    df["url"] = (
        df["url"]
        .astype(str)
        .str.strip()
        .str.replace(
            r"\.0$",
            "",
            regex=True
        )
    )


    # ========================================================
    # E. 初始化结果列
    # ========================================================

    result_columns = [
        "更新集数",
        "付费集数",
        "id",
        "总弹幕",
        "播放量",
        "追剧人数",
        "抓取错误",
    ]

    for col in result_columns:

        df[col] = None


    # ========================================================
    # F. 循环抓取
    # ========================================================

    total = len(df)

    success_count = 0
    fail_count = 0


    for idx, row in df.iterrows():

        print()
        print(
            "#" * 70
        )

        print(
            f"📌 第 {idx + 1}/{total} 行"
        )

        drama_name = row.get(
            "剧名",
            ""
        )

        print(
            f"🎭 {drama_name}"
        )


        # ----------------------------------------------------
        # 获取 drama_id
        # ----------------------------------------------------

        drama_id = get_drama_id(
            row
        )


        if not drama_id:

            print(
                "⚠️ 无法识别 drama_id"
            )

            print(
                f"   url = {row.get('url')}"
            )

            df.at[
                idx,
                "抓取错误"
            ] = "无法识别 drama_id"

            fail_count += 1

            continue


        print(
            f"🆔 drama_id = {drama_id}"
        )


        # ----------------------------------------------------
        # 抓取
        # ----------------------------------------------------

        try:

            result = fetch_one_drama(
                drama_id
            )


            # ------------------------------------------------
            # 写回 DataFrame
            # ------------------------------------------------

            for col in result_columns:

                df.at[
                    idx,
                    col
                ] = result.get(col)


            if result.get(
                "抓取错误"
            ):

                fail_count += 1

            else:

                success_count += 1


        except Exception as e:

            error = (
                f"{type(e).__name__}: {e}"
            )

            print(
                f"❌ 本剧抓取异常："
                f"{error}"
            )

            df.at[
                idx,
                "抓取错误"
            ] = error

            fail_count += 1


        # ----------------------------------------------------
        # 避免请求过快
        # ----------------------------------------------------

        time.sleep(0.5)


    # ========================================================
    # G. 调整列顺序
    # ========================================================

    preferred_order = [
        "剧名",
        "url",
        "更新集数",
        "付费集数",
        "id",
        "总弹幕",
        "播放量",
        "追剧人数",
        "抓取错误",
    ]

    existing_first = [
        col
        for col in preferred_order
        if col in df.columns
    ]

    remaining = [
        col
        for col in df.columns
        if col not in existing_first
    ]

    df = df[
        existing_first + remaining
    ]


    # ========================================================
    # H. 保存
    # ========================================================

    print()
    print("=" * 70)
    print("💾 正在保存...")
    print("=" * 70)

    df.to_excel(
        OUTPUT_FILE,
        index=False
    )


    # ========================================================
    # I. 最终统计
    # ========================================================

    print()
    print("=" * 70)
    print("🎉 抓取完成")
    print("=" * 70)

    print(
        f"📄 输出：{OUTPUT_FILE}"
    )

    print(
        f"📊 总剧数：{total}"
    )

    print(
        f"✅ 完整成功：{success_count}"
    )

    print(
        f"⚠️ 有错误：{fail_count}"
    )


    # ========================================================
    # J. 简单汇总
    # ========================================================

    numeric_columns = [
        "更新集数",
        "付费集数",
        "id",
        "总弹幕",
        "播放量",
        "追剧人数",
    ]

    print()
    print("📊 数据汇总")
    print("-" * 70)

    for col in numeric_columns:

        if col not in df.columns:
            continue

        numeric = pd.to_numeric(
            df[col],
            errors="coerce"
        )

        print(
            f"{col:<10} "
            f"有效：{numeric.notna().sum():>4} "
            f"合计：{numeric.sum():,.0f}"
        )

    print()
    print("=" * 70)
    print("✅ 全部完成")
    print("=" * 70)


# ============================================================
# 12. Entry point
# ============================================================

if __name__ == "__main__":
    main()
