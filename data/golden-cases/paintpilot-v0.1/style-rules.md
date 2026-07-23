# PaintPilot Golden Case Style Rules

状态：`TARGET_STYLE_CONFIRMED`

本文档区分用户已确认的艺术基线与仍待审美判断的施工细节。`USER_CONFIRMED` 是 Golden Case 事实；`DRAFT_SUGGESTION` 仍只是建议。

## 已确认艺术配置

| Field | Value | Status |
| --- | --- | --- |
| `target_style` | `cel_shading` | `USER_CONFIRMED` |
| `light_direction` | `upper_left` | `USER_CONFIRMED` |
| `shadow_intensity` | `medium` | `USER_CONFIRMED` |
| `shadow_layers` | `2` | `USER_CONFIRMED` |
| `shadow_edge` | `hard` | `USER_CONFIRMED` |
| `highlight_style` | `blocked_hard_edge` | `USER_CONFIRMED` |
| `gradient_policy` | `generally_disallowed` | `USER_CONFIRMED` |
| `limited_manual_transition` | `allowed` | `USER_CONFIRMED` |

## 已确认规则解释

- USER_CONFIRMED：整体采用 Cel Shading，不再把 Manga High Contrast 作为本 Golden Case 的候选目标。
- USER_CONFIRMED：主光源固定为左上。
- USER_CONFIRMED：阴影强度为中等，使用两层硬边阴影。
- USER_CONFIRMED：高光使用分块硬边形式。
- USER_CONFIRMED：原则上不使用渐变。
- USER_CONFIRMED：极少量人工过渡允许，但仅作为人工施工建议。
- USER_CONFIRMED：`limited_manual_transition=allowed` 不授权系统执行自动渐变计算，也不表示系统需要推导渐变宽度、比例或颜色。

## 当前案例施工建议

以下没有被用户确认为最终颜色或施工细节：

- DRAFT_SUGGESTION：头发可按主要发束组织分块式高光和根部阴影；具体色相、明度和块面位置仍需人工审美判断。
- DRAFT_SUGGESTION：肌肉区域可使用硬边阴影表达结构；具体阴影形状仍需人工确认。
- DRAFT_SUGGESTION：蓝色上衣可探索深蓝或蓝紫阴影，但具体颜色未确认。
- DRAFT_SUGGESTION：橙色裤装可探索较亮高光与红橙阴影，但具体颜色未确认。
- DRAFT_SUGGESTION：护腕、靴子和腰部布料应分别确认材质表现，不因颜色相近而自动合并规则。
- DRAFT_SUGGESTION：不在 MVP 中自动生成精确混色比例。
- DRAFT_SUGGESTION：当前图片存在环境光、背景虚化和可能的色彩增强，不用于精确颜色校准。

## 底色、阴影与高光边界

- USER_CONFIRMED：阴影采用两层、硬边、中等强度的规则。
- USER_CONFIRMED：高光采用分块硬边规则。
- DRAFT_SUGGESTION：底色优先保持稳定色面，避免未经确认的纹理、脏化和材质特效。
- DRAFT_SUGGESTION：第二层阴影的局部覆盖范围需要逐区域人工判断。
- DRAFT_SUGGESTION：面部阴影应优先保留表情可读性，但具体块面未确认。
- DRAFT_SUGGESTION：不同材质的光泽差异需要人工审美判断。

## 渐变与人工过渡边界

- USER_CONFIRMED：`gradient_policy=generally_disallowed`。
- USER_CONFIRMED：`limited_manual_transition=allowed`。
- DRAFT_SUGGESTION：仅在人工认为硬边会损害结构可读性的极少局部考虑手工过渡。
- DRAFT_SUGGESTION：手工过渡的位置、宽度、颜料和施工方式尚未确认。
- 禁止解释：不得把极少量人工过渡转换为自动渐变生成、精确混色比例或物理级光照计算。

## 容易失败的地方

- DRAFT_SUGGESTION：不同区域的左上光源解释不一致。
- DRAFT_SUGGESTION：两层阴影覆盖过多，破坏 Cel Shading 色块感。
- DRAFT_SUGGESTION：面部硬边阴影过重，影响表情可读性。
- DRAFT_SUGGESTION：头发分块高光过密或与发束方向冲突。
- DRAFT_SUGGESTION：把摄影反光、环境色或后期增强误当作固有色。
- DRAFT_SUGGESTION：把允许的人工过渡误实现为系统自动渐变。

## 尚未确认

- Vallejo 产品系列、具体颜色、编号和实际库存；
- GSI Creos / Mr.Hobby 补土具体型号；
- GSI Creos / Mr.Hobby 消光具体型号；
- 具体区域颜色值；
- 每个 Polygon 内的阴影与高光块面位置；
- 极少量人工过渡的具体施工位置和材料；
- 最终知识库资料及其施工规则来源。

不得在上述信息确认前写入具体产品型号、色值、混色比例或材料兼容性结论。
