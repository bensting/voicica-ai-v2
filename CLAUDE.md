# AI Voice Labs v2 - 项目重构记忆

> 本项目是对 `voicica-ai` 老项目的重写。老项目路径见下方"老项目参考"，**仅作参考，不再直接改动**。

## 重构背景与目标

老项目堆叠太久、代码结构混乱，因此重启新项目而非继续在老代码上改。

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

## 老项目参考

路径：`C:\Users\NITRO V15\PycharmProjects\voicica-ai`

老项目技术栈（可复用的经验/资产，具体见老项目自己的 CLAUDE.md）：
- 前端 Next.js 15 (App Router) + TypeScript + Tailwind + Firebase Auth
- 后端 FastAPI + Firebase Admin SDK
- Prisma + Neon (Postgres)
- 双版本管理机制（Web 版本 / 原生 App 版本）、PWA 更新机制、i18n（en / zh-CN / zh-TW）等

这些老项目里跑通的模式（认证流程、i18n 方案、版本管理脚本等）可以按需搬过来，但**目录结构和业务逻辑组织方式要按新项目的规则重新设计**，不要整体照搬。

## 当前状态

刚创建骨架目录（`backend/`、`frontend/`），尚未安装任何依赖、尚未写代码。下一步：在此项目中重新打开 Claude Code 继续讨论技术选型和具体实现。
