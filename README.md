# 月夜狼人杀

一个基于 `FastAPI + Vue 3 + WebSocket` 的 AI 狼人杀项目，支持真人混玩、管理员配置、模型池管理、对局统计和上帝模式。

## 功能概览

- 支持 AI 对 AI、真人 + AI 混合对局
- 使用 WebSocket 推送实时游戏状态
- 支持管理员后台配置 API 地址、API Key 和模型 ID 列表
- 支持从兼容 OpenAI 的 `/models` 接口拉取模型 ID
- 支持随机分配模型，或按座位手动指定模型 ID
- 支持角色统计、模型统计、人格统计和历史对局记录
- 支持上帝模式查看隐藏信息

## 技术栈

- 后端：`FastAPI`
- 前端：`Vue 3` + `Vite`
- 通信：`WebSocket`
- 数据存储：本地 JSON 文件
- 模型接口：兼容 OpenAI 风格 `/v1/chat/completions`

## 项目结构

```text
AI Wolves Killer/
├── backend/
│   ├── app/                # 后续拆分中的模块化代码
│   ├── data/               # 静态角色配置与默认运行期数据目录
│   ├── Emojis/             # 头像素材
│   ├── .env.example        # 环境变量模板
│   ├── app.py              # 当前主后端入口
│   ├── config.yaml         # 模型池与超时配置
│   ├── game_engine.py      # 核心游戏逻辑
│   ├── game_storage.py     # 运行期数据存储路径定义
│   ├── game_stats.py       # 统计与历史记录
│   └── requirements.txt
├── frontend/
│   ├── src/
│   ├── package.json
│   └── vite.config.js
└── README.md
```

## 快速启动

### 1. 后端准备

```bash
cd backend
pip install -r requirements.txt
```

复制环境变量模板：

```bash
cp .env.example .env
```

至少需要配置：

```env
WEREWOLF_API_KEY=your_api_key
WEREWOLF_API_BASE_URL=https://your-compatible-api-host
WEREWOLF_ADMIN_PASSWORD=your_admin_password
WEREWOLF_DATA_DIR=./data
```

说明：

- `backend/config.yaml` 用于静态配置，例如模型池和超时参数
- `backend/data/roles.json`、`backend/data/personalities.json` 用于静态角色与人格目录
- `WEREWOLF_DATA_DIR` 用于运行期数据目录，默认是 `backend/data/`
- 运行期生成的 `game_history.json`、`game_stats.json`、`data/games/`、`data/reports/` 都属于本地数据产物，不应和源码改动混在同一次提交里

### 2. 配置模型 ID 池

你可以直接编辑 `backend/config.yaml`：

```yaml
models:
  - bl-DeepSeek-V3-250324
  - bl-DeepSeek-V3.1
  - bl-DeepSeek-V3.2-Exp
```

也可以在管理员后台里：

- 配置 API 地址和 API Key
- 远程拉取 `/models`
- 选择并保存模型 ID 列表

保存后的模型池会被用于：

- 游戏创建时的随机模型分配
- 座位手动指定模型时的可选项展示

### 3. 启动后端

```bash
cd backend
python app.py
```

默认地址：

- HTTP: `http://localhost:8000`
- WebSocket: `ws://localhost:8000`

### 4. 启动前端

```bash
cd frontend
npm install
npm run dev
```

默认访问地址：

- `http://localhost:3000`

## 管理员能力

管理员后台支持：

- 登录鉴权
- API 地址配置
- API Key 配置
- 模型 ID 列表维护
- 远程获取模型列表
- 查看默认超时和模型超时配置

## 安全说明

- 仓库中不应提交真实 `.env`
- API Key 通过环境变量读取
- 示例脚本中的硬编码密钥已移除
- 上传公开仓库前，建议再次确认本地 `.env`、日志和数据库文件未被纳入版本控制

## 当前状态

目前主线已支持：

- 模型 ID 列表配置
- 远程获取模型 ID
- 游戏创建时随机/手动分配模型
- 前后端围绕模型 ID 的统一展示和保存

## 备注

`backend/app/` 目录下保留的是逐步拆分中的模块化骨架，目前只承载部分公共模型、配置和管理员路由；当前实际运行入口仍是 `backend/app.py`，不要把该目录视为已完整接管主应用。
