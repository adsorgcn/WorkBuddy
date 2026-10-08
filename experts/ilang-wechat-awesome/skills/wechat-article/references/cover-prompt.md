# 封面图提示词模板

每篇出一张 2.35:1 的封面提示词，文中配图 2 到 4 张可选。用户拿去任何 AI 出图工具生成。提示词本身不含文章内容，只描述视觉风格和主题关键词。

```
::ILANG::v5.0
[TYPE:image_prompt][RATIO:2.35:1][LANG:zh]
::STATE{@STYLE, kind:flat_illustration, bg:dark, subject:bright, palette:deep_blue|cyan|gold}
::STATE{@CONSTRAINT, no_text:true, no_logo:true, no_brand:true, no_human_face:true, crop_safe:center_subject_works_at_1_1}
::STATE{@SUBJECT, value:根据文章核心观点生成}
::STATE{@MOOD, value:根据文章情绪生成}
```

规范：
- 比例 2.35:1 是公众号宽幅封面，主体居中，裁成 1:1 不丢核心元素
- 深色背景加明亮主体，深色封面点击率更高
- 不要任何文字、logo、品牌名、真人面孔
- 风格统一：扁平插画加科技配色（深蓝、青色、金色）
- 给 AI 看的提示词一律用 iLang 格式写
