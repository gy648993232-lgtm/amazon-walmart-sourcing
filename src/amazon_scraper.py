"""
Amazon 爬虫模块
使用 DrissionPage 隐身浏览器绕过反爬机制
"""

import time
import json
import logging
from datetime import datetime
from DrissionPage import ChromiumPage, ChromiumOptions

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [Amazon] %(levelname)s: %(message)s',
    datefmt='%H:%M:%S'
)
log = logging.getLogger(__name__)


def _build_page(keyword: str) -> str:
    """构建 Amazon 搜索 URL"""
    import urllib.parse
    q = urllib.parse.quote_plus(keyword)
    return f"https://www.amazon.com/s?k={q}&ref=nb_sb_noss"


def scrape_amazon(keyword: str, max_products: int = 20) -> list[dict]:
    """
    从 Amazon 抓取商品数据

    Args:
        keyword: 搜索关键词
        max_products: 最大采集数量

    Returns:
        商品数据列表
    """
    results = []

    co = ChromiumOptions()
    co.set_argument("--no-sandbox")
    co.set_argument("--disable-dev-shm-usage")
    co.set_argument("--disable-blink-features=AutomationControlled")
    co.set_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/122.0.0.0 Safari/537.36")
    co.set_argument("--disable-images")          # 加速加载
    co.set_argument("--disable-javascript")     # 静态页面更快（Amazon搜索页）
    co.set_argument("--blink-settings=imagesEnabled=false")

    page = None
    try:
        log.info(f"启动浏览器访问 Amazon: {keyword}")
        page = ChromiumPage(addr_or_opts=co)

        url = _build_page(keyword)
        page.get(url, timeout=30)
        time.sleep(3)

        # 尝试处理反爬挑战
        if page.title == "Bot Detection":
            log.warning("检测到 Bot 挑战，尝试绕过...")
            time.sleep(5)
            page.refresh()
            time.sleep(3)

        # 向下滚动加载更多商品
        for _ in range(3):
            page.scroll.down(800)
            time.sleep(1.5)

        # 提取商品卡片数据
        product_cards = page.eles("@class:sg-col-4-of-12")
        if not product_cards:
            product_cards = page.eles("@data-component-type: s-search-result")
        if not product_cards:
            product_cards = page.eles("css:.s-result-item")

        log.info(f"找到 {len(product_cards)} 个商品卡片")

        for card in product_cards[:max_products]:
            try:
                # 商品名称
                name_el = card.ele("css:.a-text-normal", index=None)
                name = name_el.text if name_el else ""

                # ASIN
                asin = card.attr("data-asin") or card.attr("id", "s-result-item-") or ""

                # 价格
                price_el = card.ele("css:.a-price-whole")
                price = float(price_el.text.replace(",", "")) if price_el else 0.0

                # 评分
                rating_el = card.ele("css:.a-icon-star-small")
                rating = 0.0
                if rating_el:
                    rating_text = rating_el.text or ""
                    try:
                        rating = float(rating_text.split(" ")[0])
                    except (ValueError, IndexError):
                        pass

                # 评论数
                reviews_el = card.ele("css:.a-size-base.s-underline-text")
                reviews = 0
                if reviews_el:
                    try:
                        reviews = int(reviews_el.text.replace(",", ""))
                    except ValueError:
                        pass
                if reviews == 0:
                    reviews_el2 = card.ele("css:.a-link-normal .a-size-base")
                    if reviews_el2:
                        try:
                            reviews = int(reviews_el2.text.replace(",", ""))
                        except ValueError:
                            pass

                # Prime 标识
                is_prime = bool(card.ele("css:.a-icon-prime"))

                # 商品链接
                link_el = card.ele("css:a.a-link-normal")
                link = f"https://www.amazon.com{link_el.attr('href')}" if link_el else ""

                # BSR（排名）
                bsr_el = card.ele("css:#sp-cc-annotation, .a-badge-text")
                bsr = bsr_el.text if bsr_el else ""

                product = {
                    "keyword": keyword,
                    "asin": asin,
                    "name": name[:200],
                    "price_amazon": price,
                    "rating": rating,
                    "reviews_count": reviews,
                    "is_prime": is_prime,
                    "link_amazon": link,
                    "source": "amazon",
                    "scraped_at": datetime.now().isoformat(),
                }

                # 只保留有价格的有效数据
                if price > 0 and name:
                    results.append(product)
                    log.info(f"  ✓ {name[:60]}... | ${price} | ⭐{rating} | {reviews} reviews")

            except Exception as e:
                log.debug(f"解析卡片失败: {e}")
                continue

        log.info(f"Amazon 采集完成: {len(results)} 个有效商品")

    except Exception as e:
        log.error(f"Amazon 爬虫异常: {e}")

    finally:
        if page:
            page.quit()

    return results


if __name__ == "__main__":
    # 测试
    data = scrape_amazon("dog toy", max_products=5)
    print(f"\n采集到 {len(data)} 个商品")
    for p in data:
        print(f"  {p['name'][:50]} | ${p['price_amazon']}")
