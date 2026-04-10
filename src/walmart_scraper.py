"""
Walmart 爬虫模块
使用 DrissionPage 隐身浏览器
"""

import time
import logging
from datetime import datetime
from DrissionPage import ChromiumPage, ChromiumOptions

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [Walmart] %(levelname)s: %(message)s',
    datefmt='%H:%M:%S'
)
log = logging.getLogger(__name__)


def _build_url(keyword: str) -> str:
    """构建 Walmart 搜索 URL"""
    import urllib.parse
    q = urllib.parse.quote_plus(keyword)
    return f"https://www.walmart.com/search?q={q}&sort=best_match"


def scrape_walmart(keyword: str, max_products: int = 20) -> list[dict]:
    """
    从 Walmart 抓取商品数据

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
    co.set_argument("--disable-images")

    page = None
    try:
        log.info(f"启动浏览器访问 Walmart: {keyword}")
        page = ChromiumPage(addr_or_opts=co)

        url = _build_url(keyword)
        page.get(url, timeout=30)
        time.sleep(3)

        # 向下滚动加载更多商品
        for _ in range(4):
            page.scroll.down(1000)
            time.sleep(1.5)

        # Walmart 商品卡片选择器（多种兼容）
        selectors = [
            "css:[data-automation-id='product-item']",
            "css:.mb1.ph2.pa0-xl.tl",
            "css:article[data-item-id]",
            "css:.search-result-gridview-item",
        ]

        cards = []
        for sel in selectors:
            cards = page.eles(sel)
            if cards:
                log.info(f"使用选择器 '{sel}' 找到 {len(cards)} 个商品")
                break

        if not cards:
            # 备选：所有 article 元素
            cards = page.eles("css:article")
            log.info(f"备选方案找到 {len(cards)} 个 article")

        for card in cards[:max_products]:
            try:
                # 商品名称
                name_el = card.ele("css:h2, .f2.fw5", index=None)
                name = name_el.text if name_el else ""

                # 价格
                dollar_el = card.ele("css:[data-automation-id='product-price'] .w_iUH7, .price-characteristic")
                cent_el = card.ele("css:.supreme-container .price-mantissa, .price-mantissa")

                price = 0.0
                if dollar_el:
                    try:
                        price = float(dollar_el.text.replace("$", "").replace(",", ""))
                    except ValueError:
                        pass
                if price == 0 and cent_el:
                    try:
                        cents = cent_el.text
                        price_str = card.ele("css:.f2.fw5,.price-main-block span").text if card.ele("css:.f2.fw5,.price-main-block span") else ""
                        price = float(price_str.replace("$", "").replace(",", ""))
                    except Exception:
                        pass

                # 评分
                rating = 0.0
                rating_el = card.ele("css:[data-testid='rating-stars'], .rating-number")
                if rating_el:
                    try:
                        rating_text = rating_el.attr("aria-label") or rating_el.text
                        rating = float(rating_text.split(" ")[0].split("★")[0].split("out")[0].strip())
                    except (ValueError, IndexError):
                        pass

                # 评论数
                reviews = 0
                rev_el = card.ele("css:[data-automation-id='ratings-count'], .review-ratings")
                if rev_el:
                    try:
                        reviews = int(rev_el.text.replace(",", "").replace(" ratings", "")
                                     .replace(" ratings", "").replace(" reviews", "").strip())
                    except ValueError:
                        pass

                # 商品链接
                link_el = card.ele("css:a[href*='/ip/']")
                link = link_el.attr("href") if link_el else ""
                if link and not link.startswith("http"):
                    link = f"https://www.walmart.com{link}"

                product = {
                    "keyword": keyword,
                    "name": name[:200],
                    "price_walmart": price,
                    "rating": rating,
                    "reviews_count": reviews,
                    "link_walmart": link,
                    "source": "walmart",
                    "scraped_at": datetime.now().isoformat(),
                }

                if price > 0 and name:
                    results.append(product)
                    log.info(f"  ✓ {name[:60]}... | ${price} | ⭐{rating}")

            except Exception as e:
                log.debug(f"解析卡片失败: {e}")
                continue

        log.info(f"Walmart 采集完成: {len(results)} 个有效商品")

    except Exception as e:
        log.error(f"Walmart 爬虫异常: {e}")

    finally:
        if page:
            page.quit()

    return results


if __name__ == "__main__":
    data = scrape_walmart("kitchen shelf", max_products=5)
    print(f"\n采集到 {len(data)} 个商品")
    for p in data:
        print(f"  {p['name'][:50]} | ${p['price_walmart']}")
