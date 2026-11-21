from PIL import Image, ImageDraw, ImageFont
S = 256
im = Image.new("RGBA", (S, S), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
d.polygon([(128,8),(240,48),(240,144),(128,248),(16,144),(16,48)], fill=(245,179,1,255))
f = ImageFont.truetype(r"C:\Windows\Fonts\segoeuib.ttf", 150)
d.text((128,118), "N", font=f, fill=(0,0,0,255), anchor="mm")
im.save("nashama.ico", sizes=[(256,256),(64,64),(48,48),(32,32),(16,16)])
