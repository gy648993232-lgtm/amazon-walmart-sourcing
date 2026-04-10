# 🛒 Amazon → Walmart 跨平台选品自动化

> 使用 GitHub Actions 定时抓取 Amazon & Walmart 商品数据，自动分析利润空间，筛选出可从 Amazon 搬运到 Walmart 销售的优质商品。

---

## 🌟 功能特点

| 功能 | 说明 |
|------|------|
| 🤖 **自动采集** | DrissionPage 隐身浏览器绕过反爬，采集 Amazon + Walmart 商品数据 |
| 📊 **智能选品** | 自动过滤评论数/评分/利润率，筛选优质候选商品 |
| ⏰ **定时执行** | GitHub Actions 自动每天/每周运行，无需本地电脑 |
| 📄 **多格式报告** | 输出 Excel（带推荐表+统计摘要）和 CSV 文件 |
| 🛠️ **可自定义** | 修改 `config.yaml` 即可调整选品策略和过滤参数 |

---

## 🚀 快速开始

### 1. Fork 本项目

点击右上角 **Fork** 复制到你的 GitHub 账号。

### 2. 配置关键词

编辑 `config.yaml`，设置你要分析的品类关键词：

```yaml
keywords:
  - "kitchen tools"
  - "home organization"
  - "office supplies"
  - "fitness accessories"
```

### 3. 手动测试运行

进入 GitHub 仓库 → **Actions** → 选择 **Amazon → Walmart 选品自动化** → 点击 **Run workflow**

---

## ⚙️ 配置文件说明

`config.yaml` 控制所有选品参数：

```yaml
# 采集数量
max_products_per_keyword: 20

# 选品过滤条件
filter:
  min_amazon_reviews: 50      # 最少评论数
  max_amazon_reviews: 3000   # 最多评论数（避免竞争激烈商品）
  min_amazon_rating: 3.5    # 最低评分（有痛点才有改进空间）
  max_amazon_rating: 4.5    # 最高评分（太高意味着竞争激烈）
  min_price_gap: 3.0         # Walmart 必须比亚马逊贵 $3 以上
  min_profit_margin: 0.20   # 最低利润率 20%
  max_weight_lbs: 3.0        # 最大重量（控制FBA成本）
```

---

## 📊 报告解读

运行后下载报告，包含以下 Sheet：

| Sheet | 内容 |
|-------|------|
| **候选商品** | 所有满足基础条件的商品列表 |
| **✅推荐商品** | 利润 ≥ $3 且利润率 ≥ 20% 的商品 |
| **📊统计摘要** | 总数、平均利润率、最高利润等汇总指标 |

### 报告字段说明

| 字段 | 说明 |
|------|------|
| `Amazon售价` | 采购成本（假设从 Amazon 购买） |
| `总成本` | 采购 + 推荐费(12%) + Closing费($0.30) + 国际运费 + 重量费 |
| `预计利润` | Walmart参考价 - 总成本 |
| `利润率` | 预计利润 ÷ Walmart参考价 |
| `是否推荐` | ✅利润≥$3且利润率≥20% / ❌利润不足 |

---

## 🔧 本地运行

```bash
# 克隆
git clone https://github.com/YOUR_USERNAME/amazon-walmart-sourcing.git
cd amazon-walmart-sourcing

# 安装依赖
pip install -r requirements.txt

# 运行（指定关键词）
python run_pipeline.py --keyword "kitchen shelf"

# 运行（多个关键词）
python run_pipeline.py --keywords "dog toy,cat bed,outdoor decor"

# 使用配置文件中的关键词
python run_pipeline.py
```

---

## 📁 项目结构

```
amazon-walmart-sourcing/
├── .github/workflows/
│   └── product-sourcing.yml   ← GitHub Actions 调度文件
├── src/
│   ├── amazon_scraper.py       ← Amazon 爬虫（DrissionPage）
│   ├── walmart_scraper.py      ← Walmart 爬虫
│   └── analyzer.py             ← 选品分析 + 报告生成
├── data/                       ← 原始 JSON 数据（采集后自动保存）
├── reports/                    ← 报告输出目录（CSV + Excel）
├── config.yaml                 ← 选品策略配置文件
├── requirements.txt
└── run_pipeline.py             ← 主程序入口
```

---

## ⚠️ 注意事项

1. **反爬风险**：Amazon 和 Walmart 有反爬机制，GitHub Actions 运行时可能触发验证码。建议配合代理池使用。
2. **数据时效性**：抓取的是实时的公开数据，不代表未来价格和利润。
3. **利润估算**：运费、平台费等为估算值，实际成本请以官方计算器为准。

---

## 📌 推荐选品参数参考

| 品类 | 评论数范围 | 评分范围 | 利润率目标 |
|------|-----------|---------|-----------|
| 家居收纳 | 100-2000 | 3.5-4.2 | ≥25% |
| 厨房工具 | 50-1500 | 3.5-4.3 | ≥20% |
| 运动户外 | 50-1000 | 3.5-4.4 | ≥30% |
| 宠物用品 | 100-3000 | 3.5-4.5 | ≥20% |
| 儿童玩具 | 100-2000 | 3.8-4.5 | ≥25% |

---

*Made with ❤️ for Walmart sellers*
