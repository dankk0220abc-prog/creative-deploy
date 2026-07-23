# PaintPilot 候选风格规则

状态：`TARGET_STYLE_PENDING_USER_CONFIRMATION`

候选风格：`Cel Shading` / `Manga High Contrast`

两种风格均未被用户确认为最终目标。以下所有艺术判断均为 `DRAFT_SUGGESTION`，只用于 planning-only 讨论和结构化需求。

## 候选风格目标

- DRAFT_SUGGESTION — Cel Shading：使用清晰、有限层数的明暗色块表达二维赛璐璐观感。
- DRAFT_SUGGESTION — Manga High Contrast：使用更强的明暗对比和轮廓强调表达漫画式结构，但不自动推断最终配色。
- 最终选择：TODO_USER_CONFIRM

## 底色特点

- DRAFT_SUGGESTION：底色以稳定、相对均匀的色面为主，避免未经确认的复杂纹理和脏化效果。
- 用户确认：TODO_USER_CONFIRM

## 阴影层数

- DRAFT_SUGGESTION：每个主要区域先采用一层主阴影；是否增加第二层强调阴影由用户确认。
- 用户确认：TODO_USER_CONFIRM

## 阴影边缘

- DRAFT_SUGGESTION：优先使用清晰硬边；仅在转折或材质需要时使用有限软边。
- 用户确认：TODO_USER_CONFIRM

## 高光特点

- DRAFT_SUGGESTION：高光使用少量、形状明确的色块，不以自动推断替代人工审美判断。
- 用户确认：TODO_USER_CONFIRM

## 是否允许渐变

- DRAFT_SUGGESTION：默认不使用大面积连续渐变；局部例外必须由用户按区域确认。
- 用户确认：TODO_USER_CONFIRM

## 头发处理

- DRAFT_SUGGESTION：沿主要发束组织底色、主阴影和少量方向性高光，不虚构最终发色或高光形状。
- 用户确认：TODO_USER_CONFIRM

## 皮肤处理

- DRAFT_SUGGESTION：保持面部可读性，减少过强对比；肤色、阴影色和红润程度均由用户确认。
- 用户确认：TODO_USER_CONFIRM

## 服装处理

- DRAFT_SUGGESTION：以褶皱转折和光源方向组织硬边阴影；图案、材质差异和旧化效果按最终图片确认。
- 用户确认：TODO_USER_CONFIRM

## 配饰处理

- DRAFT_SUGGESTION：根据材质分别处理，金属、塑料、布料等不得仅凭区域名称自动混用同一高光规则。
- 用户确认：TODO_USER_CONFIRM

## 当前案例专项建议

- DRAFT_SUGGESTION：头发适合使用分块式高光和深色根部阴影。
- DRAFT_SUGGESTION：肌肉区域适合使用硬边阴影表达结构。
- DRAFT_SUGGESTION：蓝色上衣适合使用有限层数的深蓝或蓝紫阴影。
- DRAFT_SUGGESTION：橙色裤装适合使用较亮高光与红橙阴影。
- DRAFT_SUGGESTION：不建议在 MVP 中自动生成精确混色比例。
- DRAFT_SUGGESTION：不建议使用当前照片进行精确颜色校准。
- DRAFT_SUGGESTION：当前图片光线和色彩可能经过处理，只能作为视觉规划参考。
- 用户确认：TODO_USER_CONFIRM

## 最容易失败的地方

- DRAFT_SUGGESTION：光源方向在不同区域不一致。
- DRAFT_SUGGESTION：阴影层数过多，破坏 Cel Shading 的色块感。
- DRAFT_SUGGESTION：面部阴影过重，影响表情可读性。
- DRAFT_SUGGESTION：头发高光过密或与发束方向冲突。
- DRAFT_SUGGESTION：把摄影反光、环境色或背景颜色误当作手办固有色。
- DRAFT_SUGGESTION：未区分材质便复用同一边缘和高光规则。
- 用户补充：TODO_USER_INPUT

## 可转换为程序字段的规则

以下字段名与候选值只是数据建模建议，最终枚举和值域尚未确认。

| 字段 | DRAFT_SUGGESTION 候选值 | 当前值 |
| --- | --- | --- |
| `style_name` | `cel_shading` / `manga_high_contrast` | TODO_USER_CONFIRM |
| `light_direction` | `upper_left` | TODO_USER_CONFIRM |
| `shadow_intensity` | `low` / `medium` / `high` | TODO_USER_CONFIRM |
| `shadow_layers` | 整数，建议 1 或 2 | TODO_USER_CONFIRM |
| `shadow_edge` | `hard` / `mixed` | TODO_USER_CONFIRM |
| `gradient_policy` | `none` / `limited` | TODO_USER_CONFIRM |
| `highlight_amount` | `low` / `medium` | TODO_USER_CONFIRM |
| `region_overrides` | 按已确认区域保存例外规则 | TODO_USER_CONFIRM |

确定性状态（例如用户是否确认、颜料是否可用、许可是否验证）应由程序保存，不应由模型臆测。

## 需要人工审美判断的规则

- DRAFT_SUGGESTION：阴影形状是否强化了造型而不是制造噪声；
- DRAFT_SUGGESTION：面部阴影和高光是否保留角色表情；
- DRAFT_SUGGESTION：头发高光的形状、密度和节奏；
- DRAFT_SUGGESTION：不同材质之间的光泽差异；
- DRAFT_SUGGESTION：哪些局部允许软边或有限渐变；
- DRAFT_SUGGESTION：配色是否符合用户期望的角色气质；
- DRAFT_SUGGESTION：最终方案是否具有整体一致性。

人工审美结论：TODO_USER_INPUT
