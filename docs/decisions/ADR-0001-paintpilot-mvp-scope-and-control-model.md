# ADR-0001: PaintPilot MVP Scope and Control Model

- Status: `Accepted`
- Revision: `0.1.1`
- Date: `2026-07-23`
- Accepted Date: `2026-07-23`
- Decision Owners: `Project Owner / System Architect`
- Implementation Status: `NOT_STARTED`

本 ADR 已作为 PaintPilot MVP 初始实现的架构基线；所有 Revisit Triggers 继续有效。Accepted 不表示相关系统已经实现。

## Context

CreativeDeploy 需要通过一个边界明确、可评测的部署案例验证多模态 Agent 应用能力。PaintPilot 同时涉及图片理解、人工区域编辑、结构化库存、知识检索、模型生成、审批和 Trace。如果在需求尚未冻结时先建设通用平台、微服务或复杂编排基础设施，项目会扩大到无法验证的范围，并模糊确定性程序、模型建议和人工事实之间的责任。

当前 Golden Case 是 planning-only demo：使用一张主图片规划超级赛亚人悟空手办的 Cel Shading 方案，不执行真实重涂，也不进行精确色彩校准。区域语义和艺术目标已经确认，但 Polygon、材料型号、知识库资料、模型 Provider 和部署平台仍待后续确认。

## Decision

1. **先完成 PaintPilot，再抽象 CreativeDeploy 平台。** 只有 PaintPilot 完成部署和评测后，才从真实重复点中抽象平台能力。
2. **采用 Modular Monolith。** MVP 使用清晰模块边界的单体架构，不采用微服务。
3. **MVP 只处理一张主图片。** 参考图片属于 Golden Case 辅助资料，不进入多图融合流程。
4. **通用视觉模型只生成建议。** 区域名称、Bounding Box、置信度和不确定原因属于 `RegionSuggestion`，不是最终事实。
5. **人工确认后的 Polygon 才是区域几何事实。** 事实保存在版本化 `RegionGeometryVersion`，Approval 绑定具体版本。
6. **状态由程序控制。** `PaintProject.status` 由后端命令、Guard 和数据库事务控制，LLM 无权改变。
7. **结构化输出必须通过 Schema 校验。** 无效 RegionSuggestion 或 PaintPlan 不能推进状态。
8. **文档走 RAG，库存走结构化查询。** 知识资料通过 KnowledgeDocument/Chunk/Citation 检索；颜料库存通过 `PaintInventoryItem` 查询，不把库存统一向量化。
9. **当前照片不用于精确色彩校准。** 环境光、背景虚化和可能的色彩增强使其只适合视觉规划。
10. **MVP 不验证真实重涂效果。** 不评估干燥色差、材料兼容性、补土或消光的实物影响，也不声明质量提升。
11. **暂不引入 Redis、独立任务队列或独立向量数据库。** 只有观测到明确容量、延迟或可靠性需求后再评估。
12. **Arcana 延后。** 在 PaintPilot 完成部署与评测并形成可复用证据后，再开始 Arcana。
13. **图片质量采用 pass/review/fail 三态。** `review` 必须进入 `IMAGE_REVIEW_REQUIRED` 并由用户作出版本绑定决定；用户批准只表示允许进入 planning-only 流程。
14. **用户放弃使用独立 `ABANDONED` 终态。** `FAILED_FINAL` 只表示技术错误、数据不可恢复或重试耗尽。
15. **运行中取消采用 best-effort cooperative cancellation。** 系统写入 `AgentRun.cancel_requested_at` 并阻止迟到结果成为当前事实，但不保证物理终止已发出的 Provider 请求。
16. **RegionGeometryVersion 保存完整语义与几何快照。** RegionDefinition 不可变；区域 Approval 绑定一个同时包含确切语义和 Polygon 的版本。
17. **图片权利只记录用户 attestation。** 系统不进行法律权属验证，声明不等于确认用户拥有第三方角色、产品设计或商标权。
18. **图片质量数值阈值在实现前校准。** 阈值属于版本化 ImageQualityPolicy，必须使用 Golden Case 和负面测试集校准，不在需求文档中伪造数值。
19. **数据库审计记录是状态事实来源。** PaintProject.status 与 StateTransitionEvent 同事务提交；外部观测平台不是事实来源。
20. **MVP 采用最小 Principal Contract。** 每个请求携带稳定 principal_id、principal_type、display_name 和 authentication_mode；当前不提供公共注册、完整用户管理、多租户或复杂 RBAC。
21. **PaintProject 由一个 owner_principal_id 所有。** 创建项目时从已验证 Principal 写入且客户端不可覆盖；MVP 不支持所有权转移，project_private 数据按该 owner 隔离。
22. **在线公开演示在真实认证实现前不得匿名写入。** 部署只能使用受保护的单一演示操作者、只读公开演示或部署平台访问保护，不能把“没有公共注册”解释为匿名可修改。
23. **HumanApproval 使用 target_type + target_id 的受控多态引用。** approval_type、目标类型、存在性、同项目归属和不可变/版本化约束必须在同一事务中校验；MVP 不新增四张独立审批表。
24. **PrincipalContext 是非持久化 Value Object。** 它来自认证或演示访问 Adapter，不增加 User 表；业务实体只保存必要的 PrincipalID 与历史展示快照。
25. **正式登录或多人协作触发身份与授权模型复评。** 真实认证 Adapter 可以替换当前身份来源，但在明确需求出现前不提前建设完整用户、组织或角色系统。

## Alternatives Considered

### A. 先建设通用 CreativeDeploy 平台

不采用。当前只有一个已定义 Golden Case，通用抽象缺少第二个真实消费者验证，容易产生未被使用的 Workspace、Tenant、插件和编排层。

### B. 使用微服务

不采用。MVP 的团队规模、流量和故障隔离需求尚未被测量；微服务会提前引入网络边界、部署、契约和分布式一致性成本。Modular Monolith 已能保持领域边界并支持未来拆分。

### C. 使用 LangGraph 或第三方工作流框架作为强依赖

当前不采用。核心流程是有限状态机，确定性 Guard 和人工 Gate 需要直接、可审计的控制。先用领域状态和命令定义语义；当流程复杂度或恢复需求有实测证据时再重新评估框架。

### D. 把自动精确分割作为 MVP 强依赖

不采用。Golden Case 只确认了语义区域，Polygon 尚未标注；自动像素级分割会扩大模型、数据集和评测范围。MVP 使用粗略建议加人工 Polygon Editor。

### E. 把所有数据统一向量化

不采用。知识文档适合语义检索，但颜料库存、权限、版本、状态和 Approval 是结构化事实。统一向量化会降低可验证性，并可能让模型猜测确定性数据。

### F. 同时开发 Arcana

不采用。并行开发第二个领域会分散 Golden Case、部署和评测工作，也会诱导过早平台抽象。Arcana 在 PaintPilot 形成端到端证据后启动。

## Consequences

### Positive

- MVP 范围可审查，核心用户任务清晰。
- 确定性状态、模型建议和人工事实之间责任明确。
- Region 与 Plan 两个 Gate 可独立测试和审计。
- 数据模型支持版本、Citation、Trace 和未来评测。
- 单一部署单元降低 Phase 0 后首次实现的运维复杂度。
- 文档检索与库存查询使用适合各自事实类型的机制。
- 图片 review、技术故障与质量 fail 具有不同、可审计的路径。
- 用户主动终止与技术失败在状态和指标上可区分。
- 完整区域快照可以证明 Approval 覆盖的语义和几何版本。
- 稳定 PrincipalID 使项目所有权、人工审批、权利声明和状态审计具有一致的归因来源。
- 受控 target_type + target_id 消除了 HumanApproval 目标表和目标版本的歧义。
- 非持久化 PrincipalContext 保留未来替换认证 Adapter 的边界，不把完整用户系统带入 MVP。

### Negative / Trade-offs

- Polygon Editor 和人工审批会增加用户操作步骤。
- 单图 MVP 不能利用多角度融合提升区域建议。
- 不使用独立队列会限制首版长任务的并发与恢复能力。
- 不使用独立向量数据库可能限制知识库规模。
- 延后通用平台意味着未来抽象时可能需要重构模块边界。
- planning-only Golden Case 不能证明实物涂装价值。
- cooperative cancellation 不能保证停止 Provider 侧计算，仍可能产生延迟和费用。
- 图片权利 attestation 只能形成用户声明证据，不能替代法律审核。
- ImageQualityPolicy 在校准完成前会阻塞对应能力进入 implementation-ready。
- 单一 owner 且不支持转移会限制多人协作、共享项目与委托管理。
- 公开演示的写保护依赖部署侧或单一操作者配置，增加一项必须验证的运维控制。
- 受控多态引用在没有数据库统一外键时依赖应用服务事务校验。
- 展示名称变化不会回写历史快照，因此界面必须明确快照代表事件发生时的名称。

## Risks

- 模型区域建议质量可能不足，导致较高人工编辑率。
- Polygon 交互可能成为可用性和实现复杂度重点。
- 当前具体颜料库存与材料型号未确认，方案可能只能显示缺失状态。
- 知识库资料未冻结，Citation coverage 暂时无法建立基线。
- 模型 Provider、成本、延迟和部署平台仍未知。
- 如果模型调用耗时超过同步请求可接受范围，可能需要提前引入异步执行。
- 用户授权覆盖照片本身，不等于拥有第三方角色、产品造型或商标权。
- 用户可能提交错误或不完整的权利 attestation，系统不能把 confirmed 状态表述为法律验证。
- Provider 请求在用户放弃后仍可能返回；如果迟到结果 Guard 实现错误，可能污染当前版本。
- 图片质量阈值若只针对单个 Golden Case 调优，可能对其他图片产生系统性误判。
- 若部署保护配置错误，未实现真实认证的在线环境可能暴露匿名写入口。
- 若 worker 丢失 initiating_principal_id 或 project_id，可能造成不可归责操作或跨项目访问；实现时必须 fail closed。
- 若应用服务遗漏 HumanApproval 目标类型、存在性或项目归属校验，受控多态引用可能产生跨项目或错误类型审批。

## Revisit Triggers

- PaintPilot 已部署并完成首轮人工评测；
- 出现第二个真实部署案例并证明平台抽象具有两个以上消费者；
- 同步模型调用在实测中频繁超时或需要可靠后台恢复；
- 单体部署出现明确的独立扩缩容、隔离或团队所有权需求；
- 知识库规模或检索延迟证明当前方案不足；
- 多 Provider 路由成为成本、可靠性或合规要求；
- Polygon 建议质量达到可评估自动分割的证据门槛；
- Arcana 需求和 Golden Case 已独立冻结。
- 引入可靠后台任务或独立队列后，重新评估取消、租约、重试和迟到结果语义；
- 出现多人协作区域编辑后，重新评估不可变 RegionDefinition 与完整快照模型；
- 图片权利审核成为真实客户合规要求时，重新评估用户 attestation 并考虑正式审核流程。
- 需要多个用户共享同一个项目；
- 需要项目所有权转移；
- 需要邀请、角色或组织权限；
- Arcana 需要独立创作者与普通用户身份；
- 在线部署需要真实用户登录；
- 需要数据库级严格多态外键。
