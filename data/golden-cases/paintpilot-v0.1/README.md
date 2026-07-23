# PaintPilot Golden Case v0.1

状态：`CONDITIONALLY_APPROVED_FOR_MVP`

本目录定义 PaintPilot 的固定规划案例，供后续需求设计、数据结构设计、工作流开发、自动化测试和评测使用。当前状态表示手办实体、用户提供的案例图片、摄影作者授权和 planning-only 使用场景已经确定，但不表示第三方角色与产品权利、艺术规则或材料型号已经全部确认，也不表示任何系统能力已经实现。

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
- [ ] 最终目标风格已确认
- [ ] 精确区域列表已由用户确认
- [ ] Vallejo 具体产品系列与颜色已确认
- [ ] 郡士补土具体型号已确认
- [ ] 郡士消光具体型号已确认
- [ ] 风格规则已由用户确认

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
