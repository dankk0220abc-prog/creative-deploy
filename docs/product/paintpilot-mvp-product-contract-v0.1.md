# PaintPilot MVP Product Contract v0.1

## 1. Document Metadata

- Document Status: `APPROVED_FOR_IMPLEMENTATION`
- Version: `0.1.3`
- Product: `PaintPilot`
- Parent Project: `CreativeDeploy`
- Current Phase: `Phase 1D — Ready for Implementation`
- Implementation Status: `FOUNDATION_IMPLEMENTED_PAINTPROJECT_NOT_STARTED`
- Baseline Approval Date: `2026-07-23`
- Amendment Date: `2026-07-26`
- Approval Date: `2026-07-26`
- Previous Approved Version: `0.1.2`
- Golden Case: `Super Saiyan Goku Cel-Shading Planning Case`

### 1.1 Approval Scope

- Version 0.1.1 产品需求基线已获批。
- Version 0.1.2 是已批准用于实施的 PaintProject 创建、读取和幂等边界窄范围修订。
- Version 0.1.3 是已批准用于实施的物理字段长度、StateTransitionEvent
  `event_metadata` 和 `agent_run_id` 延后边界基线。
- Phase 1B Foundation 已实现；PaintProject 业务实现尚未开始。
- Phase 1D-1A 数据库迁移基础已实现；PaintProject ORM、业务 Revision 和业务表尚未实现。
- Phase 1D-1B 已解除合同阻塞，但 PaintProject ORM、业务 Revision 和业务表仍未实现。
- 先前的 Phase 1D-1B 实施指令已废弃，不构成合同来源；新实施必须以本批准版本、
  Data Dictionary 0.1.3 和 ADR-0003 为准。
- 不代表真实重涂结果已经验证。
- 后续需求变更必须通过新版本或新的 ADR 记录。

本文档保留已批准的 MVP 需求，只澄清 Phase 1D 物理字段和审计事件边界；它不是实现
说明、上线承诺或真实涂装效果声明。创建事务、幂等行为、Rights Attestation 所属阶段、
16 个状态、47 条 Transition、17 个编号 Guard、Golden Case 艺术规则和 planning-only
验证边界均不在本次修订范围内。

## 2. Problem Statement

小型手办重涂工作室的方案设计通常依赖少数资深人员的经验。教程、内部案例、知识文档与颜料库存分散在不同载体中，初级涂装师难以把这些信息稳定地转化为可执行方案。普通生成式 AI 可以生成建议，但输出容易缺少结构、来源、库存约束、状态控制和可追踪的人工审批。

用户需要保留对语义区域、Polygon 边界、艺术方向、材料事实与最终方案的控制权。PaintPilot 的价值是把图片、人工确认、结构化库存和有来源的内部资料组织成一份可审核、可追踪的涂装规划，而不是代替涂装师，也不保证真实涂装结果。

## 3. Target Users

### 3.1 Primary Users

- 2—20 人的小型手办重涂工作室；
- 工作室负责人；
- 资深涂装师；
- 具有基础涂装能力、需要复用工作室知识的初级涂装师。

### 3.2 Secondary Users

- 已有基础涂装知识的个人手办玩家。

### 3.3 Explicitly Excluded Users

- 完全没有涂装知识，并期望系统保证最终实物效果的普通消费者。

## 4. Primary Job to Be Done

当用户需要为一个手办制定风格化重涂方案时，帮助其把一张主图片、人工确认区域、风格、光源、已确认库存和内部资料整合成一份可人工审核、可追踪且有来源的施工计划。

## 5. MVP Scope

### 5.1 Core Workflow

MVP 只支持一个核心流程：创建 Paint Project，上传一张主手办照片并记录用户权利声明，完成图片质量检查、必要的人工图片复核与候选区域分析，由用户通过 Polygon Editor 确认完整语义和几何快照，应用已确认的 Cel Shading 艺术配置，查询库存与知识资料，生成带引用的结构化方案，经用户审批后保存版本与 Trace。

### 5.2 Included

- 一张主图片；
- 图片来源、用户权利声明和预期用途记录；
- 格式、尺寸、模糊、亮度和遮挡检查；
- 图片质量 `pass/review/fail` 三态与附加人工复核；
- 结构化候选区域与粗略 Bounding Box；
- Polygon 人工添加、修改与删除；
- 区域确认 Gate；
- 已冻结 Cel Shading、左上光源和中等阴影配置；
- 已确认库存的结构化查询；
- PDF、Markdown、TXT 知识资料检索；
- 带引用的结构化涂装方案；
- 方案审批或修订；
- 项目状态、版本、AgentRun、ModelCall 和状态转换 Trace。

### 5.3 Explicitly Excluded

- 真实重涂执行或结果验证；
- 进度照片诊断；
- 自动像素级精确分割；
- 3D 重建、AR 或物理级光照仿真；
- 自动生成重涂完成图；
- 精确混色比例或精确色彩校准；
- 多图融合；
- 自定义模型训练；
- 公共注册或完整多租户；
- Arcana；
- Redis、独立任务队列、微服务或 Kubernetes。

### 5.4 Frozen Golden Case Art Configuration

以下字段已经由用户确认，不属于 Open Question：

| Field | Value | Confirmation |
| --- | --- | --- |
| `target_style` | `cel_shading` | `USER_CONFIRMED` |
| `light_direction` | `upper_left` | `USER_CONFIRMED` |
| `shadow_intensity` | `medium` | `USER_CONFIRMED` |
| `shadow_layers` | `2` | `USER_CONFIRMED` |
| `shadow_edge` | `hard` | `USER_CONFIRMED` |
| `highlight_style` | `blocked_hard_edge` | `USER_CONFIRMED` |
| `gradient_policy` | `generally_disallowed` | `USER_CONFIRMED` |
| `limited_manual_transition` | `allowed` | `USER_CONFIRMED` |

`limited_manual_transition=allowed` 只允许极少量人工施工过渡，不能被系统解释为自动渐变计算。

## 6. MVP User Journey

| Step | Input | Planned System Behavior | Output | Failure / Fallback | User Confirmation |
| --- | --- | --- | --- | --- | --- |
| 1. 创建项目 | 标题、可选说明与 Idempotency-Key | 创建 `PaintProject`，写入初始意图和 planning-only 边界，并以 `DRAFT` 保存初始审计事件 | 真实项目记录与项目 ID | 输入无效或事务失败时不创建任何记录 | 否 |
| 2. 上传图片与权利声明 | 一张主图片、来源、权利声明和预期用途 | 校验文件头、允许格式和上传限制，保存不可变 `ImageAsset`；只记录用户 attestation | `IMAGE_UPLOADED`、图片元数据与权利状态 | 文件不安全或不支持时拒绝；权利状态未确认时不得分析 | 权利声明由用户提交 |
| 3. 图片质量检查 | `ImageAsset` | 程序读取尺寸并依据版本化 Policy 执行模糊、亮度、遮挡检查 | `ImageQualityAssessment`；`pass` 进入 `IMAGE_VALIDATED`；`review` 进入 `IMAGE_REVIEW_REQUIRED` | `fail` 进入 `IMAGE_VALIDATION_FAILED`；服务故障进入有限重试；用户可重新上传 | `review` 时是 |
| 4. 区域建议 | 已验证且权利声明已确认的图片 | 启动一次 `AgentRun`，模型只生成候选语义、Bounding Box、材质、置信度和不确定原因 | `RegionSuggestion[]`；进入 `REGION_REVIEW_REQUIRED` 或低置信度阻塞 | Provider 或 Schema 错误按受限重试处理；未知标签必须人工重分类或删除 | 是 |
| 5. 人工区域确认 | 候选区域 | Polygon Editor 允许添加、修改、删除；每次保存产生包含完整语义和几何快照的 `RegionGeometryVersion` | 用户确认的完整区域快照 | 几何无效时拒绝保存；保留上一版本 | 是，阻塞 Gate |
| 6. 风格与光源确认 | 已确认区域、已冻结艺术配置 | 载入 `cel_shading / upper_left / medium` 等已确认字段，显示只读基线与人工可审查项 | `StyleConfiguration` | 配置缺失或未确认时禁止生成方案 | 是 |
| 7. 库存和知识检索 | 区域、风格、查询意图 | 对 `PaintInventoryItem` 做结构化查询；对文档分块检索并创建 Citation | 可用库存、缺失状态、`RetrievalCitation[]` | 无有效库存时明确显示缺失；无来源时不得伪造 Citation | 否，但材料事实需由用户预先确认 |
| 8. 方案生成 | 已确认区域、风格、库存、Citation | 模型组织候选方案；程序执行 Schema 和引用一致性校验 | 版本化 `PaintPlan` 与 `PaintPlanRegion[]` | Schema 无效不得进入审批；可受限重试或人工修订 | 否 |
| 9. 人工方案审批 | 结构化方案与引用 | 展示假设、未决问题、库存匹配与来源；接受审批或修订请求 | `PLAN_APPROVED` 或回到修订路径 | 未审批不得完成项目；LLM 无权改变审批结果 | 是，阻塞 Gate |
| 10. 保存版本和 Trace | 审批事件 | 保存计划版本、Approval、AgentRun、ModelCall 与 StateTransitionEvent | `COMPLETED` 项目及可审计记录 | 持久化失败时保持原状态并返回可重试错误 | 否 |

用户可在任何非终态通过 `abandon_project` 主动终止项目并进入 `ABANDONED`。运行中采用 best-effort cooperative cancellation；迟到 Provider 结果只能记录为 `discarded`，不得覆盖当前项目事实。

## 7. Functional Requirements

所有功能均处于 `MVP implementation (future)`，当前没有实现证据。

### FR-001 — Create Paint Project

- Requirement: 系统应允许用户创建一个 `PaintProject`，并以 `DRAFT` 作为初始状态。
- Rationale: 为图片、区域、方案、审批和 Trace 提供稳定聚合根。
- Input: Header `Idempotency-Key: UUID`；Body 只接受 `title` 与可选 `description`。
- Validation: `title` trim 后为 1–80 个 Unicode code point；`description` trim 后最多
  500 个 Unicode code point，空字符串归一化为 `null`。
- Program-owned Fields: 从请求 Principal 写入不可为空的 `owner_principal_id`；确定性
  写入 `requested_target_style=cel_shading`、`planning_mode=planning_only_demo` 和
  `status=DRAFT`。客户端不能提供或覆盖这些字段、ID 或时间戳。
- Output: HTTP 201；返回真实 PaintProject Read Schema，包括项目 ID、Owner、规范化
  字段、初始意图、planning-only 边界、`DRAFT` 状态和带时区时间戳。
- Acceptance Criteria: 有效输入只创建一个项目；重复请求遵守 14.1；创建同时保存
  `from_state=null → to_state=DRAFT` 的初始 StateTransitionEvent；PaintProject、状态
  事件和完成后的幂等结果在同一数据库事务提交，任一失败全部回滚。
- Failure / Fallback: 输入无效时返回字段级错误；持久化失败时不返回成功。
- Human Review Required: No.
- Planned Phase: Phase 1D vertical slice.

### FR-002 — Upload One Primary Image

- Requirement: 每个 MVP 项目应接收一张主图片并创建不可变 `ImageAsset`，同时记录最小范围的用户权利声明。
- Rationale: 严格限制 MVP 范围并保证图片版本可追踪。
- Input: 图片文件、原始文件名、项目 ID、来源类型、权利声明、预期用途和 `Idempotency-Key`。
- Output: 图片存储引用、SHA-256、格式、尺寸、大小、权利 attestation 与 `IMAGE_UPLOADED`。
- Acceptance Criteria: 满足 14.2 Image Upload Contract；同一上传幂等键不重复落库；原图保留；`rights_attestation_status != confirmed` 时不能开始区域分析。
- Failure / Fallback: 不支持或不安全文件被拒绝，不创建有效资产。
- Human Review Required: No.
- Planned Phase: MVP implementation.

### FR-003 — Validate Image Quality

- Requirement: 系统应依据版本化 `ImageQualityPolicy` 执行格式、尺寸、模糊、亮度和遮挡检查，并持久化 decision 为 `pass/review/fail` 的 `ImageQualityAssessment`。
- Rationale: 在模型调用前阻止明显不可用输入。
- Input: 主 `ImageAsset`。
- Output: 指标、Policy 版本、结论和原因；状态为 `IMAGE_VALIDATED`、`IMAGE_REVIEW_REQUIRED` 或 `IMAGE_VALIDATION_FAILED`。
- Acceptance Criteria: 满足 14.3 Image Quality Assessment Contract；`review` 必须产生人工决定；未通过或未完成人工复核时不能分析区域。
- Failure / Fallback: 图片校验服务技术故障创建 `operation_type=image_validation` 的 AgentRun 并进入 `FAILED_RETRYABLE`；默认最大重试 1 次；不得把未知结果写成通过。
- Human Review Required: Failed or ambiguous result only.
- Planned Phase: MVP implementation.

### FR-004 — Generate Structured Region Suggestions

- Requirement: 系统应让通用视觉模型按照 14.4 RegionSuggestion Schema 生成候选区域名称、显示名、材质、粗略 Bounding Box、置信度和不确定原因。
- Rationale: 降低人工初始标注成本，同时保持建议与事实分离。
- Input: 已验证主图、允许的语义标签集合。
- Output: `RegionSuggestion[]`，其状态固定为 `suggested`。
- Acceptance Criteria: 输出通过版本化 Schema；每项包含置信度、人工复核标志与 ModelCall 关联；未知标签标记为 `unknown_candidate`，不得静默写入已确认区域。
- Failure / Fallback: Schema 无效按策略重试；低置信度进入人工阻塞；最终失败进入错误状态。
- Human Review Required: Yes.
- Planned Phase: MVP implementation.

### FR-005 — Edit Region Polygons

- Requirement: Polygon Editor 应允许用户添加、修改和删除区域，并按 14.5 Geometry Contract 保存新的完整 `RegionGeometryVersion` 快照。
- Rationale: 模型不能可靠提供最终几何边界。
- Input: 候选区域、用户绘制的 normalized polygon coordinates。
- Output: 含不可变语义快照、完整几何映射和坐标系统版本的新 `RegionGeometryVersion`。
- Acceptance Criteria: 坐标、Polygon 和重叠 warning 满足 14.5；多 Polygon 可属于同一语义区域；旧版本保留；已确认区域可通过显式返工事件重新打开。
- Failure / Fallback: 非法、自交或空几何按定义的校验策略拒绝；上一版本不受影响。
- Human Review Required: Yes.
- Planned Phase: MVP implementation.

### FR-006 — Enforce Region Confirmation Gate

- Requirement: 只有用户确认同时包含确切语义快照和几何边界的当前 `RegionGeometryVersion` 后，项目才能进入 `REGIONS_CONFIRMED`。
- Rationale: 区域边界是用户事实，不是模型事实。
- Input: 当前 `RegionGeometryVersion`、用户确认事件。
- Output: `HumanApproval` 和 `REGIONS_CONFIRMED`。
- Acceptance Criteria: Approval 关联确切完整快照；缺少确认时 `start_plan_generation` 被拒绝；返工后旧 Approval superseded，旧计划 stale/superseded。
- Failure / Fallback: 版本已过期时要求重新加载和确认。
- Human Review Required: Yes; `REGION_REVIEW_REQUIRED` is blocking.
- Planned Phase: MVP implementation.

### FR-007 — Apply Confirmed Style Configuration

- Requirement: MVP 应使用用户已确认的 `cel_shading`、`upper_left`、`medium`、2 层硬边阴影、分块硬边高光和渐变政策。
- Rationale: 冻结艺术基线以便 Golden Case 和评测保持一致。
- Input: `StyleConfiguration` v0.1。
- Output: 可追踪、`user_confirmed=true` 的配置引用。
- Acceptance Criteria: 所有冻结字段通过枚举和范围校验；极少量人工过渡不得触发自动渐变计算。
- Failure / Fallback: 配置缺失或版本不符时阻止方案生成。
- Human Review Required: Yes, configuration is user-owned.
- Planned Phase: MVP implementation.

### FR-008 — Query Confirmed Paint Inventory

- Requirement: 系统应通过结构化字段查询已确认的 `PaintInventoryItem`，不得由模型猜测库存。
- Rationale: 库存是确定性业务事实。
- Input: 区域目标、库存过滤条件。
- Output: 已验证匹配项或明确缺失状态。
- Acceptance Criteria: 只把 `verified=true` 且所有权状态明确的项作为已确认库存；返回数据来源。
- Failure / Fallback: 当前 Golden Case 只有品牌级计划时，显示库存未就绪，不生成具体色号。
- Human Review Required: Material data must be user-confirmed before use.
- Planned Phase: MVP implementation.

### FR-009 — Retrieve Knowledge Documents

- Requirement: 系统应按 14.6 Knowledge Permission Contract 检索 PDF、Markdown 或 TXT 文档中的相关 `KnowledgeChunk`。
- Rationale: 让方案引用可追溯的内部知识而不是无来源生成。
- Input: 区域、材料与施工问题。
- Output: 排序后的 chunks 与检索元数据。
- Acceptance Criteria: 每个结果关联文档、chunk 和定位信息；权限固定为项目级 `project_private`；不返回无权限内容。
- Failure / Fallback: 无结果时返回 `no_source_found`，不得生成虚假来源。
- Human Review Required: No, but citations are visible during plan review.
- Planned Phase: MVP implementation.

### FR-010 — Create Retrieval Citations

- Requirement: 每个被方案使用的知识主张应按照 14.8 Citation Consistency Contract 关联 `RetrievalCitation`。
- Rationale: 支持人工核对和审计。
- Input: 检索结果与被支持的方案字段。
- Output: 文档、chunk、locator、摘录摘要和关联 target。
- Acceptance Criteria: Citation 必须指向真实、可访问且版本可回溯的文档与 chunk；库存事实不得伪装成 Citation；旧计划 Citation 不自动复制到新计划。
- Failure / Fallback: 缺少来源时将主张标为未支持或移除，不得伪造 Citation。
- Human Review Required: Reviewed at plan gate.
- Planned Phase: MVP implementation.

### FR-011 — Generate Structured Paint Plan

- Requirement: 系统应按照 14.7 PaintPlan Schema 生成版本化 `PaintPlan` 和 `PaintPlanRegion[]`。
- Rationale: 让输出可测试、可保存、可比较，而不是只保留自由文本。
- Input: 已确认区域、StyleConfiguration、已确认库存、Citation。
- Output: 基础版本引用、assumptions、unresolved_questions、overall_steps、区域步骤、材料引用、citations 和结构化 uncertainties。
- Acceptance Criteria: Schema 校验成功；图片、区域、风格版本可追踪；库存引用存在；Citation 可解析；保存 prompt/schema 版本和 ModelCall ID；低置信度只能通过 uncertainties 和 Guard 进入人工评审。
- Failure / Fallback: 无效输出不得进入 `PLAN_REVIEW_REQUIRED`；按限制重试或转最终失败。
- Human Review Required: Yes after generation.
- Planned Phase: MVP implementation.

### FR-012 — Enforce Plan Review Gate

- Requirement: 用户应能批准方案、请求仅方案修订或请求区域返工；只有批准事件能进入 `PLAN_APPROVED`。
- Rationale: 艺术与施工可行性必须由人判断。
- Input: 当前 PaintPlan 版本、decision、revision_scope、reason 和 `Idempotency-Key`。
- Output: 版本绑定的 `HumanApproval`；仅方案修订进入 `REGIONS_CONFIRMED`，区域返工进入 `REGION_REVIEW_REQUIRED`。
- Acceptance Criteria: LLM 不能写入 approved；过期版本不能被批准；仅方案修订保持区域快照不变；区域返工创建新快照、supersede 旧区域 Approval、使旧计划 stale/superseded 且不转移 Citation。
- Failure / Fallback: 决策无效或版本冲突时返回业务错误。
- Human Review Required: Yes; `PLAN_REVIEW_REQUIRED` is blocking.
- Planned Phase: MVP implementation.

### FR-013 — Complete Approved Project

- Requirement: 只有 `PLAN_APPROVED` 项目可以通过程序命令进入 `COMPLETED`。
- Rationale: 防止未审批方案被误认为完成。
- Input: 当前项目版本、完成命令。
- Output: `COMPLETED` 与审计事件。
- Acceptance Criteria: Guard 验证有效 Approval 和目标计划版本；转换幂等。
- Failure / Fallback: 缺少 Approval 时返回 `PLAN_APPROVAL_REQUIRED`。
- Human Review Required: Approval already required.
- Planned Phase: MVP implementation.

### FR-014 — Preserve Versions

- Requirement: 图片、区域几何、PaintPlan、Prompt 和 Schema 必须具有可追踪版本。
- Rationale: 支持审计、回滚和评测对比。
- Input: 修改命令及当前版本号。
- Output: 新版本与父版本关联。
- Acceptance Criteria: 不原地覆盖不可变版本；RegionDefinition 修改创建替代实体；RegionGeometryVersion 保存完整语义与几何快照；Approval 绑定确切版本；旧版本不可静默删除。
- Failure / Fallback: 乐观锁冲突时拒绝并要求重新加载。
- Human Review Required: No.
- Planned Phase: MVP implementation.

### FR-015 — Record Trace and Audit

- Requirement: 系统应按照 14.9 Trace Transaction Contract 分别记录 `AgentRun`、`ModelCall` 和 `StateTransitionEvent`。
- Rationale: 区分业务工作流、Provider 调用与确定性状态变更。
- Input: 命令、模型响应元数据、actor、reason。
- Output: 延迟、用量、估算成本、重试、版本和转换记录。
- Acceptance Criteria: 三类记录通过 correlation ID 关联但不混为同一实体；项目状态更新与 StateTransitionEvent 同事务提交；不可审计的模型调用不得继续；不记录完整 API Key、完整 Prompt 或不必要图片二进制。
- Failure / Fallback: Trace 写入失败不得伪装成功；按一致性策略处理业务事务。
- Human Review Required: No.
- Planned Phase: MVP implementation.

### FR-016 — Handle Errors, Retries and Fallbacks

- Requirement: 计划中的外部操作应有超时、有限重试、14.10 Error Contract、用户放弃路径和最终失败路径。
- Rationale: 防止无限循环和不可审计失败。
- Input: 失败分类、operation、retry_count、max_retries。
- Output: `FAILED_RETRYABLE`、`BLOCKED_LOW_CONFIDENCE`、`FAILED_FINAL` 或 `ABANDONED`。
- Acceptance Criteria: 重试依据 operation_type、resume_state、retry_count 和 max_retries；默认上限为 image validation 1 次、region analysis 2 次、plan generation 2 次且可配置；用户主动放弃只进入 `ABANDONED`；运行中迟到结果不得恢复或覆盖项目。
- Failure / Fallback: 不可重试错误直接进入 `FAILED_FINAL`；低置信度进入人工路径；用户可在任何非终态主动放弃。
- Human Review Required: Low-confidence and material ambiguity cases.
- Planned Phase: MVP implementation.

## 8. Non-Functional Requirements

所有指标在实现后测量；本文档不声明已经达到性能或质量目标。

| ID | Requirement | Planned Verification |
| --- | --- | --- |
| NFR-001 | 所有模型输入后的结构化抽取与 PaintPlan 必须通过版本化 Schema validation。 | Schema 合法/非法 fixture 测试，planned。 |
| NFR-002 | API、领域命令和持久化边界应保持类型安全，禁止依赖未校验动态字段推进状态。 | 类型检查与契约测试，planned。 |
| NFR-003 | 状态 Guard、解析器、库存查询和版本规则应可独立测试。 | 单元与集成测试设计，planned。 |
| NFR-004 | AgentRun、ModelCall、错误、状态转换和 initiating Principal 应可观测并可关联。 | Trace 与 Principal 审计完整性检查，planned。 |
| NFR-005 | 创建、上传、生成和完成命令应支持幂等键或等效防重机制。 | 重复请求测试，planned。 |
| NFR-006 | 用户可见错误应包含稳定错误码、原因、影响和下一步，不暴露内部秘密。 | 错误契约评审，planned。 |
| NFR-007 | 上传文件应校验文件头、MIME、大小与安全策略；不能只信任扩展名。 | 恶意/错误文件 fixture，planned。 |
| NFR-008 | 外部 API 和模型 Provider 调用应配置超时与取消策略；具体阈值待实测后冻结。 | 超时与取消测试，planned。 |
| NFR-009 | 每次 ModelCall 应记录 provider timestamps、token/usage、latency 和 estimated cost；Provider 无用量时记录 `usage_unavailable`。 | Provider 响应与成本重算测试，planned。 |
| NFR-010 | 项目、版本、审批和状态转换应持久化；成功响应前满足定义的一致性边界。 | 持久化故障测试，planned。 |
| NFR-011 | 文件、知识文档、库存、方案和 Trace 应采用 owner-based project_private 访问控制；当前 MVP 不引入完整多租户或复杂 RBAC。 | Principal/ownership 权限矩阵评审，planned。 |
| NFR-012 | 日志和 Trace 不得记录完整 API Key、secret 或授权头。 | 日志扫描，planned。 |
| NFR-013 | 日志不得记录不必要的完整图片二进制；使用资产 ID、哈希和必要元数据。 | 日志负载检查，planned。 |
| NFR-014 | 部署产物应可重复构建，运行配置与代码分离；目标平台仍是 Open Question。 | 构建与部署演练，planned。 |
| NFR-015 | 版本写入和状态转换应使用并发控制，避免旧客户端静默覆盖新版本。 | 并发冲突测试，planned。 |

## 9. Human-in-the-loop Gates

### 9.0 IMAGE_REVIEW_REQUIRED — Supplemental Review

- 进入条件：`ImageQualityAssessment.decision=review`。
- 定位：附加人工图片复核状态，不是区域和方案两个核心业务审批 Gate 之一。
- 用户动作：`approve_image`、`reject_image` 或重新上传图片。
- Approval：使用 `approval_type=image_quality`，绑定确切 `ImageQualityAssessment.id`。
- 批准含义：只表示用户允许该图片进入当前 planning-only 流程，不表示图片完美，也不表示颜色适合精确校准。
- 阻塞规则：没有人工决定时不能进入 `IMAGE_VALIDATED` 或开始区域分析。

### 9.1 REGION_REVIEW_REQUIRED

- 进入条件：模型区域建议已通过 Schema，或用户从低置信度阻塞进入人工编辑。
- 阻塞规则：没有用户确认的 `RegionGeometryVersion`，不能执行 `start_plan_generation`。
- 用户动作：添加、修改、删除 Polygon；确认语义与当前几何版本。
- 低置信度：必须显示 uncertainty reason 并进入人工处理。
- 权限边界：模型只能建议，不能把区域审批写成 approved。

### 9.2 PLAN_REVIEW_REQUIRED

- 进入条件：PaintPlan Schema、库存引用与 Citation 一致性检查通过；低置信度建议需带警告。
- 阻塞规则：没有绑定当前计划版本的用户批准，不能进入 `PLAN_APPROVED` 或 `COMPLETED`。
- 用户动作：批准、请求仅方案修订，或请求区域返工，并填写原因。
- 权限边界：LLM 不能自行将 HumanApproval decision 改为 approved。

## 10. Deterministic vs Model Responsibilities

| Responsibility | Program / Database | Model | Human |
| --- | --- | --- | --- |
| 文件格式与安全校验 | Responsible | Not allowed | 提供文件 |
| 图片来源与权利声明 | Stores attestation; does not perform legal verification | Not authoritative | Provides attestation |
| 图片尺寸、大小、SHA-256 | Responsible | Not authoritative | 可查看 |
| 图片质量人工复核 | Stores version-bound decision | May provide non-authoritative signals | Authoritative for workflow continuation only |
| 项目状态与 Guard | Responsible | Not allowed to mutate | 触发授权事件 |
| 结构化输出 Schema 校验 | Responsible | Produces candidate output | 审核业务意义 |
| 颜料库存事实 | Structured query; authoritative | May explain, cannot invent | 确认拥有与数据来源 |
| 颜色距离计算 | Deterministic algorithm | May explain result | 判断艺术适用性 |
| 权限判断 | Responsible | Not authoritative | 提供授权和审批 |
| Principal 识别与项目所有权 | Adapter + program Guard; authoritative | Not authoritative | Provides authenticated/demo context |
| HumanApproval 审批者身份 | Stores stable principal ID and display snapshot | Not allowed to impersonate | Human Principal only |
| 版本编号与并发控制 | Responsible | Not allowed | 选择要审批的版本 |
| 重试次数、超时、延迟、成本 | Responsible | Not authoritative | 可查看 |
| 图片语义理解 | Validates schema | Responsible for suggestion | 审核 |
| 候选区域建议 | Stores as suggestion | Responsible | 确认/修正 |
| 文档查询意图理解 | Executes retrieval | Responsible for intent | 可修正查询 |
| 方案组织与推荐解释 | Validates output | Responsible | 审批 |
| 不确定性说明 | Requires field | Responsible | 决定是否接受 |
| 区域边界 | Stores confirmed version | Suggests only | Authoritative |
| 风格与材料确认 | Stores confirmed facts | Cannot self-approve | Authoritative |
| 艺术可行性判断 | Not authoritative | Suggests only | Authoritative |

## 11. Business Value Metrics

以下全部为待测指标，不表示已有改善。

| Metric | Calculation / Data Source |
| --- | --- |
| `time_to_first_plan` | 第一张有效图片上传时间到第一份 Schema-valid PaintPlan 创建时间；来自事件时间戳。 |
| `region_suggestion_acceptance_rate` | 未经几何修改即被确认的建议区域数 / 被审查建议区域总数。 |
| `region_manual_edit_rate` | 发生用户 Polygon 添加、修改或删除的区域数 / 被审查区域总数。 |
| `plan_first_approval_rate` | 第一版即获批准的项目数 / 进入 PLAN_REVIEW_REQUIRED 的项目数。 |
| `citation_coverage_rate` | 需要外部知识支持且具有有效 Citation 的方案主张数 / 需要来源的方案主张总数。 |
| `inventory_match_rate` | 引用已确认库存项的材料建议数 / 所有需要材料的建议数。 |
| `schema_valid_output_rate` | 首次模型输出即通过 Schema 的调用数 / 产生结构化输出的 ModelCall 总数。 |
| `task_completion_rate` | 进入 COMPLETED 的项目数 / 创建且未被主动放弃的项目数。 |
| `provider_latency` | `ModelCall.provider_completed_at - provider_started_at`；`latency_ms` 是程序计算的缓存值；按 provider/model 分类。 |
| `estimated_model_cost` | 程序根据 `raw_usage`、`currency`、`pricing_source` 和 `pricing_version` 计算；usage 不可用时标记 `usage_unavailable`，不得编造。 |
| `retry_rate` | 发生至少一次自动重试的外部操作数 / 外部操作总数。 |
| `fallback_rate` | 进入人工低置信度或降级路径的运行数 / AgentRun 总数。 |

## 12. Validation Boundary

### 12.1 Requirements Baseline and Future MVP Can Validate

- 输入能否被确定性文件与质量规则接受；
- 图片权利声明是否被记录并正确阻塞未确认状态；
- `pass/review/fail` 三个图片质量分支是否按版本化 Policy Fixture 工作；
- 模型候选区域是否结构完整；
- 用户能否修正和确认 Polygon；
- 状态机是否正确阻塞非法转换；
- StyleConfiguration 是否与 Golden Case 一致；
- 方案是否通过 Schema；
- 材料建议是否只引用已确认库存；
- 知识主张是否带真实检索来源；
- 版本、Trace、延迟、用量、成本估算和错误是否可记录；
- 人工评审是否认为计划具有施工可行性。

### 12.2 Cannot Validate in Current Golden Case

- 实际重涂后的颜色准确性或质量提升；
- 真实笔涂难度、干燥色差与材料兼容性；
- 补土和消光对实物颜色与质感的影响；
- 当前照片的精确颜色校准；
- 进度照片闭环；
- 真实完成品是否优于原始手办。
- 用户对第三方角色、产品造型或商标是否具有法律权利；系统只记录用户 attestation。

## 13. Open Questions

- Vallejo 产品系列、实际颜色与用户库存是什么？
- GSI Creos / Mr.Hobby 补土和消光的具体产品是什么？
- Golden Case 使用哪些 PDF、Markdown 或 TXT 作为知识库演示资料？
- MVP 采用哪个模型 Provider 与模型组合？
- 目标部署平台是什么？
- 首版实测后是否需要异步任务；如需要，触发条件是什么？
- 颜料颜色距离采用何种表示与算法？
- 自动评测的评分标准、阈值与人工标注集是什么？

已确认的 Cel Shading、光源、阴影、高光和渐变政策不属于 Open Question。

## 14. MVP Contract Appendices

以下契约是 MVP 验收基线。除明确放入 Implementation Readiness Gate 的校准值外，实现不得自行放宽或改变。

### 14.1 Command Idempotency Contract

- 适用命令：`create_paint_project`、`upload_image`、`confirm_regions`、
  `start_plan_generation`、`approve_plan`。
- 客户端必须提供 UUID 格式的 `Idempotency-Key`；客户端不能提供 `scope_key`。
- Idempotency-Key 是一次逻辑命令的唯一标识。客户端必须为每个新的逻辑命令生成新的
  UUID，不得在不同业务操作之间主动复用旧 Key；只有同一逻辑命令因 timeout 或未知
  结果重试时才复用原 Key 和不变的 canonical payload。
- 服务端为每条命令计算稳定 `scope_key`：
  - 创建项目：`principal:{principal_id}:command:create_paint_project`
  - 已有项目命令：
    `principal:{principal_id}:project:{project_id}:command:{command_type}`
- 唯一约束为 `scope_key + idempotency_key`。
- 创建命令不要求 project ID 进入幂等作用域，不从 Idempotency-Key 派生业务资源 ID，
  不使用客户端 project ID，也不确定性预分配 PaintProject UUID。
- `CommandIdempotencyRecord` 至少保存 `id`、`scope_key`、`principal_id`、
  `command_type`、`idempotency_key`、`payload_hash`、`execution_status`、
  `resource_type`、`resource_id`、`http_status`、`response_snapshot`、`created_at` 和
  `expires_at`。
- `execution_status` 至少允许 `in_progress/completed`。
- 对 Phase 1D 同步 Create Project，只有 `completed` 记录可以被其他请求读取；
  `in_progress` 保留给未来异步命令，不是当前 API 状态或响应分支。
- 规范化 payload hash 对版本化 canonical serialization 计算。Create Project 使用
  trim 后的 Title、trim 且空字符串转 `null` 后的 Description；不包含 Header 顺序、
  Secret、认证信息或服务端生成字段。
- Phase 1D Create Project 使用单一短数据库事务和 PostgreSQL 唯一约束仲裁：

  1. 开始事务，规范化请求并计算 payload_hash；
  2. 服务端计算 scope_key；
  3. 使用 `INSERT ... ON CONFLICT DO NOTHING` 尝试取得
     `scope_key + idempotency_key` 的执行权；
  4. 插入成功时，在同一事务创建 PaintProject、初始 StateTransitionEvent、保存 HTTP
     201 响应快照并把幂等记录完成为 `completed`；
  5. 唯一冲突时等待竞争事务结束，再读取已提交记录；相同 payload_hash 重放原 HTTP
     201，不同 payload_hash 返回 HTTP 409 `IDEMPOTENCY_KEY_REUSED`；
  6. 竞争事务回滚时，并发请求可以取得执行权并继续。
- 当前 API 不读取其他事务尚未提交的记录，也不暴露 in-progress 响应。
- 事务中只执行本地数据库工作，不包含外部网络调用。
- 数据库事务失败时业务资源、状态事件和幂等结果全部回滚；客户端可以使用同一 key
  安全重试。
- `expires_at` 固定为 `created_at + 24 hours`，表示记录最早可以进入清理流程的时间，
  即 minimum retention / cleanup eligibility；它不会自动使数据库中的现有记录失效，
  也不是客户端可以复用 Key 的时间。
- 只要幂等记录仍存在，相同 Key 与相同 payload_hash 重放原响应，相同 Key 与不同
  payload_hash 返回 HTTP 409 `IDEMPOTENCY_KEY_REUSED`，即使当前时间已经超过
  `expires_at`。
- 记录被未来清理机制删除后，旧 Key 可能不再被服务端识别；客户端仍不得依赖旧 Key
  的长期复用，新的逻辑命令必须使用新的 UUID。
- Phase 1D 不实现后台清理任务；清理机制延后到未来后台任务阶段，并需单独批准。
- 幂等重放不得重复创建项目、版本、Approval、AgentRun 或 ModelCall。

### 14.2 Image Upload Contract

- 允许 MIME：`image/jpeg`、`image/png`、`image/webp`。
- 禁止：SVG、GIF、动画 WebP，以及只依赖扩展名判断格式。
- 最大文件大小：20 MiB。
- 最短边至少 768 px。
- 最长边不超过 8192 px。
- 必须检查文件签名 / magic bytes，并验证实际类型与 MIME 一致。
- 必须计算 SHA-256。
- 原始文件不可原地覆盖。
- EXIF Orientation 可用于创建标准化分析版本，但原图必须保留且两个资产可追踪关联。
- EXIF 中不必要的位置数据不得写入普通日志或公开 API。

### 14.3 Image Quality Assessment Contract

`ImageQualityAssessment.decision` 固定为：

- `pass`
- `review`
- `fail`

至少保存：

- `policy_version`
- `blur_score`
- `brightness_score`
- `occlusion_flags`
- `reasons`
- `decision`
- `assessed_by`
- `model_call_id`
- `created_at`

规则：

- 格式、尺寸与文件完整性由程序判断。
- 模糊、亮度与遮挡可以组合确定性规则和非权威模型建议。
- 所有数值阈值属于版本化 `ImageQualityPolicy`。
- 当前需求基线不伪造未经评测的阈值。
- 自动化测试使用固定 Policy Fixture 验证 `pass/review/fail` 和技术故障四个分支。
- 真实阈值必须在实现前通过 Golden Case 与负面测试集校准，并通过 15.1 Readiness Gate。

### 14.4 RegionSuggestion Schema

每个版本化响应至少包含：

- `schema_version`
- `image_asset_id`
- `label`
- `display_name`
- `material`
- `bounding_box`
- `confidence`
- `uncertainty_reason`
- `requires_human_review`
- `model_call_id`
- `status`

`status` 必须为 `suggested`。Golden Case 已知 label 只允许：

- `hair`
- `skin`
- `upper_gi`
- `pants`
- `waist_sash`
- `wristbands`
- `boots`

未知 label 必须标记为 `unknown_candidate`，由用户重新分类或删除；不得静默写入已确认区域。

### 14.5 Geometry Contract

坐标系统：

- 坐标归一化到 `[0, 1]`。
- 原点为图片左上角。
- x 向右增加，y 向下增加。
- 每个几何快照保存坐标系统版本。

Polygon：

- 至少包含 3 个不同顶点。
- 每个点必须在 `[0, 1]` 范围内。
- 不允许 NaN 或 Infinity。
- 不允许自相交。
- 同一语义区域允许多个不连续 Polygon。
- 空 Polygon 不得确认。
- 跨区域重叠允许保存，但必须生成 warning。
- MVP 不自动判断复杂遮挡层级。

### 14.6 Knowledge Permission Contract

- MVP 没有公共注册或完整多租户。
- 知识文档权限固定使用 `project_private`。
- 文档只可被所属 PaintProject 使用，且当前 human Principal 必须匹配 `PaintProject.owner_principal_id`。
- 不实现跨 Workspace 或跨 Tenant 权限。
- 无权限文档不得被检索。
- RetrievalCitation 只能指向当前项目真实可访问的文档。
- 已授权 worker/system 必须携带 project ID 和 initiating principal ID，不得跨项目访问。

### 14.7 PaintPlan Schema

PaintPlan 至少包含：

- `schema_version`
- `project_id`
- `based_on_image_asset_id`
- `based_on_region_geometry_version_id`
- `style_configuration_id`
- `assumptions`
- `unresolved_questions`
- `overall_steps`
- `region_plans`
- `required_inventory_items`
- `missing_inventory_items`
- `citations`
- `uncertainties`
- `status`
- `prompt_version`
- `generated_by_model_call_id`

每个 `region_plan` 至少包含：

- `region_definition_id`
- `base_color_plan`
- `shadow_plan`
- `highlight_plan`
- `paint_candidates`
- `steps`
- `warnings`
- `citation_ids`

每个 `uncertainties` 条目至少包含：

- `code`
- `scope`
- `severity`
- `explanation`
- `requires_human_review`

MVP 不要求或推断具体 Vallejo 产品编号，也不使用未经校准的单一 plan confidence 数字。

### 14.8 Citation Consistency Contract

- Citation ID 必须存在于 RetrievalCitation。
- RetrievalCitation 必须绑定确切 `paint_plan_id`。
- Citation 必须指向真实、可访问的 KnowledgeDocument 和 KnowledgeChunk。
- 每个 Citation 必须可回溯到文档标题、chunk、locator 和内容版本。
- 用户没有上传资料时不得伪造引用。
- 库存事实使用 PaintInventoryItem ID，不得伪装成 Citation。
- 没有资料支持的建议必须标记为 `model_generated_guidance`。
- 旧计划的 Citation 继续属于旧计划，不自动复制或转移到新计划。

### 14.9 Trace Transaction Contract

- PaintProject.status 更新与 StateTransitionEvent 写入必须在同一数据库事务中。
- 状态变化没有对应 StateTransitionEvent 时不得提交。
- StateTransitionEvent 的结构化补充审计字段命名为 `event_metadata`，必须是 JSON
  object；它不能替代一等业务字段或保存未经合同批准的任意上下文。
- AgentRun 和 ModelCall 使用 correlation ID 关联。
- 数据库中的 StateTransitionEvent 是权威审计记录。
- 外部观测平台不是状态或审计事实来源；外部写入失败不得破坏数据库事实。
- ModelCall 记录创建失败时，不得执行不可审计的模型调用。
- Provider 调用结果更新失败时，AgentRun 进入 retryable 或 final failure，不得假装成功。
- 运行取消后到达的 Provider 结果只记录为 `discarded`，不得创建当前有效业务输出。

### 14.10 Error Contract

统一错误响应字段：

- `error_code`
- `category`
- `message`
- `retryable`
- `request_id`
- `current_state`
- `allowed_actions`
- `safe_details`

`category` 至少包含：

- `VALIDATION_ERROR`
- `NOT_FOUND`
- `IDEMPOTENCY_KEY_REUSED`
- `INVALID_STATE_TRANSITION`
- `CONFLICT`
- `DATABASE_UNAVAILABLE`
- `STORAGE_ERROR`
- `PROVIDER_TIMEOUT`
- `PROVIDER_RATE_LIMIT`
- `PROVIDER_RESPONSE_INVALID`
- `RETRIEVAL_ERROR`
- `SCHEMA_VALIDATION_ERROR`
- `INTERNAL_ERROR`

`message` 和 `safe_details` 不得返回 API Key、完整 Provider 原始响应、不必要的文件路径或用户文档完整内容。

### 14.11 Image Rights Attestation Contract

ImageAsset 至少保存：

- `source_type`
- `rights_attestation_status`
- `rights_attested_by_principal_id`
- `rights_attested_at`
- `intended_usage`

`rights_attestation_status`：`pending/confirmed/rejected`。

`intended_usage`：`private_project/portfolio_demo/public_repository`，可保存多个明确用途。

规则：

- `rights_attestation_status != confirmed` 时不得开始区域分析。
- 用户可以重新提交声明或更换图片；历史声明保留审计记录。
- 系统只记录用户声明，不进行法律权属验证。
- 用户声明不等于平台确认其拥有第三方角色、产品设计或商标权。
- 该能力是产品风险控制和审计能力，不是法律清权服务。

### 14.12 Workflow State Vocabulary

Product Contract 使用且只允许以下 16 个项目状态：

`DRAFT`、`IMAGE_UPLOADED`、`IMAGE_REVIEW_REQUIRED`、`IMAGE_VALIDATION_FAILED`、`IMAGE_VALIDATED`、`REGION_ANALYSIS_RUNNING`、`REGION_REVIEW_REQUIRED`、`REGIONS_CONFIRMED`、`PLAN_GENERATION_RUNNING`、`PLAN_REVIEW_REQUIRED`、`PLAN_APPROVED`、`COMPLETED`、`BLOCKED_LOW_CONFIDENCE`、`FAILED_RETRYABLE`、`FAILED_FINAL`、`ABANDONED`。

终态为 `COMPLETED`、`FAILED_FINAL`、`ABANDONED`。用户主动终止只能进入 `ABANDONED`。

Create Project 由服务端写入初始 `DRAFT`，客户端不能提交 status。数据库 status 约束
必须允许本节全部 16 个状态，并拒绝集合外字符串；初始默认值不能被实现为只允许
`DRAFT` 的永久数据库约束。

### 14.13 Revision and Termination Command Semantics

- `reopen_regions`: `REGIONS_CONFIRMED → REGION_REVIEW_REQUIRED`；用户主动重新打开已确认区域。
- `request_region_revision`: `PLAN_REVIEW_REQUIRED → REGION_REVIEW_REQUIRED`；方案评审发现区域本身需要调整。
- `request_plan_revision`: `PLAN_REVIEW_REQUIRED → REGIONS_CONFIRMED`；区域保持不变，只重新组织或修订方案。
- 前两个区域返工事件必须新建 RegionGeometryVersion、supersede 旧区域 Approval、使旧计划 stale/superseded、保留旧计划及其 Citation，并清除或更新 current_plan_id。
- `abandon_project`: 任一非终态进入 `ABANDONED`；运行中同时设置 AgentRun.cancel_requested_at。

### 14.14 Phase 1D PaintProject Creation and Read API Contract

完整 PaintProject 逻辑领域定义包含：

- `id`
- `owner_principal_id`
- `title`
- `description`
- `requested_target_style`
- `planning_mode`
- `status`
- `created_at`
- `updated_at`
- `current_image_asset_id`
- `current_region_version_id`
- `current_plan_id`

`requested_target_style` 是创建时初始意图。未来 StyleConfiguration 创建并确认后，详细
艺术配置以当前已确认 StyleConfiguration 为权威；两个字段不得静默冲突。

Phase 1D 首次物理表和 Read Schema 只包含前九个字段，即从 `id` 到 `updated_at`。
三个 `current_*` 字段保留为逻辑领域字段，但分别推迟到 ImageAsset、
RegionGeometryVersion 和 PaintPlan 实体表存在时通过后续 Migration 增加，并同时建立
真实 Foreign Key。不得提前创建没有引用完整性的 UUID 列。

#### Create

`POST /api/v1/paint-projects`

- Header：`Idempotency-Key: UUID`。
- Body 只接受 `title` 和 `description`。
- Body 不接受 `owner_principal_id`、`requested_target_style`、`planning_mode`、
  `status`、`id` 或 timestamps。
- 成功返回 HTTP 201 和真实 PaintProject Read Schema。

#### List

`GET /api/v1/paint-projects`

- 只返回当前 Principal 拥有的项目。
- 响应 Envelope 固定包含 `items`、`total`、`limit` 和 `offset`。
- 默认 `limit=20`、`offset=0`。
- `limit` 范围为 1–100；`offset` 最小为 0。
- `total` 表示应用分页前当前 Principal 可访问的匹配项目总数。
- 默认排序为 `updated_at DESC, id DESC`。
- 前端首屏卡片数量不限制 API 可返回的项目数量。

#### Detail

`GET /api/v1/paint-projects/{project_id}`

- 当前 Owner 读取存在的项目返回 HTTP 200。
- 项目不存在返回 HTTP 404。
- 项目属于其他 Principal 时同样返回 HTTP 404，不使用 403 暴露资源存在性。
- UUID 格式错误使用统一 Validation Error。

#### Errors

Phase 1D 至少规划：

- HTTP 422 validation error；
- HTTP 404 project not found；
- HTTP 409 `IDEMPOTENCY_KEY_REUSED`；
- HTTP 503 database unavailable；
- HTTP 500 safe internal error。

错误响应遵守 14.10，不得返回 SQL、Database URL、原始异常、Stack Trace 或其他
Principal 信息。

### 14.15 Phase 1D Physical Persistence Contract

本节冻结 Phase 1D-1B 首次物理 Schema 所需的字符串长度与 StateTransitionEvent
边界。所有字符串长度均以 Unicode 字符数量作为 API 和产品验证合同；PostgreSQL 使用
对应的 `VARCHAR(n)`，未来 Pydantic Schema 与数据库都必须执行相同上限。

#### PrincipalId

`PrincipalId` 是系统内部稳定 opaque identifier，物理类型为 `VARCHAR(128)`。它必须
trim、长度为 1–128、不得是空白字符串，不使用邮箱或 display name，也不得由客户端
覆盖项目 Owner。未来外部认证 subject 必须通过 Principal Adapter 映射为内部
PrincipalId；当前仍不创建 Principal 表，也不对安全格式施加过度严格的字符正则。

#### Physical String Matrix

| Table | Column | PostgreSQL type | Nullability / value boundary |
| --- | --- | --- | --- |
| `paint_projects` | `owner_principal_id` | `VARCHAR(128)` | Non-null PrincipalId |
| `paint_projects` | `title` | `VARCHAR(80)` | Non-null; trimmed; 1–80 |
| `paint_projects` | `description` | `VARCHAR(500)` | Nullable; trimmed when present |
| `paint_projects` | `requested_target_style` | `VARCHAR(32)` | Non-null; currently `cel_shading` |
| `paint_projects` | `planning_mode` | `VARCHAR(32)` | Non-null; currently `planning_only_demo` |
| `paint_projects` | `status` | `VARCHAR(64)` | Non-null; all 16 approved states |
| `state_transition_events` | `from_state` | `VARCHAR(64)` | Nullable; approved state when present |
| `state_transition_events` | `to_state` | `VARCHAR(64)` | Non-null approved state |
| `state_transition_events` | `event` | `VARCHAR(64)` | Non-null controlled machine token |
| `state_transition_events` | `actor_type` | `VARCHAR(32)` | Non-null controlled machine token |
| `state_transition_events` | `actor_principal_id` | `VARCHAR(128)` | Non-null PrincipalId |
| `state_transition_events` | `actor_display_name_snapshot` | `VARCHAR(200)` | Conditional; trimmed; 1–200 when present |
| `state_transition_events` | `reason` | `VARCHAR(128)` | Conditional controlled reason code |
| `command_idempotency_records` | `scope_key` | `VARCHAR(512)` | Non-null; server-generated; trimmed; 1–512 |
| `command_idempotency_records` | `principal_id` | `VARCHAR(128)` | Non-null PrincipalId |
| `command_idempotency_records` | `command_type` | `VARCHAR(64)` | Non-null controlled machine token |
| `command_idempotency_records` | `payload_hash` | `VARCHAR(64)` | Non-null lowercase SHA-256 hex |
| `command_idempotency_records` | `execution_status` | `VARCHAR(32)` | Non-null; `in_progress/completed` |
| `command_idempotency_records` | `resource_type` | `VARCHAR(64)` | Nullable until completed |

以下小写 machine-token 字段使用 canonical syntax：

`^[a-z][a-z0-9]*(?:_[a-z0-9]+)*$`

适用于 `command_type`、`event`、`reason`、`resource_type`、`actor_type`、
`execution_status`、`requested_target_style` 和 `planning_mode`。Token 必须以小写
英文字母开头；后续 segment 只包含小写字母或数字，segment 间使用单个下划线。禁止
大写、空格、连字符、连续下划线和尾随下划线。

格式 Check 不替代批准值白名单。固定枚举字段必须同时满足长度、machine-token 格式和
allowed-values 约束。

`PaintProject.status`、`StateTransitionEvent.from_state` 和
`StateTransitionEvent.to_state` 是例外：它们不使用小写正则，继续只允许 14.12 中
批准的 16 个大写 Workflow State，不改变名称、数量或大小写。

该正则不适用于 PrincipalId、`scope_key`、`title`、`description`、
`actor_display_name_snapshot`、`payload_hash`、UUID 或 JSONB 字段。`payload_hash`
独立使用 `^[0-9a-f]{64}$`；PrincipalId 不增加过度严格字符正则；`scope_key` 使用
服务端结构生成规则，不使用 snake_case 正则，也不包含 Secret 或原始请求正文。
`actor_display_name_snapshot` 是允许 Unicode 的审计显示快照。未来确需人工说明时，
必须新增经过批准的独立字段，不得把自由文本塞入 `reason`。

#### StateTransitionEvent First Physical Boundary

Phase 1D-1B 首次 `state_transition_events` 表恰好包含 12 个物理字段：
`id`、`project_id`、`from_state`、`to_state`、`event`、`actor_type`、
`actor_principal_id`、`actor_display_name_snapshot`、`reason`、`correlation_id`、
`event_metadata` 和 `created_at`。

`event_metadata` 使用 non-null PostgreSQL JSONB，server default 为 `{}`，并通过
`ck_state_transition_events_event_metadata_is_object` 保证顶层只能是 JSON object。
它只保存明确 Event Contract 批准的非敏感结构化审计补充字段；禁止原始请求或响应、
认证信息、Secret、DATABASE_URL、Stack Trace、异常对象、Prompt、模型完整输出、二进制、
文件内容、无 Schema 自由文本或为逃避建模而放入 JSON 的核心业务字段。当前
`create_project` 事件必须保存 `{}`，本阶段不创建 JSONB Index 或查询 API。

`agent_run_id` 仍是 StateTransitionEvent 的 nullable 逻辑领域字段，但 Phase 1D-1B
不创建该物理列。它随 `agent_runs` 表在 AgentRun persistence phase 引入，类型为 UUID，
同时建立真实 Foreign Key；默认 `NO ACTION / RESTRICT`，既有事件回填 `null`。在目标表
存在前，不创建裸 UUID、ORM relationship 或虚假 AgentRun 表，也不使用
`event_metadata` 替代该引用。

这项物理澄清不改变 Create Project 的单事务语义、幂等行为、Rights Attestation
所属阶段、16-state vocabulary、47 条 Transition 或 17 个 Guard，也不允许创建任何
没有真实 Foreign Key 的未来资源 UUID。

## 15. Implementation Readiness Gate

以下 Gate 是进入业务实现前的阻塞条件，不是隐含待办：

1. 发布版本化 ImageQualityPolicy，并用 Golden Case、遮挡、模糊、过暗、过曝和损坏文件 fixture 校准阈值。
2. 固定 Policy Fixture 必须覆盖 `pass/review/fail` 和 `image_validation_error`。
3. 发布 RegionSuggestion、RegionGeometryVersion、PaintPlan、Citation、AgentRun metadata 和 Error response 的版本化 Schema。
4. 冻结上传限制、幂等键规范化方式、默认重试配置和 Provider 超时配置。
5. 验证权利 attestation Gate、图片人工复核 Approval 和两个核心业务 Gate。
6. 验证区域返工会 supersede 旧 Approval、使旧计划 stale/superseded，并阻止旧 Citation 转移。
7. 验证运行中 abandon、`cancel_requested_at` 与迟到结果 discarded 保护。
8. 验证状态更新与 StateTransitionEvent 同事务，以及不可审计模型调用被阻止。
9. 验证所有用户可见错误满足 14.10 且日志、API 和 Trace 遵守敏感数据处理矩阵。
10. 验证 PrincipalContext Adapter、owner-based project_private Guard 和 initiating principal 传播。
11. 验证所有 HumanApproval 的 reviewer_principal_id、target_type、target_id、目标存在性和同项目归属。
12. 在线公开演示在真实认证前必须验证为只读、受保护单一操作者或部署平台访问保护之一，匿名写操作不得暴露。

任何一项未通过时，不得把对应能力标记为 implementation-ready。

### 15.1 Acceptance Criteria Mapping

| Requirement | Normative Contract / Readiness Evidence |
| --- | --- |
| `FR-001` | 14.1 Command Idempotency；14.14 PaintProject API；17.3 Project Ownership；project creation fixture |
| `FR-002` | 14.2 Image Upload；14.11 Rights Attestation；upload/EXIF/rights fixtures |
| `FR-003` | 14.3 Image Quality；Policy calibration Gate；pass/review/fail/error fixtures |
| `FR-004` | 14.4 RegionSuggestion Schema；known/unknown label fixtures |
| `FR-005` | 14.5 Geometry；valid/self-intersecting/overlap/reopen fixtures |
| `FR-006` | 14.13 Revision Semantics；18 HumanApproval Target；complete snapshot Approval and supersession fixtures |
| `FR-007` | Frozen Art Configuration；StyleConfiguration Schema and Golden Case fixture |
| `FR-008` | PaintInventoryItem validation；verified/owned/missing fixtures |
| `FR-009` | 14.6 Knowledge Permission；project-private allow/deny fixtures |
| `FR-010` | 14.8 Citation Consistency；valid/missing/stale source fixtures |
| `FR-011` | 14.7 PaintPlan Schema；valid/invalid/uncertainty fixtures |
| `FR-012` | 14.13 Revision Semantics；18 HumanApproval Target；current/stale plan Approval fixtures |
| `FR-013` | 14.9 Trace Transaction；completion Guard and idempotency fixtures |
| `FR-014` | Domain versioning and supersession rules；concurrency fixtures |
| `FR-015` | 14.9 Trace Transaction；ModelCall usage/cost and audit failure fixtures |
| `FR-016` | 14.10 Error Contract；retry defaults；abandon and late-result fixtures |

## 16. Traceability Matrix

所有 Test Type 和 Evidence 均为计划项，当前没有 passed 证据。

| Requirement ID | State | Primary Entity | Test Type | Evidence |
| --- | --- | --- | --- | --- |
| FR-001 | DRAFT | PaintProject, StateTransitionEvent, CommandIdempotencyRecord | Contract + integration, planned | Project creation fixture, planned |
| FR-002 | IMAGE_UPLOADED | ImageAsset, CommandIdempotencyRecord | File + rights contract, planned | Upload, EXIF and attestation fixtures, planned |
| FR-003 | IMAGE_VALIDATED / IMAGE_REVIEW_REQUIRED / IMAGE_VALIDATION_FAILED / FAILED_RETRYABLE | ImageQualityAssessment, HumanApproval, AgentRun | Policy + workflow, planned | pass/review/fail/error fixtures, planned |
| FR-004 | REGION_ANALYSIS_RUNNING / REGION_REVIEW_REQUIRED / BLOCKED_LOW_CONFIDENCE | RegionSuggestion, AgentRun, ModelCall | Schema + workflow, planned | Model response fixtures, planned |
| FR-005 | REGION_REVIEW_REQUIRED | RegionDefinition, RegionGeometryVersion | Geometry + UI contract, planned | Polygon, overlap and reopen fixtures, planned |
| FR-006 | REGION_REVIEW_REQUIRED / REGIONS_CONFIRMED | HumanApproval, StateTransitionEvent, CommandIdempotencyRecord | Guard + supersession test, planned | Full snapshot approval fixture, planned |
| FR-007 | REGIONS_CONFIRMED | StyleConfiguration | Schema + Golden Case, planned | Frozen configuration fixture, planned |
| FR-008 | REGIONS_CONFIRMED | PaintInventoryItem | Query + data validation, planned | Confirmed/unconfirmed inventory fixtures, planned |
| FR-009 | PLAN_GENERATION_RUNNING | KnowledgeDocument, KnowledgeChunk | Retrieval integration, planned | Search corpus fixture, planned |
| FR-010 | PLAN_GENERATION_RUNNING | RetrievalCitation | Citation integrity, planned | Citation locator fixture, planned |
| FR-011 | PLAN_GENERATION_RUNNING / PLAN_REVIEW_REQUIRED | PaintPlan, PaintPlanRegion, ModelCall, AgentRun, CommandIdempotencyRecord | Schema + integration, planned | Valid/invalid plan fixtures, planned |
| FR-012 | PLAN_REVIEW_REQUIRED / PLAN_APPROVED | HumanApproval, CommandIdempotencyRecord | Guard + concurrency, planned | Approval and stale-version fixtures, planned |
| FR-013 | PLAN_APPROVED / COMPLETED | PaintProject, StateTransitionEvent | State transition, planned | Completion guard fixture, planned |
| FR-014 | Multiple states | RegionGeometryVersion, PaintPlan | Versioning + concurrency, planned | Version history fixture, planned |
| FR-015 | Multiple states | AgentRun, ModelCall, StateTransitionEvent | Observability, planned | Trace correlation fixture, planned |
| FR-016 | FAILED_RETRYABLE / BLOCKED_LOW_CONFIDENCE / FAILED_FINAL / ABANDONED | AgentRun, StateTransitionEvent | Retry + cancellation + failure path, planned | Timeout/retry/late-result fixtures, planned |

## 17. MVP Principal and Access Contract

### 17.1 Principal

Principal 表示一次请求或已授权后台操作中已经识别的操作者。最小字段为：

- `principal_id`
- `principal_type`
- `display_name`
- `authentication_mode`

`principal_type`：

- `human`
- `system`

`authentication_mode`：

- `local_development`
- `configured_demo_operator`
- `future_authenticated_user`

规则：

1. principal_id 使用统一 `PrincipalId` Value Type：trim 后长度 1–128，物理持久化为
   `VARCHAR(128)`；它必须稳定、非空，且不能依赖 display_name。
2. display_name 只用于界面显示和历史展示快照，不参与权限判断。
3. API、worker 和 system actor 不得伪装成人工审批者。
4. HumanApproval 只能由 `principal_type=human` 的 Principal 创建。
5. 系统自动转换使用 system actor，但不能创建 approved 的人工审批。
6. 日志可记录非秘密 principal_id，不得记录认证秘密。
7. 外部认证 subject 必须由未来 Adapter 映射为内部 PrincipalId；当前只定义 Adapter
   契约，不实现第三方登录、Principal 表或完整用户管理。

### 17.2 MVP Access Mode

开发和本地演示：

- 使用固定、由环境配置的开发 Principal。
- Phase 1D 使用 `authentication_mode=configured_demo_operator` 或等价配置型 Adapter，
  且创建项目的 Principal 必须是 `principal_type=human`。
- 非秘密示例 ID 为 `local-demo-owner`。
- 不得把个人邮箱、密码、API Key 或 Session Secret 硬编码进仓库。
- 环境变量只可保存非秘密 Principal 标识和展示名称；认证秘密不属于 Principal 数据。

在线公开演示：

- 在真实认证实现前，写操作不得匿名公开暴露。
- 只能选择受保护的单一演示操作者、只读公开演示或部署平台访问保护之一。
- “没有公共注册”不等于“任何访问者可以修改项目”。
- 后续正式生产化阶段通过 Adapter 接入真实认证，不改变领域审批语义。

### 17.3 Project Ownership

PaintProject 必须保存 `owner_principal_id`：

- 创建项目时从经过验证的请求 Principal 写入。
- worker/system Principal 不能创建归属于 human 的 Phase 1D 项目。
- 创建后不可为空，MVP 不支持转移所有权。
- 客户端不得任意提交或覆盖其他 owner_principal_id。
- project_private 文档、图片、库存、方案和 Trace 必须属于同一 PaintProject。
- human Principal 读取或修改项目时必须满足 `current_principal_id == owner_principal_id`。
- worker/system 只能在已授权项目上下文运行，必须携带 project_id 和 initiating_principal_id。
- worker/system 不得跨项目读取或写入数据。

### 17.4 Human Audit Identity

以下持久化字段统一保存稳定 Principal 标识：

- `PaintProject.owner_principal_id`
- `HumanApproval.reviewer_principal_id`
- `ImageAsset.rights_attested_by_principal_id`
- `RegionDefinition.created_by_principal_id`
- `RegionGeometryVersion.created_by_principal_id`
- `StateTransitionEvent.actor_principal_id`
- `AgentRun.initiating_principal_id`
- `CommandIdempotencyRecord.principal_id`

以下字段只保存历史展示快照，不参与权限判断：

- `HumanApproval.reviewer_display_name_snapshot`
- `StateTransitionEvent.actor_display_name_snapshot`

Principal 展示名称后续变化时，不得回写或修改历史审批与状态事件。

## 18. HumanApproval Target Contract

HumanApproval 至少包含：

- `id`
- `project_id`
- `approval_type`
- `decision`
- `target_type`
- `target_id`
- `reviewer_principal_id`
- `reviewer_display_name_snapshot`
- `reason`
- `created_at`
- `superseded_at`

`approval_type`：

- `image_quality`
- `region_geometry`
- `paint_plan`
- `style_configuration`

`target_type`：

- `image_quality_assessment`
- `region_geometry_version`
- `paint_plan`
- `style_configuration`

`decision`：

- `approved`
- `rejected`
- `revision_requested`

固定类型映射：

| approval_type | target_type |
| --- | --- |
| `image_quality` | `image_quality_assessment` |
| `region_geometry` | `region_geometry_version` |
| `paint_plan` | `paint_plan` |
| `style_configuration` | `style_configuration` |

这是受控多态引用，规则如下：

1. `target_type + target_id` 共同确定唯一审批对象。
2. approval_type 必须与 target_type 使用固定映射。
3. target 必须存在。
4. target 必须属于 HumanApproval.project_id 指向的同一个 PaintProject。
5. target 必须是不可变或版本化对象。
6. 不允许审批“当前最新版本”等动态引用。
7. 新版本创建后，旧 Approval 不自动适用于新版本。
8. superseded Approval 必须保留，不得删除。
9. 客户端不得把 target_id 指向其他项目。
10. 数据库无法建立统一多态外键时，应用服务必须在同一事务中验证目标类型、存在性和项目归属。
11. MVP 不为四种审批目标增加四张独立审批表；后续可按数据库与合规需求重新评估。
