import os
import time
from datetime import datetime

import pandas as pd
import pytz
import requests
import urllib3


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

INPUT_FILE = os.path.join(
    ROOT,
    "data",
    "漫播临时周数据链接.xlsx"
)

OUTPUT_DIR = os.path.join(ROOT, "output")

TZ = pytz.timezone("Asia/Shanghai")


urllib3.disable_warnings(
    urllib3.exceptions.InsecureRequestWarning
)


session = requests.Session()

session.headers.update({
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/130.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
})


def safe_get(url, timeout=10, retries=2):
    """
    请求 URL。

    1. 正常 SSL
    2. SSL 失败后使用 verify=False
    3. 普通网络错误自动重试
    4. 最终失败返回 None

    这里沿用原有漫播脚本的请求策略。
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
                    f"⚠️ 请求失败，第 {attempt + 1}/{retries} 次重试："
                    f"{exc}"
                )
                time.sleep(1)
            else:
                print(f"❌ 请求最终失败：{url}")
                print(f"   {exc}")
                return None

    try:
        response = session.get(
            url,
            timeout=timeout,
            verify=False
        )

        response.raise_for_status()

        print("   ✓ verify=False 请求成功")

        return response

    except Exception as exc:
        print("❌ SSL关闭后仍然请求失败：")
        print(f"   {url}")
        print(f"   {exc}")
        return None


def get_member_episode_ids(set_list):
    """
    按原漫播脚本逻辑：
    - vipFree=1
    - payType=1
    - price>0
    直接判断为付费/会员集。
    其他集访问 dramaSetDetail，
    code=105 时加入付费集。
    """

    episodes = []
    failed = []

    for item in set_list:
        vip_free = item.get("vipFree", 0)
        pay_type = item.get("payType", 0)
        price = item.get("price", 0)
        set_id = item.get("setIdStr")

        if not set_id:
            continue

        if (
            vip_free == 1
            or pay_type == 1
            or (
                price is not None
                and price > 0
            )
        ):
            episodes.append(set_id)
            continue

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
            failed.append(set_id)
            continue

        try:
            check_data = check_response.json()

            if check_data.get("code") == 105:
                episodes.append(set_id)

        except Exception as exc:
            print(
                f"⚠️ 判断会员剧失败："
                f"setId={set_id}，{exc}"
            )
            failed.append(set_id)

    return episodes, failed


def get_danmaku_uids(episode_ids):
    """
    获取付费/会员集中的：
    - 全部 UID
    - danmakuSource 1 + 4 UID
    """

    all_uids = []
    source1_4_uids = []
    failed = []

    for ep_index, set_id in enumerate(
        episode_ids,
        start=1
    ):
        print(
            f"  弹幕进度："
            f"{ep_index}/{len(episode_ids)}",
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
            failed.append(set_id)
            continue

        try:
            data = response.json()

            danmaku_list = (
                data
                .get("b", {})
                .get("danmakuList", [])
            )

            for item in danmaku_list:
                eid = item.get("eid")

                if eid is None:
                    continue

                all_uids.append(eid)

                if item.get("danmakuSource") in [1, 4]:
                    source1_4_uids.append(eid)

        except Exception as exc:
            print(
                f"\n⚠️ 弹幕解析失败："
                f"setId={set_id}"
            )
            print(f"   {exc}")
            failed.append(set_id)

    print()

    return (
        len(set(all_uids)),
        len(set(source1_4_uids)),
        failed
    )


def fetch_one(url):
    response = safe_get(
        url,
        timeout=15
    )

    if response is None:
        raise RuntimeError("剧集详情请求失败")

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

    print(f"\n处理剧名《{drama_name}》")
    print(f"最近更新：{last_set}")

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

    set_list = drama_data.get(
        "setRespList",
        []
    )

    print(f"原始剧集数量：{len(set_list)}")

    episode_ids, episode_check_failed = (
        get_member_episode_ids(set_list)
    )

    print(
        f"共计筛选出 "
        f"{len(episode_ids)} "
        f"个付费或会员剧集。"
    )

    if episode_check_failed:
        print(
            f"⚠️ {len(episode_check_failed)} "
            f"个剧集无法判断会员状态"
        )

    uid_count, source1_4_count, danmu_failed = (
        get_danmaku_uids(episode_ids)
    )

    print(f"UID 总数：{uid_count}")
    print(
        f"弹幕ID_source1+4："
        f"{source1_4_count}"
    )

    return {
        "最近更新": last_set,
        "付费集数": len(episode_ids),
        "UID数量": uid_count,
        "弹幕ID_source1+4": source1_4_count,
        "播放量": watch_count,
        "收藏数": favorite_count,
        "评论数": comment_count,
        "投喂数": diamond_value,
        "实际付费人数": pay_count,
        "抓取错误": "",
    }


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    if not os.path.exists(INPUT_FILE):
        raise FileNotFoundError(
            f"找不到输入文件：{INPUT_FILE}\n"
            "请把「漫播临时周数据链接.xlsx」放进 data/"
        )

    df = pd.read_excel(INPUT_FILE)

    if "url" not in df.columns:
        raise ValueError(
            "漫播输入 Excel 必须包含 url 列。"
        )

    result_lists = {
        "最近更新": [],
        "付费集数": [],
        "UID数量": [],
        "弹幕ID_source1+4": [],
        "播放量": [],
        "收藏数": [],
        "评论数": [],
        "投喂数": [],
        "实际付费人数": [],
        "抓取错误": [],
    }

    urls = df["url"].tolist()

    for i, url in enumerate(urls, start=1):
        print("\n" + "=" * 70)
        print(f"进度：{i}/{len(urls)}")
        print(f"URL：{url}")
        print("=" * 70)

        try:
            result = fetch_one(url)

            for key in result_lists:
                result_lists[key].append(
                    result.get(key)
                )

        except Exception as exc:
            print(
                f"❌ 处理 URL 时发生错误：{url}"
            )
            print(f"错误：{exc}")

            for key in result_lists:
                if key == "抓取错误":
                    result_lists[key].append(
                        str(exc)
                    )
                else:
                    result_lists[key].append(None)

    for key, values in result_lists.items():
        df.loc[:, key] = values

    now = datetime.now(TZ)
    date_str = now.strftime("%m%d")

    output_path = os.path.join(
        OUTPUT_DIR,
        f"漫播周数据{date_str}.xlsx"
    )

    df.to_excel(
        output_path,
        index=False
    )

    success_count = sum(
        x is not None
        for x in result_lists["UID数量"]
    )

    print("\n" + "=" * 60)
    print("漫播处理完成")
    print("=" * 60)
    print(f"总剧数：{len(df)}")
    print(f"成功：{success_count}")
    print(f"失败：{len(df) - success_count}")
    print(f"文件：{output_path}")


if __name__ == "__main__":
    main()
