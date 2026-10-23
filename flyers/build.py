import math,os,sys
from playwright.sync_api import sync_playwright
h=open("flyer2.html").read()
def star(cx,cy,r):
    pts=[]
    for i in range(10):
        a=-math.pi/2+i*math.pi/5; rr=r if i%2==0 else r*0.4
        pts.append(f"{cx+rr*math.cos(a):.2f},{cy+rr*math.sin(a):.2f}")
    return f'<polygon points="{" ".join(pts)}"/>'
ve="".join(star(50+20*math.cos(math.radians(a)),66+20*math.sin(math.radians(a)),3.6) for a in range(-160,-19,20))
eu="".join(star(50+30*math.cos(math.radians(a)),50+30*math.sin(math.radians(a)),5.2) for a in range(0,360,30))
h=h.replace('<g fill="#fff">STARS</g>',f'<g fill="#fff">{ve}</g>').replace("EUSTARS",eu)
rio=[f for f in os.listdir(".") if f.startswith("rio.")]
h=h.replace("RIO_SLOT",f'<img src="{rio[0]}">' if rio else '<div class="ph">FOTO DE RÍO AQUÍ</div>')
open("render.html","w").write(h)
with sync_playwright() as p:
    b=p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
    pg=b.new_page(viewport={"width":1080,"height":1080})
    pg.goto("file://"+os.path.abspath("render.html")); pg.wait_for_timeout(2000)
    pg.screenshot(path="flyer-brasil-foto.png"); b.close()
