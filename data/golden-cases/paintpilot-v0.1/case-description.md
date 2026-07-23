# PaintPilot Golden Case v0.1

## 基本信息

- 案例名称：Super Saiyan Goku Cel-Shading Planning Case
- 手办名称：超级赛亚人悟空手办
- 手办所有权：USER_CONFIRMED
- 照片来源：USER_PROVIDED
- 照片拍摄者：USER_CONFIRMED
- 图片 source_type：user_provided
- rights_attestation_status：confirmed
- rights_attested_by：项目用户本人
- intended_usage：private_project / portfolio_demo / public_repository
- 私人项目使用：ALLOWED
- 公开求职展示：ALLOWED
- 公开 GitHub：ALLOWED
- 公开使用状态：USER_AUTHORIZED
- 主图片：assets/primary-front.jpeg
- 主图片来源：IMG_1606.jpg
- 角度参考图：assets/reference-angle.jpeg
- 角度参考图来源：IMG_1608.jpg
- 真实重涂计划：false
- 案例类型：planning_only_demo
- planning_only_demo：true
- real_repaint_validation：false
- 当前图片状态：visually_appears_prepainted（VISUAL_OBSERVATION，不是用户已确认事实）
- 精确颜色校准：NOT_ELIGIBLE
- 第三方角色与产品权利：RIGHTS_NOT_OWNED
- 官方合作或品牌授权：NONE
- semantic_regions_confirmed：true
- geometry_confirmed：false
- 目标风格：cel_shading（USER_CONFIRMED）
- 光源方向：upper_left（USER_CONFIRMED）
- 阴影强度：medium（USER_CONFIRMED）
- 阴影层数：2（USER_CONFIRMED）
- 阴影边缘：hard（USER_CONFIRMED）
- 高光形式：blocked_hard_edge（USER_CONFIRMED）
- 渐变政策：generally_disallowed（USER_CONFIRMED）
- 极少量人工过渡：allowed（USER_CONFIRMED，仅限人工施工建议）
- 计划颜料体系：Vallejo / AV acrylic paints，具体系列与颜色待确认
- 计划底层材料：Mr.Hobby / GSI Creos primer，具体产品待确认
- 计划表面保护：Mr.Hobby / GSI Creos matte finish，具体产品待确认

## 用户希望解决的问题

为当前手办建立可复用的视觉区域分析、人工确认和结构化涂装规划案例，不执行真实重涂。

## 期望最终输出

符合既定 Schema、引用已确认材料库存并保留人工确认节点与来源记录的 planning-only 涂装方案。

## 必须由人工确认的内容

- 图片是否适合分析
- 七个语义区域的具体 Polygon、多边形顶点和像素边界
- 具体颜料、补土与消光产品
- 最终知识库演示资料
- 最终结构化涂装方案

## 已确认语义区域

1. `hair` — 头发
2. `skin` — 皮肤，包括面部、颈部、胸部、手臂和手部；一个语义区域可以由多个不连续 Polygon 组成
3. `upper_gi` — 蓝色上衣
4. `pants` — 橙色裤装
5. `waist_sash` — 腰带与腰部布料
6. `wristbands` — 护腕
7. `boots` — 靴子

语义定义已经确认，但当前没有 Polygon、顶点或像素边界数据。

## 排除对象

- `display_base`
- `background`
- `overlay_text`
- `human_hand_occlusion`

## 系统应该拒绝或暂停的情况

- 主体严重遮挡
- 图片过暗、过曝或严重模糊
- 无法确认图片许可或公开使用权限
- 无法识别主要手办主体
- 区域建议置信度过低
- 用户尚未确认 Polygon 几何版本
- 方案引用未确认或不在库存中的具体材料

## Validation Boundary

当前可以评测：

- 图片是否能够进入系统；
- 区域建议是否完整；
- 用户是否能够修正区域；
- 状态机是否正确阻塞；
- 方案是否符合 Schema；
- 颜料推荐是否引用已确认库存；
- RAG 是否提供来源；
- Trace、延迟、成本和错误是否可记录；
- 人工评审是否认为方案具有可执行性。

当前不能评测：

- 实际涂装后的颜色准确性；
- 真实笔涂操作难度；
- 颜料干燥后的色差；
- 不同底漆造成的实际颜色变化；
- 消光后颜色与质感变化；
- 真实完成品是否优于原始手办。

以上条目是未来系统的评测边界，不代表相应系统能力已经实现。

当前图片受环境光、背景虚化和可能的色彩增强影响，不能用于精确颜色校准。该 planning-only demo 不能证明真实涂装效果，也不代表项目获得任何相关版权方、品牌方或制造商的官方合作或授权。

上述 `rights_attestation_status=confirmed` 只记录用户对照片来源与预期用途的声明，不是法律权属验证，也不表示项目拥有第三方角色、产品造型或商标权。

## MVP 明确不实现

- 3D 重建
- AR 预览
- 物理级光照模拟
- 自动像素级精确分割
- 精确颜料混色比例
- 涂装进度照片诊断
- 自动生成最终重涂效果图
