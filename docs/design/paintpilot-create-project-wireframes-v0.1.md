# PaintPilot Create Project Wireframes v0.1

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

这些 ASCII Wireframe 冻结页面结构、字段顺序、状态和恢复路径，不代表路由、表单、
API、数据库、动画或 PaintProject 创建已经实现。

## 2. Shared Constraints

- 独立页面，不使用 modal。
- 单一主要 CTA：`Create Project`。
- Cancel 是低权重次级动作。
- 字段标签和错误永久可见，不用视觉效果替代。
- 粒子只位于表单外围，字段出现后动效收敛。
- 表单主表面固定为 warm-neutral matte。
- Target Style 和 Planning Mode 是只读信息，不是 disabled 控件。
- 首版不显示图片上传、AI Prompt、Provider、库存、知识库、Polygon、团队或复杂设置。
- 成功必须来自服务端持久化结果，不能创建本地假项目。

## 3. Desktop Create Project

```text
┌──────────────────────────────────────────────────────────────────────────────┐
│ CREATIVEDEPLOY · PAINTPILOT                         Projects                 │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  CREATE PAINT PROJECT                              ·       ·                 │
│  Start with the facts needed to create a real      · low particle field     │
│  planning-only project.                                  ·                  │
│                                                                              │
│  ┌────────────────── warm-neutral matte form ─────────────────────────────┐ │
│  │ Project Title *                                       0 / 80            │ │
│  │ [____________________________________________________________]          │ │
│  │ Use a clear name you can recognize later.                              │ │
│  │                                                                         │ │
│  │ Short Description                                      0 / 500          │ │
│  │ [____________________________________________________________]          │ │
│  │ [____________________________________________________________]          │ │
│  │ Optional context; no AI prompt or upload here.                          │ │
│  │                                                                         │ │
│  │ Target Style                                                            │ │
│  │ Cel Shading · Current release                                           │ │
│  │                                                                         │ │
│  │ Planning-only demo                                                      │ │
│  │ Results are guidance, not verified repaint outcomes.                    │ │
│  │                                                                         │ │
│  │ [ CREATE PROJECT ]                                      [ Cancel ]       │ │
│  └─────────────────────────────────────────────────────────────────────────┘ │
│                                                                              │
│  No image upload or AI processing occurs on this page.                      │
└──────────────────────────────────────────────────────────────────────────────┘
```

### 3.1 Desktop Placement

- 标题和 real-product boundary 位于表单之前。
- 字段使用单一稳定主列，不为宽屏拆成复杂步骤。
- Create Project 紧随 Planning Mode capability note。
- 辅助说明紧邻相关字段。
- 粒子区域位于标题右侧和表单外围，不穿过标签、输入或错误。

### 3.2 Desktop Reduced Motion

- 直接显示最终稳定页面。
- 不执行页面景深或粒子聚合。
- 表单、错误、Submitting 和成功反馈的位置不变。

## 4. Mobile Create Project

```text
┌──────────────────────────────┐
│ PAINTPILOT · PROJECTS        │
├──────────────────────────────┤
│ CREATE PAINT PROJECT         │
│ Create a real planning-only  │
│ project.                     │
│                              │
│ Project Title *       0 / 80 │
│ [__________________________] │
│ Clear, recognizable name.    │
│                              │
│ Short Description    0 / 500 │
│ [__________________________] │
│ [__________________________] │
│ Optional.                    │
│                              │
│ Target Style                 │
│ Cel Shading                  │
│ Current release              │
│                              │
│ Planning-only demo           │
│ Guidance, not verified       │
│ repaint outcomes.            │
│                              │
│ [     CREATE PROJECT       ] │
│ [          Cancel          ] │
│                              │
│ No upload or AI occurs here. │
└──────────────────────────────┘
```

### 4.1 Mobile Order

1. Page title and short boundary;
2. Project Title;
3. Short Description;
4. Target Style current-release information;
5. Planning Mode capability note;
6. Create Project;
7. Cancel;
8. Final real-product boundary.

### 4.2 Mobile Behavior

- 单列顺序等于 DOM 和键盘顺序。
- Create Project 使用明显宽度，Cancel 保持可发现但低权重。
- 错误在对应字段下方换行，无横向滚动。
- 背景使用静态或极少粒子，软件键盘不能遮挡当前字段。
- Reduced motion 与 Desktop 相同，直接显示稳定表单。

## 5. Validation Error State

```text
┌──────────────────────── stable form surface ────────────────────────────────┐
│ CREATE PAINT PROJECT                                                        │
│                                                                             │
│ ┌─ Please correct 1 field ────────────────────────────────────────────────┐ │
│ │ • Project Title is required.                                           │ │
│ └─────────────────────────────────────────────────────────────────────────┘ │
│                                                                             │
│ Project Title *                                                  0 / 80    │
│ [____________________________________________________________]             │
│ [!] Enter a project title.                                                  │
│                                                                             │
│ Short Description                                               0 / 500    │
│ [____________________________________________________________]             │
│                                                                             │
│ Target Style                  Cel Shading · Current release                 │
│ Planning Mode                 Planning-only demo capability note            │
│                                                                             │
│ [ CREATE PROJECT ]                                         [ Cancel ]       │
└─────────────────────────────────────────────────────────────────────────────┘
```

- 标题：保持 `Create Paint Project`。
- CTA：保持可识别；无效提交后不清空数据。
- 错误：顶部摘要获得焦点并链接到具体字段，字段错误同时内联显示。
- 粒子：停止或保持静态，避免干扰错误恢复。
- Mobile：摘要先于第一个无效字段；错误文字自然换行。
- Reduced motion：错误立即出现，不使用抖动、位移或颜色闪烁。

## 6. Submitting State

```text
┌──────────────────────── stable form surface ────────────────────────────────┐
│ CREATE PAINT PROJECT                                      [aria-busy=true]  │
│                                                                             │
│ Project Title *     [ Garage Kit Repaint Study               ]              │
│ Short Description  [ Planning a controlled cel-shaded finish. ]            │
│ Target Style       Cel Shading · Current release                            │
│ Planning Mode      Planning-only demo capability note                       │
│                                                                             │
│ [ CREATING PROJECT… ]                                      [ Cancel ]       │
│ Sending one protected request. Do not close this page.                      │
└─────────────────────────────────────────────────────────────────────────────┘
```

- 标题和全部输入值保持可见。
- CTA 变为 `Creating project…` 并阻止重复激活。
- 字段暂不可编辑；不显示虚假进度百分比。
- Cancel 不执行不确定的中途离开；等待结果或显示明确恢复路径。
- 粒子停止，只有必要状态文字可更新。
- Mobile 使用相同字段顺序，状态说明位于按钮之后。
- Reduced motion 不显示 spinner 旋转依赖；使用文字和静态状态图形。

## 7. Success Transition

```text
┌─────────────────────────────────────────────────────────────────────────────┐
│                                                                             │
│                          PROJECT CREATED                                    │
│                                                                             │
│                 Garage Kit Repaint Study                                    │
│                 Planning-only demo                                          │
│                                                                             │
│                 Saved as project: {projectId}                               │
│                                                                             │
│       Opening project…  /paintpilot/projects/{projectId}                    │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

- 只有服务端返回持久化 `projectId` 后显示。
- 固定目标是 `/paintpilot/projects/:projectId`。
- Phase 1D 必须包含最小详情页，不采用长期列表 fallback。
- 刷新后新项目必须仍存在；否则不能报告成功。
- 不自动开始上传、AI、Polygon 或涂装方案。
- 允许一次有限完成反馈，随后由用户确认的提交动作触发导航。
- Mobile 使用同一内容顺序，不加入额外按钮墙。
- Reduced motion 使用明确文字和直接淡入或导航，不做空间推进。

## 8. Unsaved Changes / Cancel State

```text
┌────────────────────────── confirmation dialog ──────────────────────────────┐
│ Discard unsaved changes?                                                    │
│                                                                             │
│ Your project has not been created. The current form values will be lost.    │
│                                                                             │
│ [ CONTINUE EDITING ]                              [ Discard changes ]       │
└─────────────────────────────────────────────────────────────────────────────┘
```

- 标题：明确说明未保存更改。
- `Continue editing` 是安全默认动作并返回原焦点。
- `Discard changes` 是危险次级动作；执行后返回 `/paintpilot/projects`。
- 页面背景和表单保持静止，不播放粒子或景深。
- 错误信息不被对话框永久清除。
- Mobile 对话框不超出视口，按钮纵向排列时安全动作在前。
- Reduced motion 直接显示对话框，无缩放或旋转。

## 9. Network Failure and Unknown Outcome

```text
┌──────────────────────── submission status ──────────────────────────────────┐
│ We could not confirm whether the project was created.                       │
│ Your form values are still here.                                            │
│                                                                             │
│ [ RETRY SAFELY ]                                      [ Return to form ]    │
│                                                                             │
│ Retry uses the same protected request identifier.                           │
└─────────────────────────────────────────────────────────────────────────────┘
```

- Retry 复用同一 idempotency key。
- 不生成第二个项目，不重置表单，不显示本地假成功。
- 服务端确认已有 project ID 后进入 Success Transition。
- 错误区不显示数据库地址、原始异常或 stack trace。
- Mobile 和 reduced motion 使用相同文本与动作顺序。

## 10. State Matrix

| State | Primary CTA | Error placement | Particle behavior | Mobile | Reduced motion |
| --- | --- | --- | --- | --- | --- |
| Ready | Create Project | None | 外围一次聚合后稳定 | 单列 | 静态背景 |
| Validation error | Create Project | 摘要 + 字段内联 | 停止 | 摘要先读 | 即时错误 |
| Submitting | Creating project… | 状态区 | 停止 | 原顺序锁定 | 文字状态 |
| Success | No second create CTA | Success region | 可有限收敛 | 单列反馈 | 直接淡入/导航 |
| Unsaved cancel | Continue editing | Dialog text | 停止 | 按钮纵排 | 即时对话框 |
| Unknown outcome | Retry safely | Submission status | 停止 | 单列动作 | 无 spinner 依赖 |

## 11. Real-product Boundary

本页面只创建真实 PaintProject。Wireframe 中的 title 和 project ID 是结构占位，不是
数据库记录或实现证据。不得在实现前把这些画面描述为可用产品。

首版不包含 AI Prompt、图片上传、Provider、库存、知识库、Polygon、多租户、邀请、
复杂设置或自动涂装方案。

未来 Image Upload UX 必须对每个具体 ImageAsset 收集并持久化 Rights Attestation；
未确认时不得进入区域分析。Create Project 页面不显示该声明。

## 12. Owner Decisions Resolved

`OWNER_DECISIONS_RESOLVED`

- Warm-neutral matte form surface。
- Title 上限 `80`，Description 上限 `500`。
- Target Style 显示 `Cel Shading · Current release`，无选择控件。
- Planning Mode 只显示 capability note，无选择控件。
- Create Project 页面无 Rights Attestation。
- Success 固定进入最小详情页。
