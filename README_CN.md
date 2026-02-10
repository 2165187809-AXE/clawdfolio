# Clawdfolio 🦙📊

[![CI](https://github.com/2165187809-AXE/clawdfolio/actions/workflows/ci.yml/badge.svg)](https://github.com/2165187809-AXE/clawdfolio/actions/workflows/ci.yml)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Claude Code](https://img.shields.io/badge/Claude%20Code-技能-blueviolet)](https://github.com/anthropics/claude-code)

[English](README.md) | 中文

> **为 Claude Code 生态打造的 AI 投资组合监控工具**
>
> 投资者的终极 Claude Code 技能 - 支持多券商持仓聚合、机构级风险指标计算和智能交易警报，并具备生产级数据可靠性。

---

## 为什么选择 Clawdfolio？

| 传统工具 | Clawdfolio |
|----------|------------|
| 手动录入数据 | 自动同步券商数据 |
| 简单盈亏统计 | VaR、夏普比率、Beta、最大回撤 |
| 单一券商视图 | 多券商聚合 |
| Excel 设置警报 | 智能 RSI/价格警报 |
| 无 AI 集成 | **Claude Code 原生技能** |

---

## 功能特性

- **多券商支持** - 长桥证券 (Longport)、富途牛牛 (Moomoo)、演示模式
- **风险分析** - 波动率、Beta、夏普比率、VaR、最大回撤
- **技术指标** - RSI、SMA、EMA、布林带
- **集中度分析** - HHI 指数、行业暴露、相关性警告
- **智能警报** - 价格异动、RSI 超买超卖、盈亏阈值
- **财报日历** - 追踪持仓股票财报日期
- **定投分析** - DCA 信号与绩效追踪

---

## v1.0.2 最新优化

- **金融可靠性同步** - 将实盘工作流中验证过的可靠性改进同步到 `clawdfolio`
- **RSI 更贴近实盘** - RSI 计算切换为 **Wilder EMA 平滑**
- **Longport 报价刷新修复** - 修复 `LongportBroker.get_positions()` 的 symbol 传递问题
- **行情数据增强** - yfinance 单票/MultiIndex 历史数据标准化，并补齐 `prev_close` 回退逻辑
- **CI 稳定性提升** - Python 3.10/3.11/3.12 的 lint/type/test 全链路稳定通过

---

## 快速开始

### 作为 Claude Code 技能使用

直接在 Claude Code 中输入：

```
/clawdfolio summary
/clawdfolio risk
/clawdfolio quotes AAPL MSFT NVDA
/clawdfolio alerts
```

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
```

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
- [Claude Code](https://github.com/anthropics/claude-code)

---

**如果 Clawdfolio 对你有帮助，请给一个 ⭐ Star！**
