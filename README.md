# ClaudeCode第三方接口首字测速工具
**本项目初始版本受到anyrouter和anyhelp算力资助**

## 📖 项目简介

ClaudeCodeSpeedTest 是一个专门用于测试 Claude API 第三方接口性能的工具，特别关注"首字时间"（Time to First Byte, TTFB）的测量。该工具采用并发测试模式，能够同时测试多个线路的性能，帮助用户选择最优的 API 接口。

## ✨ 主要特性

- 🚀 **并发测试支持**：支持异步和多线程两种并发模式
- ⚡ **首字时间测量**：精确测量 API 响应的首字节时间
- 📊 **详细性能报告**：提供成功率、响应时间、并发数等详细统计
- 🎯 **智能推荐**：根据测试结果自动推荐最优线路
- 🔧 **灵活配置**：支持通过配置文件自定义测试参数
- 🎨 **美观界面**：使用 Rich 库提供彩色终端界面
- 📈 **实时进度**：实时显示测试进度和状态

## 🛠️ 技术特点

- **异步支持**：基于 aiohttp 的异步 HTTP 请求
- **多线程备选**：提供传统多线程测试模式
- **智能评分**：综合成功率和响应时间的性能评分算法
- **统计分析**：计算平均值、中位数、最大最小值等统计指标

## 📋 系统要求

- Python 3.7+
- 依赖库：
  - aiohttp
  - rich
  - configparser

## 🚀 快速开始

### 安装依赖

```bash
pip install aiohttp rich
```

### 运行工具

```bash
python ClaudeCodeSpeedTest.py
```

### 首次运行

程序会自动创建 `config.ini` 配置文件，您需要：

1. 填入有效的认证令牌
2. 配置要测试的线路信息
3. 调整测试参数（可选）

## ⚙️ 配置说明

### 基本配置

```ini
[DEFAULT]
timeout = 30                    # 请求超时时间（秒）
test_count = 10                 # 每个线路的测试次数
delay_between_tests = 0.2       # 请求间隔（秒）
model = claude-3-5-haiku-20241022  # 使用的模型
content = Hello                 # 测试消息内容
```

### 并发配置

```ini
[concurrent]
max_concurrent_routes = 3       # 最大并发线路数
max_concurrent_per_route = 5    # 单个线路最大并发数
use_async = true               # 是否使用异步模式
connection_pool_size = 100     # 连接池大小
```

### 线路配置

```ini
[route_线路名称]
name = 线路名称
url = https://api.example.com/v1/messages
description = 线路描述
enabled = true
```

## 📊 测试报告

工具会生成包含以下信息的详细报告：

- **线路名称**：配置的线路标识
- **服务器**：API 服务器地址
- **成功率**：请求成功的百分比
- **首字时间**：平均首字节响应时间
- **总响应时间**：完整请求的平均时间
- **并发数**：实际使用的并发连接数
- **状态评级**：🟢 优秀 / 🟡 良好 / 🔴 较差

## 🎨 界面预览

- 启动横幅显示工具信息
- 实时进度条显示测试状态
- 彩色表格展示测试结果
- 并发性能统计面板
- 智能推荐面板

## 👥 开发团队

- **开发者**：jsrcode
- **版本**：V1.1.0
- **赞助方**：anyrouter, anyhelp

## 📄 许可证

本项目采用开源许可证，具体信息请查看项目文件。

## 🤝 贡献

欢迎提交 Issue 和 Pull Request 来改进这个工具！

## 📞 支持

如有问题或建议，请在 GitHub 上提交 Issue。
