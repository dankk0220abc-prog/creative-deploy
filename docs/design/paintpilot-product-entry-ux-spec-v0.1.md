# PaintPilot Product Entry UX Specification v0.1

## 1. Document Status

- Status: `OWNER_APPROVED`
- Version: `0.1.0`
- Implementation Status: `NOT_STARTED`
- Approval Date: `2026-07-24`
- Concept Status: `OWNER_APPROVED`
- Concept Approval: `OWNER_APPROVED`
- Product: `PaintPilot`
- Parent Platform: `CreativeDeploy`
- Route: `/paintpilot`
- Experience Layer: `Brand Experience Layer`
- Visual Direction: `Nocturne Studio`
- Layout Direction: `Cinematic Product Entry`
- Decision Authority: `Project Owner`

本文档冻结已批准的体验职责与后续实施候选细节，不表示路由、页面、互动视觉、上传、
AI、Polygon、RAG、库存查询或施工计划已经实现。

概念图只用于方向确认，不是正式产品资产。机器人、机甲、动漫或游戏角色以及其他
未授权角色资产不得进入产品或公开仓库；复杂 Product Entry 动效不阻塞 Phase 1D。

## 2. Page Purpose

让首次访问者理解 PaintPilot 的专业价值、核心工作流和 Human-in-the-loop 特征，
并进入 Projects Workspace。

Product Entry 是产品理解和品牌体验层，不承担项目管理、项目创建或日常状态操作。

## 3. Primary Audience

- PDE / FDE 面试官；
- 手办涂装工作室；
- 手办重涂玩家；
- 创意 AI 产品评审者。

页面必须同时让专业评审者看见可控 Agent 工作流，让领域用户快速理解这是一个涂装
规划工具；不能依赖工程术语或纯视觉特效完成解释。

## 4. Experience and Route Boundary

| Route | Surface | Responsibility | Product Entry relationship |
| --- | --- | --- | --- |
| `/paintpilot` | Product Entry | 品牌、产品价值、四步工作流叙事 | Current surface |
| `/paintpilot/projects` | Projects Workspace | 查看、创建和进入 Paint Project | Primary CTA destination |
| `/paintpilot/projects/new` | Create Project | 独立沉浸式创建流程 | 不从 Entry 直接创建 |
| `/paintpilot/projects/:projectId` | Minimum Project Detail / future Project Workspace | Phase 1D 真实详情与未来精确操作边界 | Detail first; Precision Workspace later |

Product Entry 不显示 Project Cards、项目状态、管理筛选器或 Create Project。Projects
Workspace 不复制完整 Hero、互动视觉主体或四步滚动故事。

## 5. Primary Action

页面只有一个主要 CTA：

`Enter PaintPilot Workspace`

- 目标路由为 `/paintpilot/projects`。
- CTA 在 Hero 中明确可见，并在叙事结束后以
  `Enter PaintPilot Workspace` 再次完成旅程收束。
- Hero 与最终 CTA 是同一任务在不同叙事节点的延续，不在同一视区重复竞争。

允许一个低权重次级操作：

`View Workflow`

- 只滚动到 Capture 段落，不创建新的产品任务。
- 视觉权重明显低于 Enter PaintPilot Workspace。

不显示 Create Project、项目列表、多个同权重功能按钮、大量统计或管理筛选器。

## 6. Hero Structure

首屏只包含：

1. CreativeDeploy / PaintPilot 品牌关系；
2. PaintPilot 大标题；
3. 一句产品价值；
4. 一个 `Enter PaintPilot Workspace` CTA；
5. 一个非角色化互动视觉主体；
6. 极少量 Capability Boundary。

候选文案：

**PaintPilot**

`Plan repaint workflows with visual understanding and human control.`

文案仍需通过视觉概念稿和用户评审确认。首屏不得加入项目卡片、Create Project、
功能网格、工程统计或密集导航。

## 7. Interactive Visual Subject

### 7.1 Recommended Subject

`Abstract Material Study`

这是一个无角色身份的抽象材质研究体，用于在同一视觉主体上表现输入、区域结构、
光线方向、颜料关系、知识节点和 Human Review。它不能被明显识别为人物、机器人、
具体手办或商业 IP。

可使用：

- 雕塑式几何体块；
- 树脂、石膏或模型材料质感；
- 图像区域轮廓和 Polygon 节点；
- 光源方向线与阴影分区；
- 低饱和颜料色块；
- 知识与库存信号节点；
- Human Review 确认信号。

禁止：

- 机器人、机甲、动漫人物或游戏人物；
- 塔罗牌、魔法阵或玄学图形；
- 未授权角色、具体商业手办或无法追溯来源的图像；
- 将旧概念图中的角色化占位转为正式资产。

### 7.2 Interaction Role

- 视觉主体在四个叙事阶段保持身份连续，只改变信息层和材质状态。
- 指针或滚动互动用于揭示区域、光线或节点关系，不成为理解前提。
- 所有关键变化同时具有短文字说明。
- 视觉加载失败时保留标题、说明、CTA 和四步内容。
- 不使用自动播放声音。

## 8. Scroll Narrative

滚动叙事只使用四段。每段包含一个序号、一个短标题、一段简短说明和一次核心视觉
变化，不扩展为功能墙。

### 8.1 01 Capture

**Meaning**

- 上传手办图片；
- 检查图片质量；
- 保留原始输入。

**Visual change**

- 抽象输入图像或材质体进入焦点；
- 粒子由分散转为聚焦；
- 输入图像边界形成。

**Human-control boundary**

输入被保留并等待明确检查；概念叙事不得暗示图片已真实上传或验证。

### 8.2 02 Structure

**Meaning**

- 识别候选区域；
- 用户修正 Polygon；
- 人工确认后才成为事实。

**Visual change**

- 材质表面逐渐出现区域轮廓；
- 节点与 Polygon 边界形成；
- AI suggestion 与 confirmed state 使用不同文字和形状。

**Human-control boundary**

模型建议不能被自动表现为已确认区域，颜色也不能成为唯一状态区分。

### 8.3 03 Direct

**Meaning**

- 设置目标风格；
- 设置光源方向；
- 设置阴影和高光规则。

**Visual change**

- 光源方向线改变；
- 表面形成硬边明暗区；
- 低饱和色块和材质层次发生可控变化。

**Human-control boundary**

视觉变化表达规划意图，不表示 PaintPilot 已完成渲染或保证真实涂装结果。

### 8.4 04 Plan

**Meaning**

- 查询颜料库存；
- 检索知识资料；
- 生成可审核的施工计划。

**Visual change**

- 节点收敛为少量结构化步骤；
- Citation 与库存信号出现；
- Human Review 后，输出从候选状态转为稳定状态。

**Human-control boundary**

库存、Citation、RAG 和施工计划均为未来能力叙事；概念页面不能展示虚假实时结果。

## 9. Final CTA

叙事结束后显示：

`Enter PaintPilot Workspace`

- 进入 `/paintpilot/projects`，不直接创建项目。
- 附近只保留一句说明和有限 Capability Boundary。
- 不增加第二组功能按钮或项目预览。
- 如果 Projects Workspace 尚未实现，未来实现必须提供诚实的 unavailable 状态，
  不能伪装为完整产品。

## 10. Capability Boundary

页面明确显示：

`PaintPilot is under active development.`

- 当前已实现和未实现内容必须与 README 及仓库事实一致。
- Product Entry 不能暗示 AI 分析、Polygon Editor、RAG、库存集成或施工计划已完成。
- 不能暗示真实产品已经上线或已有用户项目数据。
- Capability Boundary 必须可读，但不能扩展成状态面板或功能清单墙。

## 11. Responsive Behavior

### 11.1 Desktop

- 视觉主体占据主要空间，文案与视觉并行。
- 极大留白用于建立节奏，不用卡片或图标填满。
- 四段故事共享同一主体，通过滚动焦点改变信息层。
- 景深有限，正文和 CTA 始终位于稳定阅读层。

### 11.2 Mobile

- 文案先于复杂视觉，使用单列滚动。
- 视觉主体简化，粒子、模糊和景深显著降低。
- CTA 始终清晰，首屏不拥挤。
- 不强制 3D、拖拽、精确指针或 hover 交互。
- 不出现项目列表、横向滚动或复杂固定导航。

## 12. Accessibility

- Enter PaintPilot Workspace、View Workflow 和最终 CTA 支持键盘操作及清晰
  `focus-visible`。
- 每段视觉变化都有文字解释，故事不能只依赖动画。
- reduced motion 下直接显示四步稳定状态，移除视差、连续粒子和景深推进。
- 状态同时使用文字、形状或图标，不只依赖颜色。
- 正文与 CTA 需要达到实施时适用的 WCAG AA 对比度。
- 视觉主体使用合适的文本替代；纯装饰粒子不进入可访问名称。
- DOM 顺序遵循 Capture、Structure、Direct、Plan，不随空间位置改变。
- 不自动播放声音，不使用闪烁或高频亮度变化。

## 13. Future Technology Options

当前不选择最终实现技术，也不安装任何依赖。

### 13.1 Option 1 — CSS + Canvas 2D / 2.5D

**Advantages**

- 依赖小、性能较可控；
- 容易与 React 集成；
- 适合粒子、节点、遮罩和有限景深；
- 便于解释代码与渐进降级。

**Limitations**

- 真实 3D 材质、复杂光照和自由视角能力有限。

### 13.2 Option 2 — Lightweight WebGL / Three.js

**Advantages**

- 空间感、材质和光照变化更强；
- 更接近高质量互动 3D 产品入口体验。

**Limitations**

- 开发、调试和性能成本更高；
- 移动端必须设计明确降级；
- 会增加依赖和 JavaScript 体积。

### 13.3 Option 3 — Spline Runtime

**Advantages**

- 视觉制作效率高；
- 互动与材质表达能力强。

**Limitations**

- 引入外部运行时和加载体积；
- 性能、版本、降级和长期可控性需要评估；
- 可能弱化代码自主性；
- 对求职项目的技术讲解不一定最优。

### 13.4 Default Recommendation

MVP 默认建议使用 CSS + Canvas 2D / 2.5D 建立视觉语言。只有在视觉概念验证证明其
明显不足，并完成性能、可访问性和维护成本评估后，才评估 Lightweight WebGL。
当前不得安装或选择 Spline Runtime。

## 14. Candidate Performance Budget

- 首屏文本和 CTA 必须先于复杂视觉可用。
- 互动视觉不能阻塞导航或页面可操作性。
- 粒子或材质视觉加载失败时，页面结构和四步说明保持完整。
- 移动端降低粒子数量、模糊、纹理和更新频率。
- `prefers-reduced-motion` 关闭复杂运动。
- 低性能设备使用静态渐变、节点背景或静态材质体。
- 视觉效果不得成为业务功能依赖。

实施前必须测量并记录：

- Largest Contentful Paint；
- 动画 FPS 与掉帧；
- Long Tasks；
- Mobile memory；
- JavaScript bundle impact。

本阶段不冻结绝对 KB、粒子数或帧率阈值；这些数值需要在技术原型和目标设备测试后
确定，不能被描述为已经达成。

## 15. Approved Concept Freeze

项目所有者已批准：

- `/paintpilot` Cinematic Product Entry；
- Nocturne Studio；
- spacious、low-density、single-primary-action 布局；
- `Enter PaintPilot Workspace`；
- 非角色 Abstract Material Study；
- magnetic particles、Polygon nodes、light direction、material / color zones 和有限景深；
- Capture、Structure、Direct、Plan 四段叙事；
- 禁止 robot、mecha、anime/game character、Tarot、未授权 IP、Hero Project Cards、
  dense dashboard 和 fake user data。

批准的是视觉方向，不是概念图片资产，也不表示 Product Entry、动画或相关业务能力
已经实现。概念图片不得进入产品或公开仓库。

## 16. Real-product Delivery Priority

核心产品实施顺序高于完整电影化入口：

1. PaintProject 创建与数据库持久化；
2. 项目列表与项目打开；
3. 图片上传和质量检查；
4. 区域人工确认；
5. 涂装方案工作流；
6. 完整电影化 Product Entry 动效。

首屏文本、CTA 和基础路由未来可以渐进实现；复杂粒子和滚动叙事不得阻塞前五项真实
产品能力。求职展示只能引用经过测试、评测和实际使用证据支持的能力。
