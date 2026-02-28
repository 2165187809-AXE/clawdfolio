# Clawdfolio 🦙📊

[![CI](https://github.com/YichengYang-Ethan/clawdfolio/actions/workflows/ci.yml/badge.svg)](https://github.com/YichengYang-Ethan/clawdfolio/actions/workflows/ci.yml)
[![codecov](https://codecov.io/gh/YichengYang-Ethan/clawdfolio/branch/main/graph/badge.svg)](https://codecov.io/gh/YichengYang-Ethan/clawdfolio)
[![PyPI](https://img.shields.io/pypi/v/clawdfolio.svg)](https://pypi.org/project/clawdfolio/)
[![Downloads](https://static.pepy.tech/badge/clawdfolio/month)](https://pepy.tech/project/clawdfolio)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[English](README.md) | 中文

> **生产级量化投资组合工具包** — 多券商聚合、机构级风险分析、期权全生命周期管理，以及 20+ 自动化金融工作流。

---

## 为什么选择 Clawdfolio？

| 传统工具 | Clawdfolio |
|----------|------------|
| 手动录入数据 | 自动同步长桥、富途持仓 |
| 简单盈亏统计 | VaR、夏普比率、Beta、最大回撤、HHI |
| 单一券商视图 | 多券商聚合 |
| Excel 设置警报 | 智能 RSI / 价格 / 盈亏警报 |
| 无法扩展 | Python API + CLI |

---

## 功能特性

- **多券商支持** — 长桥证券 (Longport)、富途牛牛 (Moomoo)、演示模式
- **风险分析** — 波动率、Beta、夏普比率、VaR、最大回撤、GARCH 预测
- **泡沫风险评分** — 基于 [Market-Bubble-Index-Dashboard](https://github.com/YichengYang-Ethan/Market-Bubble-Index-Dashboard) 的实时市场泡沫检测，融合 SMA 偏离、趋势加速和波动率体制分析
- **风险驱动 Covered Call 策略** — 11 年回测验证 (2014-2026)：仅在风险评分 >= 66 时卖出 CC，实现 **83% 胜率**和 **+3.0% 年化超额收益**
- **技术指标** — RSI、SMA、EMA、布林带
- **集中度分析** — HHI 指数、行业暴露、相关性警告
- **压力测试** — 5 个历史场景（COVID 崩盘、2022 熊市等），支持杠杆 ETF 放大效应
- **智能警报** — 价格异动、RSI 超买超卖、盈亏阈值
- **财报日历** — 追踪持仓股票财报日期
- **期权工具集** — 期权报价/Greeks、期权链快照、回补触发监控
- **期权策略手册 (v2.1)** — 覆盖式卖出看涨与裸卖看跌的完整生命周期管理，含 Delta/Gamma/保证金风控规则
- **金融工作流套件** — 20 个来自实盘交易的生产工作流，覆盖报告、警报、行情和券商快照

---

## 快速开始

### 安装

```bash
pip install clawdfolio                  # 核心包
pip install clawdfolio[longport]        # + 长桥券商
pip install clawdfolio[futu]            # + 富途券商
pip install clawdfolio[all]             # 全部券商
```

### 命令行使用

```bash
clawdfolio summary                     # 持仓概览
clawdfolio risk                        # 风险指标（VaR、夏普、Beta 等）
clawdfolio quotes AAPL TSLA NVDA       # 实时行情
clawdfolio alerts                      # 查看警报
clawdfolio earnings                    # 财报日历
clawdfolio dca AAPL                    # 定投分析
```

### 期权命令

```bash
clawdfolio options expiries TQQQ
clawdfolio options quote TQQQ --expiry 2026-06-18 --strike 60 --type C
clawdfolio options chain TQQQ --expiry 2026-06-18 --side both --limit 10
clawdfolio options buyback             # 按配置检查回补触发
```

### Python API

```python
from clawdfolio.brokers import get_broker
from clawdfolio.analysis import analyze_risk

broker = get_broker("demo")  # 或 "longport", "futu"
broker.connect()

portfolio = broker.get_portfolio()
metrics = analyze_risk(portfolio)

print(f"净资产: ${portfolio.net_assets:,.2f}")
print(f"夏普比率: {metrics.sharpe_ratio:.2f}")
print(f"VaR 95%: ${metrics.var_95:,.2f}")
```

---

## 风险指标

| 指标 | 说明 |
|------|------|
| **波动率** | 20 日和 60 日年化波动率，GARCH(1,1) 预测 |
| **Beta** | 与 SPY/QQQ 的相关性 |
| **夏普比率** | 风险调整后收益 |
| **索提诺比率** | 仅计入下行波动的风险调整收益 |
| **VaR / CVaR** | 在险价值 (95%/99%) + 预期损失 |
| **最大回撤** | 最大峰值到谷值跌幅 |
| **HHI** | 投资组合集中度指数 |
| **压力测试** | COVID-19、2022 熊市、闪崩等历史场景 |

---

## 泡沫风险评分

集成自 [Market-Bubble-Index-Dashboard](https://github.com/YichengYang-Ethan/Market-Bubble-Index-Dashboard) — 实时复合市场风险指标。

**三大评分维度：**
- **SMA-200 偏离** (0-40 分) — 市场价格相对 200 日均线的偏离程度
- **趋势加速** (0-30 分) — 多项式拟合衡量抛物线式价格加速
- **波动率体制** (0-30 分) — 年化已实现波动率评估

| 评分 | 体制 | 操作建议 |
|------|------|----------|
| 0-39 | 低风险 | 持有股票，不卖 CC |
| 40-54 | 中等 | 监控观察 |
| 55-65 | 升高 | 准备 CC 订单 |
| 66-100 | 高风险 | 执行 Covered Call |

```python
from clawdfolio.analysis.bubble import fetch_bubble_risk

risk = fetch_bubble_risk()  # 从 Dashboard API 获取（不可用时自动回退本地计算）
print(f"风险评分: {risk.drawdown_risk_score:.1f} ({risk.regime})")
print(f"是否应卖 CC: {risk.should_sell_cc}")
print(f"建议 Delta: {risk.cc_delta}")
```

---

## 风险驱动 Covered Call 策略

基于泡沫风险评分的量化 CC 策略，用于决定**何时**卖出看涨期权和**什么** Delta。专为杠杆 ETF (TQQQ) 或宽基 ETF (QQQ/SPY) 长期持有者设计。

**11 年回测结果 (2014-2026, 64 种参数组合)：**

| 指标 | 数值 |
|------|------|
| 最优阈值 | 风险评分 >= 66 (历史 P85) |
| 最优 Delta | 0.25 |
| 胜率 | **83%** |
| 年化超额收益 | **+3.0%** (相对买入并持有) |
| 被行权率 | 1.5% (11 年仅 1 次) |
| 信号类型 | 非对称 — 仅适用于 sell-call |

```python
from clawdfolio.strategies.covered_call import CoveredCallStrategy

strategy = CoveredCallStrategy(tickers=["TQQQ"])
signals = strategy.check_signals()

for sig in signals:
    print(f"{sig.ticker}: {sig.action.value} δ={sig.target_delta} "
          f"风险={sig.bubble_risk_score:.0f} ({sig.regime})")
```

---

## 期权工具集

内置期权模块提供实时 Greeks 查询、链分析和有状态的回补监控：

| 命令 | 说明 |
|------|------|
| `options expiries` | 列出标的可用到期日 |
| `options quote` | 单个期权报价与 Greeks（delta、gamma、theta、vega、IV） |
| `options chain` | 完整期权链快照，支持筛选 |
| `options buyback` | 有状态的空头期权回补触发监控 |

策略方法论详见[期权策略手册](docs/OPTIONS_STRATEGY_PLAYBOOK_v2.1.md) — 覆盖 Covered Call 和 Sell Put 全流程，包含基于 Delta 的行权价选择、Roll/被行权规则和保证金风控。

---

## 配置

### 环境变量

```bash
# 长桥证券
export LONGPORT_APP_KEY=your_app_key
export LONGPORT_APP_SECRET=your_app_secret
export LONGPORT_ACCESS_TOKEN=your_access_token

# 富途：本地运行 OpenD，端口 11111
```

### 配置文件（可选）

创建 `config.yaml`：

```yaml
brokers:
  longport:
    enabled: true
  futu:
    enabled: true
    extra:
      host: "127.0.0.1"
      port: 11111

alerts:
  pnl_trigger: 500.0
  rsi_high: 80
  rsi_low: 20

option_buyback:
  enabled: true
  symbol: "TQQQ"
  targets:
    - name: "cc-june"
      strike: 60
      expiry: "2026-06-18"
      type: "C"
      trigger_price: 1.60
      qty: 2
      reset_pct: 0.20
```

### 支持的券商

| 券商 | 地区 | 状态 |
|------|------|------|
| 演示模式 | 全球 | 内置 |
| 长桥证券 | 美/港/新 | 可选 |
| 富途牛牛 | 美/港/新 | 可选 |

---

## 金融工作流

从实盘交易基础设施迁移的 20 个生产工作流，按类别组织：

| 类别 | 示例 |
|------|------|
| **持仓报告** | 账户报告、投组分析、风险拆解 |
| **简报卡片** | 每日简报（终端 + Telegram）、多格式 |
| **警报与监控** | 价格/RSI 警报、期权回补触发 |
| **市场情报** | 实时行情、财报日历、市场新闻 |
| **券商快照** | 长桥/富途资产摘要 |
| **策略** | DCA 定投提案 |

```bash
clawdfolio finance list                # 按类别浏览所有工作流
clawdfolio finance init                # 初始化 ~/.clawdfolio/finance 工作区
clawdfolio finance run <workflow_id>   # 执行工作流
```

---

<details>
<summary><strong>更新日志</strong></summary>

### v2.4.0 (2026-02-28)

- **泡沫风险评分** — 集成 Market-Bubble-Index-Dashboard 的实时回撤风险评分 (0-100)
- **风险驱动 Covered Call 策略** — 量化 CC 信号：83% 胜率，+3.0% 超额收益（11 年回测）
- `CoveredCallStrategy`、`check_cc_signals()`、`get_cc_recommendation()` 便捷 API
- `fetch_bubble_risk()` 支持 Dashboard API + 本地实时计算回退
- 泡沫风险和 CC 策略模块的全面测试覆盖

### v2.3.0 (2026-02-16)

- Sortino 比率和 CVaR/预期损失风险指标
- `analyze_risk()` 输出中新增 Portfolio RSI
- `clawdfolio export` CLI 命令（CSV/JSON）
- 动态美股交易日历（算法化节假日生成）
- 批量 SPY/QQQ 基准获取
- 覆盖率提升至 70%，Python 3.13 CI 支持

### v2.2.0 (2026-02-14)

- 线程安全市场数据缓存（`threading.Lock`）
- 批量报价获取，通过 `yf.download` 并支持逐个回退
- 共享 `suppress_stdio` 工具（DRY 重构）
- CLI 版本号从 `__version__` 动态读取
- PEP 561 合规（`py.typed` 标记）
- 核心模块结构化日志
- 集中化 ticker 标准化（`_yf_symbol()`）
- 配置路径迁移至 `clawdfolio` 命名空间（向后兼容）

### v2.1.0 (2025-01-28)

- 期权策略手册 v2.1（`docs/OPTIONS_STRATEGY_PLAYBOOK_v2.1.md`）
- CC 与 Sell Put 全生命周期的研究到执行框架
- 明确 Gamma 风险、保证金、杠杆和被行权决策规则

### v2.0.0 (2025-01-15)

- 全量金融迁移：从实盘基础设施迁移 20 个生产工作流
- `clawdfolio finance` 命令组（list、init、run）
- 可写工作区启动（`~/.clawdfolio/finance`）
- 期权报价/期权链/回补监控
- Wilder RSI 平滑、Longport 标的修复、yfinance 加固

详见 [CHANGELOG.md](CHANGELOG.md)。

</details>

---

## 贡献

欢迎贡献代码！请提交 Pull Request。

## 许可证

MIT License — 查看 [LICENSE](LICENSE)

## 链接

- [GitHub 仓库](https://github.com/YichengYang-Ethan/clawdfolio)
- [问题反馈](https://github.com/YichengYang-Ethan/clawdfolio/issues)
- [期权策略手册](docs/OPTIONS_STRATEGY_PLAYBOOK_v2.1.md)
