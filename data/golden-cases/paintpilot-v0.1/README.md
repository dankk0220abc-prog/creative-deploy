# PaintPilot Golden Case v0.1

状态：`CONDITIONALLY_APPROVED_FOR_MVP`

本目录定义 PaintPilot 的固定规划案例，供后续需求设计、数据结构设计、工作流开发、自动化测试和评测使用。当前状态表示手办实体、用户图片、摄影授权、语义区域和核心艺术方向已经确定，但 Polygon 几何、具体材料和知识库资料仍未确认，也不表示任何系统能力已经实现。

本案例目前属于 planning-only demo，不包含真实重涂结果验证。

## 用户确认清单

- [x] Golden Case 手办已由用户确认
- [x] 手办所有权已由用户确认
- [x] 四张照片由用户本人拍摄
- [x] 允许用于私人项目开发和本地测试
- [x] 允许用于公开求职演示
- [x] 允许进入公开 GitHub
- [x] 主图与辅助图片映射已确认
- [x] 是否真实重涂已确认
- [x] 计划使用的材料品牌已确认
- [x] 最终目标风格已确认
- [x] 语义区域列表已由用户确认
- [x] 光源方向已确认
- [x] 阴影规则已确认
- [x] 高光规则已确认
- [x] 渐变政策已确认
- [ ] 具体 Polygon 边界已确认
- [ ] Vallejo 具体产品系列与颜色已确认
- [ ] 郡士补土具体型号已确认
- [ ] 郡士消光具体型号已确认
- [ ] 最终知识库资料已确认

## 已冻结的 Golden Case 基线

- `target_style`: `cel_shading`
- `light_direction`: `upper_left`
- `shadow_intensity`: `medium`
- `shadow_layers`: `2`
- `shadow_edge`: `hard`
- `highlight_style`: `blocked_hard_edge`
- `gradient_policy`: `generally_disallowed`
- `limited_manual_transition`: `allowed`
- `semantic_regions_confirmed`: `true`
- `geometry_confirmed`: `false`
- `source_type`: `user_provided`
- `rights_attestation_status`: `confirmed`
- `intended_usage`: `private_project / portfolio_demo / public_repository`

极少量人工过渡仅是人工施工许可，不能被解释为系统自动渐变计算。具体颜色、材料型号、Polygon 顶点和像素边界没有被冻结。

权利状态只表示系统可记录的用户 attestation；它不是开放许可证、法律权属验证或第三方官方授权。

## 当前素材状态

- 主输入：`assets/primary-front.jpeg`，来源于 `IMG_1606.jpg`
- 背面参考：`assets/reference-back.jpeg`
- 前侧角度参考：`assets/reference-angle.jpeg`，来源于 `IMG_1608.jpg`
- 遮挡失败案例：`assets/failure-hand-occlusion.jpeg`
- 文件校验值和尺寸：见 `asset-manifest.json`
- 摄影作者：用户本人，`USER_CONFIRMED`
- 公开使用状态：`USER_AUTHORIZED`

当前主流程只使用 `primary-front.jpeg`；其余图片用于辅助区域测试和失败测试。四张照片获准用于私人项目开发、本地测试、公开求职演示和公开 GitHub，但不得标记为开放许可证素材。该授权仅覆盖照片本身，不覆盖第三方角色、产品造型或商标。

## 使用边界

允许用于图片接入、区域分析、Human-in-the-loop、结构化方案、工作流和评测设计。不得声称已经真实执行涂装、通过真实成品验证颜色或材料匹配，或改善了真实涂装效果。
