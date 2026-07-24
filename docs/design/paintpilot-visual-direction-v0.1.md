# PaintPilot Visual Direction v0.1

## 1. Document Status

- Status: `APPROVED_FOR_IMPLEMENTATION`
- Version: `0.1.0`
- Implementation Status: `NOT_STARTED`
- Owner Approval: `APPROVED`
- Approval Date: `2026-07-24`
- Design Baseline Status: `APPROVED_FOR_IMPLEMENTATION`
- Visual Direction: `OWNER_APPROVED`
- Direction Name: `Nocturne Studio`
- Layout Direction: `Spacious Editorial`
- Layout Direction Status: `OWNER_APPROVED`
- Product Entry Concept: `OWNER_APPROVED`
- Product: `PaintPilot`
- Parent Platform: `CreativeDeploy`
- Decision Authority: `Project Owner`

本文档冻结已确认的视觉与布局方向；具体 Token、字体、组件、动效和页面实现仍是候选
或未开始状态。

## 2. Brand Relationship

CreativeDeploy 是领域中立的平台品牌，表达“可控的多模态 AI 工作流”以及图片、
文档、结构化数据和 Human Review 之间的可观察连接。PaintPilot 是当前 Featured
Deployment，也是拥有独立产品空间的专业手办重涂规划工具。

PaintPilot 可以通过颜料、材料、图片和创作过程形成自己的领域气质，但必须继续
使用 CreativeDeploy 的基本品牌语法：清晰的系统状态、明确的人工控制、稳定的操作
区域和克制的空间层次。产品主题不能让平台外壳变成游戏网站或手办品牌官网。

Arcana 是未来 Planned / Upcoming Deployment。它可以在未来复用 CreativeDeploy 的
平台设计语言，但不属于 PaintPilot Product Entry 或 Projects Workspace，不与
PaintPilot 平级出现在当前产品导航，也不能被表现为已经实现。

## 3. Experience Architecture

PaintPilot 的体验正式拆分为三个强度不同、职责不同的层级。高级感不能只通过配色、
阴影或粒子背景实现；它来自单一视觉主角、清楚的页面叙事、节奏控制、空间层次，
以及内容与动效的同步。任何页面都不得同时承担品牌展示、完整产品叙事、项目管理和
精确操作。

### 3.1 Brand Experience Layer

**Surface:** PaintPilot Product Entry

**Route:** `/paintpilot`

- 电影化、高级、极低信息密度。
- 使用四段滚动叙事和一个明确的非角色化视觉主体。
- 中高强度动效只服务品牌理解、工作流理解和页面节奏。
- 一个主要动作 `Enter PaintPilot Workspace`；品牌和产品理解优先。
- 不显示项目列表、Create Project、管理筛选器或功能卡片墙。

### 3.2 Application Layer

**Surface:** PaintPilot Projects Workspace

**Route:** `/paintpilot/projects`

- 专业、稳定、高效率，用户任务优先。
- 使用清晰、宽松的项目网格和最多三张首屏大卡片。
- 动效收敛到少量 Header 粒子、轻微卡片反馈和短页面切换。
- 只负责查看已有项目、创建新项目、查看状态和进入项目。
- 不承担完整品牌叙事、滚动产品故事或大型互动视觉展示。

Create Project 使用独立路由 `/paintpilot/projects/new`，作为 Application Layer 内的
沉浸式任务流程；它不与 Projects Workspace 弹窗或 Product Entry 混合。

### 3.3 Precision Layer

**Future surface:** Project Workspace / Polygon Editor

**Future route:** `/paintpilot/projects/:projectId`

- 使用暖灰中性画布，背景粒子关闭。
- 高精度操作、状态、工具和 Human Review 清晰可见。
- 动效只用于必要反馈，不干扰图片、Polygon、颜色或施工步骤判断。
- 当前仅冻结层级和路由边界，不表示完整 Workspace 已设计或实现。

### 3.4 Real-product Delivery Priority

CreativeDeploy / PaintPilot 的首要目标是成为真实可用、可持续迭代的产品，而不是只
用于求职演示。实现优先级冻结为：

1. PaintProject 创建与数据库持久化；
2. 项目列表与项目打开；
3. 图片上传和质量检查；
4. 区域人工确认；
5. 涂装方案工作流；
6. 完整电影化 Product Entry 动效。

Product Entry 视觉方向已经批准，但复杂粒子、滚动叙事和完整电影化动效不能阻塞
核心产品流程。求职展示必须建立在真实产品能力、测试、评测和使用证据上，不能通过
虚假功能、假数据或未实现视觉状态补足作品集叙事。

## 4. Design Principles

1. **Content before decoration.** 项目、状态和主要动作必须先于氛围效果被理解。
2. **Motion supports meaning.** 动效只表达进入、聚合、状态变化和空间层级。
3. **Creative but operational.** 页面可以有创作气质，但必须像可靠工具而不是作品集特效。
4. **Clear system status.** 状态同时使用文字、形状或图标，不只依赖颜色。
5. **Human review must be visible.** 人工确认是产品控制模型的一部分，不藏在次级界面。
6. **Precise work areas remain stable.** Polygon、表单、比较和阅读区域不使用干扰性粒子或视差。
7. **Accessibility is not optional.** 键盘、焦点、对比度、触摸目标和 reduced motion 从规划开始考虑。
8. **Do not imply unimplemented capabilities.** 未来能力必须标记为 planned 或 unavailable。

### 4.1 Fewer, Larger, Clearer

- 每个主要页面只保留一个最强主任务。
- 核心 CTA 使用明显尺寸，不与多个同权重按钮竞争。
- 不通过堆叠卡片、Badge 或模块证明功能丰富。
- 每个区域必须有清晰呼吸空间，页面不以填满屏幕为目标。

### 4.2 Hierarchy before Density

- 使用大标题、简短说明和单一主要操作建立第一层级。
- Product Entry 首屏不显示项目内容；Projects Workspace 首屏只显示少量真实项目。
- 次级字段、统计和完整历史延后到项目详情。
- 用户第一眼应能回答“我在哪里”和“下一步做什么”。

### 4.3 Atmosphere around Content

- 粒子、柔和体积光和景深存在于内容周围。
- 粒子不穿过正文、不覆盖项目数据、不用于填满留白。
- 动效用于建立空间感与状态变化，不替代信息结构。
- Project Gallery 和精确工作区保持稳定、清晰。

### 4.4 Real Content or Neutral Placeholder

- 项目图片来自用户真实项目或明确授权素材。
- 没有真实图片时使用中性几何、低饱和渐变或抽象材质占位。
- 不使用无关机器人、机甲、动漫人物、游戏角色或未授权角色填充界面。
- 占位视觉不得被描述为真实项目数据。

### 4.5 Approved Density Constraints

以下密度边界已获批准，但不表示已经实现：

- Product Entry Hero 最多一个主标题、一段短说明和一个主要 CTA，不显示 Project Card。
- Projects Workspace 桌面首屏最多展示 3 张大型 Project Card。
- Projects Workspace 移动端一次主要展示 1 张 Project Card。
- 卡片默认只显示最重要的信息，次级信息延后。
- Projects Workspace 不显示成本、Token、Trace 数量、评测分数或完整版本历史。
- 页面区域之间保留明显垂直间距。
- 留白是层级工具，不需要用装饰或功能模块填满。

## 5. Visual Keywords

### 5.1 Desired

- refined
- tactile
- atmospheric
- controlled
- editorial
- dimensional
- professional
- creative

### 5.2 Explicitly Avoid

- cyberpunk
- neon
- gaming HUD
- generic SaaS
- glassmorphism everywhere
- noisy
- playful cartoon
- mystical tarot aesthetic

## 6. Color Direction — Nocturne Studio

Nocturne Studio 是用户确认的正式视觉方向。它使用深石墨蓝环境、暗色雾面卡片、
低饱和青绿、旧金和有限陶土色，但不使用纯黑、高饱和霓虹或通用紫色 AI 渐变。
以下 Token 仍是实现前候选值，不表示已经进入 CSS、组件或 Design Token Package。

### 6.1 Historical Candidates

- Mineral Studio：历史候选，保留其冷静、精密和 CreativeDeploy 一致性原则。
- Atelier Earth：历史候选，保留其温暖材料感和有限陶土语义。
- Nocturne Studio：`OWNER_APPROVED`，取代前两者成为当前正式方向。

### 6.2 Nocturne Studio Candidate Tokens

`light/dark foreground` 是该底色上建议使用的文字方向。对比度使用 WCAG 相对亮度
公式做基础静态检查；实施时仍需按实际字号、字重、状态和高对比模式复测。

| Token name | Usage | Candidate hex | Light/dark foreground | Contrast note | Implementation status |
| --- | --- | --- | --- | --- | --- |
| `shell-bg` | 平台与 Project Home 主环境 | `#0D1318` | light `#F1F0EB` | primary text `16.38:1` | `CANDIDATE_NOT_IMPLEMENTED` |
| `shell-bg-secondary` | Header 次级层、深度分区 | `#141D23` | light `#F1F0EB` | primary text `14.97:1` | `CANDIDATE_NOT_IMPLEMENTED` |
| `surface-elevated` | 暗色雾面项目卡片、面板 | `#1C252B` | light `#F1F0EB` | primary `13.64:1`; secondary `7.36:1` | `CANDIDATE_NOT_IMPLEMENTED` |
| `surface-interactive` | hover、selected、可交互卡片层 | `#263239` | light `#F1F0EB` | primary `11.52:1`; secondary `6.22:1` | `CANDIDATE_NOT_IMPLEMENTED` |
| `canvas-neutral` | Polygon 与颜色判断的暖灰画布 | `#E7E1D8` | dark `#192329` | dark text `12.30:1` | `CANDIDATE_NOT_IMPLEMENTED` |
| `canvas-neutral-dark` | 颜料比较的可选深灰观察背景 | `#30383C` | light `#F1F0EB` | primary text `10.48:1` | `CANDIDATE_NOT_IMPLEMENTED` |
| `border-subtle` | 非关键表面分隔 | `#48575F` | n/a | `2.08:1` on elevated; decorative only | `CANDIDATE_NOT_IMPLEMENTED` |
| `accent-primary` | Create Project、选中、主动作 | `#63B3A6` | dark `#192329` | dark text `6.49:1`; accent on shell `7.59:1` | `CANDIDATE_NOT_IMPLEMENTED` |
| `accent-primary-hover` | 主动作 hover / active | `#78C6B8` | dark `#192329` | dark text `8.04:1` | `CANDIDATE_NOT_IMPLEMENTED` |
| `accent-gold` | 收藏、高光、人工 Gate 辅助 | `#B89A5A` | dark `#192329` | dark text `5.94:1`; accent on shell `6.95:1` | `CANDIDATE_NOT_IMPLEMENTED` |
| `accent-paint` | 颜料语义、有限创作强调 | `#A95537` | light `#F1F0EB` | light text `4.55:1`; adjusted from `#B96F50` | `CANDIDATE_NOT_IMPLEMENTED` |
| `text-primary` | 暗色环境主文字 | `#F1F0EB` | dark background | `16.38:1` on shell; `13.64:1` on elevated | `CANDIDATE_NOT_IMPLEMENTED` |
| `text-secondary` | 暗色环境辅助文字 | `#A9B4BB` | dark background | `8.84:1` on shell; `7.36:1` on elevated | `CANDIDATE_NOT_IMPLEMENTED` |
| `text-muted` | 次要 metadata | `#839099` | dark background | `5.71:1` on shell; `4.76:1` on elevated | `CANDIDATE_NOT_IMPLEMENTED` |
| `success` | 成功状态 | `#6FBE93` | dark `#192329` | dark text `7.20:1`; color on shell `8.42:1` | `CANDIDATE_NOT_IMPLEMENTED` |
| `warning` | 等待、风险、人工注意 | `#D2A45F` | dark `#192329` | dark text `7.01:1`; color on shell `8.20:1` | `CANDIDATE_NOT_IMPLEMENTED` |
| `error` | 失败、不可用 | `#DE7D83` | dark `#192329` | dark text `5.61:1`; color on shell `6.56:1` | `CANDIDATE_NOT_IMPLEMENTED` |
| `focus-ring` | 键盘焦点和高对比交互边界 | `#8BD8CA` | n/a | `11.37:1` on shell; `9.47:1` on elevated | `CANDIDATE_NOT_IMPLEMENTED` |

`border-subtle` 不得作为唯一的交互控件边界；键盘焦点使用高对比
`focus-ring`。`accent-paint` 已从用户初始候选调整为更深的 `#A95537`，以便暖白
正文在其上达到基础 AA。所有色值仍需通过视觉概念图和真实组件组合确认。

## 7. Typography Direction

不下载字体，不把任何商业字体文件放入仓库。以下仅是实施时可评估的方向：

| Use | Candidate direction | Reason |
| --- | --- | --- |
| English display / heading | Manrope | 几何感清晰，适合产品标题与大尺寸信息 |
| English body / UI | Source Sans 3 | 长文本可读，字重和语言覆盖实用 |
| Chinese | Noto Sans SC / Source Han Sans SC | 中英文并用时结构稳定，需在实施时确认加载策略 |
| Numbers / status metadata | IBM Plex Mono | 仅用于版本、时间和状态辅助信息，不用于大段正文 |
| System fallback | `system-ui`, `-apple-system`, `sans-serif` | 字体未加载或受限时保持可靠 |

这些候选通常可通过开放许可用于 Web，但实施时仍需重新核对许可、子集、加载性能和
中文字重。当前不安装字体，也不承诺最终组合。

## 8. Material and Surface

Nocturne Studio 的材料方向冻结为：

- **dark graphite shell**：Product Entry、Projects Workspace 和 Create Project 的主要环境；
- **matte elevated surfaces**：暗色雾面卡片和操作面板；
- **warm neutral precision canvas**：图片、Polygon 和颜色判断区域；
- **subtle metallic highlights**：只用于有限旧金边缘与人工 Gate 辅助；
- **restrained paint texture**：低频、低对比的颜料材料暗示；
- **limited translucency**：只允许少量氛围层，并提供不透明 fallback；
- **no global glassmorphism**：不把玻璃拟态应用到所有卡片和工作区。

PaintPilot 的神秘感来自深度、光线、粒子组织和材质层次，不来自塔罗符号、魔法阵、
高饱和霓虹、大量星座或玄学图形。精确工作区必须切换到暖灰画布，避免暗色环境影响
图片和颜料颜色判断。

## 9. Motion Language

以下持续时间都是候选范围，不表示已经实现或冻结。

### 9.1 Brand Motion

- 磁场粒子表现图片、知识、结构化节点和 Human Review 的聚合关系。
- 景深推进用于平台外壳进入 PaintPilot 产品空间。
- 抽象图像节点保持领域中立，不直接使用手办或 Arcana 资产冒充平台品牌。
- 强度可中高，但只用于 Product Entry、入口转换和重大成功节点。

### 9.2 Product Motion

- Project Card hover：轻微图片缩放、有限视差、状态信息渐显。
- Create Project：粒子或节点向入口聚合，明确主要动作。
- 状态变化：Badge、说明文字和可用动作同步改变。
- 加载完成：卡片按阅读顺序分层进入，不随机飞入。
- Projects Workspace 不继承 Product Entry 的连续滚动叙事或大型互动视觉主体。

### 9.3 Precision Motion

- Polygon Editor、表单、颜料比较、Trace 和长步骤阅读使用极低强度动效。
- 精确操作区域不覆盖粒子，不使用持续漂浮和大角度 3D 旋转。
- 状态反馈可以淡入或局部高亮，但布局位置保持稳定。

### 9.4 Candidate Timing Ranges

| Motion class | Candidate duration | Notes |
| --- | --- | --- |
| Micro interaction | `120–180 ms` | hover、pressed、focus 辅助 |
| Status transition | `160–240 ms` | 文字和 Badge 同步，不延迟关键信息 |
| Panel transition | `240–360 ms` | 面板进入或信息展开 |
| Page / depth transition | `480–700 ms` | 只用于产品空间或独立创建页 |
| Ambient particle cycle | `8–16 s` | 低速、可暂停、不可成为理解前提 |

### 9.5 Nocturne Motion Token Candidates

这些 Token 是设计候选，不是已实现代码。`easing direction` 描述运动性格，不冻结
具体 cubic-bezier 数值。

| Token | Purpose | Duration range | Easing direction | Reduced-motion behavior | Allowed pages | Forbidden contexts |
| --- | --- | --- | --- | --- | --- | --- |
| `motion-micro` | focus、pressed、状态细节 | `120–180 ms` | quick ease-out | 保留短淡入与即时状态 | 全站必要交互 | 不延迟错误和状态文字 |
| `motion-hover` | 卡片图片轻微缩放、有限视差 | `180–260 ms` | smooth ease-out | 取消缩放和视差，只保留 focus/outline | Projects Workspace 卡片 | 表单输入、Polygon、触摸专属路径 |
| `motion-panel` | 面板展开与信息层级变化 | `240–360 ms` | balanced ease-in-out | 使用短淡入或立即显示 | Projects Workspace、Precision Workspace 面板 | 施工步骤连续阅读中的频繁循环 |
| `motion-page-depth` | Entry → Projects / Create / Precision | `480–700 ms` | depth-weighted ease-in-out | 替换为 `120–180 ms` 淡入 | Product Entry、创建页、打开项目 | Polygon 操作中、Trace 精读中 |
| `motion-particle-settle` | 分散节点聚合并稳定 | `900–1600 ms` | slow settle, no spring bounce | 显示最终静态节点布局 | Product Entry、Workspace Header、Empty / Create | 项目卡片正文、表单、精确画布 |
| `motion-analysis-scan` | 未来分析等待的柔和扫描反馈 | `1200–2200 ms` per pass | linear-soft loop | 使用静态进度与文字状态 | 未来分析等待页 | 未实现分析、Polygon、颜色比较 |

环境粒子循环可以比表中交互更慢，但必须有数量、帧率和暂停预算。不得因为
`motion-analysis-scan` 出现在设计文档中，就暗示分析能力已经实现。

## 10. Reduced Motion

在 `prefers-reduced-motion: reduce` 下：

- 关闭磁场粒子位移、景深推进、视差、连续缩放和装饰性循环；
- 保留必要的短淡入、焦点和状态变化，但不使用大幅位移；
- 所有功能、状态和导航必须在没有动画时仍然完整可理解；
- Create Project、Project Card 和错误恢复不得依赖动画提供唯一线索；
- 后续实施需要同时验证键盘路径、屏幕阅读顺序和 reduced-motion 路径。

## 11. Design-system Boundary

本阶段只记录未来可能需要的基础组件：

- `Button`
- `ProjectCard`
- `StatusBadge`
- `PageHeader`
- `EmptyState`
- `MotionSurface`
- `ProductSwitcher`

本阶段不创建完整 Token Package、通用组件库、Storybook、UI Library 或独立 Design
System Workspace。视觉方向已经获批；实现级 Token 和组件 API 仍只在后续出现真实
复用需求时定义。

## 12. Deferred Implementation Decisions

Product Entry 的概念方向、非角色 Abstract Material Study、四段叙事和单一主要 CTA
已经由项目所有者批准。以下仍属于实施前决策：

1. 确认 Nocturne Studio Token 候选与字体组合。
2. 评估 CSS + Canvas 2D / 2.5D 是否足以进入后续技术原型。
3. 确认 Product Entry、Projects Workspace 和 Precision Workspace 的性能预算。
4. 确认复杂 Product Entry 动效在核心产品能力完成后的实施排期。

## 13. UI Content and Asset Policy

### 13.1 Hero Visual

允许：

- 抽象磁场粒子；
- Polygon 节点；
- 光源方向线；
- 低饱和色块；
- 不可识别为具体角色或具体手办的 Abstract Material Study；
- 树脂、石膏或模型材料质感的匿名雕塑体块；
- 中性空间与材质光影。

禁止：

- 机器人、机甲、动漫人物或游戏角色；
- 未授权 IP；
- 塔罗牌、魔法阵或玄学符号；
- 与 PaintPilot 无关的视觉对象。

### 13.2 Project Cards

Project Card 图片只允许来自：

1. 用户真实上传的项目图片；
2. 用户明确确认可用于项目展示的图片；
3. PaintPilot Golden Case 的用户授权图片；
4. 中性、原创、非角色化占位图形。

不得使用为填满页面而生成的虚构角色项目、网络随机动漫图片、未记录来源的手办
照片，或机器人、机甲和动漫人物默认模板。

### 13.3 Empty State

- 真实显示 `No projects yet`。
- 使用抽象粒子、节点和中性占位视觉。
- 不伪造用户已经拥有多个项目。
- Create Project 是唯一主要入口。
- 不出现 Arcana、Tarot 或 Future Modules 墙。

### 13.4 Concept Mockup Boundary

- 之前生成的 UI 概念图片只用于布局和气质讨论。
- 其中出现的角色、机器人、项目名称和图像不属于正式设计资产。
- 概念图内容不得复制到正式产品或提交到公开仓库。
- 概念图中的项目不得视为真实数据库记录或已实现功能。
- 已批准的是 Product Entry 的视觉方向，不是概念图片文件本身。
- 概念图不会进入产品或公开仓库，也不证明磁场粒子、Polygon、光照、RAG 或工作流
  能力已经实现。
- Product Entry 概念必须使用中性原创 Abstract Material Study；Projects Workspace 的
  项目图片仍只允许使用中性原创占位或用户授权 Golden Case。
