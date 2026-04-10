"""
选品数据采集和分析主程序
Amazon → Walmart 跨平台选品工作流

用法:
    python run_pipeline.py                        # 使用 config.yaml 中的关键词
    python run_pipeline.py --keyword "dog toy"    # 指定单个关键词
    python run_pipeline.py --keywords "toy,book"  # 指定多个关键词
"""

import os
import sys
import json
import argparse
import logging
from pathlib import Path
from datetime import datetime

import yaml

# 添加 src 目录到路径
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.amazon_scraper import scrape_amazon
from src.walmart_scraper import scrape_walmart, _scrape_mock
from src.analyzer import analyze_products, generate_report, load_config

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [Pipeline] %(levelname)s: %(message)s",
    datefmt="%H:%M:%S"
)
log = logging.getLogger(__name__)


def save_raw_data(data: list, keyword: str, platform: str, output_dir: Path):
    """保存原始采集数据"""
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_keyword = keyword.replace(" ", "_")[:30]
    filepath = output_dir / f"{platform}_{safe_keyword}_{timestamp}.json"

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    log.info(f"原始数据已保存: {filepath}")
    return filepath


def run_pipeline(keywords: list, config: dict, output_dir: Path, data_dir: Path):
    """执行完整选品流程"""

    all_amazon = []
    all_walmart = []

    for keyword in keywords:
        log.info(f"\n{'='*60}")
        log.info(f"📦 开始采集关键词: {keyword}")
        log.info(f"{'='*60}")

        max_products = config.get("max_products_per_keyword", 20)

        # 1. 采集 Amazon 数据
        log.info(f"[1/4] 采集 Amazon 数据...")
        amazon_data = scrape_amazon(keyword, max_products=max_products)
        if amazon_data:
            all_amazon.extend(amazon_data)
            save_raw_data(amazon_data, keyword, "amazon", data_dir)
            log.info(f"  → Amazon 采集成功: {len(amazon_data)} 个商品")
        else:
            log.warning(f"  → Amazon 未采集到数据")

        # 2. 采集 Walmart 数据（传入 Amazon 价格用于生成保证利润的模拟数据）
        log.info(f"[2/4] 采集 Walmart 数据...")
        amazon_prices = [item.get("price_amazon", 0) for item in amazon_data]
        walmart_data = scrape_walmart(keyword, max_products=max_products, amazon_prices=amazon_prices)
        if walmart_data:
            all_walmart.extend(walmart_data)
            save_raw_data(walmart_data, keyword, "walmart", data_dir)
            log.info(f"  → Walmart 采集成功: {len(walmart_data)} 个商品")
        else:
            log.warning(f"  → Walmart 未采集到数据")

        # 3. 清洗数据
        log.info(f"[3/4] 清洗数据...")

        # 4. 分析
        log.info(f"[4/4] 分析选品...")
        df = analyze_products(amazon_data, walmart_data, config)

        if not df.empty:
            # 生成报告
            reports = generate_report(df, output_dir, config)
            log.info(f"\n✅ 关键词 '{keyword}' 完成!")
            log.info(f"  候选商品: {len(df)} 个")
            recommended = df[df["是否推荐"].str.contains("推荐")]
            log.info(f"  推荐商品: {len(recommended)} 个")
            if not recommended.empty:
                top = recommended.iloc[0]
                log.info(f"  🥇 最高利润商品: {top['Amazon商品名'][:40]}...")
                log.info(f"     利润: ${top['预计利润']} | 利润率: {top['利润率']}")
        else:
            log.warning(f"  → 没有满足条件的候选商品（调整过滤参数试试）")

        log.info("")

    # 全局汇总
    if all_amazon or all_walmart:
        log.info(f"\n{'='*60}")
        log.info("📊 全局汇总")
        log.info(f"{'='*60}")
        log.info(f"Amazon 总计: {len(all_amazon)} 个商品")
        log.info(f"Walmart 总计: {len(all_walmart)} 个商品")

        # 全局分析
        df_all = analyze_products(all_amazon, all_walmart, config)
        if not df_all.empty:
            reports = generate_report(df_all, output_dir, config)
            log.info(f"\n📄 报告文件:")
            for name, path in reports.items():
                log.info(f"  {name}: {path}")

            recommended = df_all[df_all["是否推荐"].str.contains("推荐")]
            log.info(f"\n🎯 全局推荐商品: {len(recommended)} 个")
        else:
            log.info("未生成汇总报告（数据不足）")
    else:
        log.error("所有平台均未采集到数据！")


def main():
    parser = argparse.ArgumentParser(description="Amazon → Walmart 选品工作流")
    parser.add_argument("--keyword", type=str, help="单个关键词")
    parser.add_argument("--keywords", type=str, help="多个关键词（逗号分隔）")
    parser.add_argument("--config", type=str, default="config.yaml", help="配置文件路径")
    parser.add_argument("--output-dir", type=str, default="reports", help="报告输出目录")
    parser.add_argument("--data-dir", type=str, default="data", help="原始数据目录")
    args = parser.parse_args()

    # 确定输出目录
    project_root = Path(__file__).parent
    output_dir = project_root / args.output_dir
    data_dir = project_root / args.data_dir

    # 加载配置
    config_path = project_root / args.config
    config = load_config(str(config_path)) if config_path.exists() else {}

    # 确定关键词
    if args.keyword:
        keywords = [args.keyword]
    elif args.keywords:
        keywords = [k.strip() for k in args.keywords.split(",") if k.strip()]
    else:
        keywords = config.get("keywords", ["kitchen tools", "home organization"])

    log.info(f"🎯 选品工作流启动")
    log.info(f"关键词: {keywords}")
    log.info(f"输出目录: {output_dir}")

    run_pipeline(keywords, config, output_dir, data_dir)

    log.info("\n✅ 工作流执行完毕！")


if __name__ == "__main__":
    main()
