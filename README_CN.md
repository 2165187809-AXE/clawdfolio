# Clawdfolio 🦙📊

[![CI](https://github.com/2165187809-AXE/clawdfolio/actions/workflows/ci.yml/badge.svg)](https://github.com/2165187809-AXE/clawdfolio/actions/workflows/ci.yml)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Clawdbot](https://img.shields.io/badge/Clawdbot-技能-1f7a4c)](https://github.com/2165187809-AXE/clawdfolio)
[![Claude Code Compatible](https://img.shields.io/badge/Claude%20Code-兼容-blueviolet)](https://github.com/anthropics/claude-code)

[English](README.md) | 中文

> **为 Clawdbot 生态打造的 AI 投资组合监控工具**
>
> 面向实盘的 Clawdbot 金融技能 - 支持多券商持仓聚合、机构级风险指标计算和智能交易警报，并具备生产级数据可靠性。期权方法论来自权威书籍课程研究、严谨回测与多年实战沉淀。

---

## 为什么选择 Clawdfolio？

| 传统工具 | Clawdfolio |
|----------|------------|
| 手动录入数据 | 自动同步券商数据 |
| 简单盈亏统计 | VaR、夏普比率、Beta、最大回撤 |
| 单一券商视图 | 多券商聚合 |
| Excel 设置警报 | 智能 RSI/价格警报 |
| 无 AI 集成 | **Clawdbot 原生技能** |

---

## 功能特性

- **多券商支持** - 长桥证券 (Longport)、富途牛牛 (Moomoo)、演示模式
- **风险分析** - 波动率、Beta、夏普比率、VaR、最大回撤
- **技术指标** - RSI、SMA、EMA、布林带
- **集中度分析** - HHI 指数、行业暴露、相关性警告
- **智能警报** - 价格异动、RSI 超买超卖、盈亏阈值
- **财报日历** - 追踪持仓股票财报日期
- **定投分析** - DCA 信号与绩效追踪
- **期权工具集** - 期权报价/Greeks、期权链快照、回补触发监控
- **期权策略手册 (v2.1)** - 覆盖式卖出看涨与裸卖看跌的完整流程，含 Delta/Gamma/保证金风控规则
- **金融工作流套件 (v2)** - 从本地 `~/clawd/scripts` 全量迁移 20 个实盘脚本，并可通过 `clawdfolio finance` 分类运行

---

## v2.1.0 最新优化

- **新增专门期权策略文档** - 增加 `docs/OPTIONS_STRATEGY_PLAYBOOK_v2.1.md`，作为 CC 与 Sell Put 的统一方法论手册
- **研究到执行一体化** - 将权威学习、数据回测和多年实战经验整理为可执行规则
- **风控框架升级** - 明确 Gamma 风险、保证金/杠杆、Roll、被行权和暂停条件
- **功能映射更清晰** - 将策略决策与 `clawdfolio options`、`clawdfolio finance` 工作流一一对应

完整手册请见：`docs/OPTIONS_STRATEGY_PLAYBOOK_v2.1.md`

---

## v2.0.0 最新优化

- **本地金融能力全量迁移** - 将 `~/clawd/scripts` 的全部在用金融脚本迁移进 `clawdfolio`（报告、简报、监控、行情、快照、DCA、安全）
- **结构化编排** - 新增 `clawdfolio finance` 命令组，支持按分类列出、初始化、按 id 执行工作流
- **目录重构** - 新增 `legacy_finance` 打包目录，并保留历史归档脚本以便追溯和回滚
- **运行隔离** - 增加可写工作区 `~/.clawdfolio/finance`，兼容 legacy 脚本的配置与状态文件写入
- **既有可靠性修复保留** - Wilder RSI、Longport symbol 修复、yfinance 增强、期权报价/期权链/回补监控全部保留

---

## 快速开始

### 作为 Clawdbot 技能使用

在 Clawdbot 中直接运行：

```
/clawdfolio summary
/clawdfolio risk
/clawdfolio quotes AAPL MSFT NVDA
/clawdfolio alerts
```

`clawdfolio` 同时兼容 Claude Code 的 CLI 使用方式。

### 命令行安装

```bash
# 基础安装
pip install clawdfolio

# 带券商支持
pip install clawdfolio[longport]  # 长桥
pip install clawdfolio[futu]      # 富途
pip install clawdfolio[all]       # 全部券商
```

### 命令行使用

```bash
clawdfolio summary              # 持仓概览
clawdfolio risk                 # 风险指标
clawdfolio quotes AAPL TSLA     # 实时行情
clawdfolio alerts               # 查看警报
clawdfolio earnings             # 财报日历
clawdfolio dca AAPL             # 定投分析
clawdfolio options expiries TQQQ
clawdfolio options quote TQQQ --expiry 2026-06-18 --strike 60 --type C
clawdfolio options chain TQQQ --expiry 2026-06-18 --side both --limit 10
clawdfolio options buyback      # 按配置检查回补触发
clawdfolio finance list         # 查看全部迁移后的金融工作流
clawdfolio finance init         # 初始化 ~/.clawdfolio/finance 工作区
clawdfolio finance run portfolio_daily_brief_tg_clean
```

### 金融工作流 (v2)

`clawdfolio finance list` 会按以下分组展示工作流：
- Portfolio Reports
- Briefing Cards
- Alerts and Monitors
- Market Intelligence
- Broker Snapshots
- Strategy
- Security

---

## Python API

```python
from clawdfolio.brokers import get_broker
from clawdfolio.analysis import analyze_risk

# 连接券商
broker = get_broker("demo")  # 或 "longport", "futu"
broker.connect()

# 获取持仓并分析
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
| **波动率** | 20日和60日年化波动率 |
| **Beta** | 与 SPY/QQQ 的相关性 |
| **夏普比率** | 风险调整后收益 |
| **VaR** | 在险价值 (95%/99%) |
| **最大回撤** | 最大峰值到谷值跌幅 |
| **HHI** | 投资组合集中度指数 |

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

### 配置文件 (可选)

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
  state_path: "~/.cache/clawdfolio/option_buyback_state.json"
  targets:
    - name: "target1"
      strike: 60
      expiry: "2026-06-18"
      type: "C"
      trigger_price: 1.60
      qty: 2
      reset_pct: 0.20
    - name: "target2"
      strike: 60
      expiry: "2026-06-18"
      type: "C"
      trigger_price: 0.80
      qty: 1
      reset_pct: 0.20
```

---

## 支持的券商

| 券商 | 地区 | 状态 |
|------|------|------|
| 演示模式 | 全球 | 内置 |
| 长桥证券 | 美/港/新 | 可选 |
| 富途牛牛 | 美/港/新 | 可选 |

---

## 贡献

欢迎贡献代码！请提交 Pull Request。

---

## 许可证

MIT License - 查看 [LICENSE](LICENSE)

---

## 链接

- [GitHub 仓库](https://github.com/2165187809-AXE/clawdfolio)
- [问题反馈](https://github.com/2165187809-AXE/clawdfolio/issues)
- [Claude Code 兼容说明](https://github.com/anthropics/claude-code)

---

**如果 Clawdfolio 对你有帮助，请给一个 ⭐ Star！**
