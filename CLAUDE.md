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
- 双版本管理机制（Web 版本 / 原生 App 版本）、PWA 更新机制、i18n 切换机制（语言内容是 en / zh-CN / zh-TW）等

这些老项目里跑通的模式（认证流程、版本管理脚本等）可以按需搬过来，但**目录结构和业务逻辑组织方式要按新项目的规则重新设计**，不要整体照搬。**i18n 尤其要注意**：新项目目标市场是泰语/印尼语/西语（见 `docs/product-scope.md` §0），跟老项目的 en/zh-CN/zh-TW 完全不重合——能抄的只是"怎么做语言切换"这套工程机制，语言内容要整个重做，不是简单加几个语言包。

## 当前状态

**TTS 垂直切片端到端跑通了，backend + frontend/web 都有，而且是在真实浏览器里对着真实基础设施（Neon/Firebase/Fish Audio/R2）验证过的，没有一层是 mock**：注册（Firebase 邮箱密码/Google 都开着）→ 自动建号发 500 积分 → 提交 TTS → 真调 Fish Audio 合成 → 音频通过后端代理真的能播放 → 标记公开 → 积分正确扣减、历史记录/公开状态都对得上。细节和怎么跑起来分别见 `backend/README.md`、`frontend/web/README.md`。

**外部账号/凭证现状**：Neon（库 `voicica-ai-v2`，亚太/美东）、Firebase（复用老项目 `ai-voice-labs-473713`，前端 Web SDK config 在 `frontend/web/.env.local.example`，后端 service account JSON 在根目录 `secrets/firebase-adminsdk.json`——这个文件夹整体 gitignore，只留 README 说明用途）、Fish Audio、R2（桶 `voicica-v2`）都已配置并实测通过。

**踩过的坑，已经修了、也写进了对应 README 当"约定"（别再犯）**：
- **时间戳必须显式 `DateTime(timezone=True)`**——迁移是 `timestamptz`，ORM 模型不声明会在写入 tz-aware 值时崩溃（`backend/app/models/models.py` 的 `_TZ` 常量）。
- **写接口必须显式 `await db.commit()`**，不能只靠 `get_db()` 兜底——这套 FastAPI/Starlette 版本下，生成器依赖的 post-yield commit 可能晚于响应发出，导致"提交成功但立刻查询查不到"（真实复现过）。
- **R2 预签名 URL 在这版 `botocore` 下会被拒**（"Missing x-amz-content-sha256"）——改成后端自己读 R2 转发（`GET /jobs/{id}/asset`），不暴露裸 R2 URL。
- Neon 连接串的 `sslmode=require`/`channel_binding=require` 参数 asyncpg 不认，改用 `DATABASE_SSL_REQUIRE` 开关处理。

**目标市场：泰语、印尼语、西班牙语**（不是英文/中文），老项目 en/zh-CN/zh-TW 的语言内容不能直接复用。基础设施 region 暂定亚太（泰语+印尼语覆盖东南亚，西语用户延迟暂不是最优,等有真实流量再考虑多区域）。已记入 `docs/product-scope.md` §0。

**文档体系**：根 `README.md`、`docs/product-scope.md`、`docs/architecture.md`、`docs/data-model.md`、`docs/api-contract.md`、`docs/flows.md`、`docs/decisions/`（0001-0012）、`CONTRIBUTING.md`，加上 `backend/README.md`、`frontend/web/README.md` 这两份"怎么跑起来 + 踩过的坑"。代码落地按"文档策略"同步维护。

**已定（ADR 0001-0012）**：provider 适配层、异步 Job 契约、积分账本（冻结→结算/释放）、素材持久化到 R2、前端四端拆分、数据库选型、Fish Audio 接入、provider 目录同步策略、Auth = Firebase Auth、语音克隆是可复用资产、作品库 = 可见性字段、前端框架 Next.js、`app_settings` 配置模式。`docs/flows.md` 持续更新，别让它过期。

**明确暂缓、不阻塞往下做的**：`(marketing)` 展示页、语音选择器（没有 voice catalog 接口）、公开作品库浏览页（`/gallery` 接口没做）、Android、真实支付、Admin 网页界面（现在只有三个受保护接口）、作品库审核方式、具体计费数字。

**下一步候选**（还没定，看用户想先做哪个）：① 接 Azure/Google 第二个 provider，验证 fallback/多 provider 场景；② 把 Kie 的图片/视频接进来，验证真正的异步 Job 路径（目前只验证过 Fish Audio 这种"伪同步"路径）；③ 补 `/gallery` 端点 + 展示页；④ Android。
