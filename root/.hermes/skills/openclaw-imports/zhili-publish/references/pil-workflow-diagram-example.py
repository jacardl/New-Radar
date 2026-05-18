#!/usr/bin/env python3
"""
PIL 绘制工作流示意图示例：prototype → rewind → summarize 三阶段
复制此文件到 /tmp/ 修改颜色和文案后使用。
"""
from PIL import Image, ImageDraw

W, H = 900, 400
img = Image.new('RGB', (W, H), (255, 255, 255))
d = ImageDraw.Draw(img)

# === 颜色常量 ===
CYAN   = (0, 182, 194)   # 阶段1
ORANGE = (255, 140, 0)   # 阶段2
GREEN  = (0, 180, 120)   # 阶段3
GRAY   = (100, 100, 110) # 箭头/标注

# === 背景网格 ===
for y in range(0, H, 30):
    d.line([(0, y), (W, y)], fill=(245, 245, 250), width=1)
for x in range(0, W, 30):
    d.line([(x, 0), (x, H)], fill=(245, 245, 250), width=1)

# === 顶部阶段标注 ===
d.text((130, 60),  '探索阶段', fill=CYAN,   anchor='mm')
d.text((370, 60),  '反思阶段', fill=ORANGE, anchor='mm')
d.text((610, 60),  '压缩阶段', fill=GREEN,  anchor='mm')

# === 阶段1：圆角矩形 ===
d.rounded_rectangle([30, 130, 230, 270], radius=12, fill=CYAN)
d.text((130, 175), '/prototype', fill=(255,255,255), anchor='mm')
d.text((130, 210), '原型实验',  fill=(255,255,255), anchor='mm')
d.text((130, 240), '不计成本探索', fill=(200,220,230), anchor='mm')

# === 箭头1：prototype → rewind ===
d.polygon([(238, 202), (258, 185), (258, 219)], fill=CYAN)

# === 阶段2 ===
d.rounded_rectangle([270, 130, 470, 270], radius=12, fill=ORANGE)
d.text((370, 175), '/rewind',    fill=(255,255,255), anchor='mm')
d.text((370, 210), '回到问题点', fill=(255,255,255), anchor='mm')
d.text((370, 240), '带着洞察回去', fill=(220,200,180), anchor='mm')

# === 箭头2：rewind → summarize ===
d.polygon([(478, 202), (498, 185), (498, 219)], fill=ORANGE)

# === 阶段3 ===
d.rounded_rectangle([510, 130, 710, 270], radius=12, fill=GREEN)
d.text((610, 175), 'summarize',  fill=(255,255,255), anchor='mm')
d.text((610, 210), '压缩过程',   fill=(255,255,255), anchor='mm')
d.text((610, 240), '提取热数据', fill=(180,220,200), anchor='mm')

# === 箭头3：summarize → 热数据 ===
d.polygon([(718, 202), (738, 185), (738, 219)], fill=GRAY)

# === 底部总结框 ===
d.rounded_rectangle([280, 300, 620, 365], radius=10, fill=(255, 245, 220))
d.text((450, 332), '热数据 → 可复用记忆', fill=(160, 110, 0), anchor='mm')

# === 保存 ===
img.save('/tmp/prototype_rewind_diagram.png', 'PNG', quality=95)
print("Saved: /tmp/prototype_rewind_diagram.png")
