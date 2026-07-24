# PaintPilot Create Project UX Specification v0.1

## 1. Document Status

- Status: `APPROVED_FOR_IMPLEMENTATION`
- Version: `0.1.0`
- UX Status: `APPROVED_FOR_IMPLEMENTATION`
- Implementation Status: `NOT_STARTED`
- Approval Date: `2026-07-24`
- Owner Decisions: `OWNER_DECISIONS_RESOLVED`
- Product: `PaintPilot`
- Page Name: `Create Paint Project`
- Route: `/paintpilot/projects/new`
- Experience Layer: `Application Layer`
- Visual Direction: `Nocturne Studio`
- Decision Authority: `Project Owner`

本文档定义首版真实 PaintProject 创建体验，不表示页面、API、数据库表、验证或持久化
已经实现。

## 2. Page Purpose

通过一个独立、清晰且可重复使用的表单创建真实 PaintProject，并将经过验证的数据
可靠持久化。

Create Paint Project 不是弹窗，也不是 Product Entry 展示页。首版不上传图片、不
调用 AI、不生成 Polygon 或涂装方案。

## 3. Primary User Goal

用户应能：

1. 理解当前创建的是 planning-only PaintProject；
2. 用最少必要字段准确描述项目；
3. 清楚处理字段错误、网络失败和重复提交；
4. 创建成功后打开从 API 重新读取的持久化项目。

首要设计原则依次是：真实使用效率、数据准确、错误可恢复、状态清楚、可访问性和
重复使用舒适度。视觉展示不能牺牲这些原则。

## 4. Entry and Exit Routes

| Direction | Route | Behavior |
| --- | --- | --- |
| Primary entry | `/paintpilot/projects` | Create Project CTA 进入独立页面 |
| Direct entry | `/paintpilot/projects/new` | 显示同一创建表单；不依赖前一页状态 |
| Successful exit | `/paintpilot/projects/:projectId` | 固定进入新建项目的最小详情页 |
| Cancel exit | `/paintpilot/projects` | 无未保存更改时直接返回 |

Product Entry `/paintpilot` 不直接创建项目。成功或取消都不返回 Product Entry。

## 5. Visual and Interaction Structure

- 深石墨蓝 Nocturne 环境。
- 表单默认使用 warm-neutral matte 稳定表面，字段区域具有高对比度。
- 低饱和青绿用于主要 Create Project，旧金只作有限辅助。
- 大标题、简短说明和明显留白。
- 页面只有一个主要动作 `Create Project`；`Cancel` 是低权重次级动作。
- 进入页面时允许有限景深，背景粒子可向表单区域聚合一次。
- 字段可操作后动效立即收敛；表单、标签和错误位置保持稳定。

禁止字段持续漂浮、粒子覆盖文字、强烈 3D 旋转、隐藏字段标签或错误，以及未确认便
自动进入后续步骤。

## 6. Field Contract

所有长度在前后端使用同一规则：去除首尾空白后，按 Unicode code point 计数。服务端
是最终验证权威，客户端使用相同规则提供即时反馈。

| Field | Required | First-release contract | Stored value |
| --- | --- | --- | --- |
| Project Title | Yes | `1–80` characters after trim；空白字符串无效 | Trimmed string |
| Short Description | No | Maximum `500` characters after trim；空值不提交空白字符串 | Trimmed string or `null` |
| Target Style | System fixed | UI 显示 `Cel Shading · Current release`；不是选择控件 | `cel_shading` |
| Planning Mode | System fixed | UI 只显示 capability note；不是表单字段 | `planning_only_demo` |

首版用户提交 payload 只包含 `title` 和可选 `description`。Owner、Target Style、
Planning Mode、status、ID 和 timestamps 均由服务端确定；客户端不能指定或覆盖。

### 6.1 Fixed Target Style

界面显示只读产品信息：

`Target Style`

`Cel Shading · Current release`

不显示下拉框、radio 或 disabled selector。服务端确定性写入
`target_style = cel_shading`。`comic_ink`、`painterly`、`realistic`、
`manga_high_contrast` 和其他未实现风格不得出现在当前 UI、请求或响应选项中。

未来新增风格必须先具有结构化规则、Schema 支持、测试、自动或人工评测和真实案例。

### 6.2 Planning Mode

Planning Mode 是系统能力边界，不是用户选择。界面仅显示短说明：

`Planning-only demo — results are planning guidance and are not verified repaint outcomes.`

不显示禁用下拉框或其他控件。后端确定性写入
`planning_mode = planning_only_demo`，不能只依赖前端说明。

### 6.3 Actions

- `Create Project`：唯一主要提交按钮。
- `Cancel`：返回 Projects Workspace；有未保存更改时先确认。
- 不提供 Save Draft、Create and Upload、Generate with AI 或其他并行主动作。

## 7. Validation

### 7.1 Client-side Validation

- Title 失焦或提交时检查必填、trim 和 `80` 字符上限。
- Description 显示字符计数并在超过 `500` 时阻止提交。
- 第一次提交失败后，错误在用户修正相应字段时更新，不提前制造全屏错误。

### 7.2 Server-side Validation

- 服务端重复执行全部字段规则，不能信任客户端。
- 服务端确定性写入 `target_style=cel_shading`、
  `planning_mode=planning_only_demo` 和 `status=DRAFT`。
- `owner_principal_id` 只来自 PrincipalContext，客户端字段无效且不得覆盖。
- 字段错误返回稳定字段标识和安全用户消息。
- 服务端拒绝未知字段或明确忽略策略；实现前必须统一，不能静默持久化意外数据。
- 标题不作为唯一键；不同真实项目可以有相同标题并由不同 project ID 区分。

### 7.3 Error Presentation

- 页面顶部提供可聚焦错误摘要，并链接到具体字段。
- 每个字段附近显示对应错误文字。
- 状态不能只用红色表达；同时使用文字和图形。
- 输入值在验证失败后保持不变。

## 8. Error States

| State | User-facing behavior | Recovery | Prohibited behavior |
| --- | --- | --- | --- |
| Field validation | 显示错误摘要和字段内联错误 | 修正后重新提交 | 清空整个表单 |
| Network unavailable | 说明暂时无法连接，保留全部输入 | 使用同一请求标识 Retry | 创建本地假项目 |
| Server validation | 显示服务端字段消息 | 聚焦首个无效字段 | 显示原始响应或 stack trace |
| Server unavailable | 显示安全通用错误 | Retry 或稍后返回 | 暴露数据库、URL 或内部异常 |
| Unknown submission outcome | 说明结果尚未确认 | 使用同一 idempotency key 查询或重试 | 生成第二个项目 |

错误消息不得声称数据已经保存，除非服务端返回可验证 project ID。

## 9. Loading and Submission States

### 9.1 Initial Load

- 标题、说明和表单结构优先出现。
- 固定 Target Style 和 Planning Mode 信息不依赖异步选项加载。
- 页面初始化失败时保留安全错误、Retry 和 Cancel。

### 9.2 Ready

- 所有字段、标签和辅助说明稳定可见。
- Create Project 在 Title 和 Description 合同有效时可提交。
- 禁用状态同时提供原因，不能只依赖视觉弱化。

### 9.3 Submitting

- 按钮文字变为 `Creating project…`。
- 表单区域使用 `aria-busy="true"`。
- 禁止再次提交；字段保持可见但暂时不可编辑。
- 不清空输入、不跳转、不播放误导性成功动画。
- 提交时间异常时显示安全说明和恢复动作。

### 9.4 Submission Failure

- 恢复可编辑状态和原始输入。
- 使用相同 idempotency key Retry。
- 焦点进入错误摘要，不自动滚动到无关区域。

## 10. Duplicate Submission Protection

- 每次表单会话生成一个稳定 idempotency key；它不是用户输入字段。
- 同一表单只有一个 in-flight 请求。
- 双击、Enter 重复触发和触摸连点不得产生多个请求。
- 网络超时后的 Retry 复用原 key，不能生成新 key。
- Idempotency-Key 由前端生成 UUID，记录保留 `24 hours`。
- 作用域遵循批准合同：`principal_id + preallocated project_id + command_type + key`。
- same key + same normalized payload 重放原响应。
- same key + different payload 返回 HTTP `409 IDEMPOTENCY_KEY_REUSED`。
- 成功响应包含唯一 `projectId`；收到后立即停止重试。
- 标题重复不等于请求重复，不能通过标题去重真实项目。

Header 固定使用 `Idempotency-Key`，记录保留 24 小时；项目 ID 预分配、记录查找和服务端
事务细节由 Phase 1D 实施计划约束。端到端幂等性是首版可靠性要求，不得只依赖按钮
disabled。

## 11. Image Rights Attestation Relocation

Create Project 页面不显示、不验证也不提交 Rights Attestation。空项目尚未绑定具体
图片或文档，项目级提前声明不能证明具体素材来源。

权利控制保留在未来 Image Upload UX，并绑定每一个具体 ImageAsset：

- 每个 ImageAsset 必须保存 `rights_attestation_status`；
- 声明绑定具体文件、提交 Principal 和 `intended_usage`；
- `rights_attestation_status != confirmed` 时不得开始区域分析；
- 历史声明保留审计记录；
- 系统只记录用户声明，不把它解释为平台法律确认。

本次迁移不删除 Product Contract 或 Data Dictionary 的图片权利控制要求。

## 12. Accessibility

- 使用语义化 `form`、`label`、`input`、`textarea`、`button`。
- 所有字段具有永久可见标签，不以 placeholder 代替。
- 键盘顺序遵循标题 → Title → Description → Create → Cancel。Target Style 和
  Planning Mode 是可读说明，不插入无意义的禁用控件。
- Enter 只能触发表单的一次有效提交；Space 可操作按钮。
- 错误摘要在提交失败后获得焦点，并通过 `aria-describedby` 关联字段错误。
- 字符计数、Submitting 和成功状态使用克制的 live region。
- 焦点环、文本和控件边界实施时验证 WCAG AA。
- 颜色、粒子和动效不是状态或验证的唯一表达。
- 常用触摸目标建议至少约 `44 × 44 CSS px`。

## 13. Responsive Behavior

### 13.1 Desktop

- 表单使用单一主列，可在宽屏保留辅助说明列，但不拆成复杂多栏。
- Create / Cancel 紧随 Planning Mode capability note，保持清晰提交顺序。
- 背景粒子位于表单外围，不穿过字段或错误。
- 表单最大宽度优先保证舒适阅读，不为填满屏幕拉长输入行。

### 13.2 Mobile

- 单列顺序与 DOM 顺序完全一致。
- Title、Description、Target Style 信息、Planning Mode note、Create、Cancel 依次排列。
- Create Project 使用全宽或明显宽度；Cancel 保持可发现但低权重。
- 错误文字换行而不截断，无横向滚动。
- 键盘弹出时不能遮挡当前字段或提交状态。
- 粒子、模糊和景深显著降低。

## 14. Reduced Motion

在 `prefers-reduced-motion: reduce` 下：

- 取消页面景深推进、粒子聚合和成功空间转场；
- 直接显示稳定表单；
- 保留必要的短淡入或立即状态更新；
- 错误、Submitting 和成功状态不依赖动画；
- 成功后使用明确文字和直接导航。

## 15. Success Destination

成功响应必须包含持久化 PaintProject 的 `projectId`。

固定进入：

`/paintpilot/projects/:projectId`

- Phase 1D 必须提供最小项目详情页，不采用长期列表页 fallback。
- 详情页从 GET API 读取，不能依赖提交表单的内存状态。
- 刷新详情页后项目仍然存在。
- 从 Projects 列表可以再次打开同一项目。
- 详情页明确显示 `Image upload is not implemented yet`。
- 不自动开始图片上传、AI 分析或下一业务步骤。

## 16. Cancel and Unsaved Changes

- 表单从初始值发生任何有效变化后进入 dirty 状态。
- 未修改时 Cancel 直接返回 `/paintpilot/projects`。
- 有未保存更改时显示确认对话框：
  - `Continue editing`
  - `Discard changes`
- `Continue editing` 是安全默认动作并返回原焦点。
- `Discard changes` 明确丢弃本地未提交输入后退出。
- 浏览器返回、站内导航和关闭页面需要一致的未保存更改保护；实现时优先使用平台
  能力，不能承诺浏览器允许自定义离开文案。
- 提交进行中不自动取消请求或离开；先等待确定结果或显示明确恢复路径。

## 17. Real-product Boundary

首版唯一业务结果是：创建并持久化真实 PaintProject。

明确不包含：

- AI Prompt；
- 图片上传；
- 模型 Provider；
- 颜料库存；
- 知识库或 RAG；
- Polygon；
- 多租户；
- 成员邀请；
- 复杂设置；
- 自动生成涂装方案。

页面不能展示虚假上传进度、AI 结果、库存命中、Polygon 或施工计划。求职叙事必须
基于实际 API、数据库持久化、测试、评测和刷新后仍存在的证据。

## 18. Future Extensions

只有 PaintProject 创建、列表和打开稳定后，才评估：

- 项目详情中的图片上传、逐 ImageAsset Rights Attestation 和质量检查；
- 区域建议、Polygon 修正和 Human Review；
- 风格、光源、阴影和高光规则；
- 颜料库存与知识检索；
- 可审核施工计划；
- 团队和成员能力。

Future extensions 不得提前进入首版 Create Project 表单，也不能以 disabled 功能墙
占用当前页面。

## 19. Owner Decisions Resolved

`OWNER_DECISIONS_RESOLVED`

- Title：trim 后 `1–80`。
- Description：trim 后最多 `500`，空字符串归一化为 `null`。
- Target Style：固定 `cel_shading`，UI 显示 `Cel Shading · Current release`。
- Planning Mode：后端固定 `planning_only_demo`，UI 仅显示 capability note。
- Rights Attestation：从 Create Project 移至未来逐 ImageAsset 上传流程。
- Form surface：默认 warm-neutral matte。
- Success：固定进入 `/paintpilot/projects/:projectId`。
- Idempotency：遵循批准的 24 小时 Command Idempotency Contract。
