# Resume bullets

## 中文

- 设计并实现 CreativeDeploy：一个双语 Browser-first AI 应用平台，承载手办重涂工作台 PaintPilot 与三牌解读产品 Arcana，并以共享身份、授权、审计与恢复边界支撑两个不同垂直场景。
- 为 PaintPilot 构建私有图片、ImageSet/RegionSet、结构化 Paint Plan、引用检索与人工审批链路；将 citation/provenance 绑定到实际检索上下文，避免“格式正确但来源伪造”的输出。
- 实现并独立验证 Zhipu GLM-5V-Turbo 与 GLM-5.2 集成；以加密 BYOK、策略、预算预留、耐久 pre-egress claim、幂等、会计与安全审计治理调用生命周期。
- 建立 local-first 可重复演示和合成 staging DR 证据：迁移、精确重试、checksum/字节不匹配及 manifest/HMAC 篡改拒绝均有明确验证边界；公开 Demo 默认零真实 Provider 调用。

## English

- Built CreativeDeploy, a bilingual browser-first AI application platform that supports both PaintPilot, a miniature repaint-planning workspace, and Arcana, a private three-card reflection product on shared identity, authorization, audit, and recovery boundaries.
- Designed PaintPilot’s private-image, ImageSet/RegionSet, structured Paint Plan, cited-retrieval, and human-approval workflow; bound citations/provenance to the retrieved context used for generation rather than validating only citation shape.
- Implemented and independently validated Zhipu GLM-5V-Turbo and GLM-5.2 integrations with encrypted BYOK, policy, budget reservation, durable pre-egress claims, idempotency, accounting, and safe auditability.
- Delivered a repeatable local-first demo and synthetic staging-DR evidence, including migration, exact retry, checksum/byte-mismatch, and manifest/HMAC tamper-refusal boundaries; the public demo defaults to zero real-provider calls.
