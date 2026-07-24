# ADR-0002: PaintProject Creation and Idempotency Boundary

- Status: `Accepted`
- Date: `2026-07-24`
- Accepted Date: `2026-07-24`
- Decision Owners: `Project Owner / System Architect`
- Implementation Status: `NOT_STARTED`
- Product Contract Amendment: `0.1.2 APPROVED_FOR_IMPLEMENTATION`
- Data Dictionary Amendment: `0.1.2 APPROVED_FOR_IMPLEMENTATION`

本 ADR 记录并接受 Phase 1D PaintProject 创建、读取、所有权、幂等和 Migration
边界。Accepted 表示决策可供后续授权任务实施，不表示 Migration、模型、API、页面或
依赖已经存在。

## Context

Phase 1C 已冻结 Create Paint Project UX：用户只输入 Title 和可选 Description；
Cel Shading 是当前唯一初始风格意图；系统保持 planning-only 边界；成功后进入真实项目
详情页。Phase 1D 需要把该 UX 与已批准的 Product Contract 和 Data Dictionary 对齐，
并形成可创建、可列出、可重新打开、重启后仍存在的真实数据库闭环。

Version 0.1.1 基线仍有四个阻塞点：

1. PaintProject Title 和 Description 上限大于冻结 UX；
2. PaintProject 没有用于创建意图的风格字段和 planning_mode；
3. Command Idempotency scope 强制包含尚不存在的 project ID；
4. Phase 1D 的创建 API、列表 Envelope、非 Owner 读取和初始审计事件尚未冻结。

如果为迁就旧幂等 scope 而从 Idempotency-Key 派生业务资源 UUID，会把传输级重试标识
错误地变成领域身份来源，并增加资源 ID 可预测、算法迁移和跨实现兼容风险。

## Decision

1. **PaintProject 保存 `requested_target_style`。** 当前值固定为 `cel_shading`，表示
   创建时的初始创作意图，而不是详细风格配置的永久权威来源。
2. **StyleConfiguration 保持详细配置权威。** 它保存版本化风格、光源、阴影和高光；
   可以从 requested_target_style 初始化，但一旦创建并确认，方案生成以当前已确认
   StyleConfiguration 为权威。差异必须显式处理，不能静默冲突。
3. **`planning_mode` 属于 PaintProject。** 当前由服务端写入
   `planning_only_demo`，表示项目级验证边界，不是用户选择，也不能被解释为真实重涂
   已验证。
4. **创建命令使用服务端计算的 `scope_key`。** Create Project 使用
   `principal:{principal_id}:command:create_paint_project`；未来已有项目命令使用
   `principal:{principal_id}:project:{project_id}:command:{command_type}`。
5. **幂等唯一约束是 `scope_key + idempotency_key`。** 客户端只提供 UUID
   Idempotency-Key，不能提供 scope_key。
6. **不从 Idempotency-Key 派生或确定性预分配 Project UUID。** PaintProject ID 仍由
   业务创建流程生成；客户端也不能提供 Project ID。
7. **同步创建采用单事务唯一约束仲裁。** 使用 PostgreSQL
   `INSERT ... ON CONFLICT DO NOTHING` 竞争 `scope_key + idempotency_key`。获胜请求在
   同一短事务创建 PaintProject、初始 StateTransitionEvent 和 completed 幂等结果；
   任一失败全部回滚。
8. **初始事件固定。** `from_state=null`、`to_state=DRAFT`、
   `event=create_project`、`actor_type=user`、当前 human Principal、显示名称快照、
   `reason=project_created`、correlation ID 和带时区 created_at。
9. **非 Owner 读取返回 404。** Detail 对不存在项目和其他 Principal 所有的项目均返回
   404，不通过 403 泄露资源存在性。
10. **Phase 1D 使用配置型单 Principal。** 采用 `configured_demo_operator` 或等价
    Adapter；稳定 principal_id 用于所有权，display_name 只用于显示和审计快照。真实
    认证前在线写入口不得匿名开放。
11. **API 列表使用稳定 Envelope。** `items/total/limit/offset`，默认
    `limit=20`、`offset=0`，按 `updated_at DESC, id DESC` 排序。
12. **Frontend 使用 React Router v8 Declarative Mode。** Package 为
    `react-router`，不使用 v8 已移除的 `react-router-dom`。当前官方稳定版本核验结果
    为 `8.2.0`，计划范围 `>=8.2.0,<9.0.0`；精确解析版本由 `pnpm-lock.yaml` 锁定，
    实施任务开始时仍需重新查询官方资料及 React 19、Vite 8、Node 24 兼容性。
13. **Migration 使用 Alembic。** 当前计划 Alembic 1.x 范围
    `>=1.18.5,<2.0.0`，实施前重新查询官方版本；初始化在 `apps/api`，使用现有
    Settings/SecretStr 和 async SQLAlchemy，配置一致 constraint naming convention，
    人工审查 autogenerate，并运行 `alembic check`、upgrade、downgrade 和重新 upgrade。
14. **应用启动不自动运行 Migration。** Schema 变更由显式运维或开发命令执行。
15. **当前 API 不暴露 in-progress 幂等状态。** 唯一冲突请求等待竞争事务完成并读取
    已提交结果；相同 payload 重放 201，不同 payload 只返回 409
    `IDEMPOTENCY_KEY_REUSED`。`in_progress` 只为未来异步命令保留。
16. **DRAFT 是创建默认值，不是数据库唯一状态。** Phase 1D 默认推荐使用稳定命名为
    `ck_paint_projects_status_allowed` 的 Check Constraint 覆盖完整 16-state
    vocabulary，而不是 PostgreSQL Enum。这样更容易由 Alembic 审查、修改和
    downgrade；代价是应用枚举和约束列表必须通过测试保持同步，数据库类型本身不提供
    原生 Enum 名称。
17. **current reference 物理列延后。** `current_image_asset_id`、
    `current_region_version_id` 和 `current_plan_id` 保留在完整逻辑领域模型中，但
    Phase 1D 首次 Migration 不创建这些列；它们分别随目标实体表出现，并同时建立真实
    Foreign Key。
18. **不创建无引用完整性的未来 UUID。** 被引用实体不存在时，不用裸 UUID 列占位，
    也不为解决引用而提前创建 ImageAsset、RegionGeometryVersion 或 PaintPlan 表。
19. **幂等保留时间不是 Key 复用时间。** Idempotency-Key 唯一标识一次逻辑命令；
    新逻辑命令必须使用新的客户端 UUID，不同业务操作不得主动复用旧 Key。同一逻辑
    命令因 timeout 或未知结果重试时复用原 Key 和不变 payload。`expires_at` 固定为
    `created_at + 24 hours`，只表示 minimum retention / cleanup eligibility，不会
    自动使仍存在的记录失效。只要记录存在，相同 Key + 相同 payload 重放原响应，
    相同 Key + 不同 payload 返回 409 `IDEMPOTENCY_KEY_REUSED`。未来清理后旧 Key
    可能不再被识别，但客户端仍不得依赖长期复用；Phase 1D 不实现后台清理任务。

## Alternatives Considered

### A. 在 PaintProject 使用 `target_style` 作为永久权威字段

不采用。该名称无法区分创建时意图和后续已确认的详细艺术配置，会与
StyleConfiguration 的版本化、人工确认和方案生成职责形成双重事实来源。

### B. Phase 1D 立即创建完整 StyleConfiguration

不采用。Create Project 首版只建立真实空项目；提前要求光源、阴影和高光配置会扩大
纵向切片、违背冻结 UX，并制造用户尚未确认的详细配置。

### C. 从 Idempotency-Key 确定性派生 Project UUID

不采用。重试标识不应决定领域资源身份；该方案增加可预测性、算法版本、namespace
管理和后续迁移耦合，也不能替代正确的幂等执行记录。

### D. 所有命令的幂等作用域都必须包含 project_id

不采用。资源创建前没有 project ID。强制包含会要求客户端伪造 ID、预创建资源或使用
确定性派生。server-computed scope_key 同时支持资源创建命令和已有资源命令。

### E. 非 Owner 读取返回 403

不采用。403 会确认该 project ID 存在。Owner-scoped project-private 读取对不存在和
无权访问统一返回 404，更符合最小信息披露。

### F. 现在实现完整登录、用户表和多租户

不采用。Phase 1D 只需要稳定、可替换的 PrincipalContext Adapter。完整认证会扩大
范围，且当前没有公共注册、组织、角色或共享项目需求。在线写入口仍必须受保护。

### G. 应用启动时自动迁移数据库

不采用。自动迁移会把部署启动与不可逆 Schema 变更耦合，削弱人工审查、失败恢复和
多实例启动安全性。Migration 应通过显式命令执行。

### H. 只依赖前端 disabled 防止重复创建

不采用。网络重试、多个标签页和并发请求会绕过 UI 状态；数据库唯一约束和事务化
CommandIdempotencyRecord 才是权威保护。

### I. 提前提交 in-progress 记录的两阶段事务

不采用。第一阶段 committed reservation、第二阶段创建资源会破坏“项目、初始事件和
完成结果同事务”的原子性，并引入崩溃后悬空 reservation、恢复租约和超时清理问题。

### J. 长时间持有 committed reservation

不采用。Phase 1D 创建只有本地数据库操作，允许唯一约束上的短暂等待，不需要长期
reservation、heartbeat 或 lease。事务中也不得加入外部网络调用。

### K. 数据库只允许 DRAFT

不采用。DRAFT 只是创建默认值；PaintProject.status 必须支持已批准状态机的全部 16
个状态，否则后续合法 Transition 会被数据库阻止。

### L. 提前建立无 Foreign Key 的 current reference 列

不采用。目标实体表尚不存在时，裸 UUID 不能提供引用完整性，当前 API 也不需要这些
字段。引用列必须与对应实体表和 Foreign Key 一起通过后续 Migration 引入。

## Consequences

### Positive

- Create Project UX、API 和数据库字段使用相同的 80/500 限制。
- 初始风格意图与未来详细 StyleConfiguration 职责清晰。
- 创建命令无需不存在的 project ID，也无需确定性资源 UUID。
- 事务失败不会留下半完成项目、缺失审计事件或虚假幂等成功。
- Owner-scoped 404 降低项目 ID 枚举带来的信息泄露。
- 列表 Envelope 能支持分页扩展，不受首屏三张卡片的视觉限制。
- Router 和 Migration 技术选择具有明确实施前版本核查点。

### Negative / Trade-offs

- PaintProject 与 StyleConfiguration 之间需要显式初始化和差异检查。
- scope_key 格式成为需要版本化和测试的基础设施合同。
- 并发请求可能在 PostgreSQL 唯一约束上短暂等待；必须设置合理数据库超时并验证竞争
  事务 commit/rollback 两条路径。
- 稳定命名 Check Constraint 需要应用枚举、Migration 与合同测试保持同一 16-state
  列表。
- current reference 延后意味着 Phase 1D Read Schema 暂不返回三个未来指针。
- 配置型单 Principal 不能满足真实多人协作或公开匿名写入。
- 人工 Migration 流程增加一项发布步骤，但保留了可审查性。

## Risks

- 如果 scope_key 拼接未使用受控格式，可能产生作用域碰撞或跨 Principal 重放。
- 如果 canonical payload serialization 不稳定，相同业务请求可能产生不同 hash。
- 如果 completed 幂等记录缺少受控响应快照，重放可能返回与原操作不同的响应。
- 如果 StyleConfiguration 创建时忽略 requested_target_style，可能出现静默艺术意图偏差。
- 如果 Detail 查询先按 ID 后做权限判断，日志或错误分支可能泄露其他 Principal 信息。
- 如果应用层与数据库层长度计算规则不同，Unicode 边界可能产生不一致。
- 如果 Migration autogenerate 未人工审查，可能遗漏 Check Constraint、naming convention
  或 downgrade 行为。
- 如果部署保护缺失，configured_demo_operator 可能被误用为匿名公共写身份。

## Revisit Triggers

- 引入真实登录、多个用户、项目共享、成员邀请或所有权转移；
- 同一 Principal 需要多个并行创建上下文，当前 create scope_key 产生真实冲突；
- 新增第二个可选 requested_target_style；
- StyleConfiguration 初始化或差异解决需要新的用户交互；
- 长时间命令需要持久化 lease、heartbeat、后台恢复或独立任务队列；
- 幂等记录需要超过 24 小时保留或需要正式清理任务；
- API 列表需要 cursor pagination 或稳定快照分页；
- React Router v9、Alembic 2.x 或当前技术栈兼容性发生重大变化；
- 多实例部署证明当前 Migration 执行流程或并发策略不足。
