# PaintPilot Product Entry Wireframes v0.1

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
- Entry Direction: `Cinematic Product Entry`
- Visual Direction Approval: `OWNER_APPROVED`

这些线框只冻结信息顺序、视觉主体职责、滚动焦点和降级语义，不冻结像素尺寸、实现
技术、3D 模型、文案、组件或动效参数。

任何概念图都不是正式产品资产；不得提交机器人、机甲、动漫或游戏角色以及其他
未授权角色。复杂 Product Entry 动效不阻塞 Phase 1D 核心产品闭环。

## 2. Shared Constraints

- Product Entry 只解释 PaintPilot 并引导进入 `/paintpilot/projects`。
- 唯一主要 CTA 为 `Enter PaintPilot Workspace`。
- 不出现 Project Cards、Create Project、管理筛选器、分析仪表板或功能列表墙。
- 只使用非角色化 `Abstract Material Study` 作为视觉主体。
- 不使用机器人、机甲、动漫/游戏人物、Tarot、魔法阵或未授权 IP。
- 所有能力叙事均为未来产品方向，不表示业务功能已经实现。
- 视觉加载失败、移动降级和 reduced motion 下仍保留完整文字路径。

## 3. Desktop Hero Wireframe

```text
┌──────────────────────────────────────────────────────────────────────────────┐
│ CREATIVEDEPLOY                                      PaintPilot               │
│ Platform context                            [low-weight: View Workflow]       │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  PAINTPILOT                                      ·       ·                   │
│                                                  ·  ABSTRACT MATERIAL        │
│  Plan repaint workflows with visual                 STUDY                    │
│  understanding and human control.               ╱ polygon nodes ╲            │
│                                                resin / plaster volume         │
│  ┌──────────────────────────────────┐          light-direction line          │
│  │   ENTER PAINTPILOT WORKSPACE     │                ·      ·                 │
│  └──────────────────────────────────┘                                       │
│                                                                              │
│                                                                              │
│  PaintPilot is under active development.                                    │
└──────────────────────────────────────────────────────────────────────────────┘
```

- 大标题、一个主要 CTA、一个视觉主体和极大留白。
- 文案位于稳定阅读层；粒子和主体不穿过文字。
- 没有项目卡片、Create Project 或功能网格。
- View Workflow 只作为低权重锚点，不与 Enter PaintPilot Workspace 竞争。

## 4. Desktop Scroll Story

四段共享同一个 Abstract Material Study。滚动只改变主体的信息层、光线和确认状态，
不替换成四张功能卡。

### 4.1 01 Capture

```text
┌──────────────────────── text focus ───────────────┬──── visual subject ──────┐
│ 01  CAPTURE                                      │ dispersed particles       │
│ Preserve the source image and inspect its input. │          ↓ focus          │
│                                                  │ input boundary appears    │
│ [CURRENT SCROLL FOCUS]                           │ material body resolves    │
├──────────────────────────────────────────────────┴────────────────────────────┤
│ Particle intensity: MEDIUM       CTA state: available, visually secondary    │
└──────────────────────────────────────────────────────────────────────────────┘
```

- 文案位置：左侧稳定列。
- 视觉变化：输入边界形成，粒子由分散转为聚焦。
- 当前焦点：Capture。
- CTA 状态：仍可进入 Workspace，但不打断当前故事。

### 4.2 02 Structure

```text
┌──────── visual subject ───────────────────────────┬──── text focus ──────────┐
│ material surface + candidate regions             │ 02  STRUCTURE            │
│  suggestion  - - - - -                           │ Refine Polygon regions.  │
│  confirmed   ━━━━━━━━━                           │ Human confirmation makes │
│ polygon nodes become visible                     │ a region authoritative.  │
│                                                  │ [CURRENT SCROLL FOCUS]   │
├──────────────────────────────────────────────────┴────────────────────────────┤
│ Particle intensity: MEDIUM-LOW   CTA state: available, visually secondary    │
└──────────────────────────────────────────────────────────────────────────────┘
```

- 文案位置：右侧稳定列。
- 视觉变化：候选边界与已确认边界使用不同文字和形状。
- 当前焦点：Structure。
- CTA 状态：可用但低权重。

### 4.3 03 Direct

```text
┌──────────────────────── text focus ───────────────┬──── visual subject ──────┐
│ 03  DIRECT                                       │       light direction →   │
│ Set style, light, shadow and highlight rules.    │   ┌──── hard light        │
│                                                  │   │ material zones         │
│ [CURRENT SCROLL FOCUS]                           │ muted pigment blocks      │
├──────────────────────────────────────────────────┴────────────────────────────┤
│ Particle intensity: LOW          CTA state: available, visually secondary    │
└──────────────────────────────────────────────────────────────────────────────┘
```

- 文案位置：左侧稳定列。
- 视觉变化：光线方向、硬边明暗和低饱和色块变化。
- 当前焦点：Direct。
- CTA 状态：可用但低权重。

### 4.4 04 Plan

```text
┌──────── visual subject ───────────────────────────┬──── text focus ──────────┐
│ knowledge · citation · inventory signals         │ 04  PLAN                 │
│          ↓                                       │ Build a reviewable       │
│  01 ━ 02 ━ 03 structured steps                  │ painting plan.           │
│          ↓ HUMAN REVIEW                          │ [CURRENT SCROLL FOCUS]   │
│       stable output state                        │                          │
├──────────────────────────────────────────────────┴────────────────────────────┤
│ Particle intensity: LOW          CTA state: prepares final emphasis          │
└──────────────────────────────────────────────────────────────────────────────┘
```

- 文案位置：右侧稳定列。
- 视觉变化：节点收敛为结构化步骤，Citation、库存和 Human Review 信号出现。
- 当前焦点：Plan。
- CTA 状态：准备进入最终强调。

### 4.5 Final CTA

```text
┌──────────────────────────────────────────────────────────────────────────────┐
│                      READY TO ENTER THE WORKSPACE                            │
│            Explore projects and begin a planning workflow.                  │
│                                                                              │
│                ┌────────────────────────────────────┐                        │
│                │ ENTER PAINTPILOT WORKSPACE         │                        │
│                └────────────────────────────────────┘                        │
│                                                                              │
│                    PaintPilot is under active development.                   │
└──────────────────────────────────────────────────────────────────────────────┘
```

最终区域只收束到 `/paintpilot/projects`，不展示项目预览或直接创建项目。

## 5. Mobile Hero Wireframe

```text
┌──────────────────────────────┐
│ CREATIVEDEPLOY · PAINTPILOT  │
├──────────────────────────────┤
│                              │
│ PAINTPILOT                   │
│                              │
│ Plan repaint workflows with  │
│ visual understanding and     │
│ human control.               │
│                              │
│ ┌──────────────────────────┐ │
│ │ ENTER PAINTPILOT         │ │
│ │ WORKSPACE                │ │
│ └──────────────────────────┘ │
│                              │
│  simplified material study  │
│       · polygon nodes       │
│       static light line     │
│                              │
│ Under active development.   │
└──────────────────────────────┘
```

- 单列，文案和 CTA 先于复杂视觉。
- 视觉主体缩减为静态或轻量材质体，不挤压首屏。
- 没有横向滚动、Project Cards、Create Project 或密集导航。

## 6. Mobile Narrative

移动端使用单列顺序：

```text
01 CAPTURE
[short text]
[simplified input-boundary visual]

02 STRUCTURE
[short text]
[suggestion / confirmed boundary visual]

03 DIRECT
[short text]
[static light and material-zone visual]

04 PLAN
[short text]
[structured steps + Human Review visual]

[ENTER PAINTPILOT WORKSPACE]
```

| Step | Content order | Motion downgrade | Reduced-motion state |
| --- | --- | --- | --- |
| Capture | 文案 → 输入边界视觉 | 粒子数量降低，只做一次聚焦 | 静态输入边界 |
| Structure | 文案 → 区域视觉 | 节点短淡入，无连续描边 | 候选/确认边界并列 |
| Direct | 文案 → 光线视觉 | 不使用拖拽或自由旋转 | 静态光线与明暗分区 |
| Plan | 文案 → 步骤视觉 | 节点一次收敛，不循环 | 静态步骤与 Review 信号 |

移动端不要求 3D、hover、精确指针或固定滚动控制。CTA 在 Hero 和最终收束处均可
键盘与触摸访问，但不在同一视区重复。

## 7. Transition to Projects Workspace

点击 Enter PaintPilot Workspace 后：

1. Abstract Material Study 轻微后退；
2. 页面使用有限景深向前推进；
3. Brand Experience Layer 与连续粒子淡出；
4. `/paintpilot/projects` 的稳定 Workspace Header 和项目区域进入；
5. Projects Workspace 不继承大型互动主体或四步滚动故事。

Reduced motion：

- 不执行后退、视差或景深推进；
- 使用短淡出 / 淡入或直接导航；
- 焦点移动到 Projects Workspace 的页面标题；
- 路由变化不依赖动画才能被理解。

## 8. Visual and Interaction States

- **Visual loading:** 先显示标题、说明和 CTA；主体区域使用稳定中性占位。
- **Visual unavailable:** 保留全部文字和导航，说明互动视觉暂不可用。
- **Low-performance mode:** 使用静态渐变、节点背景和材质轮廓。
- **Reduced motion:** 四个最终状态按文档顺序直接呈现。
- **Keyboard:** View Workflow 与 Enter PaintPilot Workspace 均可聚焦；滚动故事不
  劫持焦点。
- **Screen reader:** 读取四步文本，不逐个朗读装饰粒子或 Polygon 节点。

## 9. Approved Concept Freeze

- Desktop / Mobile 使用 spacious、low-density、single-primary-action 结构。
- Abstract Material Study 保持非角色化。
- Capture / Structure / Direct / Plan 共享同一主体。
- Enter PaintPilot Workspace 是唯一主要 CTA。
- Reduced motion 保留相同内容顺序和静态理解路径。
- 概念图只确认视觉方向，不是正式资产，不进入产品或公开仓库。
- 所有页面、动效和业务能力仍为 `NOT_STARTED`。

## 10. Deferred Implementation Decisions

1. 确认最终 Token、字体和具体断点。
2. 在核心产品流程后评估复杂粒子和滚动叙事排期。
3. 通过实际设备测量决定 Canvas 2D / 2.5D 或后续 WebGL 原型。
