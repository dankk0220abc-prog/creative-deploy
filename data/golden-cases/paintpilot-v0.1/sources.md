# 素材来源记录规范

状态：`DRAFT`

每项实际使用的素材都应单独建立一条记录，并保留可追溯到作者、机构或原始发布页的链接。搜索结果页、缩略图页和聚合页面不能代替原始来源。

## 素材记录模板

- 素材名称：
- 素材类型：图片 / 颜料数据 / 教程 / 色卡 / 其他
- 作者或机构：
- 原始来源：
- 许可证或授权方式：
- 是否允许修改：
- 是否允许公开展示：
- 是否允许放入公开 GitHub：
- 获取日期：
- 当前验证状态：未验证 / 已验证
- 备注：

## 记录规则

- 未找到明确许可证时，`当前验证状态` 必须写“未验证”。
- “网上可以看到”不等于允许复制、修改、公开展示或放入公开仓库。
- 搜索结果页面不是原始来源；应继续追溯到作者、机构、官方数据页或原始发布页。
- 记录 Creative Commons 素材时，应保存准确的许可证版本、许可证链接、作者署名和修改说明要求。
- 图片的摄影作品许可与图片中手办、角色、商标、包装或其他第三方内容的权利应分别核验。
- 对“是否允许修改”“是否允许公开展示”“是否允许放入公开 GitHub”无法得出明确结论时，应写 `TODO_USER_CONFIRM`，不得自行推断。
- 颜料品牌、型号、名称和色值只有在可信官方数据来源得到核验后才能标记为“已验证”。

当前 Golden Case 已使用用户本人拍摄并明确授权用于私人开发、本地测试、公开 GitHub 和公开求职展示的四张悟空手办图片。网络候选的历史调研记录见 `image-candidates.md`，不作为当前案例素材。

## 当前用户提供图片

### primary-front.jpeg

- 素材类型：用户提供的手办照片
- 原始本地文件：`~/Downloads/IMG_1606.jpg`
- 项目内文件：`assets/primary-front.jpeg`
- 素材角色：primary_mvp_input
- 手办所有权：USER_CONFIRMED
- 摄影作者：用户本人
- 摄影作者状态：USER_CONFIRMED
- 私人项目使用：允许
- 本地测试：允许
- 公开求职演示：允许
- 公开 GitHub：允许
- 授权来源：用户本人在项目过程中明确确认
- 许可证或授权方式：user_permission_for_project_use
- 是否允许修改：TODO_USER_CONFIRM
- 商业使用：未授权
- 当前验证状态：USER_AUTHORIZED
- 备注：文件由用户提供并作为正面主输入；不得重新标记为开放许可证素材。

### reference-back.jpeg

- 素材类型：用户提供的手办照片
- 原始本地文件：`~/Downloads/IMG_1607.jpg`
- 项目内文件：`assets/reference-back.jpeg`
- 素材角色：secondary_back_reference
- 手办所有权：USER_CONFIRMED
- 摄影作者：用户本人
- 摄影作者状态：USER_CONFIRMED
- 私人项目使用：允许
- 本地测试：允许
- 公开求职演示：允许
- 公开 GitHub：允许
- 授权来源：用户本人在项目过程中明确确认
- 许可证或授权方式：user_permission_for_project_use
- 是否允许修改：TODO_USER_CONFIRM
- 商业使用：未授权
- 当前验证状态：USER_AUTHORIZED
- 备注：文件由用户提供并作为背面区域参考；不得重新标记为开放许可证素材。

### reference-angle.jpeg

- 素材类型：用户提供的手办照片
- 原始本地文件：`~/Downloads/IMG_1608.jpg`
- 项目内文件：`assets/reference-angle.jpeg`
- 素材角色：secondary_angle_reference
- 手办所有权：USER_CONFIRMED
- 摄影作者：用户本人
- 摄影作者状态：USER_CONFIRMED
- 私人项目使用：允许
- 本地测试：允许
- 公开求职演示：允许
- 公开 GitHub：允许
- 授权来源：用户本人在项目过程中明确确认
- 许可证或授权方式：user_permission_for_project_use
- 是否允许修改：TODO_USER_CONFIRM
- 商业使用：未授权
- 当前验证状态：USER_AUTHORIZED
- 备注：文件由用户提供并作为约 45 度前侧区域参考；不得重新标记为开放许可证素材。

### failure-hand-occlusion.jpeg

- 素材类型：用户提供的手办照片
- 原始本地文件：`~/Downloads/IMG_1610.jpg`
- 项目内文件：`assets/failure-hand-occlusion.jpeg`
- 素材角色：negative_test_occlusion
- 手办所有权：USER_CONFIRMED
- 摄影作者：用户本人
- 摄影作者状态：USER_CONFIRMED
- 私人项目使用：允许
- 本地测试：允许
- 公开求职演示：允许
- 公开 GitHub：允许
- 授权来源：用户本人在项目过程中明确确认
- 许可证或授权方式：user_permission_for_project_use
- 是否允许修改：TODO_USER_CONFIRM
- 商业使用：未授权
- 当前验证状态：USER_AUTHORIZED
- 备注：文件由用户提供，手部明显遮挡主体，用作负向质量检查案例；不得重新标记为开放许可证素材。

## Public Usage Boundary

这些照片由项目用户本人拍摄，并由摄影作者允许用于 CreativeDeploy / PaintPilot 的开发、测试、公开 GitHub 和公开求职展示。

该授权仅适用于照片本身，不代表项目拥有或获得以下第三方权利：

- 《龙珠》角色相关权利；
- 手办造型或产品设计权利；
- 制造商品牌；
- 商标；
- 官方视觉资产。

本案例仅用于个人、非商业、求职和技术演示。

CreativeDeploy、PaintPilot 及项目作者与相关版权方、品牌方和制造商不存在官方合作或关联。

第三方角色、商标、产品设计和其他相关权利归各自权利方所有。

不得将这些照片重新标记为开放许可证素材，也不得声称相关知识产权风险已经完全消除。

以上内容是项目素材使用边界与公开展示说明，不是正式法律意见。
