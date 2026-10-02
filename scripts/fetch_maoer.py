# ============================================================
# 猫耳每周数据抓取
# GitHub Actions 版本
#
# 业务逻辑基于已验证正确的 Colab 版本
#
# 输入：
#   data/猫耳在播剧id（跑程序版）.xlsx
#
# 输出：
#   output/猫耳周数据MMDD.csv
#
# 字段：
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
#
# ============================================================

import os
import re
import json
import time
from datetime import datetime

import pandas as pd
import pytz
import requests
import urllib3


# ============================================================
# 1. 路径设置
# ============================================================

ROOT = os.path.dirname(
    os.path.dirname(
        os.path.abspath(__file__)
    )
)

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

OUTPUT_NAME = f"猫耳周数据{NOW.strftime('%m%d')}.csv"
OUTPUT_FILE = os.path.join(
    OUTPUT_DIR,
    OUTPUT_NAME
)


# ============================================================
# 3. GitHub Secret Cookie
# ============================================================

COOKIE = os.environ.get(
    "MISSEVAN_COOKIE",
    ""
).strip()

if not COOKIE:
    print("⚠️ 未检测到 MISSEVAN_COOKIE")
    print(
        "请确认 GitHub → Settings → Secrets and variables "
        "→ Actions 中已经添加 MISSEVAN_COOKIE。"
    )
else:
    print("✅ 已读取 MISSEVAN_COOKIE")


# ============================================================
# 4. HTTP Session
# ============================================================

session = requests.Session()

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/100.0.4896.127 Safari/537.36"
    ),
    "Accept": "*/*",
}

if COOKIE:
    HEADERS["Cookie"] = COOKIE


# ============================================================
# 5. API 地址
#
# 注意：
# 这里故意保持与你“正确版”一致。
#
# getdrama       -> HTTP
# getdm          -> HTTP
# getdramabysound -> HTTPS
# ============================================================

DRAMA_URL_BASE = (
    "http://www.missevan.com/"
    "dramaapi/getdrama?drama_id="
)

SOUND_DM_URL_BASE = (
    "http://www.missevan.com/"
    "sound/getdm?soundid="
)

DRAMA_BY_SOUND_URL_BASE = (
    "https://www.missevan.com/"
    "dramaapi/getdramabysound?sound_id="
)


# ============================================================
# 6. SSL 警告
# ============================================================

urllib3.disable_warnings(
    urllib3.exceptions.InsecureRequestWarning
)


# ============================================================
# 7. 请求函数
# ============================================================

def request_get(
    url,
    timeout=30,
    retries=3,
    sleep_seconds=2,
):
    """
    普通 GET 请求。

    先使用 verify=True。
    如果 SSL 出现问题，再使用 verify=False。

    返回 requests.Response。
    """

    last_error = None

    for attempt in range(1, retries + 1):

        # ----------------------------------------------------
        # 第一步：正常 SSL
        # ----------------------------------------------------

        try:

            response = session.get(
                url,
                headers=HEADERS,
                timeout=timeout,
                verify=True,
            )

            response.raise_for_status()

            return response

        except Exception as e:

            last_error = e

        # ----------------------------------------------------
        # 第二步：SSL fallback
        # ----------------------------------------------------

        try:

            response = session.get(
                url,
                headers=HEADERS,
                timeout=timeout,
                verify=False,
            )

            response.raise_for_status()

            return response

        except Exception as e:

            last_error = e

        # ----------------------------------------------------
        # 重试
        # ----------------------------------------------------

        if attempt < retries:

            print(
                f"   ⚠️ 请求失败，"
                f"第 {attempt}/{retries} 次重试："
                f"{type(last_error).__name__}: "
                f"{last_error}"
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
    JSON GET 请求。
    """

    response = request_get(
        url=url,
        timeout=timeout,
        retries=retries,
        sleep_seconds=sleep_seconds,
    )

    try:
        return response.json()

    except Exception as e:

        raise RuntimeError(
            f"JSON 解析失败：{url}\n"
            f"错误：{e}\n"
            f"返回内容前500字符："
            f"{response.text[:500]}"
        )


def request_text(
    url,
    timeout=30,
    retries=3,
    sleep_seconds=2,
):
    """
    普通文本 GET 请求。

    getdm 返回的不是 JSON，
    因此这里直接返回 response.text。
    """

    response = request_get(
        url=url,
        timeout=timeout,
        retries=retries,
        sleep_seconds=sleep_seconds,
    )

    return response.text


# ============================================================
# 8. 提取 drama_id
# ============================================================

def extract_drama_id(value):
    """
    从 url 中提取 drama_id。

    支持：

        85974
        85974.0
        "85974"
        "85974.0"
        https://www.missevan.com/drama/85974
        https://www.missevan.com/drama/85974/

    注意：
    这里不从其他 id 列猜 drama_id。
    优先按照正确版逻辑，从 url 获取。
    """

    if pd.isna(value):
        return None

    s = str(value).strip()

    if not s:
        return None

    # --------------------------------------------------------
    # 纯数字
    # --------------------------------------------------------

    m = re.fullmatch(
        r"(\d+)(?:\.0+)?",
        s
    )

    if m:
        return m.group(1)

    # --------------------------------------------------------
    # URL
    #
    # 例如：
    # https://www.missevan.com/drama/85974
    # https://www.missevan.com/drama/85974/
    # --------------------------------------------------------

    m = re.search(
        r"/(\d+)(?:/)?(?:\?.*)?$",
        s
    )

    if m:
        return m.group(1)

    # --------------------------------------------------------
    # 最后兼容：字符串中寻找数字
    # --------------------------------------------------------

    m = re.search(
        r"(\d+)(?:\.0+)?",
        s
    )

    if m:
        return m.group(1)

    return None


# ============================================================
# 9. 抓取单个剧
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
    #
    # 与正确版保持一致
    # ========================================================

    api_url = (
        DRAMA_URL_BASE
        + str(drama_id)
    )

    try:

        response = request_get(
            api_url,
            timeout=30,
            retries=3,
        )

        drama_result = response.text

    except Exception as e:

        error = (
            f"getdrama失败: {e}"
        )

        print("❌", error)

        result["抓取错误"] = error

        return result


    # ========================================================
    # B. JSON 解析
    # ========================================================

    try:

        drama_data = json.loads(
            drama_result
        )

    except Exception as e:

        error = (
            f"getdrama JSON解析失败: {e}"
        )

        print("❌", error)

        result["抓取错误"] = error

        return result


    # ========================================================
    # C. 剧名
    # ========================================================

    try:

        drama_name = (
            drama_data
            ["info"]
            ["drama"]
            ["name"]
        )

        print(
            f"📖 剧名：{drama_name}"
        )

    except Exception:

        drama_name = ""


    # ========================================================
    # D. 提取 sound_id 与 need_pay
    #
    # !!! 这里严格保持正确版逻辑 !!!
    #
    # 不使用：
    #   recursive_find_values
    #   sound_id + need_pay 对象配对
    #   pair_map
    #
    # 直接从原始 response.text 中按顺序提取。
    # ========================================================

    pattern1 = re.compile(
        r'"sound_id":(\d+),'
    )

    pattern2 = re.compile(
        r'"need_pay":(\d+),'
    )

    sound_ids_raw = re.findall(
        pattern1,
        drama_result
    )

    pay_types_raw = re.findall(
        pattern2,
        drama_result
    )


    print(
        f"🔊 sound_id 数量："
        f"{len(sound_ids_raw)}"
    )

    print(
        f"💰 need_pay 数量："
        f"{len(pay_types_raw)}"
    )


    # ========================================================
    # E. 如果没有 sound_id
    # ========================================================

    if not sound_ids_raw:

        error = "没有找到 sound_id"

        print("❌", error)

        result["抓取错误"] = error

        return result


    # ========================================================
    # F. 获取播放量、追剧人数、更新集数
    #
    # 与正确版完全一致：
    #
    # 使用第一集 sound_id
    # ========================================================

    sample_sid = sound_ids_raw[0]

    drama_info_url = (
        DRAMA_BY_SOUND_URL_BASE
        + str(sample_sid)
    )

    try:

        info_res = request_get(
            drama_info_url,
            timeout=30,
            retries=3,
        )

        data_info = info_res.json()

        if data_info.get("success"):

            info = (
                data_info
                ["info"]
                ["drama"]
            )

            result["追剧人数"] = (
                info.get("subscription_num")
            )

            result["播放量"] = (
                info.get("view_count")
            )

            cur_newest = (
                info.get("newest")
            )

            result["更新集数"] = (
                cur_newest
            )

            print(
                f"📚 更新至：{cur_newest}"
            )

            print(
                f"👥 追剧人数："
                f"{info.get('subscription_num')}"
            )

            print(
                f"▶️ 播放量："
                f"{info.get('view_count')}"
            )

        else:

            error = (
                "getdramabysound "
                "返回 success=False"
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
    # G. 计算付费集
    #
    # !!! 这里严格保持正确版 !!!
    #
    # 正确版：
    #
    # pay_types_clean = pay_types_raw[1:]
    #
    # paid_sound_ids =
    #     [sid for sid, pay in
    #      zip(sound_ids_raw, pay_types_clean)
    #      if pay != '0']
    #
    # 不改这个逻辑。
    # ========================================================

    pay_types_clean = (
        pay_types_raw[1:]
    )

    paid_sound_ids = [
        sid
        for sid, pay in zip(
            sound_ids_raw,
            pay_types_clean
        )
        if pay != "0"
    ]


    # 去重，保持原顺序
    paid_sound_ids = list(
        dict.fromkeys(
            paid_sound_ids
        )
    )


    result["付费集数"] = (
        len(paid_sound_ids)
    )


    print(
        f"💰 付费集数："
        f"{len(paid_sound_ids)}"
    )


    # ========================================================
    # H. 没有付费集
    #
    # 与正确版一致：
    #
    # id = 0
    # 总弹幕 = 0
    # ========================================================

    if not paid_sound_ids:

        result["id"] = 0
        result["总弹幕"] = 0

        print(
            "📭 没有付费集"
        )

        print(
            "   去重UID：0"
        )

        print(
            "   总弹幕：0"
        )

        result["抓取错误"] = (
            "；".join(errors)
        )

        return result


    # ========================================================
    # I. 获取弹幕与 UID
    #
    # 与正确版保持一致
    # ========================================================

    all_uids = set()

    total_dm_count = 0

    failed_sounds = 0


    for i, sid in enumerate(
        paid_sound_ids,
        start=1
    ):

        dm_url = (
            SOUND_DM_URL_BASE
            + str(sid)
        )

        print(
            f"   💬 弹幕 "
            f"{i}/{len(paid_sound_ids)}"
            f"  sound_id={sid}"
        )

        try:

            sound_result = request_text(
                dm_url,
                timeout=30,
                retries=3,
            )

            if not sound_result:

                print(
                    "      ⚠️ 返回内容为空"
                )

                failed_sounds += 1

                continue


            # ------------------------------------------------
            # 提取 p 字段
            #
            # 与正确版一致：
            #
            # r'p="(.+?)"'
            # ------------------------------------------------

            dms = re.findall(
                r'p="(.+?)"',
                sound_result
            )


            if not dms:

                print(
                    "      ⚠️ 未找到弹幕 p 字段"
                )

                failed_sounds += 1

                continue


            # ------------------------------------------------
            # 总弹幕数量
            # ------------------------------------------------

            total_dm_count += len(dms)


            # ------------------------------------------------
            # UID
            #
            # p 字段逗号分隔后的第 7 个字段
            #
            # parts[6]
            # ------------------------------------------------

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
                f"sound_id={sid}"
                f"弹幕请求失败: {e}"
            )

            print(
                f"      ❌ {error}"
            )

            errors.append(error)


    # ========================================================
    # J. 最终写入 UID / 总弹幕
    # ========================================================

    result["id"] = (
        len(all_uids)
    )

    result["总弹幕"] = (
        total_dm_count
    )


    # ========================================================
    # K. 输出本剧结果
    # ========================================================

    print()
    print("📊 本剧结果")
    print("-" * 50)

    print(
        f"   更新集数："
        f"{result['更新集数']}"
    )

    print(
        f"   付费集数："
        f"{result['付费集数']}"
    )

    print(
        f"   播放量："
        f"{result['播放量']}"
    )

    print(
        f"   追剧人数："
        f"{result['追剧人数']}"
    )

    print(
        f"   总弹幕："
        f"{result['总弹幕']}"
    )

    print(
        f"   去重UID："
        f"{result['id']}"
    )

    print(
        f"   付费集请求失败："
        f"{failed_sounds}"
    )


    # ========================================================
    # L. 记录部分失败
    # ========================================================

    if failed_sounds > 0:

        errors.append(
            f"{failed_sounds} 个付费集弹幕获取失败"
        )


    result["抓取错误"] = (
        "；".join(errors)
    )


    return result


# ============================================================
# 10. 主程序
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
    # A. 检查 Cookie
    # ========================================================

    if not COOKIE:

        print()
        print(
            "⚠️ 警告：没有读取到 "
            "MISSEVAN_COOKIE。"
        )

        print(
            "程序仍会继续运行，"
            "但猫耳接口可能返回异常。"
        )


    # ========================================================
    # B. 检查输入文件
    # ========================================================

    if not os.path.exists(
        INPUT_FILE
    ):

        raise FileNotFoundError(
            f"\n❌ 找不到输入文件：\n"
            f"{INPUT_FILE}\n\n"
            f"请确认：\n"
            f"猫耳在播剧id（跑程序版）.xlsx\n"
            f"位于仓库 data/ 目录。"
        )


    # ========================================================
    # C. 读取 Excel
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
    # D. 检查 url
    # ========================================================

    if "url" not in df.columns:

        raise ValueError(
            "❌ Excel 中没有找到 url 列。"
        )


    # ========================================================
    # E. 清理 URL
    #
    # 与正确版一致
    #
    # 85974.0
    # ↓
    # 85974
    # ========================================================

    df["url"] = (
        df["url"]
        .astype(str)
        .str.replace(
            r"\.0$",
            "",
            regex=True
        )
    )


    # ========================================================
    # F. 初始化结果列
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
    # G. 循环抓取
    # ========================================================

    total = len(df)

    success_count = 0
    fail_count = 0

    empty_count = 0


    for idx, row in df.iterrows():

        print()
        print("#" * 70)

        print(
            f"📌 第 {idx + 1}/{total} 行"
        )


        # ----------------------------------------------------
        # 剧名
        # ----------------------------------------------------

        if "剧名" in df.columns:

            drama_name_raw = (
                df.at[idx, "剧名"]
            )

        else:

            drama_name_raw = ""


        drama_name = (
            ""
            if pd.isna(drama_name_raw)
            else str(drama_name_raw).strip()
        )


        # ----------------------------------------------------
        # URL
        # ----------------------------------------------------

        url_raw = df.at[
            idx,
            "url"
        ]

        url_value = (
            ""
            if pd.isna(url_raw)
            else str(url_raw).strip()
        )


        # ====================================================
        # 空行
        #
        # 保留空行，不抓取，不报错
        # ====================================================

        if (
            not drama_name
            and not url_value
        ):

            print(
                f"[{idx + 1}/{total}] "
                f"空行，跳过抓取"
            )

            empty_count += 1

            continue


        print(
            f"🎭 {drama_name}"
        )

        print(
            f"🔗 {url_value}"
        )


        # ====================================================
        # 获取 drama_id
        # ====================================================

        drama_id = extract_drama_id(
            url_value
        )


        if not drama_id:

            error = (
                "无法识别 drama_id"
            )

            print(
                f"⚠️ {error}"
            )

            df.at[
                idx,
                "抓取错误"
            ] = error

            fail_count += 1

            continue


        print(
            f"🆔 drama_id = {drama_id}"
        )


        # ====================================================
        # 抓取
        # ====================================================

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
                ] = result.get(
                    col
                )


            # ------------------------------------------------
            # 统计成功/失败
            # ------------------------------------------------

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


        # ====================================================
        # 避免请求过快
        # ====================================================

        time.sleep(0.5)


    # ========================================================
    # H. 调整列顺序
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
    # I. 保存 CSV
    # ========================================================

    print()
    print("=" * 70)
    print("💾 正在保存...")
    print("=" * 70)


    # utf-8-sig：
    # Excel 打开中文 CSV 时更稳定
    df.to_csv(
        OUTPUT_FILE,
        index=False,
        encoding="utf-8-sig"
    )


    # ========================================================
    # J. 最终统计
    # ========================================================

    print()
    print("=" * 70)
    print("🎉 抓取完成")
    print("=" * 70)

    print(
        f"📄 输出："
        f"{OUTPUT_FILE}"
    )

    print(
        f"📊 总行数："
        f"{total}"
    )

    print(
        f"🟦 空行："
        f"{empty_count}"
    )

    print(
        f"✅ 完整成功："
        f"{success_count}"
    )

    print(
        f"⚠️ 有错误："
        f"{fail_count}"
    )


    # ========================================================
    # K. 数据汇总
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
            f"{col:<10}"
            f"有效：{numeric.notna().sum():>4} "
            f"合计：{numeric.sum():,.0f}"
        )


    print()
    print("=" * 70)
    print("✅ 全部完成")
    print("=" * 70)


# ============================================================
# 11. Entry point
# ============================================================

if __name__ == "__main__":
    main()
