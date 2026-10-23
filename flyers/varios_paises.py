import os,re
from playwright.sync_api import sync_playwright
base=open("render.html").read() if False else None
h2=open("flyer2.html").read()
r=open("render.html").read()  # tiene las estrellas ya dibujadas
round_svgs=dict((n,s) for s,n in re.findall(r'(<svg viewBox="0 0 100 100">.*?</svg>)(?:<div>)?<b>(.*?)</b>',r,re.S))
round_svgs["Brasil"]='<svg viewBox="0 0 100 100"><rect width="100" height="100" fill="#009C3B"/><path d="M50 18 90 50 50 82 10 50z" fill="#FFDF00"/><circle cx="50" cy="50" r="17" fill="#002776"/><path d="M34 46q16-5 32 6" stroke="#fff" stroke-width="3" fill="none"/></svg>'
BADGE={
 "MÉXICO":'<svg viewBox="0 0 30 21"><rect width="10" height="21" fill="#006847"/><rect x="10" width="10" height="21" fill="#fff"/><rect x="20" width="10" height="21" fill="#CE1126"/><circle cx="15" cy="10.5" r="2.6" fill="#8C5A2B"/></svg>',
 "PANAMÁ":'<svg viewBox="0 0 30 21"><rect width="30" height="21" fill="#fff"/><rect x="15" width="15" height="10.5" fill="#D21034"/><rect y="10.5" width="15" height="10.5" fill="#005293"/><circle cx="7.5" cy="5.2" r="2.2" fill="#005293"/><circle cx="22.5" cy="15.8" r="2.2" fill="#D21034"/></svg>',
 "COLOMBIA":'<svg viewBox="0 0 30 21"><rect width="30" height="10.5" fill="#FCD116"/><rect y="10.5" width="30" height="5.25" fill="#003893"/><rect y="15.75" width="30" height="5.25" fill="#CE1126"/></svg>',
}
STRIPE={"MÉXICO":["#006847","#ffffff","#CE1126"],"PANAMÁ":["#005293","#ffffff","#D21034"],"COLOMBIA":["#FCD116","#FCD116","#003893","#CE1126"]}
JOBS=[("MÉXICO","Mexico","mexico.jpg","82% 50%",["Colombia","Venezuela","Chile","Europa"]),
      ("PANAMÁ","Panama","panama.jpg","35% 50%",["Colombia","Venezuela","Chile","Europa"]),
      ("COLOMBIA","Colombia","colombia.jpg","22% 50%",["Venezuela","Chile","Brasil","Europa"])]
def page(up,photo,pos,dests):
    h=h2
    h=re.sub(r'<div class="badge">.*?</div>',f'<div class="badge">{BADGE[up]}DESDE {up}</div>',h,flags=re.S)
    h=h.replace("ENVIAMOS DESDE BRASIL",f"ENVIAMOS DESDE {up}")
    h=h.replace("font-size:68px;line-height",f"font-size:{ {'COLOMBIA':58,'PANAMÁ':64}.get(up,68) }px;line-height")
    h=h.replace("RIO_SLOT",f'<img src="{photo}">').replace("object-position:50% 40%",f"object-position:{pos}")
    h=re.sub(r'<div class="row">.*?</div></div>\n',
             '<div class="row">'+"".join(f'<div class="d">{round_svgs[d]}<b>{d}</b></div>' for d in dests)+'</div>\n',h,flags=re.S)
    h=re.sub(r'<div class="stripe">.*?</div>','<div class="stripe">'+"".join(f'<i style="background:{c}"></i>' for c in STRIPE[up])+'</div>',h,flags=re.S)
    return h
with sync_playwright() as p:
    b=p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
    for up,slug,photo,pos,dests in JOBS:
        open(f"r_{slug}.html","w").write(page(up,photo,pos,dests))
        pg=b.new_page(viewport={"width":1080,"height":1080})
        pg.goto("file://"+os.path.abspath(f"r_{slug}.html")); pg.wait_for_timeout(1500)
        pg.screenshot(path=f"flyer-desde-{slug.lower()}.png"); pg.close()
    b.close()
print("ok")
