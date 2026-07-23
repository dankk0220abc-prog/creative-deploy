# PaintPilot Domain Data Dictionary v0.1

## 1. Document Metadata

- Document Status: `APPROVED_FOR_IMPLEMENTATION`
- Version: `0.1.1`
- Implementation Status: `NOT_STARTED`
- Scope: PaintPilot MVP only

本实现基线定义 18 个持久化实体；PrincipalContext 仍是非持久化 Value Object。数据库表和 Migration 尚未创建。本文档不是已存在数据的声明，所有示例均满足所列 Validation，但不代表 Golden Case 的真实业务记录。

## 2. Data Design Principles

- **用户确认事实**：图片继续使用决定、完整区域快照、风格、材料拥有状态和方案审批由用户确认。
- **程序计算事实**：状态、文件哈希、图片尺寸、版本号、重试次数、延迟和成本估算由程序产生。
- **模型建议**：候选区域、置信度、查询意图、方案和不确定性只作为建议，不能覆盖用户事实。
- **权利 attestation**：系统记录用户声明，不进行法律权属验证，也不把声明解释为第三方官方授权。
- **人工审批**：图片 review、区域和方案使用独立 HumanApproval，并绑定确切目标版本。
- **Trace 与审计**：AgentRun、ModelCall 和 StateTransitionEvent 分开保存并通过 correlation ID 关联。
- **版本优先**：图片不覆盖；RegionDefinition 不可变；RegionGeometryVersion 保存完整语义与几何快照；PaintPlan 版本化。
- **稳定 Principal**：权限判断使用稳定 principal_id；展示名称仅作为历史快照，不作为身份或授权依据。
- **单一项目所有者**：MVP 的 project_private 数据由 PaintProject.owner_principal_id 隔离，不引入 Workspace、Tenant 或复杂 RBAC。
- **最小范围**：MVP 不定义 Workspace、Tenant、Billing、Subscription 或独立任务队列实体。

## 3. Type and Classification Conventions

### 3.1 Types

- `UUID`: RFC 4122 格式的稳定唯一标识。
- `PrincipalID`: 已识别 human 或 system Principal 的稳定、非空标识；不得使用 display_name 代替。
- `String`: UTF-8 字符串。
- `Enum`: 受版本化枚举约束的字符串。
- `Timestamp`: ISO-8601 带时区时间。
- `JSON`: 通过版本化 Schema 校验的结构。
- `Decimal`: 精确定点数；不用于声称精确实物颜色。
- `Polygon[]`: 一个或多个 normalized polygon。
- `BBox`: normalized `{x, y, width, height}` 粗略框。

### 3.2 Data Classifications

- `PUBLIC`：可公开展示的非秘密结构和演示信息。
- `INTERNAL`：不应默认公开，但可用于系统内部处理和受控日志。
- `SENSITIVE`：不得写入普通日志；API、Trace 和导出需要脱敏或权限控制。

### 3.3 PaintProject Status Enum

`DRAFT`、`IMAGE_UPLOADED`、`IMAGE_REVIEW_REQUIRED`、`IMAGE_VALIDATION_FAILED`、`IMAGE_VALIDATED`、`REGION_ANALYSIS_RUNNING`、`REGION_REVIEW_REQUIRED`、`REGIONS_CONFIRMED`、`PLAN_GENERATION_RUNNING`、`PLAN_REVIEW_REQUIRED`、`PLAN_APPROVED`、`COMPLETED`、`BLOCKED_LOW_CONFIDENCE`、`FAILED_RETRYABLE`、`FAILED_FINAL`、`ABANDONED`。

终态为 `COMPLETED`、`FAILED_FINAL`、`ABANDONED`；`ABANDONED` 不得与技术失败合并。

### 3.4 Non-persistent Value Object: PrincipalContext

PrincipalContext 来自请求认证或演示访问 Adapter，仅描述当前已识别的操作者；它不是持久化实体，也不创建数据库表。

| Field Name | Type | Required | Source of Truth | Description | Validation | Example |
| --- | --- | --- | --- | --- | --- | --- |
| `principal_id` | PrincipalID | Yes | Authentication/demo access Adapter | 当前操作者的稳定标识 | Non-empty; independent of display_name | `local-demo-owner` |
| `principal_type` | Enum | Yes | Authentication/demo access Adapter | 主体类型 | `human/system` | `human` |
| `display_name` | String | Yes | Authentication/demo access Adapter | 界面展示名称 | Non-empty; never used for authorization | `Local Demo Owner` |
| `authentication_mode` | Enum | Yes | Authentication/demo access Adapter | 身份识别方式 | `local_development/configured_demo_operator/future_authenticated_user` | `local_development` |

需要审计时，将 principal_id 与必要的展示名称快照写入对应业务实体。后续接入真实认证系统只替换 Adapter，不改变项目所有权或人工审批的领域语义。认证秘密不属于 PrincipalContext。

## 4. Entity Definitions

### 4.1 PaintProject

项目聚合根；当前状态由程序和数据库控制。

| Field Name | Type | Required | Source of Truth | Mutable | Description | Validation | Classification | Example |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `id` | UUID | Yes | Program/database | No | 项目标识 | UUID | INTERNAL | `00000000-0000-4000-8000-000000000001` |
| `owner_principal_id` | PrincipalID | Yes | Request PrincipalContext/program | No | MVP 项目所有者 | Non-empty stable ID; cannot be client-overridden; ownership transfer unsupported | INTERNAL | `local-demo-owner` |
| `title` | String | Yes | User | Yes | 用户可见标题 | 1–200 chars | INTERNAL | `Goku planning case` |
| `description` | String | No | User | Yes | 可选项目说明；不承载系统状态 | Configured finite upper bound; fixture limit 2000 chars | INTERNAL | `Planning-only cel-shading study` |
| `status` | Enum | Yes | Program/database | Yes, guarded | 当前工作流状态 | 16-state inventory | INTERNAL | `IMAGE_REVIEW_REQUIRED` |
| `created_at` | Timestamp | Yes | Program | No | 创建时间 | ISO-8601 | INTERNAL | `2026-07-23T09:00:00+08:00` |
| `updated_at` | Timestamp | Yes | Program | Yes | 最近更新时间 | Monotonic per record | INTERNAL | `2026-07-23T09:15:00+08:00` |
| `current_image_asset_id` | UUID | No | Program/database | Yes, guarded | 当前主图片 | Existing project ImageAsset | INTERNAL | `00000000-0000-4000-8000-000000000002` |
| `current_region_version_id` | UUID | No | Program/database | Yes, guarded | 当前完整区域快照 | Existing project RegionGeometryVersion | INTERNAL | `00000000-0000-4000-8000-000000000007` |
| `current_plan_id` | UUID | No | Program/database | Yes, guarded | 当前非 stale 方案 | Existing project PaintPlan or null | INTERNAL | `00000000-0000-4000-8000-000000000013` |

### 4.2 ImageAsset

不可变图片资产记录；替换图片创建新实体。

| Field Name | Type | Required | Source of Truth | Mutable | Description | Validation | Classification | Example |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `id` | UUID | Yes | Program | No | 图片资产 ID | UUID | INTERNAL | `00000000-0000-4000-8000-000000000002` |
| `project_id` | UUID | Yes | Program/database | No | 所属项目 | Existing PaintProject | INTERNAL | `00000000-0000-4000-8000-000000000001` |
| `storage_key` | String | Yes | Storage adapter | No | 非公开存储定位 | Allowed key format | SENSITIVE | `projects/0001/images/0002` |
| `original_filename` | String | Yes | Upload metadata | No | 用户原文件名 | Sanitized; no path traversal | SENSITIVE | `primary-front.jpeg` |
| `mime_type` | Enum | Yes | Program inspection | No | 实际 MIME | `image/jpeg/image/png/image/webp` | INTERNAL | `image/jpeg` |
| `width` | Integer | Yes | Program inspection | No | 像素宽度 | 768–8192 policy bounds | INTERNAL | `1320` |
| `height` | Integer | Yes | Program inspection | No | 像素高度 | 768–8192 policy bounds | INTERNAL | `1656` |
| `size_bytes` | Integer | Yes | Program inspection | No | 文件大小 | 1–20971520 | INTERNAL | `332641` |
| `sha256` | String | Yes | Program | No | 字节哈希 | 64 lowercase hex chars | INTERNAL | `aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa` |
| `role` | Enum | Yes | Program command | No | 图片角色 | `primary_mvp_input/normalized_analysis_copy` | INTERNAL | `primary_mvp_input` |
| `normalized_from_asset_id` | UUID | No | Program | No | 标准化分析版本的原始资产 | Existing immutable ImageAsset | INTERNAL | `null` |
| `source_type` | Enum | Yes | User attestation | No | 图片来源类型 | `user_provided/user_photographed/user_provided_other` | INTERNAL | `user_provided` |
| `rights_attestation_status` | Enum | Yes | User attestation | Yes, versioned event | 权利声明状态 | `pending/confirmed/rejected` | INTERNAL | `confirmed` |
| `rights_attested_by_principal_id` | PrincipalID | Conditional | PrincipalContext | No | 完成权利声明的 human Principal | Required when confirmed/rejected; must match authorized project owner | INTERNAL | `local-demo-owner` |
| `rights_attested_at` | Timestamp | Conditional | Program | No | 声明时间 | Required when confirmed/rejected | INTERNAL | `2026-07-23T09:04:00+08:00` |
| `intended_usage` | Enum[] | Yes | User attestation | Yes, versioned event | 明确预期用途 | Values from allowed usage enum | INTERNAL | `["private_project","portfolio_demo","public_repository"]` |
| `uploaded_at` | Timestamp | Yes | Program | No | 上传时间 | ISO-8601 | INTERNAL | `2026-07-23T09:05:00+08:00` |

### 4.3 ImageQualityAssessment

基于版本化 Policy 的图片质量记录；技术服务故障记录在 AgentRun，不伪装成质量 fail。

| Field Name | Type | Required | Source of Truth | Mutable | Description | Validation | Classification | Example |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `id` | UUID | Yes | Program | No | Assessment ID | UUID | INTERNAL | `00000000-0000-4000-8000-000000000003` |
| `image_asset_id` | UUID | Yes | Program | No | 被评估图片 | Existing ImageAsset | INTERNAL | `00000000-0000-4000-8000-000000000002` |
| `policy_version` | String | Yes | Program config | No | ImageQualityPolicy 版本 | SemVer | INTERNAL | `0.1.0` |
| `format_valid` | Boolean | Yes | Program inspection | No | 格式是否通过 | Boolean | INTERNAL | `true` |
| `dimension_valid` | Boolean | Yes | Program inspection | No | 尺寸是否通过 | Boolean | INTERNAL | `true` |
| `file_integrity_valid` | Boolean | Yes | Program inspection | No | 文件完整性是否通过 | Boolean | INTERNAL | `true` |
| `blur_score` | Decimal | Yes | Versioned policy evaluator | No | 模糊分数 | Finite number defined by policy | INTERNAL | `0.18` |
| `brightness_score` | Decimal | Yes | Versioned policy evaluator | No | 亮度分数 | Finite number defined by policy | INTERNAL | `0.62` |
| `occlusion_flags` | Enum[] | Yes | Rules/model suggestion | No | 遮挡标志 | Policy-known values | INTERNAL | `["possible_hand_occlusion"]` |
| `reasons` | String[] | Yes | Program | No | 可解释原因码 | Known reason codes | INTERNAL | `["manual_review_required"]` |
| `decision` | Enum | Yes | Program guard | No | 综合结论 | `pass/review/fail` | INTERNAL | `review` |
| `assessed_by` | Enum | Yes | Program | No | 评估方式 | `program/program_plus_model` | INTERNAL | `program_plus_model` |
| `model_call_id` | UUID | No | Program trace | No | 可选模型辅助调用 | Existing ModelCall | INTERNAL | `00000000-0000-4000-8000-000000000017` |
| `created_at` | Timestamp | Yes | Program | No | 评估时间 | ISO-8601 | INTERNAL | `2026-07-23T09:06:00+08:00` |

### 4.4 RegionSuggestion

模型候选建议；永远不直接成为用户确认事实。

| Field Name | Type | Required | Source of Truth | Mutable | Description | Validation | Classification | Example |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `id` | UUID | Yes | Program | No | 建议 ID | UUID | INTERNAL | `00000000-0000-4000-8000-000000000004` |
| `project_id` | UUID | Yes | Program | No | 所属项目 | Existing project | INTERNAL | `00000000-0000-4000-8000-000000000001` |
| `schema_version` | String | Yes | Program config | No | 输出 Schema 版本 | SemVer | INTERNAL | `0.1.0` |
| `image_asset_id` | UUID | Yes | Program | No | 来源图片 | Existing ImageAsset | INTERNAL | `00000000-0000-4000-8000-000000000002` |
| `label` | Enum/String | Yes | Model suggestion | No | 语义标签 | Known label or explicit unknown value | INTERNAL | `hair` |
| `label_resolution_status` | Enum | Yes | Program validation | No | 标签处理状态 | `known_candidate/unknown_candidate` | INTERNAL | `known_candidate` |
| `display_name` | String | Yes | Model suggestion | No | 展示名称 | Non-empty | INTERNAL | `头发` |
| `material` | Enum | Yes | Model suggestion | No | 候选材质 | Allowed material enum | INTERNAL | `painted_plastic` |
| `bounding_box` | BBox | Yes | Model suggestion | No | 粗略范围，不是 Polygon | Normalized and in bounds | INTERNAL | `{"x":0.30,"y":0.05,"width":0.40,"height":0.30}` |
| `confidence` | Decimal | Yes | Model suggestion | No | 模型置信度 | 0–1; not user fact | INTERNAL | `0.78` |
| `uncertainty_reason` | String | No | Model suggestion | No | 不确定原因 | Configured length limit | INTERNAL | `Overlapping visual strands` |
| `requires_human_review` | Boolean | Yes | Program policy | No | 是否要求人工处理 | Boolean | INTERNAL | `true` |
| `model_call_id` | UUID | Yes | Program trace | No | 来源模型调用 | Existing ModelCall | INTERNAL | `00000000-0000-4000-8000-000000000017` |
| `status` | Enum | Yes | Program | No | 建议状态 | Must equal `suggested` | INTERNAL | `suggested` |

### 4.5 RegionDefinition

不可变语义定义。被快照引用后，不允许原地修改。

| Field Name | Type | Required | Source of Truth | Mutable | Description | Validation | Classification | Example |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `id` | UUID | Yes | Program | No | 语义定义 ID | UUID | INTERNAL | `00000000-0000-4000-8000-000000000005` |
| `project_id` | UUID | Yes | Program | No | 所属项目 | Existing project | INTERNAL | `00000000-0000-4000-8000-000000000001` |
| `label` | Enum/String | Yes | User-confirmed definition | No | 语义标签 | Project label uniqueness in active snapshot | INTERNAL | `skin` |
| `display_name` | String | Yes | User-confirmed definition | No | 用户确认名称 | Non-empty | INTERNAL | `皮肤` |
| `material` | Enum | Yes | User-confirmed definition | No | 区域材质 | Allowed material enum | INTERNAL | `painted_plastic` |
| `required` | Boolean | Yes | User-confirmed definition | No | 是否是必须区域 | Boolean | INTERNAL | `true` |
| `supersedes_region_definition_id` | UUID | No | Program command | No | 被替代的旧定义 | Existing same-project RegionDefinition | INTERNAL | `00000000-0000-4000-8000-000000000006` |
| `created_by_principal_id` | PrincipalID | Yes | PrincipalContext/execution context | No | 创建主体 | Verified human or authorized system Principal | INTERNAL | `local-demo-owner` |
| `created_at` | Timestamp | Yes | Program | No | 创建时间 | ISO-8601 | INTERNAL | `2026-07-23T09:18:00+08:00` |

修改 label、display_name、material 或 required 时必须创建新的 RegionDefinition，并通过 supersedes 字段建立替代关系。

### 4.6 RegionGeometryVersion

一次完整区域快照，同时冻结语义定义和几何边界；不是孤立 Polygon 记录。

| Field Name | Type | Required | Source of Truth | Mutable | Description | Validation | Classification | Example |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `id` | UUID | Yes | Program | No | 快照版本 ID | UUID | INTERNAL | `00000000-0000-4000-8000-000000000007` |
| `project_id` | UUID | Yes | Program | No | 所属项目 | Existing project | INTERNAL | `00000000-0000-4000-8000-000000000001` |
| `version` | Integer | Yes | Program | No | 项目内单调版本 | Positive; unique per project | INTERNAL | `3` |
| `based_on_version_id` | UUID | No | Program | No | 基础快照 | Existing same-project version | INTERNAL | `00000000-0000-4000-8000-000000000019` |
| `semantic_snapshot` | JSON | Yes | Program from immutable definitions | No | Definition ID、label、display_name、material、required 的完整列表 | Versioned semantic snapshot Schema | INTERNAL | `[{"region_definition_id":"00000000-0000-4000-8000-000000000005","label":"skin","display_name":"皮肤","material":"painted_plastic","required":true}]` |
| `geometry_by_region` | JSON | Yes | User edit/model suggestion | No | Definition ID 到 Polygon[] 和坐标版本的映射 | Geometry Contract Schema | INTERNAL | `{"00000000-0000-4000-8000-000000000005":{"polygons":[[[0.10,0.10],[0.20,0.10],[0.15,0.20]]],"coordinate_system_version":"normalized_top_left_v1"}}` |
| `source` | Enum | Yes | Program command | No | 快照来源 | `ai_suggestion/user_edit/reopen` | INTERNAL | `user_edit` |
| `status` | Enum | Yes | Program/user event | Yes, guarded | 快照状态 | `draft/confirmed/superseded` | INTERNAL | `confirmed` |
| `created_by_principal_id` | PrincipalID | Yes | PrincipalContext/execution context | No | 创建者 | Verified human or authorized system Principal | INTERNAL | `local-demo-owner` |
| `created_at` | Timestamp | Yes | Program | No | 创建时间 | ISO-8601 | INTERNAL | `2026-07-23T09:20:00+08:00` |
| `confirmed_at` | Timestamp | No | HumanApproval event | No | 确认时间 | Requires matching active Approval | INTERNAL | `2026-07-23T09:22:00+08:00` |

HumanApproval 的区域审批只绑定 RegionGeometryVersion.id；该 ID 同时证明用户批准的确切语义快照和几何边界。

### 4.7 StyleConfiguration

版本化艺术配置；Golden Case 核心字段已由用户确认。

| Field Name | Type | Required | Source of Truth | Mutable | Description | Validation | Classification | Example |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `id` | UUID | Yes | Program | No | 配置 ID | UUID | INTERNAL | `00000000-0000-4000-8000-000000000008` |
| `project_id` | UUID | Yes | Program | No | 所属项目 | Existing project | INTERNAL | `00000000-0000-4000-8000-000000000001` |
| `version` | Integer | Yes | Program | No | 配置版本 | Positive | INTERNAL | `1` |
| `target_style` | Enum | Yes | User-confirmed | No | 目标风格 | Allowed enum | PUBLIC | `cel_shading` |
| `light_direction` | Enum | Yes | User-confirmed | No | 主光方向 | Allowed enum | PUBLIC | `upper_left` |
| `shadow_intensity` | Enum | Yes | User-confirmed | No | 阴影强度 | `low/medium/high` | PUBLIC | `medium` |
| `shadow_layers` | Integer | Yes | User-confirmed | No | 阴影层数 | Positive bounded integer | PUBLIC | `2` |
| `shadow_edge` | Enum | Yes | User-confirmed | No | 阴影边缘 | Allowed enum | PUBLIC | `hard` |
| `highlight_style` | Enum | Yes | User-confirmed | No | 高光形式 | Allowed enum | PUBLIC | `blocked_hard_edge` |
| `gradient_policy` | Enum | Yes | User-confirmed | No | 自动渐变政策 | Allowed enum | PUBLIC | `generally_disallowed` |
| `limited_manual_transition` | Enum | Yes | User-confirmed | No | 极少量人工过渡 | `allowed/disallowed` | PUBLIC | `allowed` |
| `user_confirmed` | Boolean | Yes | HumanApproval | Yes, guarded | 配置是否获确认 | Requires active Approval | INTERNAL | `true` |

### 4.8 PaintInventoryItem

结构化库存事实；具体产品为空时不得由模型补全。

| Field Name | Type | Required | Source of Truth | Mutable | Description | Validation | Classification | Example |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `id` | UUID | Yes | Program | No | 库存项 ID | UUID | INTERNAL | `00000000-0000-4000-8000-000000000009` |
| `project_id` | UUID | Yes | Program/database | No | 所属项目 | Existing PaintProject; owner-scoped | INTERNAL | `00000000-0000-4000-8000-000000000001` |
| `category` | Enum | Yes | User/workshop data | Yes | paint/primer/finish | Allowed enum | INTERNAL | `paint` |
| `brand` | String | Yes | User/workshop data | Yes | 品牌 | Non-empty | INTERNAL | `Example Acrylic Brand` |
| `product_line` | String | No | User/workshop data | Yes | 产品系列 | Source required if set | INTERNAL | `null` |
| `code` | String | No | User/workshop data | Yes | 产品编号 | Source required if set | INTERNAL | `null` |
| `name` | String | No | User/workshop data | Yes | 产品名称 | Source required if set | INTERNAL | `null` |
| `color_representation` | JSON | No | Verified source/program | Yes | 近似颜色表示 | Method and source required | INTERNAL | `null` |
| `owned` | Boolean | No | User/workshop data | Yes | 是否实际拥有 | Null means unknown | INTERNAL | `null` |
| `data_source` | String | Yes | User/workshop data | Yes | 数据来源 | Non-empty | INTERNAL | `USER_PROVIDED_PLAN` |
| `verified` | Boolean | Yes | User/program verification | Yes, guarded | 是否经过核验 | Cannot be model-set | INTERNAL | `false` |

### 4.9 KnowledgeDocument

项目私有的可检索知识资料。

| Field Name | Type | Required | Source of Truth | Mutable | Description | Validation | Classification | Example |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `id` | UUID | Yes | Program | No | 文档 ID | UUID | INTERNAL | `00000000-0000-4000-8000-000000000010` |
| `project_id` | UUID | Yes | Program | No | 所属项目 | Existing PaintProject | INTERNAL | `00000000-0000-4000-8000-000000000001` |
| `version` | Integer | Yes | Program | No | 内容版本 | Positive | INTERNAL | `1` |
| `title` | String | Yes | User/document metadata | Yes, versioned | 文档标题 | Non-empty | INTERNAL | `Brushwork guide` |
| `source_type` | Enum | Yes | Program inspection | No | 文件类型 | `pdf/markdown/txt` | INTERNAL | `markdown` |
| `storage_key` | String | Yes | Storage adapter | No | 存储定位 | Allowed key | SENSITIVE | `projects/0001/knowledge/guide.md` |
| `sha256` | String | Yes | Program | No | 文档字节哈希 | 64 lowercase hex chars | INTERNAL | `bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb` |
| `permission_status` | Enum | Yes | Program command | No | 检索权限 | Must equal `project_private` for MVP | INTERNAL | `project_private` |
| `ingestion_status` | Enum | Yes | Program | Yes, guarded | 分块处理状态 | `pending/ready/failed` | INTERNAL | `ready` |
| `created_at` | Timestamp | Yes | Program | No | 创建时间 | ISO-8601 | INTERNAL | `2026-07-23T10:00:00+08:00` |

### 4.10 KnowledgeChunk

文档的可引用分块；继承项目私有权限。

| Field Name | Type | Required | Source of Truth | Mutable | Description | Validation | Classification | Example |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `id` | UUID | Yes | Program ingestion | No | Chunk ID | UUID | INTERNAL | `00000000-0000-4000-8000-000000000011` |
| `document_id` | UUID | Yes | Program | No | 来源文档 | Existing KnowledgeDocument | INTERNAL | `00000000-0000-4000-8000-000000000010` |
| `document_version` | Integer | Yes | Program | No | 来源内容版本 | Matches document version | INTERNAL | `1` |
| `chunk_index` | Integer | Yes | Program | No | 文档内顺序 | Non-negative; unique per version | INTERNAL | `0` |
| `content` | String | Yes | Source document | No | 分块文本 | Non-empty; configured bound | SENSITIVE | `Demonstration-only technique summary.` |
| `locator` | String | Yes | Program ingestion | No | 页码、章节或行定位 | Non-empty | INTERNAL | `section:surface-preparation` |
| `metadata` | JSON | Yes | Program ingestion | No | 语言、标题等 | Metadata Schema | INTERNAL | `{"language":"zh-CN"}` |
| `embedding_version` | String | No | Retrieval subsystem | No | 可选向量版本 | Version format | INTERNAL | `embedding-v1` |

### 4.11 RetrievalCitation

方案中的来源指针，必须关联真实、可访问且版本明确的检索结果。

| Field Name | Type | Required | Source of Truth | Mutable | Description | Validation | Classification | Example |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `id` | UUID | Yes | Program retrieval | No | Citation ID | UUID | INTERNAL | `00000000-0000-4000-8000-000000000012` |
| `agent_run_id` | UUID | Yes | Program | No | 所属业务运行 | Existing AgentRun | INTERNAL | `00000000-0000-4000-8000-000000000016` |
| `paint_plan_id` | UUID | Yes | Program | No | 所属方案版本 | Existing PaintPlan created by AgentRun | INTERNAL | `00000000-0000-4000-8000-000000000013` |
| `document_id` | UUID | Yes | Retrieval system | No | 来源文档 | Accessible project document | INTERNAL | `00000000-0000-4000-8000-000000000010` |
| `document_version` | Integer | Yes | Retrieval system | No | 来源文档版本 | Positive; must match chunk | INTERNAL | `1` |
| `chunk_id` | UUID | Yes | Retrieval system | No | 来源分块 | Must belong to document version | INTERNAL | `00000000-0000-4000-8000-000000000011` |
| `locator` | String | Yes | Retrieval system | No | 可展示定位 | Must match chunk | INTERNAL | `section:surface-preparation` |
| `excerpt_summary` | String | Yes | Program/model, validated | No | 简短来源摘要 | Attribution and length rules | SENSITIVE | `Summary of the cited preparation guidance.` |
| `target_path` | String | Yes | Program | No | 支持的方案字段 | Valid PaintPlan JSON path | INTERNAL | `region_plans[0].steps[1]` |
| `retrieval_score` | Decimal | No | Retrieval system | No | 排序分数，不表示真实性 | Finite number | INTERNAL | `0.72` |

### 4.12 PaintPlan

版本化结构化涂装规划；必须经 Schema 校验和人工审批。

| Field Name | Type | Required | Source of Truth | Mutable | Description | Validation | Classification | Example |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `id` | UUID | Yes | Program | No | 方案版本 ID | UUID | INTERNAL | `00000000-0000-4000-8000-000000000013` |
| `project_id` | UUID | Yes | Program | No | 所属项目 | Existing project | INTERNAL | `00000000-0000-4000-8000-000000000001` |
| `version` | Integer | Yes | Program | No | 项目内方案版本 | Positive; unique per project | INTERNAL | `2` |
| `schema_version` | String | Yes | Program config | No | 输出 Schema 版本 | SemVer | INTERNAL | `0.1.0` |
| `based_on_image_asset_id` | UUID | Yes | Program | No | 基础图片版本 | Existing project ImageAsset | INTERNAL | `00000000-0000-4000-8000-000000000002` |
| `based_on_region_geometry_version_id` | UUID | Yes | Program | No | 基础完整区域快照 | Confirmed project snapshot | INTERNAL | `00000000-0000-4000-8000-000000000007` |
| `style_configuration_id` | UUID | Yes | Program | No | 风格配置版本 | Confirmed project StyleConfiguration | INTERNAL | `00000000-0000-4000-8000-000000000008` |
| `assumptions` | String[] | Yes | Model output, validated | No | 明示假设 | Configured item/length bounds | INTERNAL | `["Planning-only; no real repaint validation"]` |
| `unresolved_questions` | String[] | Yes | Model/program | No | 未决材料与施工问题 | No hidden nulls | INTERNAL | `["Specific paint product is not confirmed"]` |
| `overall_steps` | JSON | Yes | Model output, validated | No | 总体施工步骤 | PaintPlan Schema | INTERNAL | `{"order":["prepare","basecoat","shade","highlight"]}` |
| `region_plans` | UUID[] | Yes | Program | No | 子计划引用 | Existing PaintPlanRegion IDs | INTERNAL | `["00000000-0000-4000-8000-000000000014"]` |
| `required_inventory_item_ids` | UUID[] | Yes | Structured query | No | 已确认库存引用 | Verified items only | INTERNAL | `[]` |
| `missing_inventory_items` | JSON | Yes | Program/model, validated | No | 明确缺失材料 | Missing-item Schema; no invented product codes | INTERNAL | `[{"category":"paint","status":"unconfirmed"}]` |
| `citations` | UUID[] | Yes | Program validation | No | Citation 引用 | All IDs valid | INTERNAL | `["00000000-0000-4000-8000-000000000012"]` |
| `uncertainties` | JSON | Yes | Model/program, validated | No | code、scope、severity、explanation、requires_human_review | Uncertainty Schema | INTERNAL | `[{"code":"MATERIAL_UNCONFIRMED","scope":"project","severity":"warning","explanation":"Specific product is unknown","requires_human_review":true}]` |
| `status` | Enum | Yes | Program/approval | Yes, guarded | 方案状态 | `draft/review_required/approved/revision_requested/stale/superseded` | INTERNAL | `review_required` |
| `prompt_version` | String | Yes | Program config | No | Prompt 版本 | Version format | INTERNAL | `paint-plan-v1` |
| `generated_by_model_call_id` | UUID | Yes | Program trace | No | 生成来源调用 | Existing ModelCall | INTERNAL | `00000000-0000-4000-8000-000000000017` |
| `created_at` | Timestamp | Yes | Program | No | 创建时间 | ISO-8601 | INTERNAL | `2026-07-23T10:30:00+08:00` |

### 4.13 PaintPlanRegion

PaintPlan 中按确认语义组织的施工子计划。

| Field Name | Type | Required | Source of Truth | Mutable | Description | Validation | Classification | Example |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `id` | UUID | Yes | Program | No | 子计划 ID | UUID | INTERNAL | `00000000-0000-4000-8000-000000000014` |
| `paint_plan_id` | UUID | Yes | Program | No | 所属方案 | Existing PaintPlan | INTERNAL | `00000000-0000-4000-8000-000000000013` |
| `region_definition_id` | UUID | Yes | Program | No | 快照内区域定义 | Referenced by based-on snapshot | INTERNAL | `00000000-0000-4000-8000-000000000005` |
| `base_color_plan` | JSON | Yes | Model output, validated | No | 底色方案 | Region plan Schema | INTERNAL | `{"guidance":"Use a stable flat base color","source":"model_generated_guidance"}` |
| `shadow_plan` | JSON | Yes | Model output, validated | No | 阴影方案 | Must follow StyleConfiguration | INTERNAL | `{"layers":2,"edge":"hard"}` |
| `highlight_plan` | JSON | Yes | Model output, validated | No | 高光方案 | Must follow StyleConfiguration | INTERNAL | `{"style":"blocked_hard_edge"}` |
| `paint_candidates` | JSON | Yes | Model/program, validated | No | 候选材料，不等于库存事实 | Candidate Schema | INTERNAL | `[]` |
| `steps` | JSON | Yes | Model output, validated | No | 区域施工步骤 | Ordered step Schema | INTERNAL | `[{"order":1,"action":"apply_base_color"}]` |
| `inventory_item_ids` | UUID[] | Yes | Structured inventory query | No | 已确认库存引用 | Verified items only | INTERNAL | `[]` |
| `warnings` | String[] | Yes | Model/program | No | 缺失与风险 | Required when inventory missing | INTERNAL | `["Specific paint is not confirmed"]` |
| `citation_ids` | UUID[] | Yes | Retrieval system | No | 区域来源 | Existing citations | INTERNAL | `["00000000-0000-4000-8000-000000000012"]` |

### 4.14 HumanApproval

显式人工决定；模型不得创建 approved 决策。

| Field Name | Type | Required | Source of Truth | Mutable | Description | Validation | Classification | Example |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `id` | UUID | Yes | Program | No | Approval ID | UUID | INTERNAL | `00000000-0000-4000-8000-000000000015` |
| `project_id` | UUID | Yes | Program | No | 所属项目 | Existing project | INTERNAL | `00000000-0000-4000-8000-000000000001` |
| `approval_type` | Enum | Yes | Program command | No | 审批类型 | `image_quality/region_geometry/paint_plan/style_configuration` | INTERNAL | `image_quality` |
| `decision` | Enum | Yes | User | No | 人工决定 | `approved/rejected/revision_requested` | INTERNAL | `approved` |
| `status` | Enum | Yes | Program | Yes, guarded | Approval 有效性 | `active/superseded` | INTERNAL | `active` |
| `reviewer_principal_id` | PrincipalID | Yes | Verified PrincipalContext | No | 审批者稳定标识 | Must identify `principal_type=human`; must be authorized project owner | INTERNAL | `local-demo-owner` |
| `reviewer_display_name_snapshot` | String | Yes | PrincipalContext snapshot | No | 审批时展示名称 | Non-empty; history only; never used for authorization | SENSITIVE | `Local Demo Owner` |
| `reason` | String | Yes | User | No | 决定原因 | Configured finite length; required | SENSITIVE | `Image is sufficient for planning, not color calibration.` |
| `target_type` | Enum | Yes | Program command | No | 受控多态目标类型 | `image_quality_assessment/region_geometry_version/paint_plan/style_configuration` | INTERNAL | `image_quality_assessment` |
| `target_id` | UUID | Yes | Program + user command | No | 被审批的确切不可变或版本化对象 | Existing, type-compatible, same-project target | INTERNAL | `00000000-0000-4000-8000-000000000003` |
| `superseded_at` | Timestamp | No | Program | Yes once | 失效时间 | Required when status=superseded | INTERNAL | `null` |
| `superseded_by_event_id` | UUID | No | Program | Yes once | 触发失效的事件 | Existing StateTransitionEvent | INTERNAL | `null` |
| `created_at` | Timestamp | Yes | Program | No | 审批时间 | ISO-8601 | INTERNAL | `2026-07-23T10:40:00+08:00` |

HumanApproval 的 `target_type + target_id` 是受控多态引用，固定映射为：

| approval_type | Required target_type | Target entity |
| --- | --- | --- |
| `image_quality` | `image_quality_assessment` | ImageQualityAssessment |
| `region_geometry` | `region_geometry_version` | RegionGeometryVersion |
| `paint_plan` | `paint_plan` | PaintPlan |
| `style_configuration` | `style_configuration` | StyleConfiguration |

受控多态规则：

1. `target_type + target_id` 共同确定审批对象。
2. approval_type 必须与 target_type 使用上表的固定映射。
3. target 必须存在。
4. target 必须属于 HumanApproval.project_id 指向的同一个 PaintProject。
5. 审批只能绑定不可变或版本化对象。
6. 不允许审批“当前最新版本”等动态引用。
7. 新版本创建后，旧 Approval 不自动适用于新版本。
8. superseded Approval 必须保留，不得删除。
9. API 不得允许客户端把 target_id 指向其他项目。
10. 数据库无法提供统一多态外键时，应用服务必须在同一事务中验证目标类型、存在性和项目归属。
11. 后续可按实际数据库设计评估分表外键，但 MVP 不为四类目标新增四张独立审批表。

因此不得只保存 target_version_id，也不得只靠 approval_type 猜测目标表。审批写入事务还必须确认 reviewer_principal_id 来自该项目已授权的 human Principal。

### 4.15 AgentRun

一次业务操作执行；可包含零到多个 ModelCall。

| Field Name | Type | Required | Source of Truth | Mutable | Description | Validation | Classification | Example |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `id` | UUID | Yes | Program | No | 业务运行 ID | UUID | INTERNAL | `00000000-0000-4000-8000-000000000016` |
| `project_id` | UUID | Yes | Program | No | 所属项目 | Existing project | INTERNAL | `00000000-0000-4000-8000-000000000001` |
| `initiating_principal_id` | PrincipalID | Yes | Authorized command context | No | 发起业务运行的 Principal | Must be authorized for project; carried by worker/system | INTERNAL | `local-demo-owner` |
| `run_type` | Enum | Yes | Program command | No | 业务运行类别 | `quality_assessment/region_workflow/plan_workflow` | INTERNAL | `plan_workflow` |
| `operation_type` | Enum | Yes | Program command | No | 可恢复操作 | `image_validation/region_analysis/plan_generation` | INTERNAL | `plan_generation` |
| `status` | Enum | Yes | Program | Yes, guarded | 业务运行状态 | `running/succeeded/failed/blocked/cancelled` | INTERNAL | `running` |
| `input_version_refs` | JSON | Yes | Program | No | 结构化输入版本 ID | Version-ref Schema; no free-text refs | INTERNAL | `{"region_geometry_version_id":"00000000-0000-4000-8000-000000000007","style_configuration_id":"00000000-0000-4000-8000-000000000008"}` |
| `output_version_refs` | JSON | Yes | Program | Yes once | 结构化输出版本 ID | Version-ref Schema; may be empty while running | INTERNAL | `{"paint_plan_id":"00000000-0000-4000-8000-000000000013"}` |
| `retry_count` | Integer | Yes | Program | Yes, guarded | 已执行重试次数 | Non-negative | INTERNAL | `0` |
| `max_retries` | Integer | Yes | Program config | No | 重试上限 | image=1, region=2, plan=2 defaults; configurable | INTERNAL | `2` |
| `resume_state` | Enum | Yes | Program config/command | No | 失败恢复前置状态 | `IMAGE_UPLOADED/IMAGE_VALIDATED/REGIONS_CONFIRMED` compatible with operation | INTERNAL | `REGIONS_CONFIRMED` |
| `last_error_code` | String | No | Program | Yes | 最后业务错误码 | Known normalized code | INTERNAL | `null` |
| `last_error_message_redacted` | String | No | Program | Yes | 已脱敏错误说明 | No secret/provider raw response | INTERNAL | `null` |
| `correlation_id` | UUID | Yes | Program | No | Run/Call/Trace 关联 ID | UUID | INTERNAL | `20000000-0000-4000-8000-000000000001` |
| `cancel_requested_at` | Timestamp | No | User command/program | Yes once | cooperative cancellation 请求时间 | ISO-8601 or null | INTERNAL | `null` |
| `started_at` | Timestamp | Yes | Program | No | 开始时间 | ISO-8601 | INTERNAL | `2026-07-23T10:20:00+08:00` |
| `completed_at` | Timestamp | No | Program | Yes once | 完成时间 | After started_at | INTERNAL | `null` |
| `created_at` | Timestamp | Yes | Program | No | 记录创建时间 | ISO-8601 | INTERNAL | `2026-07-23T10:20:00+08:00` |

input/output refs 只能引用 ImageAsset、RegionGeometryVersion、StyleConfiguration、PaintPlan 等结构化版本 ID。FAILED_RETRYABLE 的恢复不得依赖自由文本 metadata。

### 4.16 ModelCall

一次模型 Provider 调用；它是 AgentRun 的子记录，不拥有项目状态。

| Field Name | Type | Required | Source of Truth | Mutable | Description | Validation | Classification | Example |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `id` | UUID | Yes | Program | No | Provider 调用 ID | UUID | INTERNAL | `00000000-0000-4000-8000-000000000017` |
| `agent_run_id` | UUID | Yes | Program | No | 所属 AgentRun | Existing AgentRun | INTERNAL | `00000000-0000-4000-8000-000000000016` |
| `correlation_id` | UUID | Yes | Program | No | 与 Run/Trace 的关联 | Must equal AgentRun correlation ID | INTERNAL | `20000000-0000-4000-8000-000000000001` |
| `provider` | String | Yes | Program config | No | Provider 名称 | Allowed provider config | INTERNAL | `configured_provider` |
| `model` | String | Yes | Program config | No | 模型标识 | Non-empty | INTERNAL | `configured_model` |
| `purpose` | Enum | Yes | Program | No | 调用用途 | Allowed purpose enum | INTERNAL | `paint_plan_generation` |
| `prompt_version` | String | Yes | Program config | No | Prompt 版本 | Version format | INTERNAL | `paint-plan-v1` |
| `schema_version` | String | Yes | Program config | No | 响应 Schema 版本 | SemVer | INTERNAL | `0.1.0` |
| `provider_request_id` | String | No | Provider response | No | Provider 请求 ID | Configured length bound | INTERNAL | `req_000000000001` |
| `provider_started_at` | Timestamp | Yes | Program timing | No | Provider 请求开始 | ISO-8601 | INTERNAL | `2026-07-23T10:21:00.000+08:00` |
| `provider_completed_at` | Timestamp | No | Program timing | Yes once | Provider 请求结束 | After started_at | INTERNAL | `2026-07-23T10:21:01.800+08:00` |
| `input_tokens` | Integer | No | Provider response | No | 输入 token | Non-negative or null | INTERNAL | `1200` |
| `output_tokens` | Integer | No | Provider response | No | 输出 token | Non-negative or null | INTERNAL | `600` |
| `cached_input_tokens` | Integer | No | Provider response | No | 缓存输入 token | Non-negative or null | INTERNAL | `400` |
| `usage_status` | Enum | Yes | Program mapping | No | 用量可用性 | `available/usage_unavailable` | INTERNAL | `available` |
| `latency_ms` | Integer | No | Program calculation | No | 完成时间差缓存 | Non-negative; consistent with timestamps | INTERNAL | `1800` |
| `estimated_cost` | Decimal | No | Program calculation | No | 估算成本 | Non-negative; requires currency and pricing version | INTERNAL | `0.0125` |
| `currency` | String | Conditional | Program config | No | 成本币种 | ISO 4217 when cost set | INTERNAL | `USD` |
| `pricing_source` | Enum | Conditional | Verified config | No | 价格来源 | `official_config/internal_config/other_verified` | INTERNAL | `official_config` |
| `pricing_version` | String | Conditional | Program config | No | 计算时价格版本 | Required when cost set | INTERNAL | `pricing-2026-07-01` |
| `status` | Enum | Yes | Program | Yes once | 调用结果 | `running/succeeded/failed/timeout/discarded` | INTERNAL | `succeeded` |
| `error_code` | String | No | Provider/program | Yes once | 归一化错误码 | Known/mapped code | INTERNAL | `null` |
| `error_message_redacted` | String | No | Program | Yes once | 已脱敏错误说明 | No secret/raw response | INTERNAL | `null` |
| `raw_usage` | JSON | No | Provider response | No | Provider 返回的结构化用量 | Usage Schema; no prompt/secret | INTERNAL | `{"input_tokens":1200,"output_tokens":600,"cached_input_tokens":400}` |
| `created_at` | Timestamp | Yes | Program | No | 记录创建时间 | ISO-8601 | INTERNAL | `2026-07-23T10:21:00.000+08:00` |

Provider 未返回用量时，usage_status 必须为 `usage_unavailable`，token、raw_usage 和成本可以为空，且不得编造。estimated_cost 是程序计算或估算结果，不是模型自报。

**AgentRun 与 ModelCall 的区别：** AgentRun 表示完整业务意图和状态机操作，可执行库存查询、检索和确定性校验，并包含零到多个 ModelCall；ModelCall 只表示一次 Provider 请求。单次 Provider 成功不等于业务成功，因此二者不能合并。

### 4.17 StateTransitionEvent

不可变权威审计记录；与 PaintProject.status 在同一数据库事务写入。

| Field Name | Type | Required | Source of Truth | Mutable | Description | Validation | Classification | Example |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `id` | UUID | Yes | Program | No | 事件 ID | UUID | INTERNAL | `00000000-0000-4000-8000-000000000018` |
| `project_id` | UUID | Yes | Program | No | 所属项目 | Existing project | INTERNAL | `00000000-0000-4000-8000-000000000001` |
| `from_state` | Enum | Conditional | Database | No | 原状态 | 16-state enum or null at creation | INTERNAL | `IMAGE_REVIEW_REQUIRED` |
| `to_state` | Enum | Yes | Program guard | No | 新状态 | 16-state enum | INTERNAL | `IMAGE_VALIDATED` |
| `event` | String | Yes | Program command | No | 触发事件 | Transition table event | INTERNAL | `approve_image` |
| `actor_type` | Enum | Yes | Execution context | No | 实际执行通道或主体类别 | `user/api/worker/system` | INTERNAL | `api` |
| `actor_principal_id` | PrincipalID | Yes | Verified PrincipalContext/execution context | No | 可归责的稳定 Principal | Human action must retain verified human ID; system action uses authorized system ID | INTERNAL | `local-demo-owner` |
| `actor_display_name_snapshot` | String | No | PrincipalContext snapshot | No | 事件发生时展示名称 | History only; never used for authorization | SENSITIVE | `Local Demo Owner` |
| `reason` | String | Conditional | Actor/program | No | 转换原因 | Required for review/failure/abandon/revision | SENSITIVE | `Approved for planning only.` |
| `occurred_at` | Timestamp | Yes | Program | No | 事件时间 | ISO-8601 | INTERNAL | `2026-07-23T09:08:00+08:00` |
| `correlation_id` | UUID | Yes | Program | No | Trace 关联 ID | UUID | INTERNAL | `20000000-0000-4000-8000-000000000001` |
| `agent_run_id` | UUID | No | Program | No | 关联运行 | Existing AgentRun | INTERNAL | `00000000-0000-4000-8000-000000000016` |
| `metadata` | JSON | Yes | Program | No | 版本化命令元数据 | Audit metadata Schema | INTERNAL | `{"image_quality_assessment_id":"00000000-0000-4000-8000-000000000003"}` |

### 4.18 CommandIdempotencyRecord

命令基础设施记录；防止重放重复创建版本、Approval、AgentRun 或 ModelCall。

| Field Name | Type | Required | Source of Truth | Mutable | Description | Validation | Classification | Example |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `id` | UUID | Yes | Program | No | 记录 ID | UUID | INTERNAL | `00000000-0000-4000-8000-000000000020` |
| `principal_id` | PrincipalID | Yes | Authorized command context | No | 发起命令的稳定 Principal | Non-empty; authorized for project | INTERNAL | `local-demo-owner` |
| `project_id` | UUID | Yes | Program | No | 命令作用域；create 前预分配 | UUID | INTERNAL | `00000000-0000-4000-8000-000000000001` |
| `command_type` | Enum | Yes | Program | No | 命令类型 | Contract-listed command | INTERNAL | `start_plan_generation` |
| `idempotency_key` | String | Yes | Client | No | 客户端键 | Non-empty; configured length bound | SENSITIVE | `idem-20260723-0001` |
| `payload_hash` | String | Yes | Program | No | 规范化 payload 哈希 | 64 lowercase hex chars | INTERNAL | `cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc` |
| `response_snapshot` | JSON | Yes | Program | No | 原响应的受控快照 | Response Schema; no secret | SENSITIVE | `{"status":"accepted","project_id":"00000000-0000-4000-8000-000000000001"}` |
| `http_status` | Integer | Yes | Program | No | 原 HTTP 状态 | 100–599 | INTERNAL | `202` |
| `created_at` | Timestamp | Yes | Program | No | 创建时间 | ISO-8601 | INTERNAL | `2026-07-23T10:19:00+08:00` |
| `expires_at` | Timestamp | Yes | Program | No | 24 小时过期时间 | Exactly 24 hours after creation | INTERNAL | `2026-07-24T10:19:00+08:00` |

唯一约束为 `principal_id + project_id + command_type + idempotency_key`。相同作用域内的 key 与不同 payload hash 返回 409 `IDEMPOTENCY_KEY_REUSED`；不同 Principal 不会错误复用同一幂等结果。

## 5. Key Relationships

- PaintProject 由 owner_principal_id 标识唯一 MVP 所有者，并 1—N ImageAsset、PaintInventoryItem、AgentRun、PaintPlan、HumanApproval、StateTransitionEvent、CommandIdempotencyRecord。
- ImageAsset 1—N ImageQualityAssessment；标准化分析资产可引用原始不可变 ImageAsset。
- ImageQualityAssessment 1—N HumanApproval，其中当前有效 image-quality Approval 决定 review 分支。
- AgentRun 1—N ModelCall，且 AgentRun 可在没有 ModelCall 时执行纯确定性操作。
- ModelCall 1—N RegionSuggestion，或关联生成的 PaintPlan。
- RegionDefinition 通过 supersedes 链保持不可变语义历史。
- RegionGeometryVersion 包含多个 RegionDefinition 的完整语义和几何快照。
- PaintPlan 必须引用确切 ImageAsset、RegionGeometryVersion 和 StyleConfiguration。
- PaintPlan 1—N PaintPlanRegion。
- KnowledgeDocument 1—N KnowledgeChunk；RetrievalCitation 同时绑定确切 PaintPlan、文档版本与 chunk。
- HumanApproval 通过受控 `target_type + target_id` 精确指向 ImageQualityAssessment、RegionGeometryVersion、PaintPlan 或 StyleConfiguration，且目标必须属于同一 PaintProject。
- PrincipalContext 不是实体关系；需要审计时只把稳定 PrincipalID 和必要的展示名称快照写入业务记录。

## 6. Source of Truth Matrix

| Data | Source of Truth | Not Authoritative |
| --- | --- | --- |
| 当前 Principal | Authentication/demo access Adapter | display_name, client-supplied owner |
| 项目所有权 | PaintProject.owner_principal_id | URL、客户端本地状态、展示名称 |
| 项目状态 | Program Guard + database | LLM text, client-local state |
| 状态审计 | Database StateTransitionEvent | External observability platform |
| 图片尺寸、大小、SHA-256 | Program inspection | Model observation, filename |
| 图片权利声明 | User attestation record | Platform legal conclusion, model |
| 图片质量确定性字段 | Program inspection + versioned policy | Filename, raw model prose |
| 图片 review 决定 | HumanApproval bound to Assessment | Model or worker |
| Approval 目标 | Validated target_type + target_id | Dynamic “latest” pointer, approval_type inference |
| 区域建议与置信度 | ModelCall output stored as suggestion | Not a user fact |
| 语义区域定义 | Immutable RegionDefinition in approved snapshot | RegionSuggestion alone |
| 区域边界 | Approved RegionGeometryVersion | Bounding Box or raw model polygon |
| 风格配置 | User-confirmed StyleConfiguration | Model preference |
| 颜料库存 | User/workshop structured data | Model guess |
| Citation | Retrieval linked to accessible document/chunk version | Fabricated URL or unlinked prose |
| 方案文本 | Model output after Schema validation | Raw unvalidated response |
| 方案批准 | HumanApproval by user | LLM or worker |
| Token usage | Provider raw_usage mapping | Model self-report |
| Provider latency | Program timestamps; latency_ms cache | Model prose |
| 成本 | Program estimate using usage, currency and pricing version | Model prose |
| 重试上下文 | AgentRun structured fields | Free-text metadata |
| 幂等结果 | CommandIdempotencyRecord | Client retry assumption |

## 7. Versioning and Supersession Rules

1. ImageAsset 不原地覆盖；替换或标准化分析版本创建新 ID，原图保留。
2. ImageQualityAssessment 不原地覆盖；人工 review Approval 绑定确切 Assessment。
3. RegionDefinition 不可变；语义字段变化创建新实体并用 supersedes 建立替代关系。
4. RegionGeometryVersion 保存完整 semantic_snapshot 和 geometry_by_region；每次编辑或 reopen 创建新版本。
5. 区域 Approval 绑定完整 RegionGeometryVersion。
6. 区域返工将旧区域 Approval 标记 superseded，相关旧计划标记 stale/superseded。
7. 旧 PaintPlan 不删除；旧 Citation 留在旧计划，不转移到新计划。
8. StyleConfiguration、Prompt、Schema 和 ImageQualityPolicy 使用显式版本。
9. HumanApproval 绑定创建时的确切 target_type + target_id；目标产生新版本时旧 Approval 不自动适用，失效记录只标记 superseded。
10. StateTransitionEvent、AgentRun、ModelCall 和 CommandIdempotencyRecord 是追加式记录。
11. 并发写入使用版本检查；旧客户端不得覆盖新版本。

## 8. Sensitive Data Handling Matrix

| Surface | PUBLIC | INTERNAL | SENSITIVE |
| --- | --- | --- | --- |
| 普通日志 | 可记录必要字段 | 仅最小必要值；优先 ID/计数 | 禁止原文；只记录脱敏标志或不可逆摘要 |
| API | 可按产品契约返回 | 仅返回当前操作必要字段 | 需要权限控制与字段级脱敏 |
| Trace | 可保存 | 可保存结构化最小字段 | 默认不保存正文；确需保存时加密与权限控制 |
| 保留期限 | 按产品/演示策略 | 按运维与审计策略限期保留 | 必须定义最短必要期限和删除/归档策略 |
| 错误响应 | 可用于安全说明 | 只返回稳定代码和 safe_details | 不得返回 secret、路径、文档正文或 Provider 原始响应 |

API Key、Authorization header、完整 Prompt、完整 Provider 原始响应、图片二进制和不必要 EXIF 位置数据不得进入普通日志、错误响应或通用 Trace。

PrincipalID 是非秘密内部标识，可以按最小必要原则进入受控日志；display-name snapshot 属于敏感历史数据，不参与权限判断。认证秘密不得进入 PrincipalContext 或任何业务实体。

## 9. Future Extensions

以下仅为未来可能扩展，不属于 MVP 数据模型或当前实现：

- Workspace 与 Tenant；
- Billing 与 Subscription；
- Arcana Domain；
- 可靠后台任务与独立队列；
- 多 Provider 路由；
- 多人协作区域编辑；
- 法律权利审核工作流。
