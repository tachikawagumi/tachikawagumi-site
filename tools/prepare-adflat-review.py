#!/usr/bin/env python3
"""Prepare owner-only review copies. Does not modify repository sources or upload files.
Requires Pillow. Usage: python tools/prepare-adflat-review.py SOURCE_DIR OUTPUT_SITE_DIR
Publication permission must be confirmed separately before deploying the generated photos.
"""
import hashlib,io,json,re,sys
from pathlib import Path
from PIL import Image,ImageOps

repo=Path(__file__).resolve().parents[1]
if len(sys.argv)!=3:
    raise SystemExit(__doc__)
source,out=map(lambda x:Path(x).resolve(),sys.argv[1:])
if out==repo or repo in out.parents:
    raise SystemExit('Output must be outside the repository to keep unapproved photos out of Git.')
page=out/'works/adflat-temporary-enclosure/index.html'
if not page.is_file():
    raise SystemExit('Copy the review site skeleton to OUTPUT_SITE_DIR before preparing photos.')
source_files={
'01':'01_completed_overview.jpg','02':'02_under_construction_frame.jpg',
'03':'03_before_wide.jpg','04':'04_before_truck.jpg','05':'05_existing_steel_condition.jpg',
'06':'06_fabrication_cutting_wide.jpg','07':'07_fabrication_cutting_close.jpg','08':'08_fabrication_welding.jpg'}
alt={
'01':'アドフラットパネルを設置した仮囲いの完成全景',
'02':'柱と単管の骨組みと設置前のアドフラットパネル',
'03':'仮囲い設置前の敷地外側からの全景',
'04':'仮囲い設置前の資材とトラックのある現場',
'05':'既存鉄骨とその周囲の現場条件',
'06':'鋼製部材を切断加工している様子',
'07':'鋼製部材の切断加工の近景',
'08':'鋼製部材の溶接作業'}
assets=page.parent/'photos';assets.mkdir(exist_ok=True)
audit=[];html=page.read_text()
for n,name in source_files.items():
    original=source/name
    with Image.open(original) as im:
        ex=im.getexif(); image=ImageOps.exif_transpose(im).convert('RGB')
        row={'id':n,'source_file':name,'source_sha256':hashlib.sha256(original.read_bytes()).hexdigest(),'source_bytes':original.stat().st_size,'exif_tags':len(ex),'gps':bool(ex.get(34853)),'permission':'pending','copies':[]}
        stem=Path(name).stem;variants=[]
        for side,suffix in [(1600,''),(800,'-800')]:
            copy=image.copy();copy.thumbnail((side,side));target=assets/(stem+suffix+'.webp')
            buffer=io.BytesIO();copy.save(buffer,'WEBP',quality=86,method=6)
            temporary=target.with_suffix('.tmp');temporary.write_bytes(buffer.getvalue());temporary.replace(target)
            with Image.open(target) as check:
                assert not check.getexif() and not check.info.get('exif')
            row['copies'].append({'file':target.name,'width':copy.width,'height':copy.height,'bytes':target.stat().st_size})
            variants.append((target.name,copy.width,copy.height))
        full,small=variants
        sizes='(max-width:720px) calc(100vw - 36px), 1032px' if n=='01' else '(max-width:700px) calc(100vw - 36px), 504px'
        loading='fetchpriority="high"' if n=='01' else 'loading="lazy" fetchpriority="low"'
        markup=f'<a href="photos/{full[0]}" aria-label="{alt[n]}：写真を大きく見る"><img src="photos/{small[0]}" srcset="photos/{small[0]} {small[1]}w, photos/{full[0]} {full[1]}w" sizes="{sizes}" width="{full[1]}" height="{full[2]}" alt="{alt[n]}" {loading} decoding="async"><span class="photo-note">写真を大きく見る →</span></a>'
        pattern=r'(<figure data-photo="'+n+r'">)<div class="photo-pending">.*?</div>'
        html,count=re.subn(pattern,lambda m:m[1]+markup,html,flags=re.S)
        if count!=1:raise ValueError('Expected exactly one photo slot '+n)
        audit.append(row)
html=html.replace('確認用原稿：案件・写真の公開可否は社長確認待ちです。外部プレビューには未承認の写真を掲載していません。','社長確認用：写真入りのローカル原稿です。人物・施設・撮影者等の掲載許諾と、必要な匿名化の確認後に公開を判断してください。')
page.write_text(html)
index=out/'works/index.html'
s=index.read_text()
s=s.replace('<div class="photo-pending" style="min-height:260px;display:grid;place-content:center;text-align:center;padding:24px;background:#eef1f3;color:#3a4b60"><strong>アドフラット仮囲い</strong><span>写真の掲載確認待ち</span></div>','<img src="adflat-temporary-enclosure/photos/01_completed_overview-800.webp" width="800" height="600" alt="アドフラット仮囲いの完成全景" loading="lazy" decoding="async">',1)
index.write_text(s)
(out/'photo-audit.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2))
print(json.dumps({'photos':len(audit),'source_bytes':sum(x['source_bytes'] for x in audit),'full_webp_bytes':sum(x['copies'][0]['bytes'] for x in audit),'small_webp_bytes':sum(x['copies'][1]['bytes'] for x in audit),'permission':'all pending'},ensure_ascii=False))
