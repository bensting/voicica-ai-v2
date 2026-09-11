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

**外部账号/凭证现状**：Neon（库 `voicica-ai-v2`，亚太/美东）、Firebase（复用老项目 `ai-voice-labs-473713`，前端 Web SDK config 在 `frontend/web/.env.local.example`，后端 service account JSON 在根目录 `secrets/firebase-adminsdk.json`——这个文件夹整体 gitignore，只留 README 说明用途）、Fish Audio、R2（桶 `voicica-v2`）、**Azure Speech（区域 `southeastasia`）、Google Cloud TTS（API key）** 都已配置并实测通过。

**TTS 多供应商已经打通（Azure + Google，加上原有的 Fish Audio）**：这是这轮新加的最大一块。核心设计点——**选哪个供应商是由用户选的"声音"决定的，不是 capability 级别写死的**：`voice_catalog` 表（provider + provider_voice_id + locale，文档早就设计好了但之前没实现）存了每个供应商的真实声音列表，`POST /generate/tts` 的请求字段从裸的 `reference_id` 改成了 `voice_id`（一个 `voice_catalog` 行的 id），后端按这个 id 查出该用哪个 provider、调用哪个 adapter（`registry.get_provider_by_name`，新加的按名字查找，区别于原来按 capability 查找）。不选 voice 时还是走 Fish Audio 默认声音（Azure/Google 都没有"默认声音"这个概念，必须显式指定）。`app/scheduled/sync_catalog.py`（ADR 0007 提到但之前没写代码的目录）负责从 Azure/Google 真实 API 拉声音列表写进 `voice_catalog`，目前手动跑（`python -m app.scheduled.sync_catalog`），真实同步过一次：Azure 779 个声音、Google 2066 个声音，泰语/印尼语/西语覆盖都确认了。`GET /catalog/voices?provider=&locale=` 接口已经能查。Fish Audio 自己的"官方声音列表"接口还没验证过，先没接入 catalog（不影响它现有的 TTS 功能，只是选声音时列表里暂时没有它）。全链路（DB migration、真实 Azure/Google 合成、R2 落地、HTTP 路由层）都用真实基础设施验证过，包括默认 Fish Audio 路径在真实浏览器里回归测试过没坏。

**前端 Select Voice 弹窗做完并端到端验证过了**（`components/VoiceSheet.tsx`），中途有一次真实的设计返工，记一下：

- **第一版做错了**：`GET /catalog/voices` 不传 locale 时我让后端默认收窄成只给 th/id/es（"目标市场"）三种语言，理由是怕选声音弹窗一次性拉几千条用不上的声音、拖慢加载。用户看到弹窗里语言下拉只有这三种，指出这是错的——**"目标市场"这个词从一开始就是指基础设施 region 优先级（infra 该往哪个区域投入），不是说要限制用户能选哪些语言**。实际推广进来的用户什么语言都有，包括英文，必须让全部语言都能选。用户还提醒"看看老版怎么实现的"，去看了老项目 `src/components/native/create/voice/VoiceSelectorSheet.tsx` + `hooks/useVoices.ts`，发现老版的解法是：**不限制语言范围（Azure/Google 支持啥就全选得到），但一次只拉一种语言的声音列表**（选语言 → 只 fetch 那个 locale 的声音），用一个"常用语言"精选短列表（比如西班牙语只挑 es-ES 一个代表，不是把 20 个国家变体都摆出来）放在下拉最上面，其余全部语言塞进"All languages"。
- **第二版又做错了一次**：改成不限制语言范围之后，选择维度用的是"精确 locale"（比如 es-MX、es-AR 分别是不同下拉选项）。用户又纠正了一次：**"你这样完全是使用 azure 的语言分法"**——Azure 一个西班牙语能拆出 22 个国家变体，Google 只有 2 个（es-ES、es-US），按精确 locale 做下拉，实际上就是把 Azure 的分类标准强加给整个产品，Google 的西语选项形同虚设（选 es-AR 之类的 Azure-only locale 时 Google 压根没有对应声音）。"西班牙语就是一种语言而已"——应该按**基础语言**分组，不是按国家变体。
- **现在的做法**：`GET /catalog/voices` 新增 `language=` 参数（前缀匹配，比如 `language=es` 匹配所有 `es-*`，横跨 Azure 和 Google），`locale=` 精确匹配保留给别的场景用；`GET /catalog/locales` 改名 `GET /catalog/languages`，按 locale 第一段分组（Postgres `split_part`），返回"有哪些基础语言 + 每种几条声音"。前端语言下拉现在选的是"Spanish"这一个选项（不是 22 个国家变体），选中后该语言下所有 provider、所有国家变体的声音都会出现，每条声音自己的行上显示具体 locale（比如"Spanish (Mexico)"）。实测：83 个基础语言（对比之前 158 个精确 locale），西班牙语一个语言下 Azure+Google 一共 184 条声音、22 个国家变体，两个 provider 都真的出现在同一个语言的结果里。
- **顺带发现并修出一个真 bug**：Azure 有些 locale 有第三段（脚本/方言标签，比如 `zh-CN-guangxi`、`sr-Latn-RS`、`iu-Cans-CA`），第一版 `Intl.DisplayNames` 格式化函数只取前两段，第三段被默默丢掉，导致下拉里 6+ 个中文方言全部显示成一模一样的"Chinese (China)"，用户截图里直接看出来了。`lib/locale-names.ts` 现在能正确区分脚本子标签（4 字母，走 `Intl.DisplayNames` 的 script 类型）和 Azure 自造的方言标签（普通小写单词，首字母大写后直接拼进去），"zh-CN-guangxi" 现在正确显示成"Chinese (Guangxi, China)"。
- **试听按钮按用户要求直接不做**（用户原话：试听不能每次都重新生成，应该播放已生成好的样本，但现在没有这套缓存机制，所以先去掉）。
- 真实浏览器验证：泰语 Google 声音、西语墨西哥 Azure 声音都真实生成播放成功；语言下拉改按基础语言分组后 Popular 14 + All languages 68 = 82（cmn 并入 zh 后少了一个）；选中"Spanish"能看到 Azure 和 Google 的声音混在一起、按 provider 筛选也对；中文方言各自显示正确名字不再撞车；选中"Chinese"现在也能看到 Azure + Google 两家的声音了。
- **第三个坑，也是用户直接问出来的**："为什么选择 chinese 没有 google 的语音呢"——一查，Google 把普通话标成 `cmn`（ISO 639-3），Azure 标成 `zh`，两家实际指的是同一个语言（都单独把粤语 `yue`、吴语 `wuu` 拆出去了，只有"普通话"这个语言本身两家用了不同代号）。后果比想象的更糟：不仅选"zh"拉不到 Google 的声音，"cmn"还会在下拉里单独占一个"Chinese"选项——跟"zh"显示的名字一模一样（`Intl.DisplayNames` 把两个代号都翻译成"Chinese"），用户根本没法从名字上分辨该选哪一个。**修复的坑**：一开始想直接把存进 `voice_catalog` 的 `locale` 字段从 "cmn-CN" 改写成 "zh-CN"，写完之后想起来这个字段同时也是**真实调用 Google API 时传的 languageCode**，实测验证了一下——Google 的合成接口严格要求 languageCode 跟声音自己的代号完全一致，传 "zh-CN" 给一个 cmn-CN 的声音直接 400。所以改法是**只在查询层做别名映射**（`services/voice_catalog.py` 里一个 `_LANGUAGE_ALIASES = {"cmn": "zh"}`，用 SQL `case` 表达式），数据库里存的 `locale` 字段完全不动，还是每个供应商自己的真实值，只是"归到哪个语言分组"这件事把两者算作一个。真实调用 Google 普通话声音生成验证过，没问题。

**这轮踩的一个坑，写进 `backend/README.md` 的 Conventions 了，别忘了**：跑了很久的 `uvicorn --reload` 进程有时候不会捡起新加的文件（不只是改动已有文件），结果就是新路由/新字段悄悄没生效，`/health` 还正常，浏览器测试甚至"看起来通过"——因为 Pydantic 默认会忽略请求里的未知多余字段，新的 `voice_id` 字段被服务器忽略后请求退回旧代码的默认行为，表面上"成功"实际上根本没走新逻辑。**以后改了路由/字段但怀疑没生效，先 `curl localhost:8000/openapi.json` 确认新路由真的在里面，不确定就直接杀掉进程重启**，别急着怀疑代码写错了。

**Audio Settings（语速/音量/音高）做完并端到端验证过了**：`components/AudioSettingsSheet.tsx`，TTS 创建页"Select a voice"下面新加一行（齿轮图标 + "Speed 1.0x · Volume 50% · Pitch 50"摘要）。三个参数是统一给前端用的一套尺度（speed 0.5-2.0x、volume/pitch 1-100 居中 50），具体怎么转换成每家供应商自己的单位，**直接照抄了老项目 `src/lib/services/{azure,google,fish-audio}-tts.ts` 里生产环境验证过的公式，不是自己瞎猜的**：
- Azure：SSML `<prosody rate="{(speed-1)*100}%" pitch="{pitch-50}%" volume="{volume}">`。
- Google：`speakingRate`=speed 原样传（本来就在 Google 更宽的 0.25-4.0 范围内）、`pitch`=(pitch-50)*0.4、`volumeGainDb`=(volume-50)*0.2。**有个坑**：部分新声音（Chirp3 HD）直接拒绝 `pitch` 参数（实测过，400 报错"This voice does not support pitch parameters"），`providers/google.py` 照抄老项目的做法：遇到这个特定报错就自动重试一次、去掉 pitch，不让整个请求因为一个声音不支持的参数失败。
- Fish Audio：只支持 speed + volume，没有 pitch（照抄老项目注释里确认过的），且只在非默认值时才把 `prosody` 塞进请求体。

真实调用测过全部四种组合：Fish Audio 默认路径（真实走了一遍浏览器 UI，speed 1.5x/pitch 85）、Azure（speed 0.7x/volume 30/pitch 20）、Google Chirp3 HD（验证 pitch 不支持时的自动重试确实生效且最终成功）、Google 普通声音（pitch 本来就支持，不触发重试）——全部成功。

前端这块也照抄了老项目的 UI 结构（3 个 tab 图标切换 speed/volume/pitch，一次看一个滑块，大字号数值显示，Save 按钮），`lib/audio-settings.ts` 里的取值范围、默认值、pitch 文字标签阈值（Deep/Dull/Consistent/Bright/Crisp）都是原样照抄老项目 `types/audioSettings.ts`。这是个**粘性的浏览器本地偏好**（存 localStorage，`tts_audio_settings`），不是每次生成单独配置、也不存后端，跟老项目的 `AudioSettingsContext` 一个思路。

顺带踩了这个 session 第二次同一个 ESLint 坑（`react-hooks/set-state-in-effect`，不让在 effect 里直接同步调用 setState）：`useAudioSettings()`从 localStorage 读初始值改用 `useState` 的懒初始化函数（不用 effect）；`AudioSettingsSheet` 每次打开需要把草稿重置成上次保存的值，没用"依赖 isOpen 的同步 effect"，而是让父组件传 `key={isOpen ? "open" : "closed"}` 强制组件每次打开都重新挂载，`useState(settings)` 的初始值自然就是新的——这样完全不需要 effect。

**踩过的坑，已经修了、也写进了对应 README 当"约定"（别再犯）**：
- **时间戳必须显式 `DateTime(timezone=True)`**——迁移是 `timestamptz`，ORM 模型不声明会在写入 tz-aware 值时崩溃（`backend/app/models/models.py` 的 `_TZ` 常量）。
- **写接口必须显式 `await db.commit()`**，不能只靠 `get_db()` 兜底——这套 FastAPI/Starlette 版本下，生成器依赖的 post-yield commit 可能晚于响应发出，导致"提交成功但立刻查询查不到"（真实复现过）。
- **R2 预签名 URL 在这版 `botocore` 下会被拒**（"Missing x-amz-content-sha256"）——改成后端自己读 R2 转发（`GET /jobs/{id}/asset`），不暴露裸 R2 URL。
- Neon 连接串的 `sslmode=require`/`channel_binding=require` 参数 asyncpg 不认，改用 `DATABASE_SSL_REQUIRE` 开关处理。

**目标市场：泰语、印尼语、西班牙语**（不是英文/中文），老项目 en/zh-CN/zh-TW 的语言内容不能直接复用。基础设施 region 暂定亚太（泰语+印尼语覆盖东南亚，西语用户延迟暂不是最优,等有真实流量再考虑多区域）。已记入 `docs/product-scope.md` §0。**注意范围**：这条是基础设施 region 优先级/UI 界面语言（i18n，ADR 0013）的决策，**不是"用户能选/能用哪些语言"的限制**——已经因为把这个和 TTS 声音选择弄混而做错过一次（选声音弹窗一开始被我限制成只给这三种语言，被用户纠正：推广进来的用户什么语言都有，包括英文，声音库不该收窄），别再犯。

**文档体系**：根 `README.md`、`docs/product-scope.md`、`docs/architecture.md`、`docs/data-model.md`、`docs/api-contract.md`、`docs/flows.md`、`docs/decisions/`（0001-0012）、`CONTRIBUTING.md`，加上 `backend/README.md`、`frontend/web/README.md` 这两份"怎么跑起来 + 踩过的坑"。代码落地按"文档策略"同步维护。

**已定（ADR 0001-0013）**：provider 适配层、异步 Job 契约、积分账本（冻结→结算/释放）、素材持久化到 R2、前端四端拆分、数据库选型、Fish Audio 接入、provider 目录同步策略、Auth = Firebase Auth、语音克隆是可复用资产、作品库 = 可见性字段、前端框架 Next.js、`app_settings` 配置模式、i18n 路由策略（marketing 前缀 URL / app cookie）。`docs/flows.md` 持续更新，别让它过期。

**能力菜单（"+"号弹出的那个 bottom sheet）已经做完并端到端验证过**：完全后端驱动，前端零业务配置（明确原则："我希望前端基本上没有任何配置，要轻"）——`GET /config/menu?locale=` 按 locale 解析好返回给客户端，`/admin/menu` 一套 CRUD（增删改查单条，不是裸 JSON blob PATCH，避免多语言结构数据被误改坏）；数据存在 `app_settings` 的一行 JSON（`capability_menu` key），这是 ADR 0012 配置分类里新加的第四类"结构化多条目、需要后台可编辑"的用法。前端唯一保留的本地配置是一张图标 key → SVG 的小对照表（`frontend/web/components/icons.tsx`，用户明确认可的唯一例外）。目前 5 个能力里只有 Text to Voice 是 `enabled`，其余 4 个（Dialogue/Image/BG Remove/Video Download）种子数据里存在但禁用，等各自后端切片。详见 `docs/api-contract.md`"Capability menu"节、`backend/app/services/menu.py`。

**路由结构修正**：之前 `/` 直接served了登录后的 app，被用户指出这不对（"后面我们还有网站的部分 那个才是根目录"）。现在 `frontend/web` 的登录后功能整体挂在字面 URL 前缀 `/app` 下（`app/(app)/app/...`，route group 本身不影响 URL，必须再套一层真实的 `app/` 目录才行——这个坑踩过一次，见 `frontend/web/README.md`），根路径 `/` 现在只是一个临时占位重定向组件（登录态判断后跳 `/app` 或 `/login`），留给以后的 `(marketing)`。

**Logo/图标资产复用了老项目的**（用户明确要求："logo相关的就复用老项目的，老项目的logo不错"）：`frontend/web/public/brand/` 下的 `mark.webp`/`mark-512.webp`（图腾鸟标）、`credits-token.png`（积分徽章），已经接进 Home 页头部、登录页、积分 pill。

**i18n 路由策略已定**（[ADR 0013](docs/decisions/0013-i18n-routing-strategy.md)）：按 surface 拆开，不是全站统一一种方案——`(marketing)` 用 locale 前缀 URL（`/th/...`、`/id/...`、`/es/...`，SEO 需要可被搜索引擎按语言收录）；`(app)` 用 cookie 存 locale，不带 URL 前缀（登录后页面不会被爬虫看到，没必要）。已经把 `frontend/web/lib/locale.ts`（`getLocale`/`setLocale`）接进 `CreateSheet` 的 `GET /config/menu` 调用，去掉了之前的硬编码 `locale="en"`——目前还没有 UI 写这个 cookie（左上角抽屉没做），所以实际效果还是都读到 "en" 默认值，但管线已经通了。

**左上角抽屉已经有个占位版本**：Home 页头部左上角真的有个图标按钮了（`components/SettingsDrawer.tsx`），点开会从左侧滑出一个面板，目前内容只有"Language and account settings are coming soon."一行占位文字——按用户要求先只做图标+面板骨架，语言切换器（会调 `lib/locale.ts` 的 `setLocale()`）和具体设置项还没做。真实浏览器里验证过：打开/关闭正常，无 console 报错。

**明确暂缓、不阻塞往下做的**：`(marketing)` 展示页、语音选择器（没有 voice catalog 接口）、公开作品库浏览页（`/gallery` 接口没做）、Android、真实支付、Admin 网页界面（现在只有受保护接口，无 UI；菜单管理已有全套 CRUD 接口可以随时接 UI）、作品库审核方式、具体计费数字、抽屉里的实际设置项（语言切换等）。

**下一步候选**（还没定，看用户想先做哪个）：① 声音试听——等真的要做，得先定是"正常走真实 TTS 扣积分"还是"搭一套样本预生成/缓存机制"，这是个真架构决策不是小事；② 把 Kie 的图片/视频接进来，验证真正的异步 Job 路径（目前只验证过同步 provider 路径）；③ 补 `/gallery` 端点 + 展示页；④ Android；⑤ 把抽屉内容做完（语言切换 + 设置项）。
