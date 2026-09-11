# AI Voice Labs v2 - 项目重构记忆

> 本项目是对 `voicica-ai` 老项目的重写。老项目路径见下方"老项目参考"，**仅作参考，不再直接改动**。

## 重构背景与目标

老项目堆叠太久、代码结构混乱，因此重启新项目而非继续在老代码上改。

**核心目标：C 端用户体验是这次重构要打出的核心竞争力**，不是成本或基础设施简洁性。以后凡是"用户体验/速度" vs "成本/单一供应商便利性/工程量"的取舍，默认站用户体验这边，要反过来才需要理由。已经因为这条原则否掉过一个选项：后端曾试着跑在 Cloudflare Workers 上，实践下来速度不达标，放弃（尽管那样能配 D1、做成纯 Cloudflare 单一技术栈，图省事）。详见 [ADR 0006](docs/decisions/0006-database-orm-choice.md)、`docs/product-scope.md` 第 0 节。

## 已确定的架构方向

### 1. 后端 = FastAPI，承载全部业务逻辑
- 前端不再放重的业务逻辑，只负责 UI/UX 和调用自家后端 API。
- 所有第三方 API（微软、Google、Kie 等语音/AI 服务）统一收敛到后端。

### 2. 第三方 API 通过统一的 Provider 适配层调用
目标：新增/替换供应商时不改业务逻辑，只加一个 adapter。

建议的目录结构（尚未实现，仅作为讨论起点）：
```
backend/
├── app/
│   ├── providers/
│   │   ├── base.py          # 抽象接口，如 TTSProvider / VoiceCloneProvider
│   │   ├── azure.py         # 微软实现
│   │   ├── google.py        # Google 实现
│   │   ├── kie.py           # Kie 实现
│   │   └── registry.py      # 按 config/请求参数选择具体 provider
│   ├── services/             # 业务逻辑层，只调用 providers 抽象接口
│   ├── api/                  # FastAPI 路由，入参校验 + 调用 service
│   └── core/config.py        # provider 的 key、优先级、fallback 策略
```
要点：
- 每个 provider 实现同一接口（如 `synthesize(text, voice, **opts) -> AudioResult`），上层业务代码不关心具体是哪家。
- 以后要做"自动 fallback"（A 挂了切 B）或"按成本/质量路由"，都在 registry 这层加逻辑，不影响业务代码和路由层。

### 3. Agent / AGI 部分
尚未设计，先把主体（后端 provider 适配层 + 前端）跑通后再讨论具体场景。

### 4. 前端拆成 4 个客户端，全部只调后端 API
- `frontend/web`：Next.js，营销页 + 登录后功能页，同一个部署单元，内部用路由分组严格隔离（ADR 0011）。
- `frontend/admin`：Next.js，独立部署，员工专用鉴权——安全边界问题，不是性能问题。
- `android/`：原生 Kotlin/Compose，不走 Capacitor/WebView 套壳（踩过的坑：文件下载保存、原生广告、权限管理）。
- 详见 [ADR 0005](docs/decisions/0005-frontend-surfaces.md)。

### 5. 业务能力模型（Kie 相关）
- Kie 是"批发"目录（图片/音乐/视频等），建模成通用网关 + 配置驱动的 model 目录，不写死具体模型。
- 所有能力（含同步的语音、异步的 Kie）统一走"提交 Job → 轮询"契约。
- 积分：冻结→结算/释放，失败不扣费。
- 生成结果镜像到 Cloudflare R2，带可配置过期时间（Kie 结果链接本身 24 小时过期）。
- 详见 [ADR 0002](docs/decisions/0002-unified-async-job-model.md) / [0003](docs/decisions/0003-credit-ledger-hold-then-settle.md) / [0004](docs/decisions/0004-asset-mirroring-r2-retention.md)。

## 文档策略

**目标读者包含未来的招聘方**：这个项目会作为求职作品集展示，文档要能让人不需要口头解释就看懂系统设计。因此：

- **文档用英文写**，结构收敛在 `docs/` 下（见 `docs/README.md` 索引），不再像老项目那样在根目录堆几十个零散 `.md`。
- **图表优先于大段文字**：架构图、模块边界、请求时序都用 Mermaid（GitHub 原生渲染），见 `docs/architecture.md`。
- **重大技术决策必须落 ADR**：`docs/decisions/`，编号 + 固定模板（Status/Context/Decision/Alternatives/Consequences），不能只存在于对话或 commit message 里。已有 `0001-provider-adapter-layer.md` 记录本文件最初定下的 provider 适配层决策。
- **代码结构变了，`docs/architecture.md` 必须同一次改动里同步更新**，不允许"文档过时了以后再补"。
- **新增文档前先问**：这个信息是"结构性/决策性"的（进 docs/），还是运维类一次性操作说明（如果将来需要，单独在 `docs/ops/` 下按需建，不预先占位）。

具体规则见 `CONTRIBUTING.md`。

## 老项目参考

路径：`C:\Users\NITRO V15\PycharmProjects\voicica-ai`

老项目技术栈（可复用的经验/资产，具体见老项目自己的 CLAUDE.md）：
- 前端 Next.js 15 (App Router) + TypeScript + Tailwind + Firebase Auth
- 后端 FastAPI + Firebase Admin SDK
- Prisma + Neon (Postgres)
- 双版本管理机制（Web 版本 / 原生 App 版本）、PWA 更新机制、i18n（en / zh-CN / zh-TW）等

这些老项目里跑通的模式（认证流程、i18n 方案、版本管理脚本等）可以按需搬过来，但**目录结构和业务逻辑组织方式要按新项目的规则重新设计**，不要整体照搬。

## 当前状态

**Backend TTS 切片代码已写完**（`backend/`，FastAPI + SQLAlchemy async + Alembic，venv 已建、依赖已装、ruff 检查通过、app 能正常 import）。实现了 provider 适配层（`base.py`/`fish_audio.py`/`registry.py`）、Job/积分/app_settings 的 ORM 模型 + 首个 migration（含 seed 数据）、`POST /generate/tts` → `GET /jobs/{id}`/`GET /jobs` → `PATCH /jobs/{id}`（公开）→ `GET /me` → `/admin/*`（调积分/看任务/读写 settings）全套接口，统一错误格式 `{error:{code,message}}`。细节和怎么跑起来见 `backend/README.md`。

**还没做/没法做的**：因为本地环境没有 Docker/Postgres，没法起 DB 跑 migration 做端到端联调；Firebase/Fish Audio/R2 的真实 key 用户还没给，所以这些集成代码写了但没实测过。`frontend/web` 还没动。

骨架目录（`frontend/{web,admin}`、`android/`）还是空的,尚未安装依赖、尚未写代码。文档体系：根 `README.md`、`docs/product-scope.md`（业务范围/能力矩阵）、`docs/architecture.md`、`docs/data-model.md`（数据库 schema，含约定：UUID 主键/snake_case/timestamptz/积分用整数）、`docs/api-contract.md`（后端 HTTP 接口清单）、`docs/flows.md`（全部流程清单+完成度）、`docs/decisions/`（0001-0010）、`CONTRIBUTING.md`。后续代码落地时按"文档策略"同步维护，不要另起一套。

已定（ADR 0001-0010，见 `docs/decisions/`）：Kie 能力模型、异步 Job 契约、积分账本、素材持久化、前端四端拆分、数据库选型（Postgres + SQLAlchemy/SQLModel）、Fish Audio 接入（TTS 同步；语音克隆两段式）、Provider 语音/模型目录同步策略（定期同步，见 ADR 0007）+ 卡住任务的兜底扫描、Auth = Firebase Auth（大陆不是目标市场）、**语音克隆是可复用声音资产**（`voice_models` 表，训练本身就是一个普通 job，复用现成的 job+积分机制，见 ADR 0009）、**作品库 = `jobs.visibility` 字段**（不是独立内容系统，浏览不需要登录，见 ADR 0010）。`docs/flows.md` 里列了全部流程的状态（19 条，8 已定义），持续更新，别让它过期。

明确暂缓、不阻塞写代码的细节：作品库的审核方式、公开作品的素材保留期是否要独立于普通过期策略（ADR 0010 open items）；Admin 具体功能列表；具体计费数字；充值支付渠道。

架构级的悬而未决项全部清空了，包括前端框架（Next.js，ADR 0011）。

下一步：不做纯前端原型也不做纯后端，做一条**完整垂直切片**（登录 → 提交 Fish Audio TTS → 轮询 → 拿到结果，前后端全串起来），选 Fish Audio TTS 是因为它是已核实过的最简单同步接口，能最快验证 provider 适配层 + Job 模型 + 积分扣费全链路跑得通，且能实际验证 `docs/api-contract.md` 写得对不对。Web 优先于 Android（迭代快，且 Android 原生投入应该等 UX/API 契约先被验证过一轮）。高保真设计稿已发布（Artifact，TTS 流程 6 屏），参考老项目 `(native)` 视觉语言。

这条切片的落地范围已经收敛完（见 ADR 0012）：**配置分三类**——工程结构类（Kie 目录）先文件后数据库；provider 自己的目录（语音列表）从第一天就是同步表；**简单运营数值（计费费率、注册赠送积分）从第一天就是 `app_settings` 表**，不用等"真需要"才搬数据库，因为这类值本来就该不用发版就能改。计费费率/注册积分具体数字先填占位值，随时能调,不阻塞开发。Admin 这条切片只做"手动调积分 + 看任务列表 + 读写 app_settings"三个接口，先不建 `frontend/admin` 网页。外部账号（Firebase/Fish Audio/R2）用户稍后提供。
