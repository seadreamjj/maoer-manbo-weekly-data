import os
import re
import time
from datetime import datetime

import pandas as pd
import pytz
import requests
import urllib3


# ============================================================
# 1. 路径
# ============================================================

ROOT = os.path.dirname(
    os.path.dirname(
        os.path.abspath(__file__)
    )
)

INPUT_FILE = os.path.join(
    ROOT,
    "data",
    "漫播临时周数据链接.xlsx"
)

OUTPUT_DIR = os.path.join(
    ROOT,
    "output"
)

TZ = pytz.timezone("Asia/Shanghai")


# ============================================================
# 2. SSL 警告
# ============================================================

urllib3.disable_warnings(
    urllib3.exceptions.InsecureRequestWarning
)


# ============================================================
# 3. Session
# ============================================================

session = requests.Session()

session.headers.update({
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/130.0.0.0 Safari/537.36"
    ),
    "Accept": (
        "application/json, text/plain, */*"
    ),
    "Accept-Language": (
        "zh-CN,zh;q=0.9,en;q=0.8"
    ),
})


# ============================================================
# 4. 请求函数
# ============================================================

def safe_get(
    url,
    timeout=10,
    retries=2
):
    """
    请求 URL。

    请求顺序：

    1. 正常 SSL
    2. SSL 失败后使用 verify=False
    3. 普通网络错误自动重试
    4. 最终失败返回 None
    """

    for attempt in range(retries):

        try:
            response = session.get(
                url,
                timeout=timeout,
                verify=True
            )

            response.raise_for_status()

            return response

        except requests.exceptions.SSLError as exc:

            print("⚠️ SSL证书错误：")
            print(f"   {url}")
            print(f"   {exc}")
            print("   → 尝试关闭 SSL 验证重新请求")

            break

        except requests.exceptions.RequestException as exc:

            if attempt < retries - 1:

                print(
                    f"⚠️ 请求失败，第 "
                    f"{attempt + 1}/{retries} 次重试："
                    f"{exc}"
                )

                time.sleep(1)

            else:

                print(
                    f"❌ 请求最终失败：{url}"
                )

                print(
                    f"   {exc}"
                )

                return None

    # --------------------------------------------------------
    # SSL 失败后，关闭 SSL 验证再次请求
    # --------------------------------------------------------

    try:

        response = session.get(
            url,
            timeout=timeout,
            verify=False
        )

        response.raise_for_status()

        print(
            "   ✓ verify=False 请求成功"
        )

        return response

    except Exception as exc:

        print(
            "❌ SSL关闭后仍然请求失败："
        )

        print(
            f"   {url}"
        )

        print(
            f"   {exc}"
        )

        return None


# ============================================================
# 5. URL 清理
# ============================================================

def normalize_url(value):
    """
    清理 Excel 中的 URL。

    支持：

    1. 正常 URL
       https://xxx.com/xxx?id=123

    2. 纯 ID
       12345

    3. Excel 数字
       12345.0

    4. 空值
       返回 ""
    """

    if pd.isna(value):
        return ""

    value = str(value).strip()

    if not value:
        return ""

    # Excel 数字型 ID，例如 12345.0
    if re.fullmatch(
        r"\d+\.0",
        value
    ):
        value = value[:-2]

    return value


# ============================================================
# 6. 判断漫播付费 / 会员集
# ============================================================

def get_member_episode_ids(
    set_list
):
    """
    按原漫播脚本逻辑：

    - vipFree=1
    - payType=1
    - price>0

    直接判断为付费/会员集。

    其他集访问：

        dramaSetDetail

    code=105 时加入付费集。
    """

    episodes = []
    failed = []

    for item in set_list:

        vip_free = item.get(
            "vipFree",
            0
        )

        pay_type = item.get(
            "payType",
            0
        )

        price = item.get(
            "price",
            0
        )

        set_id = item.get(
            "setIdStr"
        )

        if not set_id:
            continue

        # ----------------------------------------------------
        # 直接判断
        # ----------------------------------------------------

        if (
            vip_free == 1
            or pay_type == 1
            or (
                price is not None
                and price > 0
            )
        ):

            episodes.append(
                set_id
            )

            continue

        # ----------------------------------------------------
        # 对其他集访问详情接口
        # ----------------------------------------------------

        check_url = (
            "https://www.kilamanbo.com/"
            "web_manbo/dramaSetDetail"
            f"?dramaSetId={set_id}"
        )

        check_response = safe_get(
            check_url,
            timeout=8,
            retries=1
        )

        if check_response is None:

            failed.append(
                set_id
            )

            continue

        try:

            check_data = (
                check_response.json()
            )

            if (
                check_data.get("code")
                == 105
            ):

                episodes.append(
                    set_id
                )

        except Exception as exc:

            print(
                f"⚠️ 判断会员剧失败："
                f"setId={set_id}，{exc}"
            )

            failed.append(
                set_id
            )

    return (
        episodes,
        failed
    )


# ============================================================
# 7. 获取弹幕 UID
# ============================================================

def get_danmaku_uids(
    episode_ids
):
    """
    获取付费/会员集中的：

    1. 全部 UID
    2. danmakuSource = 1 或 4 的 UID

    最终进行去重。
    """

    all_uids = []
    source1_4_uids = []

    failed = []

    total = len(
        episode_ids
    )

    for ep_index, set_id in enumerate(
        episode_ids,
        start=1
    ):

        print(
            f"  弹幕进度："
            f"{ep_index}/{total}",
            end="\r"
        )

        url = (
            "https://manbo.hongrenshuo.com.cn/"
            "api/v11/radio/drama/set/danmaku/h5/pull"
            f"?radioDramaSetId={set_id}"
            "&startTime=0"
            "&endTime=10000000"
        )

        response = safe_get(
            url,
            timeout=8,
            retries=1
        )

        if response is None:

            failed.append(
                set_id
            )

            continue

        try:

            data = response.json()

            danmaku_list = (
                data
                .get("b", {})
                .get(
                    "danmakuList",
                    []
                )
            )

            for item in danmaku_list:

                eid = item.get(
                    "eid"
                )

                if eid is None:
                    continue

                all_uids.append(
                    eid
                )

                if item.get(
                    "danmakuSource"
                ) in [1, 4]:

                    source1_4_uids.append(
                        eid
                    )

        except Exception as exc:

            print(
                f"\n⚠️ 弹幕解析失败："
                f"setId={set_id}"
            )

            print(
                f"   {exc}"
            )

            failed.append(
                set_id
            )

    print()

    return (
        len(set(all_uids)),
        len(set(source1_4_uids)),
        failed
    )


# ============================================================
# 8. 抓取单部漫播剧
# ============================================================

def fetch_one(url):

    response = safe_get(
        url,
        timeout=15
    )

    if response is None:

        raise RuntimeError(
            "剧集详情请求失败"
        )

    try:

        data = response.json()

    except Exception as exc:

        raise RuntimeError(
            f"JSON解析失败：{exc}"
        )

    drama_data = data.get(
        "data",
        {}
    )

    drama_name = drama_data.get(
        "title",
        "未知剧名"
    )

    last_set = drama_data.get(
        "lastSetTitle",
        "未知"
    )

    print(
        f"\n处理剧名《{drama_name}》"
    )

    print(
        f"最近更新：{last_set}"
    )

    # --------------------------------------------------------
    # 基础数据
    # --------------------------------------------------------

    watch_count = drama_data.get(
        "watchCount"
    )

    favorite_count = drama_data.get(
        "favoriteCount"
    )

    comment_count = drama_data.get(
        "commentCount"
    )

    diamond_value = drama_data.get(
        "diamondValue"
    )

    pay_count = drama_data.get(
        "payCount"
    )

    # --------------------------------------------------------
    # 剧集列表
    # --------------------------------------------------------

    set_list = drama_data.get(
        "setRespList",
        []
    )

    print(
        f"原始剧集数量："
        f"{len(set_list)}"
    )

    # --------------------------------------------------------
    # 判断付费 / 会员集
    # --------------------------------------------------------

    (
        episode_ids,
        episode_check_failed
    ) = get_member_episode_ids(
        set_list
    )

    print(
        f"共计筛选出 "
        f"{len(episode_ids)} "
        f"个付费或会员剧集。"
    )

    if episode_check_failed:

        print(
            f"⚠️ "
            f"{len(episode_check_failed)} "
            f"个剧集无法判断会员状态"
        )

    # --------------------------------------------------------
    # 获取 UID
    # --------------------------------------------------------

    (
        uid_count,
        source1_4_count,
        danmu_failed
    ) = get_danmaku_uids(
        episode_ids
    )

    print(
        f"UID 总数："
        f"{uid_count}"
    )

    print(
        f"弹幕ID_source1+4："
        f"{source1_4_count}"
    )

    # --------------------------------------------------------
    # 抓取错误
    # --------------------------------------------------------

    errors = []

    if episode_check_failed:

        errors.append(
            f"会员集判断失败"
            f"{len(episode_check_failed)}集"
        )

    if danmu_failed:

        errors.append(
            f"弹幕抓取失败"
            f"{len(danmu_failed)}集"
        )

    error_text = "；".join(
        errors
    )

    # --------------------------------------------------------
    # 返回
    # --------------------------------------------------------

    return {
        "最近更新": last_set,

        "付费集数": len(
            episode_ids
        ),

        "UID数量": uid_count,

        "弹幕ID_source1+4": (
            source1_4_count
        ),

        "播放量": watch_count,

        "收藏数": favorite_count,

        "评论数": comment_count,

        "投喂数": diamond_value,

        "实际付费人数": pay_count,

        "抓取错误": error_text,
    }


# ============================================================
# 9. 主程序
# ============================================================

def main():

    os.makedirs(
        OUTPUT_DIR,
        exist_ok=True
    )

    # --------------------------------------------------------
    # 输入文件
    # --------------------------------------------------------

    if not os.path.exists(
        INPUT_FILE
    ):

        raise FileNotFoundError(
            f"找不到输入文件："
            f"{INPUT_FILE}\n"
            "请把「漫播临时周数据链接.xlsx」"
            "放进 data/"
        )

    df = pd.read_excel(
        INPUT_FILE
    )

    if "url" not in df.columns:

        raise ValueError(
            "漫播输入 Excel 必须包含 url 列。"
        )

    # --------------------------------------------------------
    # 如果没有剧名列，也不影响程序
    # --------------------------------------------------------

    if "剧名" not in df.columns:

        print(
            "⚠️ 输入文件没有「剧名」列，"
            "将只根据 url 判断空行。"
        )

    # --------------------------------------------------------
    # 结果列
    # --------------------------------------------------------

    result_columns = [
        "最近更新",
        "付费集数",
        "UID数量",
        "弹幕ID_source1+4",
        "播放量",
        "收藏数",
        "评论数",
        "投喂数",
        "实际付费人数",
        "抓取错误",
    ]

    # --------------------------------------------------------
    # 初始化结果列
    #
    # 使用 None，而不是直接生成错误。
    # 因此空白行最终仍然保持为空。
    # --------------------------------------------------------

    for column in result_columns:

        df[column] = None

    # --------------------------------------------------------
    # 统计
    # --------------------------------------------------------

    success_count = 0
    failed_count = 0
    blank_count = 0

    # ========================================================
    # 遍历 Excel
    # ========================================================

    for i in range(
        len(df)
    ):

        # ----------------------------------------------------
        # 原始剧名
        # ----------------------------------------------------

        if "剧名" in df.columns:

            drama_name_raw = (
                df.at[i, "剧名"]
            )

        else:

            drama_name_raw = ""

        # ----------------------------------------------------
        # 原始 URL
        # ----------------------------------------------------

        url_raw = df.at[
            i,
            "url"
        ]

        # ----------------------------------------------------
        # 清理
        # ----------------------------------------------------

        drama_name = (
            ""
            if pd.isna(
                drama_name_raw
            )
            else str(
                drama_name_raw
            ).strip()
        )

        url = normalize_url(
            url_raw
        )

        # ====================================================
        # 空白行
        # ====================================================

        if (
            not drama_name
            and not url
        ):

            blank_count += 1

            print(
                f"\n[{i + 1}/{len(df)}] "
                "空行，跳过抓取"
            )

            # 不写任何结果
            # 保持这一行所有结果列为空

            continue

        # ====================================================
        # 有剧名但没有 URL
        # ====================================================

        if (
            drama_name
            and not url
        ):

            error_text = (
                "有剧名但缺少URL"
            )

            print(
                f"\n[{i + 1}/{len(df)}] "
                f"❌ {drama_name}："
                f"{error_text}"
            )

            df.at[
                i,
                "抓取错误"
            ] = error_text

            failed_count += 1

            continue

        # ====================================================
        # 正常抓取
        # ====================================================

        print(
            "\n" + "=" * 70
        )

        print(
            f"进度："
            f"{i + 1}/{len(df)}"
        )

        if drama_name:

            print(
                f"剧名："
                f"{drama_name}"
            )

        print(
            f"URL："
            f"{url}"
        )

        print(
            "=" * 70
        )

        try:

            result = fetch_one(
                url
            )

            for key in result_columns:

                df.at[
                    i,
                    key
                ] = result.get(
                    key
                )

            # ------------------------------------------------
            # 只要成功拿到 UID 数量，就视为主体抓取成功
            # ------------------------------------------------

            if result.get(
                "UID数量"
            ) is not None:

                success_count += 1

            else:

                failed_count += 1

        except Exception as exc:

            print(
                f"❌ 处理 URL 时发生错误："
                f"{url}"
            )

            print(
                f"错误：{exc}"
            )

            df.at[
                i,
                "抓取错误"
            ] = str(exc)

            failed_count += 1

    # ========================================================
    # 输出文件
    # ========================================================

    now = datetime.now(
        TZ
    )

    date_str = now.strftime(
        "%m%d"
    )

    output_path = os.path.join(
        OUTPUT_DIR,
        f"漫播周数据{date_str}.csv"
    )

    # utf-8-sig：
    # Windows / Excel 直接打开中文不会乱码
    df.to_csv(
        output_path,
        index=False,
        encoding="utf-8-sig"
    )

    # ========================================================
    # 完成统计
    # ========================================================

    print(
        "\n" + "=" * 60
    )

    print(
        "漫播处理完成"
    )

    print(
        "=" * 60
    )

    print(
        f"总行数：{len(df)}"
    )

    print(
        f"成功：{success_count}"
    )

    print(
        f"失败：{failed_count}"
    )

    print(
        f"空白分隔行：{blank_count}"
    )

    print(
        f"文件：{output_path}"
    )


# ============================================================
# 10. 程序入口
# ============================================================

if __name__ == "__main__":
    main()
