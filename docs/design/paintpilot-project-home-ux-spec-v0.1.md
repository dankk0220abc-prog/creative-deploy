# PaintPilot Projects Workspace UX Specification v0.1

## 1. Document Status

- Status: `OWNER_APPROVED`
- Version: `0.1.0`
- Implementation Status: `NOT_STARTED`
- Approval Date: `2026-07-24`
- Direction Status: `OWNER_APPROVED`
- Visual Direction: `OWNER_APPROVED`
- Direction Name: `Nocturne Studio`
- Layout Direction: `Spacious Editorial`
- Layout Direction Status: `OWNER_APPROVED`
- Workspace Direction: `Spacious Application Workspace`
- Workspace Direction Status: `OWNER_APPROVED`
- Product Surface: `PaintPilot Projects Workspace`
- Route: `/paintpilot/projects`
- Experience Layer: `Application Layer`
- Related Product Entry: `paintpilot-product-entry-ux-spec-v0.1.md`
- Related Visual Direction: `paintpilot-visual-direction-v0.1.md`
- Decision Authority: `Project Owner`

本文档冻结已批准的 UX 结构，不代表 PaintProject、项目列表、创建项目、图片或业务 API
已经实现。

## 2. Page Purpose

帮助用户查看已有 Paint Project，或开始创建一个 Paint Project。

这是页面唯一主任务。Knowledge、Inventory、Trace、Evaluations 和其他未来能力不能
与该任务争夺首屏注意力。完整品牌介绍、互动视觉主体和四步滚动产品故事属于
`/paintpilot` Product Entry，不在本 Workspace 重复。

## 3. User Goals

用户应能：

1. 查看已有项目，而不是从通用平台页面猜测当前产品空间。
2. 通过可读文字识别项目的当前工作流状态。
3. 发现并启动 Create Project。
4. 进入已有项目的当前有效版本。
5. 理解 PaintPilot 当前只完成 Foundation，业务能力仍处于规划或后续实现阶段。
6. 在没有项目、服务不可用或动作尚未开放时获得诚实且可操作的说明。

## 4. Product and Capability Boundary

- CreativeDeploy 是平台外壳；PaintPilot 是当前 Featured Deployment。
- `/paintpilot` Product Entry 负责品牌、产品价值和 Capture / Structure / Direct /
  Plan 滚动叙事。
- `/paintpilot/projects` Projects Workspace 只负责项目查看、创建入口、状态和打开项目。
- Projects Workspace 只显示 PaintPilot 项目，不展示 Arcana 项目或 Arcana 入口。
- Foundation health dashboard 不是最终 Projects Workspace，也不能作为已有业务项目证据。
- 未实现的页面或数据不得使用可点击导航、虚假成功状态或未标注演示记录伪装。
- 当前工作坊不实现列表、创建、上传、AI、RAG、Polygon、审批或 Trace。
- Human Review 在未来工作流中是阻塞 Gate；界面不得暗示模型可以自行批准。
- Projects Workspace 不承担产品完整介绍、大型互动视觉、滚动产品故事或平台能力墙。

## 5. Information Architecture

以下 Spacious Editorial 结构由项目所有者确认。不使用大型永久侧边栏：

1. **Compact Platform Header**
   - CreativeDeploy 品牌、当前产品上下文和最小环境位置预留。
2. **PaintPilot Workspace Header**
   - 简短 Workspace 标题、当前位置和少量环境粒子，不复述完整品牌故事。
3. **Create Project CTA**
   - 进入独立 `/paintpilot/projects/new`；每种模式只有一个主要创建入口。
4. **Your Projects**
   - 只显示真实 Paint Project，不建立单独 Recent 模块。
5. **Large Project Cards**
   - 暗色雾面宽松网格；桌面首屏最多 3 张。
6. **Capability Boundary**
   - 使用一条短文本或小面板说明当前 build 与 planning-only 边界。

Planned Feature Navigation 不属于首屏结构。Knowledge、Inventory、Trace 和
Evaluations 默认隐藏；如必须提及，只能在克制的 Capability Boundary 中标记
`PLANNED`。

## 6. Primary Visual Modes

### 6.1 Empty Mode

- 使用稳定深色 Nocturne Workspace 和低强度环境粒子。
- 首屏只包含 Compact Platform Header、Workspace 标题、一句短说明、一个大型 Create
  Project、抽象粒子、`No projects yet` 和一条克制 Capability Boundary。
- Create Project 是唯一主要动作和第一视觉焦点。
- 不使用 Product Entry 的 Abstract Material Study、连续滚动叙事或中高强度景深。
- 不显示虚假用户项目、项目数量、完成状态或 AI 结果。
- 不显示 Project Card、Future Modules、Arcana、Tarot、多个功能板块或大量 Badge。
- Create Project 未实现时必须明确标记当前 build 不可用。

### 6.2 Active Projects Mode

- Workspace Header 只保留低强度环境粒子，项目网格区域保持稳定。
- Workspace 标题、短说明和一个 Create Project CTA 位于项目内容之前。
- `Your Projects` Gallery 成为视觉中心，桌面首屏最多 3 张大型卡片。
- 项目更多时通过页面滚动或后续 `View all` 进入完整列表。
- Create Project 保持容易发现，不与大型 Future Modules 或统计面板竞争。
- 卡片标题、状态和 review gate 默认可见，不等待 hover。

## 7. Navigation

### 7.1 Active Navigation

| Item | Role | Behavior |
| --- | --- | --- |
| CreativeDeploy | Platform home / identity | 返回平台入口；本阶段只定义位置 |
| PaintPilot | Product identity | 返回 `/paintpilot` Product Entry |
| Projects | Current section | 当前 `/paintpilot/projects`，不做重复跳转 |
| Create Project | Primary task | 规划路由 `/paintpilot/projects/new`；功能仍待实现 |

PaintPilot 作为可返回 Product Entry 的产品身份出现，不形成额外功能菜单。除品牌
返回入口外，Workspace 当前最多显示 Projects 和 Create Project。

### 7.2 Planned Navigation

以下项默认隐藏，只可在后续阶段或克制的 Capability Boundary 中标记：

- Knowledge — `PLANNED`
- Inventory — `PLANNED`
- Trace — `PLANNED`
- Evaluations — `PLANNED`

它们不得成为首版常驻明显导航，不使用 enabled hover、当前数量、成功状态、模块面板
或示例结果。Arcana 是 CreativeDeploy 平台级未来部署，不进入 PaintPilot Workspace
导航。

## 8. Project Card

### 8.1 First-release Display Fields

首版卡片默认展示以下五个字段。任何尚无后端事实的字段必须显示诚实缺失状态，不得
由客户端或模型猜测：

| Field | UX purpose | First-release behavior | Source boundary |
| --- | --- | --- | --- |
| Project title | 识别项目 | 始终显示 | PaintProject.title |
| Cover image or placeholder | 视觉识别 | 无真实图片时显示中性 placeholder | 只使用真实 ImageAsset；placeholder 不冒充资产 |
| Workflow state | 识别可继续动作 | 始终显示受控状态文字 | 程序和数据库状态 |
| Updated time | 区分最近工作 | 显示相对时间并可访问精确时间 | PaintProject.updated_at |
| Current review gate | 提醒人工动作 | 无当前 Gate 时显示 `No active review gate` | 从状态与有效 Approval 确定性推导 |

Target style 是可选次级信息：概念稿需要比较“默认显示一行”与“hover / focus 后
显示”两种方案。移动端不能依赖 hover；如果空间不足，应延后到项目详情。

首版卡片不展示以下数据，统一标记为 `FUTURE_METADATA`：

- cost
- token usage
- trace count
- image count
- full version history
- evaluation score
- long description

### 8.2 Dark Matte Card Requirements

- 默认状态必须可读，标题、workflow state 和 review gate 始终可见。
- 状态同时使用文字和有限图形，不只依赖颜色。
- 图片区域与文字区域使用稳定层级，不让图片、粒子或渐变压低文字对比度。
- hover 只增加轻微图片缩放、有限视差和柔和边缘高光。
- 不使用大角度旋转、高强度玻璃拟态或持续漂浮。
- 移动端不依赖 hover；所有信息和主要动作默认可见。
- 粒子集中在 Header 和 Create Project，不覆盖卡片关键信息。

### 8.3 Card Interaction

- 整张卡片可作为进入项目的 link，但内部独立动作不能产生嵌套交互冲突。
- 标题、状态和更新时间在没有图片时仍可理解。
- hover 不是唯一可用信号；focus-visible 和触摸 pressed 状态同样明确。
- 状态使用文字和图形，不把红、黄、绿作为唯一表达。
- 未来出现 `IMAGE_REVIEW_REQUIRED`、`REGION_REVIEW_REQUIRED` 或
  `PLAN_REVIEW_REQUIRED` 时，卡片应显示 “Human review required”，但不能自动声称
  review 已批准。
- 终态 `COMPLETED`、`FAILED_FINAL`、`ABANDONED` 需要不同文字语义，不能都归为
  “Done”。

### 8.4 Information Density

- 首版使用规整的大图 Gallery 密度，默认只显示五个主要字段。
- 不加入 cost、token、Trace 和评测等工程指标造成信息噪声。
- 桌面首屏最多 3 张大型卡片，移动端一次主要展示 1 张。
- 卡片之间保留明显间隔，不用缩小卡片来填满视口。
- 当项目数量和真实使用证据增加后，再评估 Compact 或 View All 模式。

## 9. Create Project Entry

- Create Project 进入独立沉浸式页面，不在首页打开复杂内联表单。
- 规划路由为 `/paintpilot/projects/new`。
- 主入口使用明确的 `Create project` 文案，不只使用加号。
- Empty Mode 使用一个大型 CTA；Active Projects Mode 使用一个清晰的 Header CTA。
- 同一视觉区域不重复放置同权重 Create Project 卡片。
- 如果创建 API 尚未实现，入口必须显示 `Not available in this build` 或处于明确的
  planned 状态；不能产生虚假项目。
- 入口不预填虚假图片、AI 分析结果或材料信息。
- 后续实现需要在提交前说明项目初始状态是 `DRAFT`。

## 10. Empty State

没有真实项目时，Workspace 仍需具有 PaintPilot 的视觉连续性：

- 使用宽松、稳定的暗色 Nocturne 环境、Workspace 标题、一句简短说明和一个大型
  Create Project。
- 磁场粒子或抽象节点可以围绕入口低速聚合，但不覆盖文字和按钮。
- 不使用大型材质研究体或完整 Capture / Structure / Direct / Plan 叙事。
- 显示 “No paint projects yet”，不显示虚构项目数量或活动。
- 不显示 Project Card、Future Modules、Arcana、Tarot 或多个功能介绍板块。
- 不使用 Demo Project 冒充用户数据。
- 能力边界说明 PaintPilot 当前是 planning-only 工具，不保证真实涂装结果。

## 11. Loading, Loaded, Empty and Failure States

| State | User-facing behavior | Primary action | Prohibited behavior |
| --- | --- | --- | --- |
| Loading projects | 保留页面标题和 Create Project 位置；项目区显示有限 skeleton；使用 `aria-busy` | 等待或取消导航 | 无限 shimmer、布局跳动、虚假卡片文字 |
| Projects loaded | 显示真实项目数量与卡片 | Open project / Create project | 展示客户端猜测状态 |
| No projects | 显示真实 Empty State | Create project | 伪造演示项目 |
| API unavailable | 页面外壳保持可用，说明项目服务暂不可用 | Retry projects | 显示原始 fetch 异常或 stack trace |
| Database unavailable | 说明项目数据暂不可用；不把 API 整体误报为失败 | Retry projects | 显示连接地址、密码或数据库异常 |
| Create action unavailable | 保留项目浏览；解释当前 build 未开放创建 | Return / view projects | 点击后假成功或创建本地假记录 |
| Reduced motion | 关闭粒子、视差和景深推进 | 所有动作保持可用 | 依赖动画才能找到 CTA 或理解状态 |

错误区需要稳定错误语义、重试动作和安全说明。当前 UX 规划不定义具体业务 API 或
错误码。

## 12. Responsive Behavior

### 12.1 Desktop

- Projects Workspace 使用深色 Compact Platform / Workspace Header 与暗色雾面
  Gallery；暖灰画布保留给未来 Precision Workspace。
- 内容使用有最大宽度的编辑式布局。
- 首屏最多三张大图卡片，卡片之间保留明显间隔。
- 项目更多时通过滚动或后续 View All 进入完整列表。
- Create Project 使用一个 Header CTA，不在同屏重复大型入口。
- 粒子只位于 Header、Empty State 或 Create 入口附近。

### 12.2 Tablet

- Header 简化为品牌、当前产品和主 CTA。
- Project Grid 在空间允许时两列，否则单列。
- 辅助描述可缩短，但状态文字和更新时间不隐藏。
- 不显示常驻 Planned Navigation 或拥挤横向菜单。

### 12.3 Mobile

- 项目卡片改为单列，大图比例降低以保证状态和 CTA 可见。
- 一次主要展示一张卡片，保持卡片高度和文字留白。
- Create Project 保持首屏或紧随产品标题可见。
- 不出现横向滚动；长标题可换行但不被截断为不可理解文本。
- 触摸动作不依赖 hover，状态信息默认可见。
- 低性能移动设备关闭或大幅降低粒子数量、视差和模糊滤镜。
- 页面底部不设置遮挡系统浏览器控件的固定 CTA。

## 13. Precision Workspace Transition

未来从 Projects Workspace 打开项目并进入 `/paintpilot/projects/:projectId` 时：

- Nocturne Studio 深色平台外壳继续保留，维持 CreativeDeploy / PaintPilot 上下文。
- 中央图片和 Polygon 主画布切换为 `canvas-neutral` 暖灰背景。
- Header 与 Create 区域粒子淡出；Polygon 精确编辑区关闭背景粒子和视差。
- 工具、状态、Human Review 和 Trace 面板保持暗色稳定表面。
- 颜料比较允许切换中性浅灰与深灰观察背景，但必须明确当前背景模式。
- 图片和颜料颜色判断不应被高饱和环境光、覆盖渐变或背景颜色污染。
- 进入 Workspace 的动效完成后，所有精确区域位置保持稳定。

## 14. Accessibility

- 所有导航和动作支持键盘 Tab 顺序。
- 使用明确的 `:focus-visible`，不只改变背景色。
- Project Card 必须有可聚焦 link；内部按钮保持独立可访问名称。
- 状态同时显示文字、图标/形状和必要说明，不只靠颜色。
- 动效遵循 `prefers-reduced-motion`，且提供没有动画的等价理解路径。
- 项目图片使用描述内容和用途的 alt；装饰性纹理使用空 alt 或 CSS。
- 动作使用语义化 `button` 或 `a`，不使用无语义 `div` 模拟。
- 正文和交互文字目标达到 WCAG AA 对比度；状态色组合实施时逐项验证。
- 常用触摸目标建议至少约 `44 × 44 CSS px`。
- Loading、error 和更新后的项目数量需要合适的 live-region 策略，避免重复播报。
- 卡片阅读顺序与视觉顺序一致；空间层次不能改变 DOM 语义顺序。

## 15. Human-review Visibility

未来 Human Review 信息必须：

- 使用 `Review required` 等直接文字，不使用 AI confidence 替代用户决定；
- 指向确切的当前版本或 Gate；
- 区分 image supplemental review、region review 和 plan review；
- 不把模型建议标记为 approved；
- 在卡片密度不足时提供状态摘要，进入项目后展示完整原因和可用动作。

当前 Phase 1C Projects Workspace Slice 不要求实现这些 Gate，只预留可扩展位置。

## 16. Analytics / Evidence Event Candidates

以下只是后续埋点候选，不在本阶段实现：

- `projects_workspace_viewed`
- `create_project_started`
- `project_opened`
- `retry_projects_requested`
- `empty_state_cta_clicked`

未来实施前需补充事件目的、触发时机、字段最小化、Principal/项目隐私边界和测试
方法。不得记录图片内容、Secret、完整错误或不必要的个人信息。

## 17. Future Component Candidates

- `Button`
- `ProjectCard`
- `StatusBadge`
- `PageHeader`
- `EmptyState`
- `MotionSurface`

这些是未来实现候选，不在工作坊中创建组件、Token Package、Storybook 或 UI Library。

## 18. Owner Decisions Required

1. 在 Product Entry 视觉评审后复核 Workspace 的桌面 Empty / Active 比例。
2. 复核移动端单列卡片、Create Project 位置和低强度动效。
3. 确认具体 Color Token 与字体组合。
4. 确认粒子技术方案和设备性能降级规则。
5. 评审 `/paintpilot/projects/new` Create Project 详细线框。
