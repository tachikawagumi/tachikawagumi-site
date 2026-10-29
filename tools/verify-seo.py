from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit, unquote
import json,subprocess,hashlib,xml.etree.ElementTree as ET
class Doc(HTMLParser):
 def __init__(self,text):
  super().__init__(convert_charrefs=True);self.nodes=[];self.scripts=[];self.titles=[];self.active=None;self.buf='';self.feed(text)
 def handle_starttag(self,t,a):
  a=dict(a);self.nodes.append((t,a))
  if t in ('script','title'):self.active=(t,a);self.buf=''
 def handle_data(self,d):
  if self.active:self.buf+=d
 def handle_endtag(self,t):
  if self.active and t==self.active[0]:
   if t=='title':self.titles.append(self.buf)
   elif self.active[1].get('type')=='application/ld+json':self.scripts.append(json.loads(self.buf))
   self.active=None
root=Path.cwd();baseline=subprocess.check_output(['git','merge-base','HEAD','origin/main'],text=True).strip();pages=[p for p in root.rglob('*.html') if not any(x in p.parts for x in ('dist','.git'))];docs={p:Doc(p.read_text()) for p in pages};errors=[];titles=[];descs=[]
for p,d in docs.items():
 rel=str(p.relative_to(root));n=d.nodes
 if rel=='404.html':continue
 h1=sum(t=='h1' for t,a in n);assert h1==1,(rel,h1)
 title=d.titles[0];desc=[a['content'] for t,a in n if t=='meta' and a.get('name')=='description'];assert len(desc)==1,rel
 titles.append(title);descs+=desc
 canonical=[a['href'] for t,a in n if t=='link' and a.get('rel')=='canonical'];expected='https://tachikawagumi.co.jp/'+('' if rel=='index.html' else rel.removesuffix('index.html'));assert canonical==[expected],(rel,canonical)
 for t,a in n:
  for k in ('href','src','srcset'):
   for val in ([x.strip().split(' ')[0] for x in a.get(k,'').split(',')] if k=='srcset' else [a.get(k,'')]):
    if not val:continue
    u=urlsplit(val)
    if u.scheme or u.netloc:continue
    target=(root/unquote(u.path.lstrip('/')) if u.path.startswith('/') else p.parent/unquote(u.path)).resolve() if u.path else p
    if target.is_dir():target=target/'index.html'
    if not target.exists():errors.append([rel,k,val,'missing'])
    elif u.fragment and target.suffix=='.html':
     td=docs.get(target) or Doc(target.read_text())
     if not any(a2.get('id')==unquote(u.fragment) for t2,a2 in td.nodes):errors.append([rel,k,val,'fragment'])
  if t=='img' and a.get('src'):
   assert 'alt' in a and 'width' in a and 'height' in a,(rel,a)
assert len(set(titles))==len(titles);assert len(set(descs))==len(descs)
assert not errors,errors
sitemap=ET.parse('sitemap.xml');assert len(sitemap.findall('.//{*}loc'))==8
for name in ['assets/contact-ui.js','assets/contact-ui.css','assets/service-content.css','robots.txt','sitemap.xml']:
 assert subprocess.check_output(['git','show',baseline+':'+name])==Path(name).read_bytes(),name
# Production scripts and form markup must stay byte-for-byte equivalent.
import re
for name in ['index.html','factory-renovation/index.html','works/index.html']:
 before=subprocess.check_output(['git','show',baseline+':'+name]).decode();after=Path(name).read_text()
 pattern=r'<script(?![^>]*application/ld\+json)[\s\S]*?</script>'
 assert re.findall(pattern,before)==re.findall(pattern,after),name
 if name=='index.html':assert re.findall(r'<form[\s\S]*?</form>',before)==re.findall(r'<form[\s\S]*?</form>',after)
print(json.dumps({'html_pages':len(pages),'sitemap_pages':8,'titles_unique':True,'descriptions_unique':True,'local_links_and_fragments':'PASS','images_alt_dimensions_files':'PASS','json_ld':'PASS','tracking_form_robots_sitemap_unchanged':'PASS'},indent=2))
