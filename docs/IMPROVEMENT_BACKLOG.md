# 修改项优先级记录

本文档用于记录当前项目后续需要修改、补强或确认的地方。优先级从高到低分为：

- P0：高优先级，影响安全、正确性或核心可用性。
- P1：中优先级，影响稳定性、可维护性或用户体验。
- P2：低优先级，属于优化、补充文档或工程体验提升。

## 开发阶段

### P0

1. 下载失败的重试边界过大
   - `download_note` 外层使用 `@retry(tries=3)`，一旦某张图片、视频、PNG 转换或音频提取中途失败，会重新执行整个笔记下载流程。
   - 风险：重复请求、重复写文件、批量任务耗时放大；视频文件失败时尤其明显。
   - 建议把重试下沉到 `download_media` 单个文件级别，`download_note` 只负责编排，并记录每个媒体文件的成功/失败状态。

1. 平台返回字段解析仍然偏脆弱
   - `handle_note_info` 仍大量使用 `data['note_card']['...']`、`interact_info['...']`、`image_list` 直接索引。
   - 风险：平台字段缺失、视频结构变化、计数字段为空时，单条笔记会直接失败，并影响批量任务完整性。
   - 建议增加统一的 note 解析保护：必需字段明确报错，可选字段给默认值，并在日志中写出缺失字段。

1. 手动 OCR 成功状态判断过宽
   - `save_ai_context` 当前只要存在 `ocr/*.md` 就标记 `has_ocr=true`，即使 OCR 文件内容被清洗后为空也会显示 true。
   - 风险：后续 AI 流程可能误以为 OCR 内容可用。
   - 建议将 `has_ocr` 拆成或收敛为“有效 OCR 文本存在”：至少一个 `.md` 清洗后非空才标记 true；必要时增加 `ocr_file_count` 和 `ocr_text_file_count`。

1. 已处理项留档
   - `.env` 与采集输出目录忽略、`.env.example`、JS 签名文件基于 `__file__` 加载、Cookie `a1` 明确校验均已处理。

### P1

1. URL 解析逻辑重复且行为可能不一致
   - `main.py` 的 `extract_first_url/normalize_note_url` 和 `apis/xhs_pc_apis.py` 的 `_extract_first_url/_resolve_share_url` 都在处理分享文案、短链和完整链接。
   - 建议抽到 `xhs_utils/url_util.py`，统一处理尾部中文标点、`xhslink` 展开、缺少 `xsec_token` 的错误提示。

1. 异常处理粒度仍偏粗
   - 多处使用 `except Exception` 并将错误转为字符串，调用方难以区分网络错误、风控错误、数据结构错误。
   - 建议定义少量业务异常类型，如 `RiskControlError`、`AuthError`、`InvalidNoteUrlError`。

1. 批量流程缺少单条失败汇总
   - `spider_some_note` 只收集成功解析的笔记，失败 URL 只在日志里出现。
   - 建议返回或保存失败清单，包括 URL、失败阶段、错误原因，方便重试。

1. 下载文件写入路径拼接不统一
   - 部分代码使用字符串拼接路径，部分使用 `os.path.join`。
   - 建议统一使用 `os.path.join` 或 `pathlib.Path`，提升跨平台稳定性。

1. 手动 OCR 入口只支持单个笔记目录
   - `--mode ocr --note-dir` 目前一次只处理一个已下载笔记目录。
   - 建议后续支持扫描目录下 `has_ocr=false` 的笔记，批量选择或批量处理，契合“用户手动选定笔记 OCR”的工作流。

1. `ai_context` 信息偏少
   - 当前只包含 `title/desc/tags/has_ocr/image_ocr_text`。
   - 建议补充 `note_id`、`note_url`、`note_type`、`author`、`media_files` 等字段，避免后续 AI 使用上下文时还要回读 `info.json`。

### P2

1. 命名与注释清理
   - 部分日志仍写着“爬取用户所有视频”，但实际是用户笔记。
   - 建议统一术语为“笔记”“图集”“视频笔记”。

1. 保存内容格式化
   - `info.json` 使用 `json.dumps(note_info)`，可读性较弱。
   - 建议增加 `ensure_ascii=False, indent=2`。

1. 类型提示补充与函数拆分
   - 目前只有少量函数有类型提示。
   - 建议逐步补充核心函数返回类型，并把 `main.py` 中的 `Data_Spider` 编排逻辑拆出到独立模块，方便测试。

1. 交互菜单文案同步
   - 模式 1 文案是“单条笔记自动下载（自动识别图集/视频）”，当前符合实际，但 OCR 已改为手动模式。
   - 建议在菜单或 README 中持续强调“下载不自动 OCR，OCR 在模式 6 手动执行”。

## 测试阶段

### P0

1. 核心解析函数单元测试
   - 需要覆盖 URL 提取、短链输入、完整笔记链接、缺失 `xsec_token`、非法输入等场景。
   - 重点测试 `extract_first_url`、`normalize_note_url`、`get_note_info` 参数解析逻辑。

1. 数据处理兼容性测试
   - 需要为 `handle_note_info` 构造图集、视频、缺字段、空标题、无图片等样例。
   - 防止小红书接口字段变化导致批量任务整体失败。

1. 下载逻辑安全测试
   - 需要测试图片返回 HTML、空 URL、错误 Content-Type、视频 URL 缺失等情况。
   - 确保不会写入损坏文件，也不会吞掉关键错误。

### P1

1. API 请求封装测试
   - 使用 mock 覆盖 5xx 重试、401/403/429 风控停止、非 JSON 响应、网络超时。
   - 重点验证 `_request_json` 的重试和停止策略。

1. 收藏分页测试
   - 模拟 `has_more`、`cursor`、`max_count` 等情况。
   - 确认 `collect_num` 能按限制截断，不多请求或漏数据。

1. Excel 输出测试
   - 验证 `save_to_xlsx` 对中文、换行、非法字符、列表字段的处理。
   - 防止输出文件无法打开或列顺序混乱。

1. OCR 客户端测试
   - 使用 mock 覆盖 sync、async 提交、轮询完成、失败、超时、结果下载失败。
   - 避免真实调用外部 OCR 服务。

### P2

1. CLI 参数 smoke test
   - 当前 `uv run python main.py --help` 可正常执行。
   - 建议加入自动化检查，确保入口参数调整后不会破坏启动。

1. 样例数据回归测试
   - 可保留脱敏后的接口响应 JSON 样例。
   - 用于回归验证数据清洗和保存逻辑。

1. 文档命令校验
   - README 中的安装、运行、OCR 示例需要定期校验。
   - 防止命令和实际参数不一致。

## 部署阶段

### P0

1. Dockerfile 完整性
   - Dockerfile 安装 Python 和 Node，但未执行 `npm install`。
   - 由于签名依赖 Node 包，容器运行前需要安装 `package.json` 中的依赖。

1. Python 版本一致性
   - Dockerfile 使用 `python:3.10-slim`，但 `pyproject.toml` 要求 `>=3.11`。
   - 建议统一为 Python 3.11 或调整项目声明。

1. 敏感信息注入方式
   - 部署时不能将真实 `.env` 打进镜像。
   - 建议通过运行时环境变量、密钥管理或挂载方式注入 `COOKIES`、`OCR_TOKEN`。

### P1

1. ffmpeg 依赖声明
   - 视频音频提取依赖 `ffmpeg`，但 Dockerfile 未安装。
   - 如果部署目标需要音频提取，应在镜像中安装；否则文档中明确该功能为可选。

1. 输出目录挂载
   - 媒体和 Excel 输出默认写入项目内 `datas`。
   - 容器部署时建议将输出目录挂载到宿主机持久化路径。

1. 日志策略
   - 当前主要通过 `loguru` 输出到控制台。
   - 建议明确日志级别、日志文件位置，以及是否需要按任务 ID 追踪。

1. 网络与风控参数配置
   - 重试次数、超时时间、重试间隔目前写在代码里。
   - 建议部署时通过环境变量配置，便于不同网络环境调整。

### P2

1. 健康检查
   - 当前是 CLI 工具，没有服务型健康检查。
   - 如果后续包装成 HTTP API，需要增加 `/health` 或启动自检。

1. 镜像体积优化
   - Dockerfile 安装了 build-essential、git 等构建依赖，运行期可能不都需要。
   - 后续可以使用多阶段构建或清理构建依赖。

1. 部署文档补充
   - README 当前以本地运行为主。
   - 建议补充 Docker 构建、运行、环境变量、目录挂载示例。
