# Spider_XHS

## 拾页 · 本地素材工作台

本项目现提供 React + TypeScript 网页界面和 Python/FastAPI 本地服务。笔记、标签、文件夹和任务进度存于 SQLite，图片/视频及 TXT/JSON 等文件继续沿用现有目录。仅监听本机 `127.0.0.1`。

首次安装（Python 3.11+，Node.js 22.12+ 或 24）：

```bash
uv sync --group dev
npm ci
npm --prefix frontend ci
npm --prefix frontend run build
bash scripts/web.sh
```

之后运行 `bash scripts/web.sh`，或在 macOS 双击 `启动拾页.command`，浏览器将打开 `http://127.0.0.1:8765`。首次打开创建本地管理员，已有下载笔记自动导入。忘记密码时先备份 `datas/app/`，再使用 `PYTHONPATH=src .venv/bin/python -m spider_xhs.web.reset_password` 在终端重设。

- **采集**：支持分享文案、批量链接、作者主页、收藏页、关键词。任务结果内可直接查看笔记；按 ID 去重，补齐缺失媒体。作者和收藏来源可设置数量，`0` 为不限。
- **内容**：封面卡片、图文翻页、视频播放、完整正文、互动数量及 OCR。搜索支持中文正文、原标签、个人标签和 OCR 文字。
- **整理**：多层文件夹、拖拽、笔记多文件夹归类，提供按钮操作作为拖拽替代；原标签与个人标签分开保存。
- **回收站**：可恢复笔记与分类，清空才删除文件。删除文件夹只删除分类及子文件夹。仍关联未结束任务的笔记需先取消任务再永久删除。
- **登录**：小红书扫码凭据自动加密保存。登录失效的采集任务等待扫码并自动恢复；平台限流/验证码会暂停并提示手动处理，不能当作 Cookie 过期直接重试。
- **OCR**：设置里填写兼容 PaddleOCR 协议的服务地址、模型及 Key。连接测试会提交一张生成的测试图片。支持整条/多选笔记识别。异步 OCR 保存服务端任务 ID，重启后继续查询，已保存的图片结果跳过。
- **导出**：沿用 `detail.txt`、`info.json`、`ai_context/note_ai_context.txt`、`ai_context/note_ai_context.json`、媒体、OCR Markdown 及 Excel；多文件通过 ZIP 下载，内部格式保持原样。文件夹导出包含子文件夹。

关闭网页后后台任务继续运行；在启动终端按 Ctrl+C 停止服务。下次启动恢复运行中任务，主动暂停/取消的任务保持不变。暂停在当前网络/文件操作结束后生效。评论全文尚未接入，首版展示已采集的评论数量。

本地工作台凭据保存在 `datas/app/`，首次运行可从 `.env` 导入；网页扫码更新工作台凭据。备份时停止服务，然后一并备份 `datas/app/` 与媒体目录，其中 `secret.key` 用于解密凭据。上述运行数据均已加入 Git 忽略。

按本机使用要求，应用 HTTP 请求显式直连，不继承 `HTTP_PROXY`、`HTTPS_PROXY`、`ALL_PROXY` 等代理环境变量；HTTPS 证书验证仍开启。系统级全局 VPN/TUN 的路由仍由操作系统或 VPN 客户端管理。

开发和验证：

```bash
# 开发前端：Vite 代理 /api 到本地后端
npm --prefix frontend run dev
# Python 离线集成测试
.venv/bin/python -m pytest tests -q
# 隔离数据的浏览器全流程测试
npm --prefix frontend run test:e2e
```

详细范围见 [本地工作台说明](docs/LOCAL_WORKBENCH.md)。下面保留原 CLI 的使用方式。

**✨ 专业的小红书数据采集解决方案，支持笔记爬取，保存格式为excel或者media**

**✨ 小红书全域运营解决方法，AI一键改写笔记（图文，视频）直接上传**

## ⭐功能列表

**⚠️ 任何涉及数据注入的操作都是不被允许的，本项目仅供学习交流使用，如有违反，后果自负**


| 模块       | 已实现                                                                                                                                                                                                                               |
| -------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 小红书创作者平台 | ✅ 二维码登录 ✅ 手机验证码登录 ✅ 上传（图集、视频）作品 ✅查看自己上传的作品                                                                                                                                                                                        |
| 小红书PC    | ✅ 二维码登录 ✅ 手机验证码登录 ✅ 获取无水印图片 ✅ 获取无水印视频 ✅ 获取主页的所有频道 ✅ 获取主页推荐笔记 ✅ 获取某个用户的信息 ✅ 用户自己的信息 ✅ 获取某个用户上传的笔记 ✅ 获取某个用户所有的喜欢笔记 ✅ 获取某个用户所有的收藏笔记 ✅ 获取某个笔记的详细内容 ✅ 搜索笔记内容 ✅ 搜索用户内容 ✅ 获取某个笔记的评论 ✅ 获取未读消息信息 ✅ 获取收到的评论和@提醒信息 ✅ 获取收到的点赞和收藏信息 ✅ 获取新增关注信息 |


## 🌟 功能特性

- ✅ **多维度数据采集**
  - 用户主页信息
  - 笔记详细内容
  - 智能搜索结果抓取
- 🚀 **高性能架构**
  - 自动重试机制
- 🔒 **安全稳定**
  - 小红书最新API适配
  - 异常处理机制
  - proxy代理
- 🎨 **便捷管理**
  - 结构化目录存储
  - 格式化输出（JSON/EXCEL/MEDIA）

## 🗂️ 项目结构

```text
02-个人魔改/
├── main.py                  # 薄入口 shim：把 src/ 加入路径并调用 spider_xhs.cli:main
├── src/
│   └── spider_xhs/          # 核心源码包（分层清晰）
│       ├── cli.py           # 入口编排：命令行参数 / 交互菜单 / 模式分发
│       ├── paths.py         # 统一路径解析（仓库根 / 资源 / 数据目录）
│       ├── apis/            # 接口适配层（PC 端、创作者平台、登录）
│       └── utils/           # 基础能力：签名、请求、限速、cookie、数据落盘、OCR
├── assets/
│   └── js/                  # execjs 运行时加载的 JS 签名脚本（原 static/）
├── config/
│   └── .env.example         # 配置样例（复制为根目录 .env 后填写）
├── docs/                    # 架构与规划文档（ARCHITECTURE / IMPROVEMENT_BACKLOG）
├── scripts/
│   └── run.sh               # 统一启动脚本（自动切到仓库根）
├── tests/                   # 离线冒烟测试（结构 / 路径 / 签名桥接）
├── datas/                   # 采集产物（媒体 / excel，运行时生成）
├── node_modules/            # JS 依赖（crypto-js / jsdom，签名运行时必需，须在根目录）
├── .env                     # 实际配置（不入库）
├── pyproject.toml / requirements.txt
└── Dockerfile
```

> 说明：`node_modules/` 必须位于运行目录（仓库根），因为 JS 签名通过 `require('crypto-js')` 按运行时工作目录向上查找依赖；`assets/js/` 里的脚本由 execjs 以临时文件方式执行，其物理位置不影响依赖解析。

## 🎨效果图

### 处理后的所有用户

image

### 某个用户所有的笔记

image

### 某个笔记具体的内容

image

### 保存的excel

image

## 🛠️ 快速开始

### ⛳运行环境

- Python 3.11+
- Node.js 18+

### 🎯安装依赖

```
pip install -r requirements.txt
npm install
```

### 🎨配置文件

先复制配置样例为根目录 `.env`（`load_dotenv` 默认读取运行目录下的 `.env`）：

```
cp config/.env.example .env
```

然后将自己的登录 cookie 放入其中，cookie获取➡️在浏览器f12打开控制台，点击网络，点击fetch，找一个接口点开
image

复制cookie到.env文件中（注意！登录小红书后的cookie才是有效的，不登陆没有用）
image

### 🚀运行项目

```
python main.py
```

在项目根目录下运行。交互菜单可选 **「下载用户收藏夹中的全部笔记」**；命令行示例：

```
python main.py --mode collect --user-url "https://www.xiaohongshu.com/user/profile/用户ID?tab=fav&subTab=note" --collect-num 50 --save-choice all --excel-name fav_export
```

与 Web「收藏 → 笔记」列表一致；需该收藏对当前 Cookie 可见。当前不按多个自定义专辑分别抓取。`--collect-num`：仅 collect 模式有效，`0` 或不写为不限制；正整数为从收藏列表最多取多少条再下载。纯交互启动（未带 `--mode`）时也会在收藏流程中询问条数，可直接回车表示不限制。

### OCR（可选）

默认不会在下载笔记时自动 OCR。后续需要识别图片文字时，再对已下载的笔记目录手动执行 OCR（推荐 async）：

1. 在 `.env` 中增加：

```
OCR_TOKEN=你的token
OCR_MODEL=PaddleOCR-VL-1.6
OCR_SUBMIT_RETRIES=5
OCR_SUBMIT_RETRY_DELAY=30
# 可选覆盖
# OCR_SYNC_URL=https://o6f4pfe0wf57ico6.aistudio-app.com/layout-parsing
# OCR_ASYNC_JOB_URL=https://paddleocr.aistudio-app.com/api/v2/ocr/jobs
```

1. 对已下载笔记目录执行 OCR：

```
python main.py --mode ocr --note-dir "datas/media_datas/作者_用户ID/标题_笔记ID" --ocr-mode async
```

OCR 结果会保存到每条笔记目录下的 `ocr/` 子目录（如 `image_0.md`、`cover.md`），并刷新 `ai_context/note_ai_context.txt` 与 `ai_context/note_ai_context.json` 中的 `image_ocr_text`。未 OCR 的笔记会在 `ai_context` 中标记 `has_ocr: false`，执行过 OCR 并生成结果文件后会标记为 `has_ocr: true`。

### 🗝️注意事项

- main.py中的代码是爬虫的入口，可以根据自己的需求进行修改
- apis/xhs_pc_apis.py 中的代码包含了所有的api接口，可以根据自己的需求进行修改
- apis/xhs_creator_apis.py 中的代码包含了小红书创作者平台的api接口，可以根据自己的需求进行修改

## 🍥日志


| 日期       | 说明                                        |
| -------- | ----------------------------------------- |
| 23/08/09 | - 首次提交                                    |
| 23/09/13 | - api更改params增加两个字段，修复图片无法下载，有些页面无法访问导致报错 |
| 23/09/16 | - 较大视频出现编码问题，修复视频编码问题，加入异常处理              |
| 23/09/18 | - 代码重构，加入失败重试                             |
| 23/09/19 | - 新增下载搜索结果功能                              |
| 23/10/05 | - 新增跳过已下载功能，获取更详细的笔记和用户信息                 |
| 23/10/08 | - 上传代码☞Pypi，可通过pip install安装本项目           |
| 23/10/17 | - 搜索下载新增排序方式选项（1、综合排序 2、热门排序 3、最新排序）      |
| 23/10/21 | - 新增图形化界面,上传至release v2.1.0               |
| 23/10/28 | - Fix Bug 修复搜索功能出现的隐藏问题                   |
| 25/03/18 | - 更新API，修复部分问题                            |
| 25/06/07 | - 更新search接口，区分视频和图集下载，增加小红书创作者api        |
| 25/07/15 | - 更新 xs version56 & 小红书创作者接口              |


## 🧸额外说明

1. 感谢star⭐和follow📰！不时更新
2. 作者的联系方式在主页里，有问题可以随时联系我
3. 可以关注下作者的其他项目，欢迎 PR 和 issue
4. 感谢赞助！如果此项目对您有帮助，请作者喝一杯奶茶~~ （开心一整天😊😊）
5. thank you~~~

## 📈 Star 趋势

## 🍔 交流群

如果你对爬虫和ai agent感兴趣，请加作者主页wx通过邀请加入群聊

ps: 群1、2已超过wx限制人数500，请加群3

06f69d67ff814b84e122bb32d123075b
