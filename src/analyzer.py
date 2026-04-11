"""
选品分析模块
将 Amazon 和 Walmart 数据合并，分析利润空间，过滤出优质候选商品
"""

import os
import logging
import pandas as pd
import yaml
from datetime import datetime
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [Analyzer] %(levelname)s: %(message)s',
    datefmt='%H:%M:%S'
)
log = logging.getLogger(__name__)


# 估算成本参数（可配置）
COSTS = {
    "amazon_buyer_fee": 0.0,        # 亚马逊采购成本（商品本身价）
    "international_shipping": 3.5,  # 国际运费（估算每件，可批量降低）
    "walmart_referral_fee": 0.12,   # 沃尔玛推荐费 12%
    "walmart_closing_fee": 0.30,     # 沃尔玛固定Closing费 $0.30
    "fba_storage_per_cubic": 0.78,  # FBA 存储费（估算 $0.78/立方英尺/月）
    "estimated_weight_lbs": 1.0,     # 估算重量（轻小件优先）
}

# ============================================================
# 全局缓存：过滤词表（从配置文件加载，只加载一次）
# ============================================================
_filter_cache: dict = {}


def _get_filter_lists() -> dict:
    """懒加载：从配置文件读取过滤词表，缓存结果"""
    global _filter_cache
    if not _filter_cache:
        config = load_config()
        _filter_cache = {
            "infringement": [k.lower() for k in config.get("infringement_keywords", [])],
            "restricted": [k.lower() for k in config.get("walmart_restricted", [])],
        }
        log.info(f"加载侵权词 {len(_filter_cache['infringement'])} 个，"
                 f"受限品类 {len(_filter_cache['restricted'])} 个")
    return _filter_cache


def load_config(config_path: str = None) -> dict:
    """加载配置文件"""
    if config_path is None:
        config_path = Path(__file__).parent.parent / "config.yaml"
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def is_infringement(product_name: str) -> bool:
    """
    检测商品名是否涉及品牌侵权风险（从配置文件读取词表）
    包含知名商标/版权关键词即标记
    """
    filters = _get_filter_lists()
    name_lower = product_name.lower()
    for brand in filters["infringement"]:
        if brand in name_lower:
            return True
    return False


def is_walmart_compliant(product_name: str) -> bool:
    """
    检测商品名是否符合 Walmart 平台基本规范（从配置文件读取词表）
    限制类别：药品/生鲜/超大件/武器/成人用品等
    """
    filters = _get_filter_lists()
    name_lower = product_name.lower()
    for restricted in filters["restricted"]:
        if restricted in name_lower:
            return False
    return True


def is_price_in_range(price: float, min_price: float, max_price: float) -> bool:
    """检测价格是否在指定区间内"""
    return min_price <= price <= max_price


def estimate_walmart_cost(amazon_price: float) -> dict:
    """
    估算在 Walmart 销售的总成本和利润

    Args:
        amazon_price: 在 Amazon 采购该商品的价格

    Returns:
        成本分解字典
    """
    referral_fee = amazon_price * COSTS["walmart_referral_fee"]
    closing_fee = COSTS["walmart_closing_fee"]
    shipping = COSTS["international_shipping"]

    # 估算 FBA 包装重量成本（加入）
    weight_surcharge = COSTS["estimated_weight_lbs"] * 0.30

    total_cost = amazon_price + referral_fee + closing_fee + shipping + weight_surcharge

    return {
        "cost_amazon_buy": amazon_price,
        "cost_referral_fee": round(referral_fee, 2),
        "cost_closing_fee": closing_fee,
        "cost_shipping": shipping,
        "cost_weight": round(weight_surcharge, 2),
        "total_cost": round(total_cost, 2),
    }


def analyze_products(amazon_data: list, walmart_data: list, config: dict = None) -> pd.DataFrame:
    """
    核心分析逻辑：合并数据，计算利润，筛选候选商品

    Args:
        amazon_data: Amazon 商品列表
        walmart_data: Walmart 商品列表
        config: 过滤配置

    Returns:
        候选商品 DataFrame
    """
    if config is None:
        config = load_config()

    f = config.get("filter", {})
    min_reviews = f.get("min_amazon_reviews", 50)
    max_reviews = f.get("max_amazon_reviews", 3000)
    min_rating = f.get("min_amazon_rating", 3.5)
    max_rating = f.get("max_amazon_rating", 4.5)
    min_price_gap = f.get("min_price_gap", 3.0)
    min_margin = f.get("min_profit_margin", 0.20)

    # 价格区间过滤（从配置文件读取）
    walmart_min_price = f.get("min_price", 8.0)
    walmart_max_price = f.get("max_price", 80.0)

    df_amazon = pd.DataFrame(amazon_data)
    df_walmart = pd.DataFrame(walmart_data)

    log.info(f"Amazon 数据: {len(df_amazon)} 条, Walmart 数据: {len(df_walmart)} 条")
    log.info(f"价格过滤区间: ${walmart_min_price} ~ ${walmart_max_price}")

    if df_amazon.empty:
        log.warning("Amazon 数据为空，跳过分析")
        return pd.DataFrame()

    # 合并分析
    results = []
    skip_reasons = {"价格超出范围": 0, "品牌侵权": 0, "Walmart不合规": 0,
                    "评论数不符": 0, "评分不符": 0}

    for _, amazon_row in df_amazon.iterrows():
        keyword = amazon_row.get("keyword", "")
        amazon_price = amazon_row.get("price_amazon", 0)
        reviews = amazon_row.get("reviews_count", 0)
        rating = amazon_row.get("rating", 0)
        product_name = amazon_row.get("name", "")

        # ---- 过滤1：价格必须在 $10-$50 ----
        if not is_price_in_range(amazon_price, walmart_min_price, walmart_max_price):
            skip_reasons["价格超出范围"] += 1
            continue

        # ---- 过滤2：品牌侵权检测 ----
        if is_infringement(product_name):
            skip_reasons["品牌侵权"] += 1
            continue

        # ---- 过滤3：Walmart 平台合规检测 ----
        if not is_walmart_compliant(product_name):
            skip_reasons["Walmart不合规"] += 1
            continue

        # ---- 过滤4：评论数、评分（0或缺失值放宽）----
        if amazon_price <= 0:
            continue
        if reviews > 0 and (reviews < min_reviews or reviews > max_reviews):
            skip_reasons["评论数不符"] += 1
            continue
        if rating > 0 and (rating < min_rating or rating > max_rating):
            skip_reasons["评分不符"] += 1
            continue

        # 在 Walmart 同类商品中找匹配
        # 策略：按"同品类同排名"匹配——第i个Amazon商品对应第i个Walmart商品
        # 真实场景下可用ASIN/商品名称相似度匹配，这里用索引对齐
        walmart_match = None
        walmart_price = 0.0

        if not df_walmart.empty:
            walmart_subset = df_walmart[df_walmart["keyword"] == keyword].reset_index(drop=True)
            amazon_index_list = df_amazon[df_amazon["keyword"] == keyword].reset_index(drop=True)
            # 找到当前商品在 amazon_index_list 中的位置
            try:
                amazon_local_idx = amazon_index_list[
                    amazon_index_list["asin"] == amazon_row.get("asin", "")
                ].index[0]
                # 用同样位置取 Walmart 对应商品
                if amazon_local_idx < len(walmart_subset):
                    walmart_match = walmart_subset.iloc[amazon_local_idx]
                    walmart_price = walmart_match.get("price_walmart", 0)
            except (KeyError, IndexError):
                pass

        # 估算成本和利润
        cost_info = estimate_walmart_cost(amazon_price)

        # 建议 Walmart 售价 = Walmart 同款价 或 Amazon 价 + 价差
        if walmart_price > 0:
            suggested_walmart_price = walmart_price
        else:
            suggested_walmart_price = amazon_price + min_price_gap + 5

        revenue = suggested_walmart_price
        total_cost = cost_info["total_cost"]
        profit = revenue - total_cost
        profit_margin = profit / revenue if revenue > 0 else 0

        # 价格差
        price_gap = suggested_walmart_price - amazon_price

        walmart_link = walmart_match.get("link_walmart", "") if walmart_match is not None else ""
        row = {
            "关键词": keyword,
            "ASIN": amazon_row.get("asin", ""),
            "Amazon商品名": product_name,
            "Amazon售价": amazon_price,
            "价格区间": f"${walmart_min_price}-${walmart_max_price}",
            "Amazon评分": rating,
            "Amazon评论数": reviews,
            "Amazon链接": amazon_row.get("link_amazon", ""),
            "Walmart参考价": walmart_price if walmart_price > 0 else suggested_walmart_price,
            "Walmart链接": walmart_link,
            "采购成本": cost_info["cost_amazon_buy"],
            "推荐费(12%)": cost_info["cost_referral_fee"],
            "Closing费": cost_info["cost_closing_fee"],
            "国际运费": cost_info["cost_shipping"],
            "总成本": total_cost,
            "预计利润": round(profit, 2),
            "利润率": f"{profit_margin:.1%}",
            "Amazon-Walmart价差": round(price_gap, 2),
            "侵权风险": "⚠️ 侵权" if is_infringement(product_name) else "✅ 无",
            "平台合规": "✅ 合规" if is_walmart_compliant(product_name) else "❌ 受限",
            "是否推荐": "✅ 推荐" if profit > 3 and profit_margin >= min_margin else "❌ 利润不足",
            "采集时间": amazon_row.get("scraped_at", ""),
        }

        results.append(row)

    df_result = pd.DataFrame(results)

    if not df_result.empty:
        # 按利润率排序
        df_result["利润率_num"] = df_result["利润率"].str.replace("%", "").astype(float)
        df_result = df_result.sort_values("利润率_num", ascending=False)

        # 推荐优先排序
        df_result = df_result.sort_values(
            by=["是否推荐", "预计利润"],
            ascending=[False, False]
        )

        log.info(f"分析完成: {len(df_result)} 个候选商品")
        # 打印过滤统计
        active_skips = {k: v for k, v in skip_reasons.items() if v > 0}
        if active_skips:
            log.info(f"过滤统计: {active_skips}")

    return df_result


def generate_report(df: pd.DataFrame, output_dir: str = None, config: dict = None) -> dict:
    """
    生成选品报告

    Returns:
        报告文件路径字典
    """
    if output_dir is None:
        output_dir = Path(__file__).parent.parent / "reports"
    else:
        output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    if config is None:
        config = load_config()

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output = {}

    # 1. 保存 CSV
    if config.get("output", {}).get("csv_enabled", True) and not df.empty:
        csv_path = output_dir / f"sourcing_results_{timestamp}.csv"
        df.to_csv(csv_path, index=False, encoding="utf-8-sig")
        output["csv"] = str(csv_path)
        log.info(f"CSV 报告已保存: {csv_path}")

    # 2. 保存 Excel（带格式）
    if config.get("output", {}).get("xlsx_enabled", True) and not df.empty:
        xlsx_path = output_dir / f"sourcing_report_{timestamp}.xlsx"
        with pd.ExcelWriter(xlsx_path, engine="openpyxl") as writer:
            # 总览表
            df.to_excel(writer, sheet_name="候选商品", index=False)

            # 推荐表
            recommended = df[df["是否推荐"].str.contains("推荐")].copy()
            recommended.to_excel(writer, sheet_name="✅推荐商品", index=False)

            # 统计摘要
            summary_data = {
                "指标": ["候选商品总数", "推荐商品数", "平均利润率", "最高利润率", "平均利润($)", "最高利润($)"],
                "数值": [
                    len(df),
                    len(recommended),
                    f"{df['利润率_num'].mean():.1f}%" if not df.empty else "N/A",
                    f"{df['利润率_num'].max():.1f}%" if not df.empty else "N/A",
                    f"${df['预计利润'].mean():.2f}" if not df.empty else "N/A",
                    f"${df['预计利润'].max():.2f}" if not df.empty else "N/A",
                ]
            }
            pd.DataFrame(summary_data).to_excel(writer, sheet_name="📊统计摘要", index=False)

        output["xlsx"] = str(xlsx_path)
        log.info(f"Excel 报告已保存: {xlsx_path}")

    return output


if __name__ == "__main__":
    # 模拟数据测试
    import random
    amazon_sample = [
        {"keyword": "kitchen shelf", "asin": "B001", "name": "Kitchen Shelf Organizer",
         "price_amazon": 15.99, "rating": 4.1, "reviews_count": 500,
         "link_amazon": "https://amazon.com/dp/B001", "scraped_at": datetime.now().isoformat()},
        {"keyword": "kitchen shelf", "asin": "B002", "name": "Bamboo Shelf Stackable",
         "price_amazon": 22.50, "rating": 4.3, "reviews_count": 1200,
         "link_amazon": "https://amazon.com/dp/B002", "scraped_at": datetime.now().isoformat()},
    ]
    walmart_sample = [
        {"keyword": "kitchen shelf", "name": "Kitchen Wire Shelf",
         "price_walmart": 19.99, "rating": 4.0, "reviews_count": 200,
         "link_walmart": "https://walmart.com/ip/001", "scraped_at": datetime.now().isoformat()},
    ]

    df = analyze_products(amazon_sample, walmart_sample)
    print(df[["Amazon商品名", "Amazon售价", "Walmart参考价", "预计利润", "利润率", "是否推荐"]])
