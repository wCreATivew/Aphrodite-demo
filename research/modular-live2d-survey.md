# 模块化/碎片化 Live2D 生成方案调研报告

## 核心问题
能否用 AI 生成角色部件（头发、眼睛、服装等），然后组装到通用骨骼模板上？

---

## 1. 模块化 Live2D 项目调研

### 现有项目
| 项目 | 描述 | 状态 |
|------|------|------|
| **Dreamer-Paul/Pio** | 支持更换 Live2D 模型的 JS 插件 | 2023 年更新 |
| **guansss/pixi-live2d-display** | PixiJS 的 Live2D 显示框架，支持所有版本模型 | 2024 年更新 |
| **stevenjoezhang/live2d-widget** | Web 平台 Live2D 看板娘组件 | 2026 年更新 |
| **Eikanya/Live2d-model** | Live2D 模型收集库 | 2026 年更新 |

### 关键发现
- **没有成熟的"模块化 Live2D"开源项目**：现有项目主要是 Live2D 模型的**显示/集成**工具，而非部件化生成系统
- **模型切换可行**：Pio 等项目证明了运行时切换完整模型是可行的，但**部件级切换**需要自定义开发
- **Live2D Cubism 原生支持**：Live2D Cubism Editor 5.3 支持参数化和物理效果，但需要手动制作

---

## 2. 自动 Rigging 工具调研

### 2D 自动绑定工具
| 工具 | 描述 | 适用性 |
|------|------|--------|
| **0xcafeb33f/automatic-rigging** | Godot 引擎 2D 骨骼自动绑定脚本 | 仅限 Godot |
| **Ember (andallas/Ember)** | 基于顶点的图形编辑器，含 2D 骨骼绑定 | 已停止维护 (2013) |

### 学术研究 (arXiv 2025)
- **"How to Train Your Dragon: Automatic Diffusion-Based Rigging"** (2025.03)
  - 使用扩散模型处理多样化骨骼拓扑
  - 仅需 3-5 帧示例即可动画化
  
- **"ASMR: Adaptive Skeleton-Mesh Rigging and Skinning via 2D Generative Prior"**
  - 通过 2D 生成先验自适应骨骼网格绑定
  - 处理骨骼和网格的多样化配置

### 关键发现
- **Live2D 专用自动 rigging 工具不存在**：搜索 "live2d auto rigging" 返回 0 结果
- **学术研究有进展**：2025 年论文显示自动 rigging 是活跃研究领域
- **需要手动或半自动方案**：目前 Live2D 绑定仍需 Cubism Editor 手动完成

---

## 3. AI 生成角色部件工作流

### 3.1 Stable Diffusion + ControlNet
| 组件 | 作用 | 项目 |
|------|------|------|
| **ControlNet** | 控制扩散模型生成，保持结构一致性 | lllyasviel/ControlNet |
| **Stable Diffusion WebUI** | 主生成界面，支持 inpainting/outpainting | AUTOMATIC1111/stable-diffusion-webui |
| **Segment Anything (SAM/SAM2)** | 图像分割，自动提取部件 | facebookresearch/segment-anything |

### 3.2 可行工作流
```
┌─────────────────────────────────────────────────────────────┐
│  1. 部件生成                                                 │
│     SD + ControlNet (Canny/Depth/OpenPose) → 头发/眼睛/服装  │
├─────────────────────────────────────────────────────────────┤
│  2. 部件分割                                                 │
│     SAM2 → 自动分割部件 → 透明 PNG                           │
├─────────────────────────────────────────────────────────────┤
│  3. 部件分层                                                 │
│     手动/脚本 → 按 Live2D 要求分层 (前发/后发/刘海等)          │
├─────────────────────────────────────────────────────────────┤
│  4. 骨骼绑定                                                 │
│     Cubism Editor → 手动绑定 或 自定义脚本半自动              │
├─────────────────────────────────────────────────────────────┤
│  5. 参数配置                                                 │
│     设置物理效果、变形器、表情参数                           │
└─────────────────────────────────────────────────────────────┘
```

### 3.3 关键挑战
- **分层一致性**：AI 生成的部件需要符合 Live2D 分层规范（通常 10-20 层/角色）
- **接缝处理**：部件连接处需要平滑过渡（头发与额头、服装与身体）
- **风格统一**：不同部件需要保持一致的画风和分辨率

---

## 4. VRoid Studio 模块化方案参考

### VRoid Hub 生态
| 项目 | 描述 | 参考价值 |
|------|------|----------|
| **char13s/VroidBreakerAndCustomizer** | Unity 工具，将 VRoid 角色拆分为部件并支持自定义组合 | ⭐⭐⭐⭐⭐ 直接参考 |
| **xiaoye97/VRoidChinese** | VRoid Studio 汉化插件 | ⭐⭐ |
| **cmd410/VRoidBones** | Blender 插件，优化 VRoid 骨骼 | ⭐⭐⭐ |

### VRoid 模块化特点
- **内置部件系统**：头发、眼睛、服装、配饰均为可替换模块
- **Unity 集成**：VRM 格式支持运行时部件切换
- **可参考架构**：
  - 部件预定义槽位（发型槽、眼睛槽等）
  - 标准化接口（UV、骨骼权重）
  - 材质/着色器统一

### 2D 转化挑战
- VRoid 是 3D 模型，Live2D 是 2D 变形
- VRoid 部件切换 = 模型替换；Live2D 部件切换 = 纹理/网格变形
- **可借鉴**：部件分类体系、槽位设计、标准化接口

---

## 5. 相关开源项目汇总

### 5.1 部件化角色生成
| 项目 | 技术栈 | 状态 |
|------|--------|------|
| **alfredo1995/2D-Character-Customization** | C#/Unity | 2025 年更新 |
| **bfaulk04/character-creator** | JavaScript | 2025 年更新 |
| **rrcarohleder/character_creator_api** | TypeScript | 2025 年更新 |

### 5.2 Live2D 集成
| 项目 | 描述 |
|------|------|
| **Open-LLM-VTuber/Open-LLM-VTuber** | LLM + Live2D 语音交互，支持本地运行 |
| **moeru-ai/airi** | 自托管 AI 伴侣，含 Live2D 实用工具 |
| **fagenorn/handcrafted-persona-engine** | C# 引擎，Live2D+LLM+ASR+TTS+RVC |

### 5.3 图像→Live2D 工具
- **无直接转换工具**：搜索 "image to live2d" 无成熟开源项目
- **商业工具**：Live2D Cubism 提供 PSD 导入，但需手动绑定
- **研究方向**：自动参数生成、物理效果自动配置

---

## 6. 可行技术路线

### 方案 A: 半自动工作流（推荐起点）
```
AI 生成部件 → 手动分层 → Cubism Editor 绑定 → 参数配置
```
- **工具链**：
  - SD WebUI + ControlNet（部件生成）
  - SAM2（自动分割）
  - Photoshop/GIMP（分层精修）
  - Live2D Cubism Editor（绑定）
  
- **工作量**：
  - 初始设置：2-3 天
  - 单角色制作：4-8 小时（熟练后 2-3 小时）
  - 自动化空间：分割、批量处理

### 方案 B: 自定义工具链（中期目标）
```
AI 生成 → 自动分割 → 标准化分层 → 脚本辅助绑定 → 导出
```
- **需要开发**：
  - 部件分层脚本（Python + OpenCV）
  - Live2D 参数生成器（基于模板）
  - 批量处理管道
  
- **工作量**：
  - 工具开发：2-4 周
  - 单角色制作：30-60 分钟

### 方案 C: 端到端自动化（长期愿景）
```
文本/草图 → AI 生成完整角色 → 自动 rigging → Live2D 导出
```
- **需要突破**：
  - 高质量部件生成模型（LoRA 训练）
  - 自动骨骼检测与绑定（研究级）
  - 物理效果自动配置
  
- **工作量**：
  - 研发：3-6 个月+
  - 依赖学术进展

---

## 7. 工具链清单

### 必需工具
| 类别 | 工具 | 用途 |
|------|------|------|
| **AI 生成** | Stable Diffusion WebUI | 部件生成 |
| **控制** | ControlNet | 保持结构一致性 |
| **分割** | SAM2 (Segment Anything 2) | 自动提取部件 |
| **编辑** | Photoshop/GIMP | 分层精修 |
| **绑定** | Live2D Cubism Editor | 骨骼绑定、参数配置 |
| **显示** | pixi-live2d-display | Web 端展示 |

### 可选工具
| 类别 | 工具 | 用途 |
|------|------|------|
| **3D 参考** | VRoid Studio | 角色设计参考 |
| **批量处理** | Python + OpenCV | 自动化脚本 |
| **版本管理** | Git | 部件库管理 |

---

## 8. 工作量评估

### 阶段 1: 原型验证（1-2 周）
- [ ] 搭建 SD + ControlNet 环境
- [ ] 测试部件生成（头发、眼睛、服装各 5 个变体）
- [ ] 手动完成 1 个完整角色的 Live2D 制作
- **产出**：验证工作流可行性

### 阶段 2: 工具开发（3-4 周）
- [ ] 开发自动分割脚本（SAM2 集成）
- [ ] 开发分层工具（按 Live2D 规范）
- [ ] 创建部件模板库（骨骼、参数预设）
- **产出**：半自动化工具链

### 阶段 3: 系统集成（4-6 周）
- [ ] 部件管理系统（分类、标签、搜索）
- [ ] 运行时部件切换（Web/Unity）
- [ ] 批量处理管道
- **产出**：可用的模块化 Live2D 系统

### 阶段 4: 优化迭代（持续）
- [ ] AI 模型微调（角色特定 LoRA）
- [ ] 绑定质量提升
- [ ] 物理效果优化
- **产出**：生产级系统

---

## 9. 关键结论

### ✅ 可行
- AI 生成角色部件（SD + ControlNet）技术成熟
- 自动分割（SAM2）可大幅减少手动工作
- VRoid 模块化方案可参考架构设计
- 部件切换在技术上是可行的（参考 Pio 等项目）

### ⚠️ 挑战
- **无现成"模块化 Live2D"项目**：需要自定义开发
- **自动 rigging 不成熟**：Live2D 绑定仍需大量手工
- **分层规范复杂**：需要深入理解 Live2D 模型结构
- **风格一致性**：AI 生成部件需要统一画风

### 🎯 建议
1. **从半自动工作流开始**：先验证 AI 生成 + 手动绑定的可行性
2. **参考 VRoid 架构**：借鉴其部件分类和槽位设计
3. **优先开发分割工具**：SAM2 集成可显著提效
4. **积累部件库**：逐步建立可复用的部件资源

---

## 10. 参考资源

### GitHub 项目
- [guansss/pixi-live2d-display](https://github.com/guansss/pixi-live2d-display) - Live2D Web 显示框架
- [char13s/VroidBreakerAndCustomizer](https://github.com/char13s/VroidBreakerAndCustomizer) - VRoid 部件拆分工具
- [lllyasviel/ControlNet](https://github.com/lllyasviel/ControlNet) - 可控图像生成
- [facebookresearch/segment-anything-2](https://github.com/facebookresearch/segment-anything-2) - 图像/视频分割

### 学术资源
- "How to Train Your Dragon: Automatic Diffusion-Based Rigging" (arXiv 2025.03)
- "ASMR: Adaptive Skeleton-Mesh Rigging" (arXiv 2025)

### 商业工具
- [Live2D Cubism](https://www.live2d.com/) - 官方编辑器（学生 76% 折扣）

---

*调研完成时间：2026-03-11*
*调研执行者：Subagent (modular-live2d-research)*
