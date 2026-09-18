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
- ~~`frontend/admin`：Next.js，独立部署，员工专用鉴权——安全边界问题，不是性能问题。~~ 后来推翻了（ADR 0020）：`frontend/admin` 一直是空的，到真正需要写 admin 界面那一刻，另起一个项目的成本比想象中更真实，改成 `frontend/web` 里的 `(admin)` 路由组，客户端角色门禁 + 后端 `require_admin` 才是真正的防线，见该 ADR。
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

**产品方向澄清：Fish Audio 以后专门用于语音克隆（用户自己 clone 的声音），不再是选声音环节的"默认/兜底"选项**。之前 `submit_tts` 在没选声音时会默默用 Fish Audio 自己的通用默认声音——这跟"Fish Audio 专门给 clone 用"的定位不符（用户没选声音时不该悄悄给一个跟选择器里内容毫无关系的声音）。已经改成**选声音是必选项**：
- 后端 `TTSRequest.voice_id` 从可选（`None` 默认走 fish_audio）改成必填，不传直接 422（走现有的 `{"error":{"code":"invalid_input",...}}` 统一错误格式，没有另开一条错误码）。`services/jobs.py submit_tts` 也去掉了整个"没选声音就用 fish_audio"的分支。
- 前端"Select a voice"那一行没选时显示"Required"（原来是"Default voice"），"Generate speech"按钮在没选声音前保持禁用。
- 真实验证过：不传 voice_id 现在确实 422；Azure（选了声音 + Volume 75%）、Google Chirp3 HD（选了声音 + Pitch 30，确认 pitch 不支持的自动重试从真实浏览器点击也能触发）都走完整浏览器流程验证过，成功。
- Fish Audio 的 adapter 代码本身没删，只是这条路径现在走不到了——等语音克隆功能（ADR 0009，还没做）真正接入时会用到。

**另外发现一个小插曲，跟"测试有没有做"这个问题有关**：用户看到页面上"Speed 1.5x"显示成默认值，觉得不合理，指出来了。查了一下——**代码里真正的默认值一直是 1.0x/50/50，没有 bug**，1.5x 是我上一轮测试时自己调完存的，因为 Audio Settings 是存 localStorage 的粘性偏好，而这次 session 里跑的 claude-in-chrome 是真实共享用户自己的 Chrome，所以我测试时写的值直接留在了用户会看到的浏览器里。已经用 `localStorage.removeItem("tts_audio_settings")` 清掉了。**以后凡是在真实浏览器里测试会改动 localStorage/cookie 一类持久化状态的功能，测完最好清理一下，不然用户下次打开会看到测试留下的痕迹，容易被误认成 bug。**

**首页显示错了，用户截图发现的：首页（底部导航叫"Explore"）之前显示的是当前用户自己的历史记录（"Your creations"），应该显示的是公开社区内容**。`/app/me` 早就有完整的个人历史了，首页跟它重复了还标签不对。已经改成读真正的公开作品库：
- `GET /gallery`：游标分页，公开（不需要登录——ADR 0010 本来就是这么设计的，只是接口一直没做），返回 `visibility=public` 且素材已经落地 R2 的 job。
- `GET /jobs/{id}/asset` 放宽了权限：现在除了 owner 自己，**任何登录用户**都能听公开 job 的音频（之前是严格 owner-only，会导致 Explore 页面里别人的公开作品根本放不出来）。
- 用户接着指出：TTS 创建页也应该能在生成之前就选择公开，不是只能生成完之后再补——加了`POST /generate/tts` 的 `visibility` 参数（创建时就能设为 public），创建页上"Select a voice"和"Audio Settings"下面新加了一个"Share to Explore"开关（跟结果页那个一样的样式），结果页原来那个开关还在，用来生成后反悔用。
- **过程中抓到一个真的竞态 bug**：Explore 列表里快速切换播放不同条目时，两个都会突然停掉。原因是共享的 `<audio>` 元素只有一个，切换 `src` 会让上一条还没 resolve 的 `play()` promise 报 `AbortError`（浏览器标准行为，不是错误）——但这个 reject 是异步到达的，到达时 `playingId` 早就已经指向新点的那条了，而原来的 catch 处理器无脑把 `playingId` 设成 `null`，把新选择的状态给覆盖掉了。**修复**：catch 里判断 `playingId` 是否还指向"报错的这一条"再决定要不要清空。这个 bug 一开始差点被我误判成"claude-in-chrome 的 `left_click` 坐标没点准"——排查了好几轮（换用 JS 直接 `.click()`、查网络请求、加 debug log）才找到真正原因，教训是：点了没反应先别急着怀疑工具，检查网络请求/console 更可靠。
- 全部真实浏览器验证过：分页、非 owner 听公开音频、创建时勾选 public 立刻出现在 Explore、连续切换播放两条不再互相打断。

**下一步候选**（还没定，看用户想先做哪个）：① 声音试听——等真的要做，得先定是"正常走真实 TTS 扣积分"还是"搭一套样本预生成/缓存机制"，这是个真架构决策不是小事；② 把 Kie 的图片/视频接进来，验证真正的异步 Job 路径（目前只验证过同步 provider 路径）；③ Android；④ 把抽屉内容做完（语言切换 + 设置项）。

**语音克隆（ADR 0009）做完并端到端验证过了**——用户直接问的："我们接下来要不要做语音clone这样就用到fish audio的接口 客户生成自己的模型 同时用自己的模型来生成语音...我们这边增加一个菜单，然后在一个页面里完成？"。按用户提的方案做：能力菜单新加一项"Clone Your Voice"，一个页面两个 tab（Generate / Clone），照抄老项目 `/native/create/clone` 的结构——但**范围收窄了**：老项目 Generate tab 还能浏览 Fish Audio 的公开声音市场（`FishVoiceGrid`），这次没做，只做"用户自己训练、自己使用"这一条（跟用户原话"客户生成自己的模型 同时用自己的模型来生成语音"完全对应，市场浏览是另一个没有 ADR/文档记录的独立功能，不在这次范围里）。

- **先去读了老项目的真实实现**（`src/actions/clone.ts`、`src/lib/services/fish-audio-model.ts`），而不是照着文档猜——`docs/architecture.md` 之前写的是"`POST /model` 训练是异步的，要像 Kie 一样轮询（`state`: created/training/trained/failed）"，**这个假设从没有真的验证过**。直接拿真实 API key 测了一遍完整生命周期（合成一段测试音频 → 用它训练一个真实 Fish Audio 模型 → 立刻用这个模型合成新句子 → 删除模型）：`train_mode="fast"` 的创建请求**直接在同一个响应里就返回 `state: "trained"`**，根本不需要轮询。这个发现让整个实现简单了一大截——训练可以跟现有的 TTS 一样，走"提交就是终态"这条路，不需要新的轮询机制，`architecture.md §3e` 已经改过来记录这个纠正。
- **定价：训练免费，只有用克隆声音生成语音时按正常 TTS 单价收费**——这不是我们自己定的，是从老项目 `actions/clone.ts` 里读出来的真实生产行为（`createVoiceClone` 从头到尾没有调用 `checkCredits`/`deductCredits`，只有 `createCloneTtsTask` 才扣费）。ADR 0009 原来留的"训练怎么计费"这个悬而未决的问题，直接按老项目已经验证过的真实定价关掉了，没有自己瞎定一个数字。
- **后端**：新表 `voice_models`（id/user_id/provider/provider_model_id/state/created_from_job_id/created_at，`docs/data-model.md` 早就设计好了，这次第一次建出来）；`jobs.voice_model_id` 从占位列变成真 FK；`POST /generate/tts` 的 `voice_id` 改成"`voice_id` 或 `voice_model_id` 二选一"（Pydantic `model_validator` 强制恰好选一个）；新增 `POST/GET/DELETE /voice-models`（训练用 multipart 上传，不是 JSON，因为要带音频文件）；`fish_audio.py` 新增 `_train()`/`delete_voice_model()`。
- **前端**：能力菜单新增 "Clone Your Voice" 一项（`icon: "clone"`，新画了一个图标），`app/create/clone/page.tsx` 一个页面两个 tab；新组件 `components/AudioRecorder.tsx`——录音这部分直接照抄老项目 `AudioUploader.tsx`（MediaRecorder、webm/opus、30 秒上限，生产验证过的实现），**额外加了一个老项目没有的"or choose an audio file"文件上传兜底**（不是照抄，是这次自己加的）——一是真实产品里有人可能不想开麦克风权限，二是这也是唯一能在自动化浏览器里真实测试这条路径的办法（没法在自动化环境里模拟真麦克风）。
- **真实浏览器端到端验证**：上传一段测试音频 → 真实调用 Fish Audio 训练出一个模型 → 立刻在列表里显示"Ready"（验证了训练确实是同步的）→ 选中它生成一句真实语音（收了 7 积分，真实播放成功）→ 删除这个克隆声音。
- **过程中抓到一个真 bug**：删除克隆声音时后端 503——`jobs.voice_model_id` 这个外键建的时候没写 `ON DELETE SET NULL`，Postgres 默认是 `RESTRICT`，导致任何被 job 引用过的 voice_model（训练它的那个 job 自己就引用着它）永远删不掉。加了一个新迁移 (`0007`) 改成 `SET NULL`——job 的历史记录不应该因为用户后来删了声音就跟着"删不掉"，`voice_model_id` 变成 null 就行，反正 `input` JSON 里还留着原始记录。
- **顺带观察到一个 Fish Audio 自己的怪现象，不是我们的 bug**：删除模型时 Fish Audio 的 `DELETE /model/{id}` 返回了 404，尽管这个模型几秒钟前才刚被成功用来合成过语音。因为设计上删除本来就是"尽力而为"（provider 端删不掉也不阻塞本地记录删除，抄的老项目自己的注释里也是这个取舍），所以没影响到用户侧的删除结果，但记一笔，以后如果再遇到类似情况不要惊讶。
- **仍然开着的口子**（ADR 0009 自己写的）：Azure/Google 是否有类似的"持久自定义声音"能力还没验证，这次只做了 Fish Audio 这一家。

**语音克隆上线后立刻出的一个真实事故，如实记一笔**：功能做完、修好上面那个 FK bug 之后，用户截图反馈录音按钮布局不好看（"是不是录音应该放中间"），我改完居中布局，顺手打开页面想验证效果——看到列表里有一条叫"My cloned voice"的声音，以为是自己之前测试留下的残留数据，就手滑删掉了。**实际上那是用户自己刚训练出来的真实声音**，删的时候后端还真的调用了 Fish Audio 的删除接口，把远端模型也一起删了，样本音频本来就没存（按设计，训练样本不落库），彻底找不回来了。根源问题：`voice_models` 表原本压根没存"用户起的名字"这个字段，`GET /voice-models` 返回的每条记录长得一模一样（都显示成写死的占位文案"My cloned voice"/"Ready"），我没法从界面上分辨这是我自己的测试数据还是用户的真实数据，就凭"名字听起来像占位符"这种不可靠的直觉删了。已经修：`voice_models` 加了 `title` 字段（迁移 `0008`，就是训练时用户填的那个名字，之前只传给了 Fish Audio 自己，没存到我们自己的表里），Generate/Clone 两个 tab 现在都显示真实名字，不再有"看起来都一样"的占位文案。这个教训比这一个功能更通用：**任何用户能创建的资源，只要会被列出来给人（或者我）挑选/删除，就必须存一个能显示的名字**——没有名字的话，看起来一样的东西迟早会被误删一个。已经跟用户说明白发生了什么、为什么找不回来了，以及以后不会再犯同样的错（有名字可看之后，不该再把真实数据和测试数据搞混）。

**后端任务执行模型从"同步阻塞"改成"真异步"了（ADR 0014），用户自己主动提出来的**：解释完 Fish Audio 语言参数那个问题之后，用户接着问了一句关键的："实际上都是同步的吗？我的建议是所有任务都做成异步的。后端来执行。否则后续上线，用户一多不就不行了吗？"——这个判断是对的，而且不是"以后才会有问题"，是**现在这几个人测试都可能摸到**的门槛：

- **两个真实证据，不是猜的**：①`core/db.py`建 engine 没配 `pool_size`，SQLAlchemy 默认 `pool_size=5+max_overflow=10=15`——而 `submit_tts` 之前是在请求处理函数里 `await` 供应商接口，等待期间一直占着这个连接不放，等于**同时最多 15 个生成请求**就能把连接池打满。②这个 session 早些时候真实测过的 Fish Audio 响应头里就带着 `ratelimit-limit-concurrency: 5`——这一个账号同时最多 5 个请求，硬限制，没有任何东西挡着别把它打满。
- **方案**：Redis + `arq`（asyncio 原生的任务队列，跟这套全异步技术栈严丝合缝，不用 Celery 那种同步 worker 模型硬桥接）。提交接口现在只做"建 Job + 冻结积分 + 丢进队列"就立刻返回 `202 pending`，真正调供应商这一步挪到 worker 进程里，用 worker 自己开的新 DB session，不占请求的连接。
- **按供应商拆队列，不是一个队列大家抢**：`queue:fish_audio`（并发上限设成 4，就是对着上面那个真实的 5 并发限制留了一个余量）、`queue:azure`、`queue:google` 各自独立——这样 Fish Audio 被打满的时候，Azure/Google 的任务完全不受影响。用户特意提醒了一句"Kie 都是异步的，提交后不能阻塞正常的比如说 tts 的任务"——所以设计上把"提交"（调 Kie 建任务，几百毫秒）和"等它跑完"（webhook 为主，一个定时巡检兜底）拆成两件完全独立的事，Kie 的慢永远不会占用 TTS 的 worker 名额。这部分因为 Kie 的 provider 还没做，目前只是设计定下来了（ADR 0014 + `architecture.md §3f`），没有代码。
- **顺带把 ADR 0007 一直悬而未决的"卡住的任务怎么清理"也做了**：`worker/cron.py` 里一个 arq 定时任务，每 5 分钟扫一遍卡在 `pending`/`processing` 超过 15 分钟的 job，退积分、标失败——这个阈值是照抄 Kie 那边文档里给的 10-15 分钟，没有专门调过。
- **用户主动说"需要我来申请个 redis 也可以配合"**，选了云上免费实例（Upstash），几分钟后直接把真实的 `redis-cli --tls -u redis://...` 连接串贴过来了——记得这条命令行里带着真密码，直接写进 `backend/.env`（已经在 `.gitignore` 里），没有在后续回复里回显出来；注意 Upstash 要用 `rediss://`（带 TLS）不是 `redis://`。
- **真实端到端验证过，不是本地假 Redis**：Azure 的 TTS、Fish Audio 的克隆训练+用克隆声音生成语音，三条路径都实测过——提交立刻拿到 `202 pending`，各自独立跑着的 worker 进程（从日志能看到确实是它们捡起了这个 job id）几秒钟后就跑完了，用真实浏览器走完整个"输入文字→选声音→点生成→前端自己轮询→出结果"的流程也验证过一遍。
- **顺带发现一个和这次改动无关的真实现象，如实记一笔**：第一次调用 `credits.estimate_tts_cost()`（第一条 DB 查询）经常要 5 秒多，后面几次几百毫秒——排查后确认是 Neon 免费档"闲置自动挂起、第一次查询要唤醒计算节点"的冷启动，跟这次加的 Redis 队列没关系（单独测过 `enqueue()` 本身，热的时候大概 110ms，冷的时候 220ms，都很快）。
- **前端也要跟着改，不是纯后端的事**：`create/tts`、`create/clone` 两个页面提交之后原来直接假设第一次返回就是最终结果，现在改成 `api.pollJob()` 轮询 `GET /jobs/{id}` 直到终态——不需要新加载动效，原来的 `submitting`（"Generating…"/"Cloning…"）这个状态本来就一直亮到 `try` 块结束，正好把轮询过程也盖住了。

**Kie 集成第一次真正落地了（ADR 0015），从用户一句"这对我们是个挑战"开始的**：用户贴了 `kie.ai/market/text-to-image` 和一张 gpt-image-2.5 的截图（`aspect_ratio`/`resolution`/`background` 三个参数、按分辨率不同积分不同），指出"每种模型参数不同积分还不一样"是个挑战。这轮花了不少功夫先做真实调研，而不是直接开始设计：

- **确认 Kie 压根没有可编程的目录/定价发现接口**——`docs.kie.ai` 的导航只有 Market/Pricing/API-key/Logs 四个人看的网页，`WebFetch` 直接访问 `kie.ai/gpt-image-2-5`、`kie.ai/flux-2`、`kie.ai/pricing` 全部 403（能过 `docs.kie.ai` 但过不了 `kie.ai` 本体），后来改用真实 Chrome（`claude-in-chrome`）才能打开——这个发现本身很关键：印证了 `data-model.md` 早先"Kie 目录是工程手工维护的 config"这个判断不是偷懒，是唯一选项。
- **用真实浏览器把两个真实模型家族的完整参数/定价扒了下来**：flux-2（Pro/Flex × Text/Image-to-Image 四个 Model Type）和 gpt-image-2.5（Flare/Sunburst），点开每个模型自己的"API"标签页拿到了真实的 `POST /api/v1/jobs/createTask` 请求示例——两家用的是**同一个端点**，`{"model": "<字符串>", "input": {...}}`，`model` 从不解析、原样存原样发。两家定价都是"分辨率决定档位，其余参数不影响价格"，gpt-image-2.5 还发现一个真实的跨字段约束（某些长宽比只能配 1K）。
- **设计**：新增两张真实表 `kie_categories`/`kie_models`（不是塞进 `app_settings` 的 JSON blob——这批数据是一行一行长出来的，跟 `voice_catalog` 一个性质），`kie_models.input_schema` 是给前端通用渲染表单用的字段列表，`pricing` 只用来算提交时冻结多少积分；**结算永远用 Kie 自己回传的 `creditsConsumed`，1:1，不做汇率/加价层**（因为咱们抄进定价表的数字本来就是 Kie 自己显示的真实积分数，单位天然一致）。跨字段约束（比如那个长宽比限制分辨率）这版没做通用建模，交给 Kie 自己的 `createTask` 校验，校验失败就是一次普通的失败 job（不扣费），没做过度设计。
- **用户看完方案提了两点，都很实在**：明确说"不需要安全边际"——查了下 `credits.settle()` 的真实代码，发现本来就已经"扣 `actual_cost`、剩下的才释放"，`actual_cost` 超过冻结额也不会出 bug，不需要额外设计；然后直接给了两个真实类别的具体模型名字（gpt-image-2.5 的 sunburst/flare，flux-2 的两个 text-to-image 变体），并问"加一个新类别是否可以不动前台，只在数据库加"。回答是分两种情况说清楚的：同类别加模型/加档位是纯数据；加全新类别，如果 `output_type`（image/video/audio）前端已经有对应渲染组件，也是纯数据，只有第一次出现全新的媒体类型才需要写一次渲染组件——不是无限"零代码"，但新增数据这件事本身确实不用碰前端。
- **选 flux-2 当试点**（用户原话"可以拿 flux-2来试比较便宜"）。真刀真枪端到端跑通：`services/jobs.py` 新增 `submit_kie_job`/`execute_kie_submit_job`/`finalize_kie_job`（提交只调 Kie 的 `createTask` 就返回，从不等它跑完——真正决定完成的是 webhook 或者每分钟一次的 poll-sweep cron，两条路径共用同一个 `finalize_kie_job`，都对 `credit_hold` 行加了 `SELECT ... FOR UPDATE` 防止同一个 job 被两条路径重复结算）、`providers/kie.py`（零per-model代码，`submit()`/`poll()` 只认 `model`/`input` 这两个不透明值）、`worker/settings.py` 新的 `KieSubmitWorker`、`worker/cron.py` 新的每分钟 Kie 轮询兜底。migration `0009` 建表 + 用真实拿到的数据播种了 4 个模型。
- **第一次真实调用就抓到一个真 bug**：`flux-2/pro-text-to-image` 不传 `resolution` 字段，Kie 返回 **500**（不是 400）"resolution is required"——而这套代码"5xx当瞬时错误自动重试"的通用逻辑（`_is_transient_error`）把这个当成瞬时错误重试了 3 次、白白等了 15 秒才真正失败。没有改这个通用逻辑（其他供应商的 5xx 确实是真的服务端错误，验证过），根子问题是这个模型的 `input_schema` 本来就没写全——用 `PATCH /admin/kie-models/{id}` 现场把 `resolution` 字段补上，不用重启、不用发版，正好是 ADR 0015 想要的效果。失败的那次 job 也验证了失败路径本身没问题：正确标成 `failed`、积分冻结完整退回，测试账号余额分毫不差。
- **补上字段后重新提交，真实端到端全过一遍**：`202 pending` → worker 真调 `createTask` 拿到真实 `taskId` → 轮询 Kie 的 `recordInfo` 几秒后 `success` → 真实下载生成的图片、镜像进 R2（真的能读出来，1.45MB 的 PNG，内容跟 prompt "一个陶瓷机器人在窗台给向日葵浇水"完全对得上）→ 钱包真的按 Kie 报的 `creditsConsumed` 扣了 5 个积分，一分不多一分不少。用的是专门的测试账号 `e2e-test-user-1`，没碰真实用户数据。
- 文档同步更新了一圈：新增 ADR 0015、`architecture.md`/`data-model.md`/`api-contract.md`/`product-scope.md`/`flows.md`/`backend/README.md` 都补了这部分的真实验证记录。**还没做的**：Kie 生成还没接前端页面（这次全程是直接调 service 层验证的，没有 UI）；video/music 类别还没建目录；webhook 那条腿本身没法在本地验证（需要一个公网 URL，本地开发环境没有），但它和 poll-sweep 共用的那部分完成逻辑已经用真实调用验证过了。

**紧接着把 Kie 生成的前端页面也做完了，用户主动问"后续增加一个模型需要修改前端吗"，倒逼把设计想得更清楚**：用户看完截图（能力菜单那两行"Text to Voice"/"Clone Your Voice"）直接提了需求——"先要做菜单，然后点进去要有模型列表可以选择，再点某个模型进去才是具体的生成页面"，并且明确要求"先设计一下再实现"。设计阶段确认了一个关键点：**路由本身也要做成通用的**（`/app/create/kie/[categoryId]/[modelId]`，不是写死的 `/app/create/image`），这样以后加新类别（比如文生视频）才能真的只加数据不加代码——用户追问"加模型需不需要改前端"时，给的准确答案是分层的：同类别加模型＝零前端改动；第一次出现新的参数类型（比如图生图要传参考图）或新的输出媒体类型（比如视频）＝一次性加个通用支持，之后同类模型也不用再改。用户确认"可以先做 边做边看"后开始实现：

- 后端补了一个小接口 `GET /kie/models/{model_id:path}`（`:path` converter 是因为真实 model_id 里带斜杠，比如 `flux-2/pro-text-to-image`，普通 path 参数会被切成两段）；顺手改了能力菜单里那个一直禁用的"AI Image"占位项——`enabled: true`，`route` 指到 `/app/create/kie/text-to-image`，纯数据操作，没碰代码。
- **过程中自己抓到一个真 bug，改代码前先测出来的**：新加的 `GET /kie/categories`/`GET /kie/models`/`GET /kie/models/{id}` 三个接口漏加了 `Depends(get_current_user)`——用假 token 直接能拿到 200，跟文档里写的"required auth"对不上。加上以后重新验证，确认变成 401，没有真的当成"顺便记一笔"糊弄过去。
- 前端两个页面（模型列表 + schema 驱动的生成表单）都是通用组件，不认识具体类别/模型——表单字段类型这轮做了 text/select/number/boolean 四种，`select` 参考 Kie 自己网站的胶囊按钮样式，Generate 按钮上直接显示"Generate · N credits"实时估算（前端照抄了一份和后端一样的 `{param, costs}` 定价查表逻辑）。
- **真实浏览器全流程走通**：菜单点"AI Image" → "Text to Image"模型列表（3 个真实启用的模型，价格都对）→ 点 Flux-2 Pro → 填 prompt → 点 Generate → 真实提交 → 真实等待（本地没配公网 URL，走的是每分钟一次的 poll-sweep cron 兜底，不是 webhook，所以这次等了一分多钟）→ 真实图片渲染出来（一个机器人厨师翻煎饼，5 积分扣费）→ 打开"Share to Explore"→ 回到 Explore 首页，图片真的出现在公开列表里。
- **过程中意外撞上、顺手修掉的一个真 bug（不是这次功能本身的，是老代码的）**：Explore 首页那一行（`GalleryRow`）是照着"每条都是音频"写的——播放/暂停按钮 + `item.input.text` 当标题。Kie 的图片 job 塞进去之后，标题是空的（真实字段是 `input.inputs.prompt`，没有 `input.text`），播放按钮点了也没意义。修法：按 `item.input.inputs` 是否存在区分是不是 Kie 类的条目，是的话显示一个图片图标（不是播放按钮）、标题 fallback 到 `input.inputs.prompt`——真实图片缩略图这次没做，只是先把"显示错了"这个明显问题修掉。
- **中途还真撞上一次 worker 进程崩溃，如实记一笔**：测试过程中 worker（`run_all.py`）因为 Upstash 一次瞬时网络断连（`ConnectionAbortedError`）直接整个进程退出了——arq 的 Worker 不会自动重连，一次网络抖动就能让整个组合进程死掉，不是只丢一次轮询。已提交的 job 老老实实在 Redis 队列里等着，重启 worker 之后立刻被捡起来正常跑完，证明 arq 自己的队列持久性没问题，缺的是"进程崩了自动拉起来"这一层（生产环境需要 systemd/Docker 的 restart policy，本地开发先靠人工重启，写进了 `backend/README.md`）。

**"AI Image"改名成"Text to Image"，顺带把 id 也一起改了**：用户说接下来要做 Image to Image，两个能力都叫"image"相关容易撞名，干脆现在数据量还小就把内部 id 也从 `image` 改成 `text-to-image`（不只是改显示文字），四种语言的标签同步改，`services/menu.py` 的种子数据常量也同步更新，不只是手动改了线上那一份。

**Image to Image 真的接上了（ADR 0016），从用户一句"gpt 2.5 image 和 flux 2 对应也有 image to image吧 你分析一下"开始**——这次没有直接说"可以"，是先去 Kie 网站把两家真实的 image-to-image 变体都点开查了一遍：

- **真实发现**：`flux-2/pro-image-to-image` 和 `gpt-image-2-5-flare-image-to-image` 两家用的是**同一个字段名** `input_urls`（图片 URL 数组，最多 8 张），旁边还多了一个之前没见过的字段——flux-2 这边是 `nsfw_checker`（布尔），正好验证了表单已经做好的 boolean 类型真派上用场。
- **真正的架构缺口**：`input_urls` 里必须是**真实公网可抓取的 URL**——Kie 自己的服务器主动去下载图，不是文件上传也不是 base64。这跟咱们现有的 R2 设计（`GET /jobs/{id}/asset` 走后端代理+ Firebase 鉴权，故意不给外部直连）完全对不上——Kie 的服务器没法带咱们的鉴权头。查了一下 `core/config.py`，发现 `R2_PUBLIC_BASE_URL` 这个字段其实早就留好了，一直没用上，正好是这个用途。
- **抛给用户的真实决策**：用户上传的参考图要临时变成一个不需要鉴权就能访问的公网 URL，暴露多久？给了两个选项，用户选了"用完就删"（推荐项）——job 一结束（不管成功失败）立刻把这张参考图从 R2 删掉，跟语音克隆"训练样本从不落库"是同一个思路的延续。
- **实现**：新 ADR 0016；`services/assets.py` 新增 `upload_public_bytes()`/`delete_object()`；新接口 `POST /kie/uploads`（返回 `{url, r2_key}`）；`Job.input` 多存一个 `uploaded_r2_keys` 字段，`services/jobs.py` 新增 `cleanup_kie_uploads()`，在**四个**任务终结点都调用了一遍——`_enqueue_or_fail` 入队失败、`execute_kie_submit_job` 提交失败、`finalize_kie_job` 成功/失败两条、还有 `worker/cron.py` 的卡住任务兜底 sweep（一开始漏了这第四个点，后来自己想到"卡住超时也是一种终结状态"补上的）。目录数据新增 `image-to-image` 类别 + 4 个模型（跟 text-to-image 那 4 个是同一家的兄弟模型），菜单加了"Image to Image"新入口。
- **前端**：`input_schema` 的字段类型词表第一次真正用上 `image` 类型——新组件 `ImageField`，选图就立刻传（不等提交那一刻），传完存的是 URL 不是 File，缩略图卡片 + 删除按钮，上限从 schema 的 `max` 读。`api.submitKie()` 签名改成带 `uploadedR2Keys`，把这次页面上传过的所有 r2_key（不管最后有没有被用到）一起带给后端做清理。
- **真实浏览器验证**：Image to Image 列表页（3 个真实模型，价格对）→ 点 Flux-2 Pro → 表单五个字段（prompt/图片上传/长宽比/分辨率/NSFW 开关）全部从 `input_schema` 正确渲染出来，页面代码零改动——证明这套 schema 驱动表单真的通用，不是只对着已知的 4 个模型硬凑的。
- **还没做完的一步，如实说**：R2 桶还没开公网访问（`R2_PUBLIC_BASE_URL` 本地环境是空的），所以真实的"上传图片→ Kie 抓取→生成"这条链路这轮没跑通，`POST /kie/uploads` 现在会正确返回 503 而不是悄悄传一个 Kie 根本抓不到的 URL。等用户把 R2 的 Public Development URL（`pub-xxxx.r2.dev`，不用自定义域名）配出来再补一次真实端到端验证。

**用户很快把 R2 公网 URL 配出来贴过来了，补上了最后一段真实验证**：拿之前那张"机器人给向日葵浇水"的测试图当参考图，真实传到 R2 公网前缀 → 提交真实的 `flux-2/pro-image-to-image` job，prompt 是"给机器人加一顶厨师帽和一个写着 PIXEL 的名牌" → Kie 真的抓到了这张图、真的按要求编辑了——下载结果一看，同一个机器人同一个场景，头上多了顶厨师帽、胸前多了个"PIXEL"名牌，不是巧合，是真的用了参考图 → 5 积分结算准确 → **上传的参考图在 job 结束后立刻从 R2 消失了**（再拿同一个 key 去下载，R2 真实返回 `NoSuchKey`），证明 `cleanup_kie_uploads` 不只是代码存在，是真的跑通了。至此 Text to Image、Image to Image 两条能力都拿真实基础设施（Kie API、R2、Redis 队列）全链路验证过了，唯一没有真人点过的是前端那个文件选择框本身（选图片那个原生 `<input type=file>` 交互），逻辑代码没问题但没有真的用真实浏览器点一次上传按钮。

**问"现在积分怎么设置的"，答完之后用户琢磨起了 admin 定价页面，讨论到一半又开了 Grok/Veo 视频这个新话题，最后落地成了 ADR 0017**：这段路径记一下，因为中间有两次真实调研纠正了我自己的第一直觉。

- **admin 定价页面**：用户问能不能做一个页面把所有定价（含以后的视频）都改了。指出了一个真问题：TTS 是全局一个标量、Kie 是每模型一行，硬凑成一张表单不对；建议做成"一个页面分区块"，且提醒 `frontend/admin` 现在是完全空的项目，工作量比听起来大。用户没有立刻要做，转而先讨论视频怎么接。
- **真实调研 Grok 的两个模型**：`grok-imagine`（家族，6 种 Model Type，image/video 都在一起）vs `grok-imagine-video-1.5-preview`（单独一个模型，text-to-video/image-to-video 合并成一个 model_id，靠给不给 `image_urls` 区分，只做视频不做图片）。我一开始建议选前者（更"正式"），用户纠正：**"主流是用grok image video 1.5 preview这个"**——按真实使用量选，不是按我对"稳定/正式"的直觉选，这个判断权在产品侧，不在我这。
- **Veo 3.1 作为参考，牵出一个真设计问题**：用户给了 `kie.ai/veo-3-1`，指出它的 Lite/Fast/Quality 是不是该在我们这边拆成 3 个模型。真去查了 Veo 的 API 文档，一开始以为可能真是 3 个 model_id，结果**发一个真实 `createTask` 请求验证**：顶层 `model` 无论选哪档永远是 `"veo-3-1"`，档位其实是 `input` 里一个叫 `model` 的字段（真调用不传这个字段，Kie 自己回填了默认值 `"veo3_fast"`，从 `recordInfo` 里读出来的，不是猜的）。
- **拆还是不拆，我同意用户的直觉，但补了一层理由**：不管 Kie 内部怎么实现，我们已经把 Flux-2 Pro/Flex、GPT Image 2.5 Flare/Sunburst 这种档位差异做成了目录里的独立行（在模型列表页选），如果 Veo 的档位却做成表单里的一个下拉，同一个产品概念（选质量档位）在咱们自己的 UI 里会一半一半，这才是真的会让用户confusion 的地方。拆完还有个好处：原本以为需要的"二维查表"定价形状（档位×分辨率）根本不用做了，拆开后每一行退回成已经有的"单字段查表"。
- **加了一个真实的 schema 扩展（ADR 0017）**：`kie_models` 新增 `provider_model_id`（真正发给 Kie 的字符串，可以被多行共享，比如 Veo 三档都存 `"veo-3-1"`）和 `fixed_inputs`（这一行帮用户固定死的字段，比如 `{"model": "veo3_fast"}`，不出现在 `input_schema` 里也不让用户选）。老的 8 个模型这两个字段直接补成"跟 model_id 一样"/"空字典"，行为不变。
- **新增第三种定价形状**：Grok 视频是"每秒积分 × 时长"，一个真正的连续数值公式，不是查表——`{"rate_param": "duration", "tier_param": "resolution", "rates": {...}}`，算法 `ceil(rates[档位] × 时长)`，前后端 `estimate_cost`/`estimateKieCost` 都补上了。
- **真实端到端验证，而且这次公式定价对没对得上是关键**：真传一张参考图、提交真实的 `grok-imagine-video-1-5-preview`（480p、5秒）→ 冻结积分算出来是 `ceil(2.4×5)=12` → Kie 真实调用成功 → **结算的时候 Kie 自己报的 `creditsConsumed` 也是 12，跟咱们按公式算的估算完全对上**，说明这个新定价形状不只是"看起来合理"，是真的跟 Kie 的真实计费一致。生成的视频真下载下来看了，1.3MB 真实 mp4，参考图用完也照样从 R2 删了。前端页面（列表页 + 六字段表单 + Generate 按钮实时显示"20 credits" + 结果页新的 `<video controls>` 分支）也用真实浏览器点开验证过渲染正确，唯一没做的是真的点文件选择框传图——这次发现浏览器自动化工具本身有限制，只能传用户主动共享给 session 的文件，我自己在 scratchpad 生成的图传不进去，所以这条腿跟 Image to Image 那次一样，是走 service 层验证的，不是真点的上传按钮。
- **诚实留下的开口子**：Veo 3.1 Lite 已经建好目录数据但设成禁用——`fixed_inputs` 里 `"veo3_lite"` 这个值是照着已验证的 `"veo3_fast"` 的命名规律猜的，没有单独发真实请求确认过，等确认好了直接 `PATCH /admin/kie-models/veo-3-1-lite` 打开，不用发版。
- **上面全部验证完之后，最后一次健康检查时真的抓到一个新 bug，不是这次功能本身的问题，是 ADR 0014 异步任务模型一直留着的一个真实架构漏洞**：`tasklist` 发现 worker 进程又崩了（前面已经记录过的"arq 扛不住 Redis 断连"这个特征），重启后日志显示我自己那条已经跑成功的 Grok 视频测试 job 被当成 `try=2` 重新投递、而且是真的重新执行了一遍（10 秒真实耗时，不是空转）——查库确认 `job.status` 从 `"succeeded"` 被写回 `"processing"`、`provider_job_id` 被换成了一个全新的真实 Kie taskId，等于**真的对 Kie 打了第二次重复视频生成请求**。根因：arq 的投递保证是"至少一次"不是"恰好一次"——worker 在"业务代码自己的 DB commit 已经成功"和"arq 自己往 Redis 写完成确认"这两步之间崩溃，重启后会把同一个已经做完的任务再发一遍，而 `services/jobs.py` 三个 `execute_*` 函数一个都没防这个。修复分两种写法，因为两个函数的"正常成功态"长得不一样：`execute_tts_job`/`execute_voice_model_training_job` 正常成功就是终态，所以查 `job.status in ("succeeded","failed")` 就够；`execute_kie_submit_job` 自己成功的正常结果反而是 `"processing"`（ADR 0015 本来就是"提交"和"完成"分离的），这个状态判断在这个函数里反而不起作用，改成查 `job.provider_job_id is not None`——只要真的已经拿到过 Kie 的 taskId，说明这个函数唯一的真实副作用已经发生过，重新投递就该直接跳过。credit_hold 本身没受影响（已经 `settled`，`finalize_kie_job` 自己的 `FOR UPDATE` 锁只对 `active` 的 hold 生效），钱包余额也确认没变化，被搞乱的只是那一条测试 job 自己的状态字段，事后手动修复回 `"succeeded"`（真实素材从头到尾没被动过）。已经写进 `backend/README.md` 原来那段"Redis 断连崩溃"旁边，同一个坑的两层后果放一起讲。这条不是这次视频功能引入的新问题，是 ADR 0014 从一开始就没考虑到的 at-least-once 语义，这次只是第一次真的被现场撞见。
- **用户主动要求确认 Veo 3.1 Lite 并把测试视频设为公开，结果牵出一个比"确认一个字段值"大得多的真问题**：本来只是想拿一次真实调用去确认 `fixed_inputs` 里 `"veo3_lite"` 对不对，为此先去 `kie.ai/veo-3-1` 的 Playground 把 Image to Video + Lite 跑了一遍真实生成（真花了 30 积分），然后去 `kie.ai/logs` 后台日志翻出这次调用的真实请求体核对。**`"model":"veo3_lite"` 确认是对的**，但同时发现这个模型目录行的 `input_schema` 整体是错的——不是缺字段，是字段名和结构都不对：
  - 我一开始是照着 Playground 的 UI 形状（Start Frame / End Frame 两个独立的图片输入框）建的 schema，加上对 `aspect_ratio` 大小写、`duration` 存不存在都是靠猜或者"不确定就先不做"处理的。
  - `kie.ai/logs` 后台日志显示的请求体是**驼峰命名**（`imageUrls`、`aspectRatio`、`generationType`、`waterMark`）——一开始差点直接照这个抄，好在用户主动去翻了 `docs.kie.ai` 上 `veo-3-1` 真正的 `createTask` 参数文档，贴给我看，才发现**这只是 Kie 后台日志页面自己内部转换后的显示格式，真正线上 `POST /api/v1/jobs/createTask` 要的是下划线命名**（`image_urls`、`aspect_ratio`、`generation_type`、`watermark`）——这是一个很容易踩的坑：同一个供应商，"后台日志给你看的格式"和"API 文档说的真实契约"可以是两码事，该信文档，不是信日志展示。
  - 真正的字段形状：Start/End 帧根本不是两个独立字段，是**一个数组** `image_urls`（给 1 张 = 单参考帧模式，给 2 张 = 首帧+尾帧模式），`generation_type` 这个枚举字段**根本不用传**——Kie 文档写明"不传就按有没有给 image_urls 自动判断"，这正好绕开了一个我们自己架构上的真空档：`fixed_inputs` 只能存"这一行固定死的常量"，处理不了"根据另一个字段填没填动态决定值"这种情况；`enable_fallback` 文档写明已废弃，直接不传；`duration` 原来因为"不确定所以先不做"被砍掉了，这次证实其实是真实存在、完整有文档的字段（枚举 4/6/8，默认 8，不影响价格）。
  - 改完 schema、把 `veo-3-1-lite` 这一行的 DB 数据更新之后，通过我们自己的 `submit_kie_job`（不是走 Kie 自己网站）重新跑了一次真实端到端：估算 30 积分（Lite/720p）、Kie 真实结算也是 30 积分，完全对上；真下载了生成的视频确认是真实的 ~2.2MB mp4；参考图用完照样从 R2 删了；job 按用户要求设成了 `visibility=public`，会出现在 Explore。
  - **这次验证过程中 worker 进程又崩了一次**（还是同一个"Redis 断连"特征，这已经是这个 session 第三次现场撞见），进程重启后队列里等着的这条 job 自己被正常捡起来跑完，没有触发刚修好的幂等性 guard（这条 job 本来就没被重复执行，只是 worker 恰好在等待区间内重启），侧面确认了幂等性修复本身没有引入新问题。
  - Veo 3.1 Lite 现在是 `enabled: true`，正式上线。Fast/Quality 还是按之前的决定往后放，但 `fixed_inputs` 的命名规律现在已经被验证过两次（`veo3_fast`、`veo3_lite`），Quality 大概率也是同样规律，仍然会在启用前单独发一次真实调用确认，不会跳过这一步。
- **用户看了一眼刚上线的表单截图，立刻指出一个真实的可用性问题**："veo 3.1 的话这种输入方式客户会输入错误吧？"——`duration` 我做成了自由输入的数字框（技术上是对的，真实发的是数字，Kie 也能收），但 Kie 的 `duration` 其实只允许 `4`/`6`/`8` 三个值，自由输入框完全没拦住用户填 5、7、100 这种会被 Kie 拒绝的值，等真提交才报错，体验很差。跟 Grok 自己那个真正连续的 `duration`（1-15 秒）不是一回事，不该用同一种字段类型。**修法**：给 `KieInputField`（`lib/api.ts`）加了一个新的 `numeric: true` 标记——`select` 类型字段选中某个选项时，如果标了 `numeric`，就发真正的数字而不是选项本身的字符串。Veo 的 `duration` 现在跟 `aspect_ratio`/`resolution` 一样是三个胶囊按钮（4/6/8），根本没有能打字的地方，也就没有能填错的空间。真实浏览器点过一遍确认选中态和值都对。顺手还发现并修了 Explore 首页的一个小问题：视频类的 Kie job 之前跟图片类共用一个图标（只判断"是不是 Kie job"，没细分是图片还是视频），现在按 `capability === "image-to-video"` 区分显示视频图标还是图片图标，真实验证过两种类型在 Explore 列表里图标不一样了。
- **用户接着追问 Grok 那边（真正的连续时长 1-15 秒）是不是也有同样问题**：确实有——虽然那个字段本来就是 `type: "number"`（技术上发的是数字，没错），但也是自由输入框，一样能打出 999。先按"加 min/max、失焦时 clamp"修了一版，但用户直接给了 Kie 自己网站的真实截图反驳："这种连续的时间我感觉用滑块比较好，你可以参考 kie 的做法。只能滑动不能输入。这样合理"——这个判断是对的，clamp 只是事后纠正，滑块是从物理上就不可能滑出范围，两者不是一个量级的解决方案。**改法**：`KieInputField` 新增 `type: "slider"`（配 `min`/`max`/`step`），前端渲染成原生 `<input type="range">` + 一个只读的数值展示（不是输入框，用户没法打字），配色用项目已有的强调色 `--a3`（`accent-a3`）。Grok 的 `duration` 字段类型从 `number` 改成 `slider`。真实浏览器验证：拖到最右/按 End 键停在 15，拖到最左/按 Home 键停在 1，两头都对应正确的实时积分（`ceil(2.4×1)=3`、`ceil(2.4×15)=36`），全程没有任何能打字的地方。Veo 那边的 `duration`（离散的 4/6/8）保持用胶囊按钮（`select` + `numeric`），因为那不是连续区间，滑块反而不是最自然的交互——同一类问题（"文字描述范围但没真正限制"），根据字段本身是连续还是离散区间选了不同但对应的两种控件，不是照抄一种方案套所有字段。

**用户主动关停了本地跑着的前后端进程，说"我来启动"，然后带来两个新的产品建议**——先是"APP首页我想是能区分 Voices Images Videos 你觉得呢"，贴了老项目 Voices/Dialogue/Image 三个 tab 的截图当参考。分析后同意这个方向：现在 Explore 是所有类型混在一条列表里，随着 Kie 目录继续长（已经有 2 个图片类别 + 2 个视频类别），混着看只会越来越难逛，而且这个数据本来就有——`output_type`（audio/image/video）在 Kie 目录那边已经是一等字段，不需要新建模型。问清楚"现在做还是先记下来"后，用户选了"现在做"：

- **后端**：`GET /gallery` 新增 `output_type` 筛选参数——复用 `kie_categories.output_type`（ADR 0017），不是另建一套分类；TTS 的 `capability="tts"` 不是 Kie 类别，单独在查询里 case 成 `"audio"`。用一个真实脚本验证过：不筛选是 14 条，筛 audio/image/video 分别是 11/2/1，加起来正好 14，没有漏判的。
- **前端**：Explore 顶部加三个 tab（Voices/Images/Videos），每个 tab 独立维护自己的 `items`/是否已拉取过（切回去不重新请求），空状态的"去生成"按钮也跟着当前 tab 换文案和跳转路径（之前是写死跳 TTS 创建页）。
- 紧接着用户又追问一次，直接甩出老项目 Image tab 的真实截图（2 列网格、缩略图铺满、底部渐变遮罩上盖标题）："对于images的展示你有什么建议 这是老版的展示风格"——这个观察也是对的：Voices 那种"图标+标题"的横条对语音这种没有画面的内容合适，但图片类内容藏在一个占位图标后面完全体现不出"逛"的意义。**照着这个参考重做了 Images/Videos 两个 tab**：2 列网格，每格是真实缩略图（`object-cover` 撑满 `aspect-[4/5]` 格子），复用音频那边已经在用的 `assetBlobUrl()`（带鉴权 fetch 真实字节转 blob URL）去加载，不是走 next/image 远程优化（blob: URL 走不了那条路，加了个有意义的 eslint-disable 而不是无脑忽略警告）。Videos 格外加一个播放小图标浮层，点击切换静音内联播放（没有做单独的详情页/大图播放，这次没人要求）。
- **真实验证**：Images 两张图（一个女生在巴黎塞纳河边、一个机器人厨师煎饼）都正确加载、裁切、标题正确显示；Videos 唯一一条真实数据的格子里播放按钮浮层能点，但**视频本身的画面在这次用的浏览器自动化 tab 里始终没能真的解码出来**——查了 `<video>` 元素的 `readyState`，卡在 0（HAVE_NOTHING）不动；为了排除是不是我代码的问题，直接绕开 React、拿 JS 现造一个原生 `<video>` 元素指向同一个 blob URL 测试，结果一样卡住，同时另外验证了这个 blob 本身完全正常（`fetch` 出来是 2.2MB、`video/mp4`，size 和之前真实下载确认过的一致）——说明这是这个特定浏览器自动化会话本身解码/播放视频有限制，不是组件写错了；组件本身的 DOM 属性（`src`/`muted`/`playsinline`/`loop`）全部正确挂上了。这是继"文件上传只能传 session 主动共享的文件"之后，这个环境的第二个已知媒体相关限制，记进了 `frontend/web/README.md`。
- **图片网格上线后，用户反馈一个真实的桌面端布局问题**："不错，移动端的展示可以 网页端的很奇怪 2个图片就占了整屏宽度"——查了一下，这是整个 `(app)` 布局一直存在但之前没显形的缺口：这个 app 是移动端优先设计（底部导航、单列页面），但主内容区域从来没设过最大宽度，宽屏浏览器里所有页面其实一直是被拉伸满宽的，只是文字列表这样拉伸看不出问题，2 列图片网格一拉伸就变得非常离谱。顺手发现 `BottomNav` 组件自己早就用了正确的模式解决了这个问题（外层 `fixed` 满宽做背景条，内层 `mx-auto max-w-md` 收窄），只是这个约定从没被套到页面主内容上。**改法**：`app/(app)/layout.tsx` 把 `{children}` 套进同一个 `mx-auto max-w-md`，一处改动对 `(app)` 下所有页面生效，不是只修 Explore。真实验证过：桌面宽屏下整个 app 现在收窄成一个居中的手机宽度专栏、两侧是纯背景色，2 图网格恢复正常比例；顺带确认了 `SettingsDrawer`/`CreateSheet` 这两个 `fixed` 定位的浮层（抽屉、底部弹层）没受影响，还是从真实浏览器视口边缘展开，不是被收窄进那个专栏里——`fixed` 定位默认相对视口，一个没有 transform 的普通包裹 div 不会创建新的定位上下文，这条也是先想清楚原理再验证，没有蒙对。
- **这个"居中窄栏"方案立刻被用户否了**："不对啊，这样桌面端的客户就不用了吗？我觉得我们既要适应移动端也要适应桌面端啊。你研究一下。"——说得对，把手机宽度的内容原样搬到桌面中间、两边留白，不叫适配桌面，只是让桌面看起来像个卡住的手机。查了 `ADR 0005`：`frontend/web` 从设计上就是给所有浏览器用户用的正式产品页面（Android 才是专门的移动端原生方案），"移动端优先"的视觉设计只是每个页面沿用下来的默认写法，从来没被真正决定过是不是要支持桌面。这里有一个真实的设计分叉需要用户来定——桌面宽屏下底部导航栏怎么处理：换成侧边栏（更像传统桌面 web app，但要新写一套导航和布局切换逻辑），还是保留底部导航、只把主内容区域按断点变宽（改动小，但导航栏本身也要跟着主内容区域同步变宽，否则会出现"内容变宽了、导航栏还卡在窄栏里"的新的不对齐）。用户选了后者。**改法**：新建 `lib/layout.ts` 导出一个共享常量 `APP_CONTENT_WIDTH = "max-w-md md:max-w-2xl lg:max-w-4xl"`——手机宽度不变，桌面下真正变宽（不是照抄手机宽度再放大）；`(app)/layout.tsx` 的主内容区域和 `BottomNav` 自己的内层 row 都用这同一个常量，保证任何断点下导航栏和上面的内容都对得齐。Explore 的网格也跟着加断点（`grid-cols-2 md:grid-cols-3 lg:grid-cols-4`）——桌面变宽真正的意义是一次能看到更多缩略图，不是把 2 张图放大。真实在约 1920px 宽的浏览器里验证过：Images tab 现在是紧凑、比例正常的缩略图（网格四等分），不再是两张贴满全屏的巨图；底部导航三个图标的间距现在跟上面内容区域同宽，不再显得"导航栏比内容窄一圈"。手机端行为完全没动——所有改动都是叠加在已有默认 class 之上的 `md:`/`lg:` override，`md` 断点以下的东西一个字节都没改。留一个诚实的口子没做：TTS/Kie 生成表单这类单列页面现在也套在这个变宽的外壳里，但表单本身没有针对性地利用变宽的空间——外壳变宽不代表每个页面内容都该跟着拉宽，尤其是表单，之后如果哪个页面看起来"空落落的"再单独处理，不是现在就统一拉伸。

**用户对着一张真实的 Kie 图片生成页截图（卡在"Generating…"）提出一个大的体验问题**："这个等待的设计不好，因为像图片视频一般要等很久。既然我们都是异步的，我觉得所有的都要立即反馈然后再如何处理，你先不急着实现，我们讨论一下这个处理流程。"——这个判断是对的，而且点出了一个一直存在的真实矛盾：ADR 0014 早就把后端做成真异步（提交立刻 `202 pending`），但每个创建页面自己还是在同一屏 `pollJob()` 死等，TTS 因为几秒钟就完事所以感觉不出来，Kie 图片/视频动辄几十秒到几分钟，这个"假异步"的体验缺口才真正暴露出来。用户主动要求先讨论流程、别急着写代码：

- 提了一个三段式设计（提交那一刻的即时反馈 → "进行中"去哪看 → 用户不主动看时怎么知道），用户确认"可以"。
- 接着追问一个更深的架构问题："是不是上websocket/SSE一劳永逸，也更适合后续android的部分？"——如实答了这不是真的"一劳永逸"：SSE/WS 解决的是"app 开着、人在逛别的页面"这一种场景，两件事它解决不了——① 不能替代 `GET /jobs` 的首次拉取，只负责"有变化就推一下"；② app 被完全关掉（不是后台，是真的没在跑）依然收不到，那是 FCM/APNs 推送的范畴，跟 web 端选 SSE 还是轮询是两码事。但"建一次、Android 能复用同一个接口"这个判断是对的，加上 Redis 本来就已经在用（给 arq），用它的 pub/sub 桥接"worker 进程完成任务"和"API 进程推给客户端"这一跳，不算新基础设施。用户听完确认："可以"，进入实现。

**实现（ADR 0018）**：
- **后端**：`services/jobs.py` 新增 `publish_job_event()`，在所有真正写终态的地方调用——`_complete_success`（TTS）、`_complete_kie_success`（Kie）、`_complete_failure`（TTS/克隆/Kie 三条失败路径共用的那一个函数，一次接入全覆盖）、`execute_voice_model_training_job` 自己内联的成功分支、以及 `worker/cron.py sweep_stuck_jobs` 超时兜底路径（这条没走 `_complete_failure`，是独立内联写终态，单独补了一处）。新增 `GET /events`（`api/routes_events.py`），SSE 而不是 WebSocket——这个通道天生只需要单向（服务端告诉客户端"job X 完成了"），SSE 用一个普通 HTTP 响应就够，`EventSource` 自带断线重连，没必要上更重的双工协议。鉴权是这个接口的真实特例：浏览器原生 `EventSource` 没法带自定义 header，token 只能走 query 参数；专门写了一个短生命周期的 DB session 解析这个 token（在 SSE 真正的长连接生成器开始跑之前就 commit+关闭），没有用 `Depends(get_db)`，否则那个 session 会跟着 SSE 连接一起活好几分钟到几小时，白占一个连接池名额。
- **前端**：新建 `lib/job-events.tsx`（`JobEventsProvider`，包在 `(app)/layout.tsx` 里，跟着整个 app session 活，不跟着某个创建页面）——维护 `pendingCount`（首次从真实 `GET /jobs` 数出 pending/processing 有几个，之后靠提交时 `registerPendingJob()` 和收到事件时自动增减）和 `lastEvent`（最近一次收到的事件，页面可以 `useEffect` 监听它去局部刷新）。**没有依赖 `EventSource` 自己的断线重连**——那会重新打开同一个 URL，包括连接那一刻快照下来的 token，一小时后过期了也只会一直重连失败；改成 `onerror` 时手动关掉、重新拿一个新 token 再连。新建 `components/Toast.tsx`（这个项目第一次需要 toast，没有库，自己写的最小实现）。四个创建页面（TTS、克隆的 Generate/Clone 两个 tab、Kie 通用生成页）全部去掉 `pollJob()` 阻塞，提交成功就弹 toast、表单立刻可用（不清空，方便改改参数再提一次）。`/app/me` 大改：每条历史记录现在是真的"活的"——pending/processing 显示转圈、failed 显示真实错误文案、succeeded 显示真正的结果（音频播放器/图片/视频，复用 Explore 那套 `assetBlobUrl()` 机制），收到 `lastEvent` 时只对那一条 `GET /jobs/{id}` 局部刷新，不整页重拉。`BottomNav` 的"Me"图标上加了个小红点数字，逛到别的页面也能看到"还有几个在跑"。voice clone 训练那条本来想保留原地等待（Fish Audio fast-mode 训练本来就接近瞬时，`backend/README.md` 验证过），但为了跟其他能力体验统一，也一起改成了提交即走，页面自己再监听 `lastEvent` 里 `capability === "voice_model_training"` 的事件去刷新克隆声音列表——训练完不用离开页面就能看到新声音。
- **真实端到端验证**：真实浏览器里提交了一条 Azure TTS job，亲眼看着底部导航的红点从 1 变 2（提交那一刻）、真实 worker 进程捡起并跑完、红点从 2 掉回 1（SSE 事件到达的那一刻，没刷新页面）、`/app/me` 里那一条卡片从转圈直接原地翻牌成一个真正能播放的 `<audio controls>`。中途抓到一个真实的自己的测试失误：选声音弹窗点击"看起来选中了"但其实没真的选上，导致头两次点"Generate"其实根本没发出请求——一开始差点以为是新写的提交逻辑本身有 bug，用 `read_network_requests` 一查发现根本没有 `/generate/tts` 请求打出去，才确认是我自己点选声音那一步没点准，不是代码问题——教训是可交互元素"看起来选中了"不代表真的选中了，结果反常时先查真实网络请求，不要只信截图。
- **顺带撞见的两次真实 worker 崩溃**（还是那个"arq 扛不住 Redis 断连"的已知特征），跟这次功能验证无关，纯粹又撞上了两回，进一步证实这是这套环境里 Upstash 连接会反复出现的真实特征，不是偶发一次——每次都是重启 worker、已入队的任务原样捡回来继续跑，跟之前记录的行为完全一致。
- ADR 0018 里诚实记了两个没做的口子：多个标签页各自维护自己的 `pendingCount`，互相不同步；一个真正被彻底关掉（不是切后台）的 app 现在还是收不到任何通知，这需要 FCM/APNs 这套完全独立的推送基础设施，明确不在这次范围内。

**`/app/me` 上线没多久，用户在自己真实账号（31 条真实历史记录，不是开发时随便造的几条测试数据）上发现两个问题**："这个部分有个问题 数据一多 就很慢啊；另外是不是加个标签 All Voices Images Videos 这样比较好呢"——两个都对：
- **性能**：`JobMedia` 原来是每条历史记录一挂载就立刻 `assetBlobUrl()` 拉真实字节（跟 Explore 网格当初的取舍一样），条数少的时候看不出问题，31 条一起拉就是 31 个并发带鉴权的请求，真的卡。**改法**：加 `IntersectionObserver`（`rootMargin: "400px"`，提前一点点开始拉，滚动到的时候基本不用等），只有卡片真的快滚到视口附近才触发请求。真实验证：31 条历史里只有 7 条在首屏触发了请求，其余的完全没碰，滚下去才会各自触发。
- **分类**：照 Explore 那套 All/Voices/Images/Videos 的 tab 模式搬过来，按 `capability` 客户端本地过滤（`GET /jobs` 本来就是一次性把这个用户自己的全部历史拉回来，不像 Explore 那个公开、跨用户、真分页的画廊，不需要为这个单独开一个带筛选参数的接口）。语音克隆的"训练"记录本身没有可播放的媒体，但也归到"Voices"标签下——这是这类记录唯一会出现的地方，不能没有归属。

**`(marketing)` 展示页做完了（ADR 0019），触发原因是一个具体的外部需求：申请 Payoneer 收款账号要求提供一个真实展示信息的商业网站**。这块之前一直是 `product-scope.md` §3 留的空项。这次没有照抄老项目 `voicica-ai` 的 `(home)` 展示页内容——老项目还覆盖 Facebook/Instagram/TikTok/X/YouTube 下载器和通用图片工具这些完全不在这次重构范围内的能力，语言也是 en/zh-CN/zh-TW/ja/ko，跟这次目标市场泰语/印尼语/西语不重合——只抄了"怎么做 locale 前缀 URL + hreflang"这套机制，文案整个重写。

- **页面范围**：7 个页面——`/`（首页）、`/voice`（TTS + 语音克隆）、`/image`（Kie 文生图/图生图）、`/video`（Kie 图生视频）、`/privacy`、`/terms`、`/contact`。没做定价页（`product-scope.md` §2 还没有真实数字）、没做音乐页（还没有对应 Kie 目录）——跟这个项目一贯的原则一样，等有真实内容再加页面。
- **首页的"Made with Voicica"横条是真实数据，但刻意只显示文字不放媒体**：`GET /gallery` 本来就是未登录可访问的（ADR 0010），拉真实标题/供应商/日期上首页是诚实且免费的；但真正的音频/图片/视频字节要走 `GET /jobs/{id}/asset`，这个接口的鉴权边界是"任何登录用户"（Explore 页收窄的结果），不是"任何人"——为了一个展示页顺手把这个边界继续放宽到完全匿名，不该是这个 ADR 里的一个副作用，所以先只上文字（标题/供应商/日期），不放缩略图/播放。
- **i18n：只搭架子，不造假翻译**。ADR 0013 早定了 `(marketing)` 用 locale 前缀 URL，这次补上"英文本身用什么 URL"——照抄老项目的约定，英文是不带前缀的默认（`/voice` 不是 `/en/voice`），以后泰语/印尼语/西语会是 `/th/...`、`/id/...`、`/es/...`。**这轮只上英文**，`/th`、`/id`、`/es` 没有注册路由——不是建好放空、也不是先塞机器翻译占位，是真的没有对应页面，访问直接 404。理由：机器翻译的泰语页面对用户体验和 SEO 排名都是负分，不如没有。但可复用的架子先搭好，以后加语言是"加一个内容文件"不是"重写路由"：文案全部收在 `content/marketing/en.ts`（照 `content/marketing/types.ts` 的类型），不是散落在 JSX 里；`lib/marketing-seo.ts` 的 canonical/hreflang 构造函数遍历一个 `MARKETING_LOCALES` 注册表（现在只有 `en`）而不是硬编码英文。
- **`/privacy`、`/terms` 是真实能用的第一版，不是"Coming soon"占位**——内容对应产品真实做的事情（Firebase 认证、积分、真实用到的第三方处理方（Azure/Google/Fish Audio/Kie）、R2 存储、目前没有接支付）。页面上没有说"仅供参考"这种弱化措辞，但也没说这是律师审过的版本——`/contact` 的真实姓名/邮箱/地址是专门为了满足 Payoneer 网站验证的"至少两项可核实信息"这条要求特意放出来的，验证通过后计划把地址收回去，这次 ADR 没有自动做这一步，是手动的后续。
- **首页横条的没做完事项**：不做缩略图/播放；没做 `/th`、`/id`、`/es` 真正的路由段（内容没有，先不建路由，避免建了个测不出东西对不对的空壳）。
- **真实验证过**（`next build` 生产构建先跑通、7 个页面全部正确生成为静态页 + `/sitemap.xml`/`/robots.txt`；然后真实浏览器逐页打开）：首页 hero/能力卡片/CTA/页脚渲染正确，"Made with Voicece" 横条真实显示 6 条数据（azure/kie/fish_audio 供应商、真实标题、真实日期），`read_network_requests` 确认真的是 `GET http://localhost:8000/gallery` 返回 200，不是假数据；`/voice`/`/image`/`/video` 三个能力页文案各自独立、不是复制粘贴换个标题；`/privacy`/`/terms` 内容完整；`/contact` 显示的姓名/邮箱/地址跟 Payoneer 要核对的信息一致；`/sitemap.xml` 包含全部 7 页且带 `hreflang` alternates，`/robots.txt` 正确 disallow `/app`；`curl /th`、`/th/voice` 确认真的是 404，不是空页面；全程浏览器 console 没有报错。

**Admin 不另起项目了，合进 `frontend/web`（ADR 0020）——用户主动提出的**："我们讨论一下 admin不另外起一套 就直接也放在web下面一起管理如何"。这正好是 [ADR 0005](docs/decisions/0005-frontend-surfaces.md) 里明确讨论过、也明确否掉过的一个选项（"Fold admin routes into the authenticated web app behind a role check. Rejected: ... The security boundary should be physical, not just logical."），所以先把这个张力摆出来讨论，而不是顺手就改：

- **原决定的理由是真实的，不是空泛的安全教条**：Next.js App Router 的 middleware 只拦路由请求，不拦 `_next/static/*` 这些编译后的静态 JS chunk——就算页面被 middleware/客户端角色门禁挡住重定向了，admin 路由编译出来的 JS 文件本身还是公开静态资源，理论上一个知道怎么翻 build manifest 的人不需要登录就能把 admin 面板的前端代码整个下载下来看。合并之后这个泄露面是真实存在的。
- **但真正保护数据的墙一直在后端，不在前端**——`require_admin` 早就在 API 层做了角色校验，不管前端结构怎么变，没有真实 admin 角色的 token 就是拿不到数据、改不了任何东西。合并后真正暴露的只是"这个产品有一个后台、长什么样"这个事实，不是数据本身。
- **推翻的理由是成本，不是否认原来的风险**：`frontend/admin` 从 ADR 0005 写下那天起就是空的（只有一个 `.gitkeep`），到真正要写第一个 admin screen 的这一刻还是零沉没成本，这时候要求先搭一整套独立 Next.js 项目（独立仓库位置、独立部署、独立鉴权接线、重新抄一遍设计系统）对一个人维护的早期项目是真实的速度成本。
- 用户同意后，写了 [ADR 0020](docs/decisions/0020-admin-folded-into-web.md) 记这个反转（不是偷偷改），并在 ADR 0005 自己身上补了删除线 + 指回 0020 的注释，`docs/`（architecture/product-scope/api-contract/data-model）、`README.md`、`backend/README.md`、`routes_admin.py` 的模块 docstring 里所有提到 `frontend/admin` 的地方都同步改了，`frontend/admin/` 目录本身删掉了。
- **实现**：`(admin)` 路由组挂在 `app/(admin)/admin/` 下（跟 `(app)/app/` 一个道理，route group 本身不进 URL，得再套一层真实的 `admin/` 目录）。`(admin)/layout.tsx` 做角色门禁——等 Firebase auth 状态、再调 `GET /me` 查 `role`（Postgres 列，不是 Firebase custom claim，这也是为什么门禁必须是一次真实的 API 调用，不能只看 ID token），不是 staff/admin 直接弹回 `/app`；未登录弹去 `/login`。这是 ADR 0020 自己承认的"地板"，不等价于物理隔离——真正的防线还是后端的 `require_admin`。**边缘层加固**（Cloudflare Access 挡住 `/admin/*` 的静态资源泄露面）记成了 ADR 里的推荐后续，这次没做。
- 顺手补了一个真实的小 gap：`GET /admin/jobs` 之前直接复用给普通用户用的 `JobResponse`，那个 schema 故意不带 `user_id`（普通用户只看自己的 job，不需要）——但一个横跨全部用户的 admin 监控页没有 `user_id` 根本没法用。加了 `AdminJobResponse(JobResponse)` 多一个 `user_id` 字段，只有 `/admin/jobs` 这一个接口用。
- 第一个真实可用的 screen：Job monitor（`/admin/jobs`，最近 100 条跨用户 job，按状态上色）。Dashboard 首页（`/admin`）老实列出其余几个（用户积分、菜单、Kie 目录、settings）——后端接口全都是现成的全套 CRUD，只是这次没做 UI，卡片上直接写清楚"没有界面，直接调 API"，不假装做完了。
- **真实验证过，包括两条路径都测了**：用已有的浏览器测试账号（`claude-web-test@voicica.app`）——没有真实密码没法走登录表单，用后端本来就有的 Firebase Admin SDK 现场签发一个 custom token，建了一个临时的 `/dev-signin?token=` 页面登录进去（验证完立刻删掉，没提交）。先把这个账号的 `role` 改成 `staff`：真实浏览器里 `/admin` 显示 dashboard、`/admin/jobs` 显示真实跨用户数据（这个测试账号自己的 job + `e2e-test-user-1` 的历史 job，状态颜色、成本、可见性全部对得上）。再把 `role` 改回 `user`：同一个浏览器 session 重新访问 `/admin`，真实被弹回了 `/app`，确认角色门禁生效。测完把账号 `role` 改回 `staff`（作为长期的管理员测试账号留着），没有碰真实用户 `bensting19@gmail.com` 的账号。

**专用落地页 `/get` 做完并端到端验证过了（ADR 0021），用户主动提出的**："marketing这块我还需要1个落地页也就是后续所有流量都是导到这个落地页"，给了真实的安卓 Play Store 链接（`ai.voicica.app`）和官网域名（`voicica.ai`，中途打错成 vocica.ai，确认过是笔误，跟 app 包名保持一致）。

- **先讨论清楚范围再动手**：问用户是强化现有首页 `/` 还是另建专用页面，用户选了"另建"，理由是**"流量来源未来比较多，也是需要便于统计"**——这个理由直接决定了设计方向：既然要统计，就该是"一个页面 + UTM 参数分渠道"，不是"每个渠道一个页面"（后者以后渠道一多，要维护 N 份雷同页面）；既然是纯转化页，就该去掉一切不是"下载 App"或"网页端开始使用"的出口——不进 `(marketing)` 的 layout（那个 layout 的 header/footer 全是指向 `/voice` `/image` `/video` 的链接，正好是这个页面不该有的），连 logo 都做成不可点击的。
- **分析工具也是现场问清楚的**：项目里之前压根没接任何分析工具，问了用 GA4/Vercel Analytics/PostHog 还是先不接，用户选 GA4。查代码时发现一个真实的惊喜：`.env.local.example` 里早就躺着一行注释掉的 `NEXT_PUBLIC_FIREBASE_MEASUREMENT_ID=G-RWBX15PP30`（老项目 Firebase 项目自带的，之前写"这个 slice 没用上"就没管它）——Firebase Analytics 本质上就是 GA4（同一个 Measurement ID，同一套 Google Analytics 报表），直接复用这个现成的，不用求用户再去 Google Analytics 控制台建一个新的。接上之后真实验证时还有意外收获：网络请求里看到这个 GA4 属性早就关联了一个真实的 Google Ads 账号（`AW-11504012045`）——说明老项目当年这块基建搭得比想象中完整，复用是对的选择。
- **安卓状态也现场确认了**：之前 CLAUDE.md 一直记着"Android 还没开始做"（这个 v2 项目自己的 `android/` 目录确实只有个 `.gitkeep`，这条没错），但用户这次给的是一个真实、可访问的 Play Store 链接，还确认"正式版，功能完整"。**这两件事不矛盾，值得说清楚**：Play Store 上线的那个 App 大概率是老项目自己的原生 App 版本（老项目 CLAUDE.md 提过"双版本管理机制：Web 版本 / 原生 App 版本"）在继续运营，不是这个 v2 重构自己那个"从零原生 Kotlin/Compose 重写"的产物——落地页该链的是"用户现在真能装到的那个 App"，跟这个链接背后是哪个代码库无关，但记录里不能把两件事混成一件事。
- **设计要点**：`app/get/`——自己的 `layout.tsx`（不复用 `(marketing)` 的），`page.tsx` 是服务端组件，直接读请求的 `User-Agent`（`next/headers`）判断安卓与否，首屏就选对主 CTA（安卓设备主按钮是"Get it on Google Play"官方徽章图——从老项目 `public/images/stores/google-play-badge.svg` 搬过来的真官方 SVG，不是自己画的近似款；非安卓主按钮是"Get started free"），不是客户端判断完再切换、会有一闪而过的错误按钮。真实作品墙（`GalleryStrip`）复用，继续证明"不是 demo 图"这个差异化优势。`robots: {index:false}`——这是给广告流量用的页面，跟首页卖点重复，不该跟首页抢自然搜索排名，但没有在 `robots.txt` 里 disallow（广告平台自己的审核爬虫还是要能正常抓到这个页面）。
- **`lib/firebase.ts` 新增 `getFirebaseAnalytics()`**：浏览器不支持（`isSupported()`，排除掉一些没有 IndexedDB 的内嵌浏览器）或没配 Measurement ID 时返回 `null`，绝不抛错——统计工具挂了不能连带把它要统计的页面搞挂。`components/Analytics.tsx` 在 `(marketing)` 和 `/get` 两个 layout 里挂载（不进登录后的 app/admin，那边不需要广告分析），SPA 路由切换手动补 `page_view`（Next.js 客户端跳转本来就不会触发真实的整页加载，不能指望 `gtag.js` 那套经典多页站点的自动机制），另外给两个转化按钮各埋了一个 `select_content` 事件，fire-and-forget、不 await——统计调用慢不能拖累真正的跳转。
- **真实端到端验证**：`curl` 分别带桌面和安卓 UA 直接请求 `/get`，服务端渲染出的按钮文案确实不同（桌面："Get started free" 是主按钮；安卓：主按钮是 Play 徽章、次要是"continue on the web"）——这是纯服务端逻辑，不需要真机也能验证对不对。真实浏览器里点"Get started free"，`read_network_requests` 里能看到真实打到 `analytics.google.com/g/collect` 的请求，`tid=G-RWBX15PP30`、`en=page_view` 和 `en=select_content&ep.item_id=get_started_web` 都对得上；作品墙、能力卡片、footer 只剩 Privacy/Terms（没有其他站内链接）都截图确认过。中途一个小插曲：自动化点击工具第一次点在按钮上没反应（后来才反应过来可能是坐标/时机问题，不是代码 bug），换成直接 `document.querySelector('a[href="/login"]').click()` 才复现——教训跟之前记过的一样：点了没反应先查真实状态（这次是 `window.location.pathname`），别急着怀疑自己代码。

**`/app` 移动端底部导航栏"看不到"的问题，用户截图反馈的，查出两个真实的、独立的 bug**——排查时先想复现，`resize_window` 这个工具在这个环境里没生效（改了窗口尺寸，`window.innerWidth` 还是桌面的 1920，可能是窗口被 Windows 固定/最大化导致自动化改不动），改用往当前 tab 里插一个 390×844 的 `<iframe>` 指向 `/app`（同源，能共享登录态）来真正拿到一个窄视口做验证——这个办法以后遇到类似"这个工具改不了窗口大小"的情况可以复用。

- **真 bug 1**：`env(safe-area-inset-bottom, 0px)`——`components/BottomNav.tsx` 早就写了这行给 `<nav>` 加底部安全区 padding，但**根本没生效过**：Safari/Chromium 只有在页面的 viewport meta 显式声明 `viewport-fit=cover` 时才会把 `env(safe-area-inset-*)` 汇报成非零值，没有这个声明的话永远是 0。`app/layout.tsx` 从来没有导出过 `viewport`（Next.js 默认只给 `width=device-width, initial-scale=1`），所以这个 padding 从写下来那天起就是个空调用。后果：在真实有 Home Indicator 手势条的手机上（iPhone X 以后全系），底部导航栏的图标/文字会紧贴屏幕最下边缘，跟手势条挤在一起甚至被系统手势区遮住一部分——这跟用户说的"看不到"对得上。**顺带发现同一个坑在 `components/Toast.tsx` 里也踩过一次**（`env(safe-area-inset-top)`，ADR 0018 那轮加的），当时也是同样没生效，只是顶部通知不像底部导航那样天天盯着看，没被注意到。**修法**：`app/layout.tsx` 新增 `export const viewport: Viewport = { width: "device-width", initialScale: 1, viewportFit: "cover" }`——一处改动，两个组件的 safe-area padding 同时修复，不用分别改。
- **真 bug 2**：`(app)/layout.tsx` 最外层用的是 `min-h-screen`（`100vh`）。移动端浏览器（尤其是地址栏会随滚动收起/展开的那种，绝大多数手机浏览器都是）的 `100vh` 是按"地址栏完全收起"的最大高度算的——地址栏还显示着的时候（比如刚打开页面那一刻），真实可视区域比 `100vh` 矮一截，`BottomNav` 的 `fixed bottom-0` 有可能被定位到这个"假设地址栏已收起"的高度上，实际上落在了当前真正可见区域的下面，要么看不见要么要滚动才能看到。**修法**：`min-h-screen` 改成 `min-h-dvh`（动态视口高度单位，专门为解决这个问题引入的，Tailwind v4 原生支持，不用额外配置），跟随真实的可视视口，不跟着地址栏收起前的假设值走。
- **诚实说一句验证边界在哪**：这两个修复都是这类问题公认的标准解法，改完真实构建过、`curl` 确认 `<meta name="viewport">` 里确实带上了 `viewport-fit=cover`、iframe 窄视口下页面布局没有回归——但这个环境（桌面 Chrome，不管是缩放窗口还是套 iframe）**物理上不存在手势条/地址栏这些东西**，`env(safe-area-inset-bottom)` 在这里测出来必然还是 0，没法在这个环境里让"修复前 vs 修复后"跑出肉眼可见的差异。真正的视觉验证需要一台真实的、带 Home Indicator 的手机（或者 Chrome DevTools 的设备模拟器，这个环境目前没有暴露那个能力），这一步留给用户自己在真机上确认。

**前端首次真实发布到 Cloudflare（ADR 0022），用户主动提出的**——为了给支付网关申请用真实的 `/contact` 页面，需要 `voicica.ai` 上有个真实网站。中途先撞上一次真实的、我这边的操作失误，如实记一笔：给用户看完 `/app` 移动端底部导航的修复方案后，我把本地起来验证用的后端进程关掉了，结果用户接着自己测试时发现"/app 和 /app/me 看不到任何数据了"——查了一下就是我忘记把后端重新启动，不是代码 bug。**教训**：以后凡是为了验证起的本地服务，只要用户后续可能还要接着自己用，验证完就该主动重启/保持着，不能默认"验证完就可以随手关掉"。

- **先确认现状**：`wrangler whoami` 发现这台机器上有过登录记录（token 过期了）——说明老项目当年就是从这台机器部署的。翻老项目的 `wrangler.jsonc` 发现它是走 **OpenNext + Cloudflare Workers**（不是 Cloudflare Pages），Worker 叫 `voicica`，还挂着老项目专属的 D1/Queue 绑定。用户发来 Cloudflare 后台截图确认：`voicica.ai` 和 `www.voicica.ai` 这两个自定义域名就是直接绑定在这个叫 `voicica` 的 Worker 上（Triggers 页面看到的）。这个发现很关键：**只要新项目部署用同一个 Worker 名字，域名绑定会原封不动继承过来，不用碰 DNS/自定义域名这一步**，直接覆盖同一个 Worker 的代码就行。
- **有意不copy老项目的 D1/Queue 绑定**——v2 前端就是个纯 API 消费者（ADR 0005），不需要任何 Cloudflare 绑定，`wrangler.jsonc` 干净地只声明了 `name`/`main`/`assets`。
- **技术选型上先查了一圈再动手，不是凭记忆**：`WebSearch` 确认 `@opennextjs/cloudflare` 官方明确支持 Next.js 16.3.x（项目正好用的 16.3.4），比老的 `@cloudflare/next-on-pages` 更被 Cloudflare 官方推荐；还搜到一篇真实踩坑记录（Next 16 部署到 Cloudflare Workers 会遇到的三个问题：peer dependency 版本、`wrangler types` 类型冲突、部署后短暂 404），提前心里有数。`next.config.ts` 加了 `images: { unoptimized: true }`——Next 默认的图片优化器在 Workers 上没有对应的运行时，这轮用到的图全是本地小资源（logo、Play 徽章），不值得为这个再引入复杂度。
- **范围收窄到只发布 marketing 部分**：后端还没部署到公网（本地跑着而已），登录后的 `/app`/`/admin` 这次发布上去也用不了——用户明确说了"后端稍晚再部署，前端先部署，我主要要用 contact 页面来申请支付网关"，所以这次的目标就是让 `/`、`/voice`、`/image`、`/video`、`/privacy`、`/terms`、`/contact`、`/get` 这些不依赖后端（或者依赖了但有优雅降级，比如首页作品墙拿不到数据就显示空状态不会整页报错）的页面先真实上线。`NEXT_PUBLIC_API_BASE_URL` 先填了一个没验证过的猜测值 `https://api.voicica.ai`（照抄老项目 `vp.voicica.ai` 这个子域名命名习惯），在 `.env.production` 里明确写了"这是猜的，后端真的部署后要改这里再重新发布"，没有含糊过去。
- **`.env.production` 直接提交进仓库**——里面全是本来就该公开的 `NEXT_PUBLIC_*` 值（Firebase web config 本来就设计成公开的，域名、GA 测量 ID 也都不是密钥），不是敏感信息。顺带又修了一次 `frontend/web/.gitignore`（这是这个仓库里第二次撞上"`.env*` 这条规则太宽，把本该提交的文件也吃掉了"——第一次是 `.env.local.example`，这次是 `.env.production`，都加了对应的例外规则）。
- **真部署前先在真实 Workers 运行时验证过，不是只跑 `next build` 看着编译通过就当过了**：`opennextjs-cloudflare build` 之后跑 `opennextjs-cloudflare preview`（这个命令是真的把编译出来的 Worker 丢进本地 `wrangler dev` 里跑，跟 Cloudflare 线上跑的是同一套 workerd 运行时，不是 Next 自己的开发服务器）——`curl` 验证了 `/`、`/contact`（真实姓名/地址/邮箱都在）、`/get`、`/privacy` 全部 200，`/get` 的服务端设备判断（安卓 UA vs 桌面 UA 走不同主 CTA）在这套运行时下依然正确，`/robots.txt`/`/sitemap.xml` 也正确读到了生产环境的 `voicica.ai` 域名。这一步是为了在真碰线上域名之前，先排除掉"本地 Node 环境能跑但 Workers 运行时跑不动"这类真实存在的兼容性坑（Windows 上跑 OpenNext 官方自己都提示"不完全兼容，建议 WSL"，多一层本地验证更值得）。

**实际部署上线，撞上两个真实的、跟这台机器有关的坑，都记进 ADR 0022 了**：

- **`wrangler login` 第一次卡在 OAuth CSRF 报错**（`request_forbidden`：token 里的 CSRF 值跟本地存的对不上）——排查发现是老项目当年登录留下的一个几个月前的过期 token 文件（`%APPDATA%\xdg.config\.wrangler\config\default.toml`）在跟这次新的登录流程打架。挪开这个文件重新 `wrangler login` 就干净了，用户自己在独立的 PowerShell 窗口里操作的（不是这边工具能完成的交互式 OAuth，浏览器授权那一步必须是用户自己点）。
- **第一次 `npm run deploy` 直接失败在 build 这一步**：`EPERM: Permission denied` 删不掉 `.open-next` 目录——原因是之前跑过的 `opennextjs-cloudflare preview` 留下的 `wrangler dev`/`workerd` 进程还占着文件锁，虽然当时以为已经用 `Stop-Process` 关掉了，但关的是外层那个 PID，底下真正的 `node`/`workerd` 子进程活得好好的。用 `Get-Process` 揪出所有真正在跑的 `node`/`workerd` 进程全部杀掉，再删目录，重新 `npm run deploy` 才成功。
- **真实上线验证**：`curl` 和真实浏览器都确认了 `https://voicica.ai/`、`https://www.voicica.ai/`、`https://voicica.ai/contact` 全部 200，`/contact` 显示真实姓名/邮箱/地址（申请支付网关要用的那个），首页作品墙因为后端还没公网可达，正确降级成空状态、没有报错或者布局错乱，浏览器 console 全程干净。域名绑定完全没碰，只是把同名 Worker 的代码换了一版，`voicica.ai` 立刻生效。

**后端也真的部署上线了（ADR 0023），前后端完整链路第一次真正打通**——用户问"后端的部署有什么想法"开始的。先查了 Render/Railway/Fly.io 三家 2026 年真实的区域覆盖和定价（不是凭旧印象），推荐 Render，理由是它的 "Background Worker" 服务类型正好对应 `worker/run_all.py` 这个早就写好的"一个进程跑完所有 worker"设计，不用改代码。中途 Render 官网的定价页面差点让人误判——首屏只显示 Hobby/Pro/Scale/Enterprise 这几个"工作区套餐"，用户截图问"没有你说的 $7 啊"，往下滑才找到真正按次计算的 Compute 价格表（Free/$7/$25 三档，Web services 和 Background workers 共用同一张表）——教训是官网首屏展示的价格维度不一定是实际计费维度，得翻到底。

- **区域问题，用户主动提的"以后统一放新加坡"，差点忽略了一个真实冲突**：查了本地 `.env` 才发现 Neon 数据库其实在 `us-east-2`（美东），如果 Render 选新加坡、数据库还在美国，反而比两边都选同一个区域更慢（计算离用户近了但离数据库远了，两头都占不到好处）。摆出这个真实冲突给用户看，用户选了"新建一个新加坡的 Neon 项目，老库直接弃用，不迁移数据"——原话"数据不要紧，这个是个人项目，后续就是一套不要分，否则我们维护不过来"，Upstash Redis 确认本来就在新加坡，不用动。
- **从空库跑全部 migration，第一次真正跑通整条链条，也第一次挖出一个真实的 migration bug**：`0009_kie_catalog.py` 从 `app/services/kie_catalog.py` 实时导入 `_SEED_CATEGORIES`/`_SEED_MODELS` 这两个常量，没有像后来的 `0010`/`0011` 那样过滤"只要自己负责的那部分"——老库因为是"边写 migration 边跑"，常量当时还小，从来没暴露过；这次一次性从空库跑完整链条，常量已经是最终形态（包含后面 ADR 加的 image-to-image/image-to-video），`0009` 把全部数据都插了，`0010` 再插同一条直接主键冲突。修法是给 `0009` 也加上跟 `0010`/`0011` 一样的过滤逻辑。顺带发现 Postgres 事务的一个好处：失败时把 `0001`-`0009` 全部干净回滚了，不用手动清理中间状态，直接改完重跑一遍就是全新的、正确的结果（3 个类别、10 个模型，验证过没有重复）。
- **真实部署撞上的两个环境变量坑，都是"复制 .env 图省事"引出来的**：用户直接把本地 `.env` 整份复制进 Render，其中 `CORS_ALLOW_ORIGINS=["http://localhost:3000"]` 也原样带过去了——真实 `curl` 模拟从 `voicica.ai` 发请求，直接验证出"Disallowed CORS origin"。这个坑倒逼把"哪些变量线上必须跟本地不一样"这件事第一次真正写进文档（`.env.example` 注释 + `backend/README.md` 新增 Deploy 一节），不再是"整份复制"这种容易出错的方式。`PUBLIC_BASE_URL` 是同一类问题的反方向（本地留空是对的，线上要填真实地址）。
- **GitHub 的 secret scanning 报警，两轮来回，最后做了一个比我最初方案更好的决定**：GitHub 检测到 `frontend/web/.env.local.example` 里的真实 Firebase web API key，标成"Publicly leaked secret"。我一开始的判断是"这个 key 本来就设计成公开的，不用管"——这个技术判断本身没错（Firebase 官方就是这么设计的：安全靠规则和授权域名，不靠藏这个 key），但用户连续两次指出更根本的问题：先是"example 文件不应该有具体值"（改成占位符，跟 `backend/.env.example` 的惯例统一），然后是"`.env.production` 也不应该提交"——这个更进一步，直接否掉了 ADR 0022 里"这个文件没有真正的密钥、可以提交"这个我自己的判断。想清楚后确实用户是对的：**逐个判断"这个值到底算不算敏感"本身就是一种脆弱的做法，一次判断错就是真事故；"所有 .env 文件一律不提交"这种一刀切的规则不需要判断，从根上把这类问题清零**。改法是 `.env.production` 改名成 `.env.production.local`（Next.js 原生支持这个后缀、效果完全一样，但按约定永远不提交），`.gitignore` 撤销了之前专门开的例外规则。没有去重写 git 历史清除旧提交里的那个值——这个操作影响面太大（所有 commit hash 变、需要强推），对一个"设计上就不是密钥"的值不值得做这么大的手术。
- **最后端到端跑通，不是只看 200 就算数**：把前端的 `NEXT_PUBLIC_API_BASE_URL` 换成真实的 Render 地址、重新发布，真实浏览器打开 `voicica.ai` 首页，`read_network_requests` 确认真的发出了 `GET https://voicica-api.onrender.com/gallery` 并返回 200，页面显示"Nothing public yet — be the first."——这句话本身就是证据：如果请求打到的是老的、有真实历史数据的美东库，或者是缓存的旧结果，不会显示这句话；显示这个说明真的连到了刚建的、干净的新加坡库。至此 `voicica.ai`（Cloudflare 新加坡）→ CORS → `voicica-api.onrender.com`（Render 新加坡）→ Neon（新加坡）这条链路第一次完整跑通，且三个环节都在同一个区域。
- **顺带确认清楚两个平台的自动部署行为不一样，容易搞混**：Render 连了 GitHub 之后 `git push` 到 `main` 会自动触发重新部署；Cloudflare 这边现在还是本地手动跑 `npm run deploy`，没有接自动化，以后前端改了代码，光 push 到 GitHub 不会自动生效，得记得手动跑一次部署命令。

**Firebase 凭证在 Render 上最终修好了，用的是比塞进环境变量更好的方案**：删掉 `FIREBASE_CREDENTIALS_PATH` 之后又报了新错——"Firebase not configured"，说明 `FIREBASE_CREDENTIALS_JSON` 压根没真的填过（本地一直用的是 PATH 那条路，JSON 这条从没配置过）。没有直接建议把 JSON 整段粘贴进普通环境变量（`private_key` 字段里的 `\n` 转义符很容易被网页输入框粘贴弄乱），改用 Render 的 **Secret Files** 功能——上传真实文件，挂载到 `/etc/secrets/firebase-adminsdk.json`，`FIREBASE_CREDENTIALS_PATH` 指过去，正好是代码里本来就优先检查的那条路径，不用改代码逻辑。真实验证：Firebase 认证请求 `202` → worker 4 秒内跑完 → `GET /jobs/{id}/asset` 下载到真实的 11.5KB `audio/mpeg` 文件。

**Redis 命令消耗量异常高，用户自己在 Upstash 后台发现的**（"这个redis明显不够用啊"）——250K/500K 免费额度大半是本地开发这几周攒下来的，真实任务没几个。根因：`worker/run_all.py` 里 5 个独立的 arq 轮询循环（4 个 provider 队列 + 1 个 cron），全部用 arq 默认的 0.5 秒 `poll_delay`，不管有没有真实任务都在持续消耗——这个成本只跟"进程开着多久"成正比，跟真实流量无关，一旦部署到 Render 24/7 常驻会变成每天都在累加的固定成本。改法：`app/core/queue.py` 新增 `WORKER_POLL_DELAY_SECONDS = 5.0`，5 个循环统一调高到 5 秒，轮询量砍到十分之一，代价是任务最多多等 5 秒才被捡起——现在所有生成任务都是提交即走、靠 SSE 推送，这几秒延迟基本无感知。记进了 ADR 0014 的 Consequences。

**新用户注册积分从 500 降到 50**，用户直接给的数字，没有讨论过程——按 ADR 0012 的设计直接改 `app_settings.signup_bonus_credits`（PATCH 接口现场生效，不用发版），顺手把代码里的兜底默认值（`app_settings.py` 的 `_DEFAULTS`）和全新环境的种子数据（`migrations/0002`）也同步改成 50，避免以后建新库又变回 500，ADR 0012 和 `product-scope.md` 里提到这个数字的地方也一起改了。

**加了一个 `/native` 路由，用户主动提的真实需求**：老项目的 Android WebView 套壳（Play Store 上真实在线、有真实用户的那个 App，参见 ADR 0021 的发现）打开时加载的固定 URL 是 `/native`，现在 `voicica.ai` 换成了这个新项目的内容，这个路径直接会 404。做了一个纯服务端重定向（`app/native/page.tsx`，`redirect("/app")`），复用 `(app)/layout.tsx` 已有的登录态门禁，不用重复实现。真实验证过：`GET voicica.ai/native` → 307 → `/app` → 200。

**移动端 `/app/create/tts` 等创建页顶部/底部安全区又出了一次真 bug，用户截图发现的**——这次不是重复第一次那个 bug（`viewport-fit=cover` 早就加了），是两个新的坑：①底部固定的"Generate speech"按钮条用的是写死的 `bottom-16`（64px），跟 `BottomNav` 没加安全区之前的高度对齐——但 `BottomNav` 早就加了 `env(safe-area-inset-bottom)` 让自己变高了，真机上导航栏比 64px 高，多出来的部分正好盖住按钮底部。这个模式在 TTS/克隆两个 tab/Kie 通用生成页四处重复，一起改成 `calc(4rem + env(safe-area-inset-bottom, 0px))`。②所有 `(app)` 页面从来没在顶部留过安全区，每个页面自己的 `<header>` 用的是写死的 `padding-top`——这次没有挨个页面改，在 `(app)/layout.tsx` 的共享外壳上一次性加了 `paddingTop: env(safe-area-inset-top)`，处处生效。这个环境物理上没有刘海/Home 指示条，`env()` 测出来必然还是 0，验证边界跟第一次一样——代码逻辑对、窄视口无回归，真机效果需要用户自己确认。

**积分购买功能做完了，用 Stripe Checkout，一次性购买（ADR 0024）**——用户主动申请了 Payoneer 又申请了 Stripe，专门为了把这个项目最老的一个悬而未决项（支付方式）解决掉。选 Stripe 不是随便选的：先查了 Payoneer 自己的开发者产品线，发现"Payoneer Checkout"（对应功能）目前**只接受香港公司主体的早期申请**，用户是泰国的个人账户，连申请资格都没有；Stripe 官方文档明确支持泰国的 Individual 账户类型，才是真正能用的路。三档定价是用户直接给的真实数字（$9/1000、$99/12500、$199/29500，按积分单价算是标准的阶梯折扣），存进 `app_settings.credit_packages`（跟能力菜单一个存法）。幂等性设计**这次是提前做的，不是出了事故才补**——`credit_purchases` 表用 Stripe 的 checkout session id 当幂等键，`complete_purchase()` 用 `SELECT ... FOR UPDATE` 锁行，跟 `finalize_kie_job` 当初为了修 Kie 那次真实重复提交事故加的是同一个思路，这次是吸取教训主动设计进去的。

真实验证：装了 Stripe CLI（`winget install Stripe.StripeCli`，用 `--api-key`/`--print-secret` 直接跳过交互式登录），`stripe listen` 转发真实 webhook 到本地。**第一次真实测试就抓到一个真 bug**：这版 `stripe` SDK 的 `event["data"]["object"]` 返回的是一个类型化对象，不是普通字典——支持 `session["id"]` 这种下标访问，但显式拒绝 `.get(...)` 这种字典方法，直接抛 `AttributeError`。改成跟 `session["id"]` 一样的下标写法就好。**更麻烦的是这个 bug 的真实后果**：用户是真的用测试卡付了钱（Stripe 自己确认 `payment_status: paid`），但因为 webhook 500 了，积分没到账——这正是这类系统最怕的故障模式，手动用真实付款状态把这笔补上了。修好以后重新走一遍：webhook 200、余额精确增加对应积分（495→1495），**幂等性也真的验证了**——故意模拟重复投递同一个 webhook，余额纹丝不动。

**顺带发现一个真实的架构缺口**：现在如果 webhook 一直失败/用户付完款就关掉页面，`credit_purchases` 会永远卡在 `pending`，没有类似 ADR 0007 那种"卡住任务清理"机制来兜底——记成了 ADR 0024 自己的 open item，没有在这次顺手补上（需要单独设计）。

**紧接着用户自己发现一个更大的问题："所以我本地测试连接的也是生产库对吗"**——是的，ADR 0023 当初为了"一个人维护不过来"特意定的"一套库不分开"，这次积分购买的真实测试（真实创建 purchase 记录、真实改动钱包余额）就是直接对着生产库做的。这个风险等级跟之前测 TTS/图片生成不是一回事——钱包余额和支付这类操作，"反正是测试账号"这个说法没那么让人安心了。用户直接决定推翻这个决定（ADR 0025），并且自己申请了一个新的新加坡 Neon 项目发过来当测试库。重新算了一遍"两套库要同步"这笔账，发现比 ADR 0023 当初担心的要轻——大部分种子数据（`kie_categories`/`kie_models`/`capability_menu`/`credit_packages`）都写在 migration 里，新库跑一遍 `alembic upgrade head` 自动就有了，真正需要手动的只有 `voice_catalog`（重新跑一次 `sync_catalog.py`，几分钟的事）。真实验证：全部 12 个 migration 在新库上零错误跑完，语音同步数字（779 Azure + 2066 Google）跟生产库完全对上，用同一个测试账号的真实 Firebase token 打 `GET /me`，返回的是全新的 50 积分（新库首次登录的赠送额度），不是生产库里那个 2495——证明真的是两个隔离的库，不是接错了看起来一样的东西。生产库的连接串搬进了 `backend/.env.production`（纯个人备忘，不会被任何代码读取，Render 读的是它自己后台配置的环境变量，不是仓库里的文件），根目录 `.gitignore` 也从"逐个列举 `.env`/`.env.local`"改成了 `.env*` 通配（这是这个仓库第三次因为漏列某个具体 `.env` 文件名栽跟头，干脆用通配规则从根上解决）。

**语音目录也要在新加坡这个新库上重新同步一次，用户主动想起来的**（"后端的语音的列表是不是要重新导入一下 azure和google的"）——查了一下 `voice_catalog` 表确实是空的（新库从零建的，这张表从没跑过 sync）。第一次跑 `sync_catalog.py` 直接炸了，又是一个只有真跑一次全新环境才会暴露的真 bug：`_google_rows()` 这个函数从写下来那天起就没设置 `display_name` 这个字段，而 `VoiceCatalog.display_name` 这一列一直是非空约束——之前从没暴露过是因为这几个月都没有真正对着一个全新数据库重新跑过这个脚本。补上 `"display_name": v["name"]`（Google 本来就没有单独的人类可读名字，用回原始 voice name，前端的 `friendlyVoiceName()` 负责美化显示，数据库这层不用管）之后重新跑，779 个 Azure + 2066 个 Google，跟老库当年的真实数字完全对上，泰语/印尼语/西语一共 266 条也验证过。因为直接是对着新加坡这个库跑的（跟 Render 后端同一个库），线上立刻就能用，不用额外操作。
