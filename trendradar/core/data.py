# coding=utf-8
"""
数据处理模块

提供数据读取、保存和检测功能：
- save_titles_to_file: 保存标题到 TXT 文件
- read_all_today_titles: 从存储后端读取当天所有标题
- detect_latest_new_titles: 检测最新批次的新增标题

Author: TrendRadar Team
"""

from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Callable


def save_titles_to_file(
    results: Dict,
    id_to_name: Dict,
    failed_ids: List,
    output_path: str,
    clean_title_func: Callable[[str], str],
) -> str:
    """
    保存标题到 TXT 文件

    Args:
        results: 抓取结果 {source_id: {title: title_data}}
        id_to_name: ID 到名称的映射
        failed_ids: 失败的 ID 列表
        output_path: 输出文件路径
        clean_title_func: 标题清理函数

    Returns:
        str: 保存的文件路径
    """
    # 确保目录存在
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as f:
        for id_value, title_data in results.items():
            # id | name 或 id
            name = id_to_name.get(id_value)
            if name and name != id_value:
                f.write(f"{id_value} | {name}\n")
            else:
                f.write(f"{id_value}\n")

            # 按排名排序标题
            sorted_titles = []
            for title, info in title_data.items():
                cleaned_title = clean_title_func(title)
                if isinstance(info, dict):
                    ranks = info.get("ranks", [])
                    url = info.get("url", "")
                    mobile_url = info.get("mobileUrl", "")
                else:
                    ranks = info if isinstance(info, list) else []
                    url = ""
                    mobile_url = ""

                rank = ranks[0] if ranks else 1
                sorted_titles.append((rank, cleaned_title, url, mobile_url))

            sorted_titles.sort(key=lambda x: x[0])

            for rank, cleaned_title, url, mobile_url in sorted_titles:
                line = f"{rank}. {cleaned_title}"

                if url:
                    line += f" [URL:{url}]"
                if mobile_url:
                    line += f" [MOBILE:{mobile_url}]"
                f.write(line + "\n")

            f.write("\n")

        if failed_ids:
            f.write("==== 以下ID请求失败 ====\n")
            for id_value in failed_ids:
                f.write(f"{id_value}\n")

    return output_path


def read_all_today_titles_from_storage(
    storage_manager,
    current_platform_ids: Optional[List[str]] = None,
) -> Tuple[Dict, Dict, Dict]:
    """
    从存储后端读取当天所有标题（SQLite 数据）

    Args:
        storage_manager: 存储管理器实例
        current_platform_ids: 当前监控的平台 ID 列表（用于过滤）

    Returns:
        Tuple[Dict, Dict, Dict]: (all_results, id_to_name, title_info)
    """
    try:
        news_data = storage_manager.get_today_all_data()

        if not news_data or not news_data.items:
            return {}, {}, {}

        all_results = {}
        final_id_to_name = {}
        title_info = {}

        for source_id, news_list in news_data.items.items():
            # 按平台过滤
            if current_platform_ids is not None and source_id not in current_platform_ids:
                continue

            # 获取来源名称
            source_name = news_data.id_to_name.get(source_id, source_id)
            final_id_to_name[source_id] = source_name

            if source_id not in all_results:
                all_results[source_id] = {}
                title_info[source_id] = {}

            for item in news_list:
                title = item.title
                ranks = getattr(item, 'ranks', [item.rank])
                first_time = getattr(item, 'first_time', item.crawl_time)
                last_time = getattr(item, 'last_time', item.crawl_time)
                count = getattr(item, 'count', 1)

                all_results[source_id][title] = {
                    "ranks": ranks,
                    "url": item.url or "",
                    "mobileUrl": item.mobile_url or "",
                }

                title_info[source_id][title] = {
                    "first_time": first_time,
                    "last_time": last_time,
                    "count": count,
                    "ranks": ranks,
                    "url": item.url or "",
                    "mobileUrl": item.mobile_url or "",
                }

        return all_results, final_id_to_name, title_info

    except Exception as e:
        print(f"[存储] 从存储后端读取数据失败: {e}")
        return {}, {}, {}


def read_all_today_titles(
    storage_manager,
    current_platform_ids: Optional[List[str]] = None,
) -> Tuple[Dict, Dict, Dict]:
    """
    读取当天所有标题（从存储后端）

    Args:
        storage_manager: 存储管理器实例
        current_platform_ids: 当前监控的平台 ID 列表（用于过滤）

    Returns:
        Tuple[Dict, Dict, Dict]: (all_results, id_to_name, title_info)
    """
    all_results, final_id_to_name, title_info = read_all_today_titles_from_storage(
        storage_manager, current_platform_ids
    )

    if all_results:
        total_count = sum(len(titles) for titles in all_results.values())
        print(f"[存储] 已从存储后端读取 {total_count} 条标题")
    else:
        print("[存储] 当天暂无数据")

    return all_results, final_id_to_name, title_info


def _parse_date_folder(folder_name: str) -> Optional[datetime]:
    """解析日期目录名，支持 ISO 与中文格式。"""
    for fmt in ("%Y-%m-%d", "%Y年%m月%d日"):
        try:
            return datetime.strptime(folder_name, fmt)
        except ValueError:
            continue
    return None


def _list_date_range_strings(
    storage_manager,
    start_date: str,
    end_date: Optional[str] = None,
) -> List[str]:
    """列出指定日期范围内、本地已存在的数据日期。"""
    try:
        start_dt = datetime.strptime(start_date, "%Y-%m-%d")
    except ValueError:
        raise ValueError(f"无效的开始日期格式: {start_date}，应为 YYYY-MM-DD")

    if end_date:
        try:
            end_dt = datetime.strptime(end_date, "%Y-%m-%d")
        except ValueError:
            raise ValueError(f"无效的结束日期格式: {end_date}，应为 YYYY-MM-DD")
    else:
        end_dt = datetime.now()

    if start_dt > end_dt:
        raise ValueError(f"开始日期 {start_date} 不能晚于结束日期 {end_dt.strftime('%Y-%m-%d')}")

    data_dir = Path(getattr(storage_manager, "data_dir", "output"))
    if not data_dir.exists():
        return []

    available_dates = []
    current = start_dt
    while current <= end_dt:
        date_str = current.strftime("%Y-%m-%d")
        if (data_dir / date_str).exists():
            available_dates.append(date_str)
        current += timedelta(days=1)

    if available_dates:
        return available_dates

    # 兼容旧中文目录名
    for child in data_dir.iterdir():
        if not child.is_dir():
            continue
        parsed = _parse_date_folder(child.name)
        if parsed and start_dt.date() <= parsed.date() <= end_dt.date():
            available_dates.append(parsed.strftime("%Y-%m-%d"))

    return sorted(set(available_dates))


def read_titles_from_date_range(
    storage_manager,
    start_date: str,
    end_date: Optional[str] = None,
    current_platform_ids: Optional[List[str]] = None,
) -> Tuple[Dict, Dict, Dict]:
    """
    从存储后端读取指定日期范围内的所有标题，并合并为一个分析视图。
    """
    date_strings = _list_date_range_strings(storage_manager, start_date, end_date)
    if not date_strings:
        return {}, {}, {}

    all_results: Dict = {}
    final_id_to_name: Dict = {}
    title_info: Dict = {}

    for date_str in date_strings:
        news_data = storage_manager.get_today_all_data(date_str)
        if not news_data or not news_data.items:
            continue

        for source_id, news_list in news_data.items.items():
            if current_platform_ids is not None and source_id not in current_platform_ids:
                continue

            source_name = news_data.id_to_name.get(source_id, source_id)
            final_id_to_name[source_id] = source_name
            all_results.setdefault(source_id, {})
            title_info.setdefault(source_id, {})

            for item in news_list:
                title = item.title
                ranks = list(getattr(item, "ranks", [item.rank]) or [item.rank])
                first_time = f"{date_str} {getattr(item, 'first_time', item.crawl_time)}"
                last_time = f"{date_str} {getattr(item, 'last_time', item.crawl_time)}"
                count = getattr(item, "count", 1)

                existing = title_info[source_id].get(title)
                if existing:
                    merged_ranks = existing["ranks"][:]
                    for rank in ranks:
                        if rank not in merged_ranks:
                            merged_ranks.append(rank)
                    merged_ranks.sort()

                    existing["first_time"] = min(existing["first_time"], first_time)
                    existing["last_time"] = max(existing["last_time"], last_time)
                    existing["count"] += count
                    existing["ranks"] = merged_ranks
                    if not existing.get("url") and item.url:
                        existing["url"] = item.url
                    if not existing.get("mobileUrl") and item.mobile_url:
                        existing["mobileUrl"] = item.mobile_url
                else:
                    title_info[source_id][title] = {
                        "first_time": first_time,
                        "last_time": last_time,
                        "count": count,
                        "ranks": sorted(set(ranks)),
                        "url": item.url or "",
                        "mobileUrl": item.mobile_url or "",
                    }

                all_results[source_id][title] = {
                    "ranks": title_info[source_id][title]["ranks"],
                    "url": title_info[source_id][title]["url"],
                    "mobileUrl": title_info[source_id][title]["mobileUrl"],
                }

    total_count = sum(len(titles) for titles in all_results.values())
    print(
        f"[存储] 已从 {start_date} 到 {(end_date or datetime.now().strftime('%Y-%m-%d'))} 读取 {total_count} 条去重标题"
    )
    return all_results, final_id_to_name, title_info


def detect_latest_new_titles_from_storage(
    storage_manager,
    current_platform_ids: Optional[List[str]] = None,
) -> Dict:
    """
    从存储后端检测最新批次的新增标题

    Args:
        storage_manager: 存储管理器实例
        current_platform_ids: 当前监控的平台 ID 列表（用于过滤）

    Returns:
        Dict: 新增标题 {source_id: {title: title_data}}
    """
    try:
        # 获取最新抓取数据
        latest_data = storage_manager.get_latest_crawl_data()
        if not latest_data or not latest_data.items:
            return {}

        # 获取所有历史数据
        all_data = storage_manager.get_today_all_data()
        if not all_data or not all_data.items:
            # 没有历史数据（第一次抓取），不应该有"新增"标题
            return {}

        # 收集历史标题（不包括最新批次的时间）
        latest_time = latest_data.crawl_time
        historical_titles = {}

        for source_id, news_list in all_data.items.items():
            if current_platform_ids is not None and source_id not in current_platform_ids:
                continue

            historical_titles[source_id] = set()
            for item in news_list:
                # 只统计非最新批次的标题
                first_time = getattr(item, 'first_time', item.crawl_time)
                if first_time != latest_time:
                    historical_titles[source_id].add(item.title)

        # 检查是否是当天第一次抓取（没有任何历史标题）
        # 如果所有平台的历史标题集合都为空，说明只有一个抓取批次，不应该有"新增"标题
        has_historical_data = any(len(titles) > 0 for titles in historical_titles.values())
        if not has_historical_data:
            return {}

        # 找出新增标题
        new_titles = {}
        for source_id, news_list in latest_data.items.items():
            if current_platform_ids is not None and source_id not in current_platform_ids:
                continue

            historical_set = historical_titles.get(source_id, set())
            source_new_titles = {}

            for item in news_list:
                if item.title not in historical_set:
                    source_new_titles[item.title] = {
                        "ranks": [item.rank],
                        "url": item.url or "",
                        "mobileUrl": item.mobile_url or "",
                    }

            if source_new_titles:
                new_titles[source_id] = source_new_titles

        return new_titles

    except Exception as e:
        print(f"[存储] 从存储后端检测新标题失败: {e}")
        return {}


def detect_latest_new_titles(
    storage_manager,
    current_platform_ids: Optional[List[str]] = None,
) -> Dict:
    """
    检测当日最新批次的新增标题（从存储后端）

    Args:
        storage_manager: 存储管理器实例
        current_platform_ids: 当前监控的平台 ID 列表（用于过滤）

    Returns:
        Dict: 新增标题 {source_id: {title: title_data}}
    """
    new_titles = detect_latest_new_titles_from_storage(storage_manager, current_platform_ids)
    if new_titles:
        total_new = sum(len(titles) for titles in new_titles.values())
        print(f"[存储] 从存储后端检测到 {total_new} 条新增标题")
    return new_titles


def is_first_crawl_today(output_dir: str, date_folder: str) -> bool:
    """
    检测是否是当天第一次爬取

    Args:
        output_dir: 输出目录
        date_folder: 日期文件夹名称

    Returns:
        bool: 是否是当天第一次爬取
    """
    txt_dir = Path(output_dir) / date_folder / "txt"

    if not txt_dir.exists():
        return True

    files = sorted([f for f in txt_dir.iterdir() if f.suffix == ".txt"])
    return len(files) <= 1
