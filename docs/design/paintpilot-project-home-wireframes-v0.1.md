# PaintPilot Projects Workspace Wireframes v0.1

## 1. Document Status

- Status: `OWNER_APPROVED`
- Version: `0.1.0`
- Implementation Status: `NOT_STARTED`
- Approval Date: `2026-07-24`
- Direction Status: `OWNER_APPROVED`
- Surface: `PaintPilot Projects Workspace`
- Route: `/paintpilot/projects`
- Experience Layer: `Application Layer`
- Visual Direction: `OWNER_APPROVED`
- Direction Name: `Nocturne Studio`
- Layout Direction: `Spacious Editorial`
- Layout Direction State: `OWNER_APPROVED`
- Workspace Direction: `OWNER_APPROVED`
- Visual Mockup: `DIRECTION_APPROVED_IMPLEMENTATION_NOT_STARTED`

这些 ASCII Wireframe 用于比较信息层级与体验方向，不代表布局尺寸、组件、数据或动效
已经实现。本文档只负责 `/paintpilot/projects`；完整 Hero、Abstract Material Study
和 Capture / Structure / Direct / Plan 滚动故事由 Product Entry 文档负责。所有项目
内容必须来自未来真实业务数据；示意标签不构成 Demo Project。

## 2. Shared Constraints

- CreativeDeploy 是平台外壳，PaintPilot 是当前 Featured Deployment。
- Arcana 不出现在 PaintPilot Projects Workspace。
- Projects Workspace 使用深色 Nocturne 环境和暗色雾面 Gallery；暖灰画布只用于
  后续 Precision Workspace，不使用全黑页面。
- Create Project 始终可发现，但创建功能未实现时必须明确标记。
- 项目状态来自程序事实；模型建议和 Human Review 不得混写。
- Project Card 使用大尺寸图片或诚实 placeholder，不伪造用户资产。
- 无大型常驻侧边栏。
- 未来 Knowledge、Inventory、Trace、Evaluations 默认隐藏；如被提及只能标记
  `PLANNED`，不能成为常驻导航或模块面板。
- 不使用 Product Entry 的大型互动视觉主体、完整品牌叙事或四步滚动故事。
- Workspace 动效保持中低强度：少量 Header 粒子、轻微卡片反馈和短页面切换。
- 所有动效均提供 reduced-motion 等价路径。

## 3. Option A — Editorial Project Gallery

`HISTORICAL_SUPERSEDED_NOT_WORKSPACE_BASIS`

### 3.1 Concept

以大型项目图片、编辑式留白和稳定卡片网格为核心。深色产品框架负责品牌与导航，
浅色画布负责长时间工作。Create Project 是与真实项目并列的大型卡片。

### 3.2 Desktop ASCII Wireframe

```text
┌──────────────────────────────────────────────────────────────────────────────┐
│ CREATIVEDEPLOY      PaintPilot / Projects        [Status] [Create project]  │
│ Platform shell                                             primary action    │
├──────────────────────────────────────────────────────────────────────────────┤
│ PAINTPILOT                                                                  │
│ Plan controllable repaint projects with visible human review.               │
│                                                     subtle node field  · ·   │
├──────────────────────── warm content canvas ─────────────────────────────────┤
│                                                                              │
│ Recent projects                                        [View: Comfortable]   │
│                                                                              │
│ ┌────────────────────────────────┐  ┌────────────────────────────────┐       │
│ │                                │  │                                │       │
│ │  REAL COVER OR PLACEHOLDER     │  │  REAL COVER OR PLACEHOLDER     │       │
│ │                                │  │                                │       │
│ ├────────────────────────────────┤  ├────────────────────────────────┤       │
│ │ Project title       [DRAFT]    │  │ Project title  [REVIEW NEEDED] │       │
│ │ Short description              │  │ Short description              │       │
│ │ Updated <real time>             │  │ Updated <real time>             │       │
│ └────────────────────────────────┘  └────────────────────────────────┘       │
│                                                                              │
│ ┌────────────────────────────────┐  ┌────────────────────────────────┐       │
│ │              · ·               │  │                                │       │
│ │         + Create project       │  │  NEXT REAL PROJECT             │       │
│ │     Start with title + intent  │  │  OR EMPTY GRID SPACE           │       │
│ │              · ·               │  │                                │       │
│ └────────────────────────────────┘  └────────────────────────────────┘       │
│                                                                              │
│ Foundation complete · Business features are not implemented in this build.  │
└──────────────────────────────────────────────────────────────────────────────┘
```

The labels `Project title` and `NEXT REAL PROJECT` describe layout slots only. An actual
screen must render real data or the Empty State, never these placeholders as user projects.

### 3.3 Mobile ASCII Wireframe

```text
┌──────────────────────────────┐
│ CREATIVEDEPLOY               │
│ PaintPilot / Projects        │
├──────────────────────────────┤
│ PAINTPILOT                   │
│ Repaint planning with        │
│ visible human review.        │
│                              │
│ [ Create project ]           │
├──── warm content canvas ─────┤
│ Recent projects              │
│                              │
│ ┌──────────────────────────┐ │
│ │ REAL COVER / PLACEHOLDER │ │
│ ├──────────────────────────┤ │
│ │ Project title            │ │
│ │ [DRAFT] · Updated time   │ │
│ │ Short description        │ │
│ └──────────────────────────┘ │
│                              │
│ ┌──────────────────────────┐ │
│ │      + Create project    │ │
│ │  Start with title        │ │
│ └──────────────────────────┘ │
│                              │
│ Foundation capability note  │
└──────────────────────────────┘
```

### 3.4 Page Sections

1. Compact Platform Header.
2. PaintPilot Product Header with quiet node field.
3. Recent Projects heading and optional density control.
4. Large Project Grid.
5. Large Create Project card.
6. Capability boundary footer.

### 3.5 Attention and Interaction

- **First sight:** PaintPilot title, then the first real project image.
- **Create Project:** Primary Header button and one large Grid card.
- **Project layout:** Two large columns on desktop; single column on mobile.
- **Particles:** Limited to Product Header and Create card perimeter.
- **Motion:** Cards enter in reading order; image hover uses slight scale; status remains visible.

### 3.6 Advantages

- Strong professionalism and clear information hierarchy.
- Large imagery supports a visual craft workflow without hiding operational state.
- Easy to understand with keyboard, touch and reduced motion.
- Adapts naturally to future project counts and Polygon Editor entry.
- More reusable within the CreativeDeploy platform shell.

### 3.7 Disadvantages

- Less theatrical than a spatial product gateway.
- Requires careful art direction to avoid looking like a generic portfolio gallery.
- Dual Create entry may feel repetitive if visual hierarchy is not tuned.

### 3.8 Implementation and Risk

- **Implementation complexity:** Medium.
- **Performance risk:** Low to medium; dominated by project-image loading and optional small
  particle field.
- **Accessibility risk:** Low if card links, focus order and state text follow the UX spec.
- **PaintPilot suitability:** High.

## 4. Option B — Immersive Studio Gateway

`HISTORICAL_SUPERSEDED_NOT_WORKSPACE_BASIS`

Option B 的大型产品视觉和沉浸式 Gateway 已迁移为独立 Product Entry 的设计问题，
不得作为 Projects Workspace 的当前结构或 Render Brief 依据。

### 4.1 Concept

入口首先建立空间和创作仪式感：抽象节点形成轻微磁场，最近项目以景深层次出现，
Create Project 成为中心动作。下方仍提供清晰、稳定的项目列表，避免体验退化为纯
视觉展示。

### 4.2 Desktop ASCII Wireframe

```text
┌──────────────────────────────────────────────────────────────────────────────┐
│ CREATIVEDEPLOY                    PaintPilot                    [Projects]    │
├────────────────── deep PaintPilot gateway / spatial field ──────────────────┤
│                                                                              │
│       · image node                         knowledge node ·                   │
│                ╲                           ╱                                 │
│                 ╲     PAINTPILOT          ╱                                  │
│                  ·  Build a paint plan.  ·                                   │
│                 ╱  Keep human control.    ╲                                  │
│       · structured node               human review node ·                    │
│                                                                              │
│                       [ + Create project ]                                   │
│                                                                              │
│     ┌─────────────────────┐       ┌─────────────────────┐                    │
│     │ RECENT REAL PROJECT │       │ RECENT REAL PROJECT │                    │
│     │ image · title       │       │ image · title       │  limited depth     │
│     │ state · updated     │       │ state · updated     │  no large rotation │
│     └─────────────────────┘       └─────────────────────┘                    │
├──────────────────────── stable warm canvas ──────────────────────────────────┤
│ All projects                                                     [Retry]     │
│                                                                              │
│ ┌─────────────┬──────────────────────────┬──────────────┬──────────────────┐ │
│ │ image       │ project title            │ state        │ updated          │ │
│ ├─────────────┼──────────────────────────┼──────────────┼──────────────────┤ │
│ │ image       │ project title            │ review gate  │ updated          │ │
│ └─────────────┴──────────────────────────┴──────────────┴──────────────────┘ │
│                                                                              │
│ Foundation complete · Future capabilities remain planned.                   │
└──────────────────────────────────────────────────────────────────────────────┘
```

The “table-like” All Projects area is still made of responsive list cards with semantic links;
it is not a dense administration data grid.

### 4.3 Mobile ASCII Wireframe

```text
┌──────────────────────────────┐
│ CREATIVEDEPLOY / PaintPilot  │
├──── compact spatial field ───┤
│        ·          ·          │
│           PAINTPILOT         │
│    Build a paint plan.       │
│    Keep human control.       │
│                              │
│     [ + Create project ]     │
│        ·          ·          │
│                              │
│ ┌──────────────────────────┐ │
│ │ Recent real project     │ │
│ │ image · state · updated │ │
│ └──────────────────────────┘ │
├──── stable warm canvas ──────┤
│ All projects                 │
│                              │
│ ┌──────────────────────────┐ │
│ │ thumb  Project title    │ │
│ │        [DRAFT] · time   │ │
│ └──────────────────────────┘ │
│                              │
│ Foundation capability note  │
└──────────────────────────────┘
```

### 4.4 Page Sections

1. Minimal Platform Header.
2. Immersive PaintPilot gateway.
3. Central Create Project action.
4. Spatial Recent Projects layer.
5. Stable All Projects list on warm canvas.
6. Capability boundary footer.

### 4.5 Attention and Interaction

- **First sight:** Central PaintPilot statement and Create Project.
- **Create Project:** One primary central entrance with stronger ceremony.
- **Project layout:** Recent projects in shallow spatial layer; all projects remain in a
  conventional responsive list.
- **Particles:** Confined to gateway; no particles over the project list.
- **Motion:** Depth entrance, node aggregation and recent-card parallax; no large rotation.

### 4.6 Advantages

- Strong visual identity and memorable first visit.
- Best expression of magnetic aggregation and CreativeDeploy multimodal nodes.
- Create Project feels like entering a focused creative workflow.
- Clear opportunity to connect platform brand motion with PaintPilot.

### 4.7 Disadvantages

- Higher risk of delaying access to existing projects.
- Recent Projects and All Projects may duplicate information.
- Mobile and reduced-motion versions require deliberate simplification.
- Can drift toward a showcase or Spline imitation if spatial effects dominate.
- Harder to maintain once project lists become the frequent daily task.

### 4.8 Implementation and Risk

- **Implementation complexity:** High.
- **Performance risk:** Medium to high; particles, blur, layered images and parallax need
  budgets and low-performance fallbacks.
- **Accessibility risk:** Medium; visual depth must not alter DOM order or hide state.
- **PaintPilot suitability:** Medium-high as an occasional gateway, lower for repetitive
  operational use.

## 5. Option C — Nocturne Editorial Studio

### 5.1 Confirmed Fusion

`SUPERSEDED_BY_OPTION_C2`

Option C 记录上一轮 Nocturne 融合方案，保留为决策历史。它的信息密度、重复入口和
Product / Application 职责混合已被用户否决，不得作为当前 Render Brief 或实施依据。
当前确认的 Projects Workspace 布局见 Option C2。

Option C 使用 Option B 的暗色品牌环境、磁场粒子与有限景深，同时使用 Option A 的
规整项目网格、信息层级、移动适配和日常扫描效率。项目卡片是暗色雾面表面；Header
与 Empty Mode 允许中高强度粒子，项目网格区域粒子必须收敛。

Desktop、Tablet 与 Mobile 都保持相同信息顺序，不使用完全漂浮或难以扫描的卡片。
以下线框冻结结构，不冻结像素尺寸、视觉稿、CSS 或粒子实现方案。

### 5.2 Desktop Empty Mode ASCII Wireframe

```text
┌──────────────────────────────────────────────────────────────────────────────┐
│ [PLATFORM HEADER] CREATIVEDEPLOY          PaintPilot        Projects        │
├────────────────────────── Nocturne Studio shell ────────────────────────────┤
│ [PAINTPILOT HEADER]                                                        │
│ PAINTPILOT · Controllable repaint planning with visible human review        │
│                                                                              │
│ [PARTICLE FIELD]       · image       · structured       · review            │
│                                  ╲   │   ╱                                  │
│                           NO PAINT PROJECTS YET                              │
│                        Build your first planning project.                    │
│                         [ + CREATE PROJECT ]                                 │
│                                  ╱   │   ╲                                  │
│                         · pigment       · polygon                            │
│                                                                              │
│ [PROJECT CARDS] None — no fake project data                                 │
├──────────────────────── stable capability area ──────────────────────────────┤
│ [CAPABILITY BOUNDARY] Foundation is complete. Business features are not     │
│ implemented in this build. Planning-only; no repaint-result guarantee.      │
│ [PLANNED NAVIGATION] Knowledge · Inventory · Trace · Evaluations [PLANNED]  │
└──────────────────────────────────────────────────────────────────────────────┘
```

### 5.3 Desktop Active Projects ASCII Wireframe

```text
┌──────────────────────────────────────────────────────────────────────────────┐
│ [PLATFORM HEADER] CREATIVEDEPLOY          PaintPilot        Projects        │
├────────────────────────── Nocturne Studio shell ────────────────────────────┤
│ [PAINTPILOT HEADER] PAINTPILOT                    [ + CREATE PROJECT ]       │
│ Planning workspace · visible human review         [PARTICLE FIELD] · · ·    │
├──────────────────────── dark matte gallery ──────────────────────────────────┤
│ Recent projects                                                             │
│                                                                              │
│ [PROJECT CARDS]                                                             │
│ ┌────────────────────────────────┐  ┌────────────────────────────────┐       │
│ │ REAL COVER / PLACEHOLDER       │  │ REAL COVER / PLACEHOLDER       │       │
│ ├────────────────────────────────┤  ├────────────────────────────────┤       │
│ │ Project title                  │  │ Project title                  │       │
│ │ [WORKFLOW STATE]               │  │ [WORKFLOW STATE]               │       │
│ │ Style · Review gate · Updated  │  │ Style · Review gate · Updated  │       │
│ └────────────────────────────────┘  └────────────────────────────────┘       │
│                                                                              │
│ ┌────────────────────────────────┐  ┌────────────────────────────────┐       │
│ │ REAL PROJECT CARD              │  │ [ + NEW PROJECT CARD ]         │       │
│ │ title · state · gate · time    │  │ Enter standalone create flow  │       │
│ └────────────────────────────────┘  └────────────────────────────────┘       │
│                  project grid particle intensity: near zero                 │
├──────────────────────────────────────────────────────────────────────────────┤
│ [CAPABILITY BOUNDARY] Only implemented facts may appear as available.       │
│ [PLANNED NAVIGATION] Knowledge · Inventory · Trace · Evaluations [PLANNED]  │
└──────────────────────────────────────────────────────────────────────────────┘
```

### 5.4 Mobile Empty Mode ASCII Wireframe

```text
┌──────────────────────────────┐
│ [PLATFORM HEADER]            │
│ CREATIVEDEPLOY               │
│ PaintPilot / Projects        │
├──────────────────────────────┤
│ [PAINTPILOT HEADER]          │
│ PAINTPILOT                   │
│ Repaint planning with        │
│ visible human review.        │
│                              │
│ [PARTICLE FIELD] ·   ·       │
│          ╲   │   ╱           │
│   NO PAINT PROJECTS YET      │
│   [ + CREATE PROJECT ]       │
│          ╱   │   ╲           │
│          ·       ·           │
│                              │
│ [PROJECT CARDS] None         │
│ No fake project data         │
├──────────────────────────────┤
│ [CAPABILITY BOUNDARY]        │
│ Foundation only in this      │
│ build.                       │
│ [PLANNED NAVIGATION]         │
│ Knowledge · Inventory        │
│ Trace · Evaluations          │
└──────────────────────────────┘
```

### 5.5 Mobile Active Projects ASCII Wireframe

```text
┌──────────────────────────────┐
│ [PLATFORM HEADER]            │
│ CREATIVEDEPLOY               │
│ PaintPilot / Projects        │
├──────────────────────────────┤
│ [PAINTPILOT HEADER]          │
│ PAINTPILOT          · ·      │
│ [ + CREATE PROJECT ]         │
│ [PARTICLE FIELD: reduced]    │
├──────────────────────────────┤
│ Recent projects              │
│ [PROJECT CARDS: one column]  │
│ ┌──────────────────────────┐ │
│ │ REAL COVER / PLACEHOLDER │ │
│ ├──────────────────────────┤ │
│ │ Project title            │ │
│ │ [WORKFLOW STATE]         │ │
│ │ Style · Review gate      │ │
│ │ Updated time             │ │
│ └──────────────────────────┘ │
│                              │
│ ┌──────────────────────────┐ │
│ │ + NEW PROJECT CARD       │ │
│ └──────────────────────────┘ │
├──────────────────────────────┤
│ [CAPABILITY BOUNDARY]        │
│ [PLANNED NAVIGATION]         │
│ Knowledge · Inventory ·      │
│ Trace · Evaluations          │
└──────────────────────────────┘
```

### 5.6 Tablet Adaptation

- 保持 Platform Header → PaintPilot Header → Create / Gallery → Boundary → Planned
  Navigation 的顺序。
- Active Projects 默认两列；空间不足时切换单列。
- 粒子数量低于桌面，卡片内容不依赖 hover。
- 不引入横向滚动或漂浮项目堆叠。

### 5.7 Option C Operating Characteristics

- **First sight in Empty Mode:** PaintPilot 与 Create Project。
- **First sight in Active Mode:** 真实 Recent Projects 与其 workflow state。
- **Create Project:** Empty Mode 中央主焦点；Active Mode 顶部 CTA 加末尾 New Card。
- **Particles:** Header / Empty 区域中高强度；Gallery 区域接近零。
- **Motion:** 入口景深明显，卡片只做有限缩放与视差，进入精确 Workspace 后停止。
- **Implementation complexity:** Medium-high.
- **Performance risk:** Medium; 取决于粒子数量、模糊、图片和技术实现。
- **Accessibility:** 信息顺序稳定，reduced motion 下可完全移除空间运动。
- **PaintPilot suitability:** Very high; 已获所有者批准作为正式方向。

## 6. Option C2 — Spacious Nocturne Editorial

`OWNER_APPROVED`

`FUTURE_REFINEMENT`

C2 保留 Nocturne Studio 的暗色氛围、磁场粒子和景深，但正式降低信息密度。每个模式
只有一个最强任务；核心元素更大，项目卡片更少，垂直间距更明显。不在 Projects
Workspace 放置 Arcana、Tarot、Future Module 面板、Product Hero 或滚动产品故事。

### 6.1 Desktop Empty Mode

```text
┌──────────────────────────────────────────────────────────────────────────────┐
│ CREATIVEDEPLOY                                            Projects           │
│ Platform Header                                                              │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  PAINTPILOT PROJECTS                             ·        ·                  │
│                                                  ·   Particle Field          │
│  Plan a controllable repaint project.                 ·        ·             │
│  Keep every review decision visible.                                        │
│                                                                              │
│  No projects yet                                                            │
│                                                                              │
│  ┌───────────────────────────────┐                                           │
│  │      + CREATE PROJECT         │           abstract nodes only             │
│  └───────────────────────────────┘                                           │
│                                                                              │
│                                                                              │
│                                                                              │
│  Foundation available. PaintPilot business features are not implemented.    │
│  Capability Boundary                                                        │
└──────────────────────────────────────────────────────────────────────────────┘
```

- 一个大标题、一段短说明、一个大型 CTA。
- Project Cards：none；不伪造项目。
- 粒子位于右侧或背景，不穿过正文。
- 无 Future Modules、Arcana、Tarot 或功能图标墙。

### 6.2 Desktop Active Projects Mode

```text
┌──────────────────────────────────────────────────────────────────────────────┐
│ CREATIVEDEPLOY                                            Projects           │
│ Platform Header                                                              │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  PAINTPILOT PROJECTS                         [ + CREATE PROJECT ]            │
│  Your repaint planning workspace.                      · · Header particles  │
│                                                                              │
│                                                                              │
│  YOUR PROJECTS                                                               │
│                                                                              │
│  ┌──────────────────────┐   ┌──────────────────────┐   ┌───────────────────┐ │
│  │ AUTHORIZED COVER     │   │ NEUTRAL PLACEHOLDER │   │ NEUTRAL PLACEHOLDER│ │
│  │                      │   │                      │   │                   │ │
│  ├──────────────────────┤   ├──────────────────────┤   ├───────────────────┤ │
│  │ Project title        │   │ Project title        │   │ Project title     │ │
│  │ State · Review gate  │   │ State · Review gate  │   │ State · Gate      │ │
│  │ Updated time         │   │ Updated time         │   │ Updated time      │ │
│  └──────────────────────┘   └──────────────────────┘   └───────────────────┘ │
│                                                                              │
│                       generous gallery spacing                              │
│                                                                              │
│  Planning-only capability boundary.                                         │
└──────────────────────────────────────────────────────────────────────────────┘
```

- 首屏最多三张大型卡片。
- 只有一个 Create Project CTA，不重复 New Project Card。
- 不显示成本、Token、Trace、评测、完整历史或复杂统计。
- 项目更多时通过滚动或后续 View All 进入完整列表。

### 6.3 Mobile Empty Mode

```text
┌──────────────────────────────┐
│ CREATIVEDEPLOY               │
│ Projects                     │
├──────────────────────────────┤
│                              │
│ PAINTPILOT PROJECTS          │
│                              │
│ Plan a controllable repaint  │
│ project.                     │
│                              │
│       ·    ·                 │
│   reduced particle field     │
│          ·                   │
│                              │
│ No projects yet              │
│                              │
│ ┌──────────────────────────┐ │
│ │    + CREATE PROJECT      │ │
│ └──────────────────────────┘ │
│                              │
│                              │
│ Foundation-only boundary.    │
└──────────────────────────────┘
```

- 单列、大标题、大按钮和明显垂直间距。
- CTA 在首屏可见。
- 不出现 Project Card 或横向滚动。
- 粒子密度低于桌面。

### 6.4 Mobile Active Projects Mode

```text
┌──────────────────────────────┐
│ CREATIVEDEPLOY               │
│ Projects                     │
├──────────────────────────────┤
│                              │
│ PAINTPILOT PROJECTS          │
│ Your repaint projects.       │
│                              │
│ [ + CREATE PROJECT ]         │
│                              │
│ YOUR PROJECTS                │
│                              │
│ ┌──────────────────────────┐ │
│ │ LARGE COVER / NEUTRAL    │ │
│ │ PLACEHOLDER              │ │
│ ├──────────────────────────┤ │
│ │ Project title            │ │
│ │ State · Review gate      │ │
│ │ Updated time             │ │
│ └──────────────────────────┘ │
│                              │
│     more projects below      │
│                              │
│ Planning-only boundary.      │
└──────────────────────────────┘
```

- 首屏主要展示一张大型卡片。
- 不依赖 hover；标题、状态、review gate 和时间默认可见。
- Create Project 始终容易找到。
- 卡片之间保留充足间距，不缩小文字以堆叠内容。

### 6.5 C2 Compared with C

| Dimension | Previous Option C | Option C2 |
| --- | --- | --- |
| Content amount | Header、Gallery、重复 Create、Planned Navigation | 一个主任务、少量项目、简短 Boundary |
| Element scale | 中等卡片与多区域 | 更大标题、CTA 和 Project Card |
| First-screen cards | 多卡片和 New Project Card | Desktop 最多 3；Mobile 主要 1 |
| Whitespace | 结构完整但偏满 | 明显增加水平与垂直留白 |
| Primary action | 多处 Create 入口 | 每个模式只有一个明显 CTA |
| Cognitive load | 中等偏高 | 低 |
| Premium character | 易受信息堆叠削弱 | 通过比例、空间和材质强化 |
| Future modules | 可见 planned navigation | 从 Projects Workspace 移除 |

### 6.6 C2 Motion Boundary

- Empty Mode：粒子在大标题和 Create Project 周围形成空间，不填满空白。
- Active Mode：只保留 Header 粒子，Gallery 区域稳定。
- Card hover：轻微图片缩放、边缘高光和有限视差。
- Reduced motion：静态粒子构图、无视差、短淡入。
- Workspace：粒子淡出并切换到暖灰精确画布。

## 7. Historical Empty-state Variants

### 7.1 Option A Empty State

```text
┌──────────────────────────────────────────────────────┐
│ No paint projects yet                               │
│ Start with a title and repaint intent.              │
│                                                     │
│       · · ·     [ + Create project ]     · · ·      │
│                                                     │
│ Planning-only. No AI analysis starts at this step.  │
└──────────────────────────────────────────────────────┘
```

The Empty State replaces the project grid. It does not render sample projects.

### 7.2 Option B Empty State

```text
┌──────────────── gateway field ──────────────────────┐
│       image ·        structured ·       review ·    │
│                 ╲       │       ╱                  │
│                  [ + Create project ]               │
│                 ╱       │       ╲                  │
│              Your first project starts in DRAFT.    │
└──────────────────────────────────────────────────────┘
```

Reduced motion renders the same nodes as a static diagram with a short fade.

## 8. Comparison Matrix

Ratings are workshop judgments, not measured implementation results.

| Dimension | Option A | Option B | Option C | Option C2 — Spacious Nocturne |
| --- | --- | --- | --- | --- |
| Professionalism | High | Medium-high | Very high | Very high |
| Visual identity | High | Very high | Very high | Very high with restraint |
| Ease of use | Very high | Medium-high | High | Very high |
| Motion expression | Medium | Very high | High | High around limited content |
| Mobile adaptation | High | Medium | High | Very high |
| Accessibility | High | Medium | High | Very high with stable hierarchy |
| Implementation cost | Medium | High | Medium-high | Medium-high |
| Performance risk | Low-medium | Medium-high | Medium | Medium, fewer animated regions |
| Polygon Editor compatibility | Very high | Medium-high | Very high | Very high; neutral canvas transition |
| Brand consistency | High | High | Very high | Very high |
| Repeated daily use | Very high | Medium | High | Very high |
| Empty-state impact | High | Very high | Very high | Very high with lower cognitive load |

## 9. Confirmed Direction

**Owner-approved layout direction:** Option C2 — Spacious Nocturne Editorial.

C2 keeps Nocturne Studio's dark environment, magnetic particles and depth while reducing
content, enlarging the primary action and Project Cards, and increasing whitespace. It is the
approved Application Layer layout for `/paintpilot/projects`, not the Product Entry.

`OWNER_APPROVED`

`FUTURE_REFINEMENT`

The layout direction is approved. Final typography, particle implementation and budget, exact
spacing and rendered visual treatment remain future refinements and do not block Phase 1D.

## 10. Projects Workspace Motion Storyboard

All timings and effects remain design proposals. Workspace motion is intentionally quieter than
the Product Entry and does not carry a continuous cinematic scroll narrative.

### 10.1 Workspace Empty

1. The stable graphite Workspace appears without flashing to pure black.
2. A small number of Header particles settle once and remain unobtrusive.
3. The Workspace title and planning-only statement appear without a cinematic sequence.
4. Create Project becomes the strongest visual focus.
5. The project area remains stable and does not inherit the Product Entry visual subject.
6. The short Capability Boundary remains readable without waiting for motion.

Reduced motion: render the final layout immediately and use only a short opacity transition.

### 10.2 Existing Projects

1. Header particles remain at reduced intensity.
2. Real Project Cards enter in reading order.
3. Particles fade out before reaching the Project Gallery.
4. The grid settles into a stable, scannable layout.
5. Title, state, review gate and updated time are visible before hover; target style is optional.

Hover may slightly scale the image and add limited parallax; keyboard focus receives an
equivalent outline, and touch users see all information by default.

### 10.3 Create Project Transition

1. Nearby nodes aggregate toward the Create Project CTA.
2. The page performs a limited depth push toward `/paintpilot/projects/new`.
3. Once the form appears, environmental motion reduces sharply.
4. Input fields remain spatially stable throughout editing.
5. No image upload or AI analysis is implied at the project-creation step.

Reduced motion: replace aggregation and depth push with a direct short fade transition.

### 10.4 Open Project

1. The selected card image scales slightly inside its frame.
2. The page advances toward future `/paintpilot/projects/:projectId` without large rotation.
3. Entering the Workspace causes particles and gateway lighting to fade out.
4. The central background changes to the warm neutral precision canvas.
5. Dark tool, state and Human Review panels remain around the canvas.

Reduced motion: navigate with a short fade and display the neutral canvas immediately.

## 11. Performance, Visual and Accessibility Risks

- A dark interface can reduce long-reading comfort; use the warm neutral precision canvas,
  strong text contrast and stable dark panels.
- Particles can reduce mobile performance; lower particle count, blur and update frequency by
  device capability.
- CSS, Canvas or another particle implementation has not been selected.
- Do not build a complex particle engine before the desktop and mobile visual mockups are
  approved.
- Set a particle-count and frame-time budget before implementation.
- Disable decorative animation when the page is hidden.
- Avoid large animated blur regions on mobile.
- Lazy-load real project images and preserve card aspect ratio to prevent layout shift.
- Never reorder semantic content to match a visual depth effect.
- Test keyboard, touch, screen reader, zoom, high contrast and reduced motion.
- Precision pages do not inherit gateway particles or parallax.

## 12. Remaining Visual Review

1. After Product Entry review, verify desktop Workspace Empty and Active proportions.
2. Verify mobile Workspace Empty and Active single-column behavior.
3. Confirm final Token values and typography.
4. Confirm particle density and implementation approach.
5. Review the detailed Create Project page wireframe.
