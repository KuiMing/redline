from pathlib import Path

src = Path('static/leaflet_full_map.html').read_text(encoding='utf-8')
html_start = src.find('<div id="app">')
html_end = src.find('<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>')
js_start = src.find('const MAP_DATA =')
js_end = src.rfind('</script>')

html = src[html_start:html_end].strip()
js = src[js_start:js_end].strip()

Path('static/leaflet_embed_fragment.html').write_text(html + '\n', encoding='utf-8')
Path('static/leaflet_embed_logic.js').write_text(js + '\n', encoding='utf-8')
print('wrote fragments')
