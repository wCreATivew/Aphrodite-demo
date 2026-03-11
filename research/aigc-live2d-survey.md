# AIGC Live2D 模型生成技术方案调研报告

## 执行摘要

本次调研针对 AIGC 生成 Live2D 模型的技术方案进行了全面搜索和分析。核心发现：**目前尚无成熟的"文本/图片→完整 Live2D 模型（含 rigging）"的一键生成方案**，但存在多个可组合的技术栈可实现类似效果。

---

## 一、技术现状概述

### 1.1 核心发现

| 能力 | 成熟度 | 说明 |
|------|--------|------|
| 文本→Live2D 模型 | ❌ 不成熟 | 无直接生成工具，需人工建模 |
| 图片→Live2D 模型 | ⚠️ 部分支持 | 需手动 rigging/骨骼绑定 |
| 参数化换装/换脸 | ✅ 成熟 | 多个开源项目支持 |
| 模块化拼装角色 | ✅ 成熟 | 类似换装游戏方案存在 |
| 自动 rigging | ⚠️ 实验性 | 部分工具支持基础绑定 |

---

## 二、可行方案清单

### 2.1 完整 AI VTuber 框架（推荐起点）

#### 🥇 Open-LLM-VTuber
- **仓库**: https://github.com/Open-LLM-VTuber/Open-LLM-VTuber
- **许可**: MIT
- **特点**:
  - 跨平台（Windows/macOS/Linux）
  - 支持 Live2D/VRM 模型
  - 完整的 LLM+ASR+TTS 集成
  - 桌面宠物模式（透明背景）
  - 支持自定义 Live2D 模型导入
- **生成质量**: ⭐⭐⭐⭐（依赖外部模型）
- **自由度**: ⭐⭐⭐⭐⭐（可替换所有组件）
- **人工调整**: 需要（模型需单独准备）

#### 🥈 AIRI (moeru-ai)
- **仓库**: https://github.com/moeru-ai/airi
- **许可**: MIT
- **特点**:
  - 受 Neuro-sama 启发
  - WebGPU/WebAssembly 技术支持
  - 支持 Live2D 和 VRM
  - 浏览器/桌面双模式
  - 长期记忆系统
- **生成质量**: ⭐⭐⭐⭐
- **自由度**: ⭐⭐⭐⭐⭐
- **人工调整**: 需要

#### 🥉 handcrafted-persona-engine
- **仓库**: https://github.com/fagenorn/handcrafted-persona-engine
- **许可**: 未明确（需确认）
- **特点**:
  - .NET/C#实现
  - 包含特制"Aria"Live2D 模型
  - 支持 Spout 输出到 OBS
  - 情感驱动动画
- **生成质量**: ⭐⭐⭐⭐
- **自由度**: ⭐⭐⭐
- **人工调整**: 中等（需配置 personality.txt）

---

### 2.2 语音克隆与 TTS 方案

#### GPT-SoVITS（强烈推荐）
- **仓库**: https://github.com/RVC-Boss/GPT-SoVITS
- **许可**: 未明确（需确认商用）
- **特点**:
  - 零样本 TTS（5 秒音频即可）
  - 少样本微调（1 分钟数据）
  - 支持中/日/英/韩/粤语
  - WebUI 工具完整
- **生成质量**: ⭐⭐⭐⭐⭐
- **自由度**: ⭐⭐⭐⭐
- **人工调整**: 低（自动化程度高）

#### unspeech（TTS 聚合服务）
- **仓库**: https://github.com/moeru-ai/unspeech
- **许可**: AGPL-3.0
- **特点**:
  - OpenAI 兼容 API
  - 支持 ElevenLabs/Azure/阿里云等
  - 统一接口多供应商
- **生成质量**: ⭐⭐⭐⭐
- **自由度**: ⭐⭐⭐⭐
- **人工调整**: 低

---

### 2.3 Live2D 显示与交互框架

#### pixi-live2d-display
- **仓库**: https://github.com/guansss/pixi-live2d-display
- **许可**: MIT（代码）+ Live2D 官方许可（模型）
- **特点**:
  - 支持 Cubism 2.1/3/4
  - PixiJS 插件
  - 高级 API 简化控制
  - 在线查看器：https://guansss.github.io/live2d-viewer-web/
- **适用场景**: Web 端 Live2D 展示

#### live2d-widget
- **仓库**: https://github.com/stevenjoezhang/live2d-widget
- **许可**: GPL-3.0
- **特点**:
  - 轻量级看板娘方案
  - TypeScript 编写
  - 支持换装功能（需 model_list.json）
  - 一键集成代码
- **适用场景**: 博客/网站添加 Live2D

#### PPet
- **仓库**: https://github.com/zenghongtu/PPet
- **许可**: 未明确
- **特点**:
  - 桌面宠物（Mac/Win/Linux）
  - 支持 Live2D v2/v3
  - 本地/在线模型导入
  - 拖拽交互
- **适用场景**: 桌面伴侣应用

---

### 2.4 模型资源与提取工具

#### Live2D 模型收集
- **Eikanya/Live2d-model**: https://github.com/Eikanya/Live2d-model
  - 游戏提取模型集合
  - 含配置说明
- **zenghongtu/live2d-model-assets**: PPet 配套模型

#### Unity Live2D 提取器
- **Perfare/UnityLive2DExtractor**: https://github.com/Perfare/UnityLive2DExtractor
  - 从 Unity AssetBundle 提取 Cubism 3 文件
  - .NET Framework 4.7.2 要求

---

### 2.5 其他 AI VTuber 项目参考

| 项目 | 仓库 | 特点 |
|------|------|------|
| AI-Vtuber | https://github.com/Ikaros-521/AI-Vtuber | 中文项目，支持多直播平台 |
| my-neuro | https://github.com/morettt/my-neuro | Neuro-sama 复刻，长期记忆 |
| LLM-Live2D-Desktop-Assitant | https://github.com/ylxmf2005/LLM-Live2D-Desktop-Assitant | Electron 桌面版，屏幕感知 |
| ChatWaifu_Mobile | https://github.com/Voine/ChatWaifu_Mobile | Android 手机版 |
| Virtual-Human-for-Chatting | https://github.com/Navi-Studio/Virtual-Human-for-Chatting | Unity 实现 |

---

## 三、参数化/模块化方案

### 3.1 换装/换发型实现

根据调研，**参数化 Live2D 换装**主要通过以下方式实现：

1. **live2d-widget 方案**:
   - 需要 `model_list.json` 定义可用模型
   - 需要 `textures.cache` 支持动态切换
   - 前端实现，无需后端 API

2. **Pio 插件**:
   - 仓库：https://github.com/Dreamer-Paul/Pio
   - Typecho 插件，支持模型切换
   - 资源站：https://mx.paul.ren（梦象）

3. **自定义方案**:
   - 使用 pixi-live2d-display 的 `model.motion()` 和表达式切换
   - 预定义多套服装/发型的 Live2D 模型
   - 通过参数控制部件可见性

### 3.2 动态换脸方案

**当前限制**: Live2D 本身不支持运行时动态换脸。可行方案：

1. **预制作多版本模型**: 为每个脸型创建独立 Live2D 模型
2. **VRM 替代**: VRM 格式支持更好的模块化（参考 VRoid Hub）
3. **AI 生成 + 人工 rigging**: 用 AI 生成脸部图片，人工绑定到 Live2D

---

## 四、技术路线推荐

### 4.1 推荐方案 A：快速原型（1-2 周）

```
技术栈:
  前端：Open-LLM-VTuber (桌面端)
  模型：现成 Live2D 模型（从模型库选择）
  TTS: GPT-SoVITS（本地部署）
  LLM: Ollama/Qwen 等本地模型
  
优点:
  - 快速搭建
  - 全本地运行
  - 隐私安全
  
缺点:
  - 模型需手动选择
  - 无自动换装
```

### 4.2 推荐方案 B：定制化方案（1-2 月）

```
技术栈:
  前端：pixi-live2d-display + 自定义 UI
  模型：模块化 Live2D（多部件组合）
  TTS: GPT-SoVITS + unspeech 聚合
  LLM: 云端 API（Qwen/Claude）
  后端：Node.js/Python 自定义服务
  
优点:
  - 高度定制
  - 支持换装/换发型
  - 可扩展性强
  
缺点:
  - 开发周期长
  - 需要 Live2D 建模知识
```

### 4.3 推荐方案 C：AI 生成实验（研究向）

```
技术路线:
  1. 用 SD/MJ生成角色图片
  2. 用 Live2D Cubism Editor 手动 rigging
  3. 或用 VRoid Studio 生成 3D 模型
  4. 集成到 Open-LLM-VTuber 框架
  
工具链:
  - 图片生成：Stable Diffusion / Midjourney
  - 3D 建模：VRoid Studio（免费）
  - Live2D 绑定：Cubism Editor（付费）
  - 或尝试：Vroid→Live2D 转换工具（实验性）
```

---

## 五、关键限制与注意事项

### 5.1 Live2D 许可限制

- **Cubism SDK**: 需遵守 Live2D 官方许可
  - Cubism 2.1: Live2D SDK License Agreement (Public)
  - Cubism 5: Live2D Proprietary Software License
  - 组件：Live2D Open Software License
- **模型版权**: 大多数收集模型**禁止商用**
- **商用建议**: 使用原创模型或购买商业授权

### 5.2 技术限制

| 限制 | 说明 | 解决方案 |
|------|------|----------|
| 无自动 rigging | 图片→Live2D 需手动绑定 | 用 VRoid 或聘请建模师 |
| 换装需预制作 | 无法动态生成服装 | 准备多套部件，代码切换 |
| 中文 TTS 质量 | 部分模型中文效果差 | 用 GPT-SoVITS 中文模型 |
| 实时性 | 全本地推理延迟 1-3 秒 | 用流式 TTS+ 小模型 |

### 5.3 硬件要求

- **GPT-SoVITS**: NVIDIA GPU（CUDA）推荐
- **Open-LLM-VTuber**: 可 CPU 运行，GPU 加速更佳
- **本地 LLM**: 8GB+ VRAM 运行 7B 模型

---

## 六、开源/商用许可总结

| 项目 | 许可 | 商用 | 备注 |
|------|------|------|------|
| Open-LLM-VTuber | MIT | ✅ | 模型需单独确认 |
| AIRI | MIT | ✅ | - |
| GPT-SoVITS | 需确认 | ⚠️ | 查看官方文档 |
| pixi-live2d-display | MIT | ✅ | Live2D 运行时另计 |
| live2d-widget | GPL-3.0 | ⚠️ | 需开源衍生作品 |
| unspeech | AGPL-3.0 | ⚠️ | 需开源衍生作品 |
| handcrafted-persona-engine | 需确认 | ⚠️ | 查看 LICENSE |

---

## 七、下一步行动建议

1. **原型验证**（本周）:
   - 部署 Open-LLM-VTuber
   - 测试 GPT-SoVITS TTS
   - 选择 1-2 个 Live2D 模型

2. **技术选型**（下周）:
   - 确定是否商用（影响许可选择）
   - 决定前端框架（Web vs 桌面）
   - 规划模块化方案

3. **模型准备**（2-4 周）:
   - 联系 Live2D 建模师
   - 或用 VRoid 制作基础模型
   - 准备多套服装/发型部件

4. **集成开发**（1-2 月）:
   - 实现换装逻辑
   - 集成记忆系统
   - 优化交互体验

---

## 附录：关键链接

### 项目仓库
- Open-LLM-VTuber: https://github.com/Open-LLM-VTuber/Open-LLM-VTuber
- AIRI: https://github.com/moeru-ai/airi
- GPT-SoVITS: https://github.com/RVC-Boss/GPT-SoVITS
- pixi-live2d-display: https://github.com/guansss/pixi-live2d-display

### 文档与教程
- Open-LLM-VTuber 文档：https://open-llm-vtuber.github.io/docs/quick-start
- GPT-SoVITS 用户指南：https://www.yuque.com/baicaigongchang1145haoyuangong/ib3g1e
- Live2D 官方：https://www.live2d.com/en/

### 模型资源
- 梦象资源站：https://mx.paul.ren
- Live2D 模型收集：https://github.com/zenghongtu/live2d-model-assets

---

**报告生成时间**: 2026-03-11
**调研执行者**: Subagent (aigc-live2d-research)
