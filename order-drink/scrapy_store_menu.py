import io
import os
import json
import warnings
import argparse
# 方案 A：引入 curl_cffi 取代標準 requests
from curl_cffi import requests as curl_requests
import requests # 保留原標準庫以備不時之需
import urllib3
from urllib.parse import urlparse
from bs4 import BeautifulSoup
from pdf2image import convert_from_bytes
from PIL import Image

DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
    "Accept-Language": "zh-TW,zh;q=0.9,en-US;q=0.8,en;q=0.7",
    "Connection": "keep-alive",
}

GITHUB_RAW_BASE = 'https://raw.githubusercontent.com/Gusty1/Database/refs/heads/main/order-drink/storeMenus/'

SSL_SKIP_STORES = {'可不可', '迷客夏', '鮮茶道'}

def update_store_menus_json(store):
    """爬取成功後，將對應店家的 url 更新至 storeMenus.json。"""
    from urllib.parse import quote
    base_dir = os.path.dirname(os.path.abspath(__file__))
    json_path = os.path.join(base_dir, 'storeMenus.json')
    with open(json_path, 'r', encoding='utf-8') as f:
        entries = json.load(f)
    # 對中文檔名做 URL encode，英數字則保持原樣
    encoded = quote(f'{store}.jpg', safe='')
    new_url = f'{GITHUB_RAW_BASE}{encoded}'
    updated = [
        {**entry, 'url': new_url} if entry['value'] == store else entry
        for entry in entries
    ]
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(updated, f, ensure_ascii=False, indent=2)
    print(f'已更新 storeMenus.json：{store} -> {new_url}')

def get_output_path(store, ext=''):
    base_dir = os.path.dirname(os.path.abspath(__file__))
    # 確保目錄存在
    os.makedirs(os.path.join(base_dir, 'storeMenus'), exist_ok=True)
    return os.path.join(base_dir, 'storeMenus', f'{store}{ext}')

def load_store_list():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    path = os.path.join(base_dir, 'storeAndUrl.json')
    with open(path, "r", encoding="utf-8") as f:
        store_list = json.load(f)
    store_dict = {item["store"]: item["url"] for item in store_list}
    return store_list, store_dict

def get_base_url(store_url):
    parsed = urlparse(store_url)
    return f"{parsed.scheme}://{parsed.netloc}/"

def safe_find(tag, *args, **kwargs):
    if tag is None: return None
    return tag.find(*args, **kwargs)

def safe_find_parent(tag, *args, **kwargs):
    if tag is None: return None
    return tag.find_parent(*args, **kwargs)

def safe_get(tag, attr):
    if tag is None: return ''
    return tag.get(attr, '')

def get_image_url(store, soup, store_dict):
    truedan_base = get_base_url(store_dict.get('珍煮丹', ''))
    wanpo_base = get_base_url(store_dict.get('萬波', ''))
    macu_base = get_base_url(store_dict.get('麻古', ''))

    strategies = {
        '19': lambda s: safe_get(s.find('a', class_='_clip_slider__link'), 'href'),
        'comebuy': lambda s: safe_get(safe_find(s.find('div', class_='tabContentItem'), 'img'), 'src'),
        'teatop': lambda s: safe_get(safe_find(s.find('div', class_='textEditor'), 'img'), 'src'),
        '五桐號': lambda s: safe_get(safe_find(s.find('div', class_='desktopArea'), 'img'), 'src'),
        '大苑子': lambda s: _prefix('https:', safe_get(safe_find(s.find('picture', class_='skip-lazy'), 'img'), 'src')),
        '珍煮丹': lambda s: _prefix(truedan_base, safe_get(s.find('a', class_='fancybox-menu'), 'href')),
        '萬波': lambda s: safe_get(safe_find_parent(s.find('img', src='images/menu-y-1.svg'), 'a'), 'href'),
        '阿義': lambda s: safe_get(safe_find(s.find('div', class_='ayd01_a02'), 'a'), 'href'),
        '麻古': lambda s: _get_macu_url(s, macu_base),
        '清原': lambda s: safe_get(safe_find_parent(s.find('img', class_='wp-image-2488'), 'a'), 'href'),
        '花好月圓': lambda s: safe_get(safe_find(s.find('div', class_='menuArea'), 'img'), 'src'),
        '茶湯會': lambda s: _prefix('https://tw.tp-tea.com/',safe_get(safe_find(s.find('div', class_='drinkIntro'), 'img'),'src')),
        '大茗': lambda s: safe_get(safe_find(safe_find(s.find('div', id='intro'), 'p'), 'img'), 'src'),
        '上宇林': lambda s: _get_shangyulin_url(s),
        '鮮茶道': lambda s: _get_presotea_url(s),
        '吳家': lambda s: _prefix('https:', safe_get(safe_find(s.find('li', id='section-f_4cb060a0-3820-4739-ad05-b4cf6edaa6da'), 'img'), 'data-src')),
        '青山': lambda s: safe_get(safe_find(s.find('div', class_='img-inner'), 'img'), 'src'),
    }

    strategy = strategies.get(store)
    if strategy:
        return strategy(soup) or ''
    return ''

def _prefix(prefix, url):
    return prefix + url if url else ''

def _get_macu_url(soup, base_url):
    tags = soup.find_all('nav', class_='menuListSub')
    if len(tags) < 2: return ''
    link = tags[1].find('a')
    return _prefix(base_url, safe_get(link, 'href'))

def _get_shangyulin_url(soup):
    tag = safe_find(safe_find(soup.find('div', class_='editor_content'), 'p'), 'img')
    src = safe_get(tag, 'src')
    if src.startswith('.'): src = src[2:]
    return f'https://www.shangyulin.com.tw/{src}' if src else ''

def _get_presotea_url(soup):
    tag = soup.find('a', id='menu_img_url')
    src = safe_get(tag, 'href')
    if src.startswith('.'): src = src[2:]
    return f'http://www.presotea.com.tw/{src}' if src else ''

MAX_IMAGE_WIDTH = 1200

def download_image(img_url, save_path):
    """下載圖片並統一轉存為 JPEG 格式。寬度超過 MAX_IMAGE_WIDTH 時自動縮圖。
    回傳 True 表示成功，False 表示失敗。"""
    try:
        # timeout 加大至 60 秒，應對清原等超大圖檔（~40 MB）
        response = curl_requests.get(
            img_url,
            headers=DEFAULT_HEADERS,
            impersonate="chrome110",
            timeout=60
        )
        response.raise_for_status()
        # 清原等網站的圖片超過 Pillow 預設的像素安全上限，明確設定後才能開啟
        Image.MAX_IMAGE_PIXELS = None
        img = Image.open(io.BytesIO(response.content)).convert('RGB')
        # 寬度超過上限時等比例縮小，避免存入過大的圖檔
        if img.width > MAX_IMAGE_WIDTH:
            ratio = MAX_IMAGE_WIDTH / img.width
            new_size = (MAX_IMAGE_WIDTH, int(img.height * ratio))
            img = img.resize(new_size, Image.LANCZOS)
            print(f'已縮圖至 {new_size[0]}x{new_size[1]}')
        img.save(save_path, 'JPEG', quality=95)
        print(f'已下載：{save_path}')
        return True
    except Exception as e:
        print(f'無法下載 {img_url}：{e}')
        return False

def convert_pdf_to_image(pdf_data, page_number, output_image_path):
    """將 PDF 指定頁轉成 JPEG。回傳 True 表示成功，False 表示失敗。"""
    images = convert_from_bytes(pdf_data, first_page=page_number, last_page=page_number)
    if images:
        images[0].save(output_image_path, 'JPEG')
        print(f"圖片已儲存至: {output_image_path}")
        return True
    print("無法提取該頁面作為圖片")
    return False

def download_pdf_menu(store, soup, store_dict, verify):
    """下載並轉換 PDF 菜單。回傳 True 表示成功，False 表示失敗。"""
    if store == '可不可':
        tag = safe_find(soup.find('div', class_='page-menu__download'), 'a')
        url = safe_get(tag, 'href')
        page = 3
    elif store == '迷客夏':
        milksha_base = get_base_url(store_dict.get('迷客夏', ''))
        tag = safe_find(soup.find('div', class_='about_list'), 'a')
        url = _prefix(milksha_base, safe_get(tag, 'href'))
        page = 1
    else:
        return False

    if not url:
        print(f'商家 {store} 找不到 PDF 連結')
        return False

    # 使用 curl_cffi 下載 PDF
    response = curl_requests.get(
        url,
        headers=DEFAULT_HEADERS,
        verify=verify,
        impersonate="chrome110",
        timeout=30
    )
    response.raise_for_status()
    return convert_pdf_to_image(response.content, page, get_output_path(f'{store}.jpg'))

def download_images_from_url(store, store_dict):
    store_url = store_dict.get(store)
    if not store_url:
        print(f'找不到商家 {store} 的網址')
        return

    verify = store not in SSL_SKIP_STORES
    
    # 動態產生 Referer，模擬正常瀏覽路徑
    current_headers = DEFAULT_HEADERS.copy()
    current_headers["Referer"] = get_base_url(store_url)

    try:
        # 使用 curl_requests 並加上 impersonate="chrome110" 繞過 403
        response = curl_requests.get(
            store_url, 
            headers=current_headers, 
            verify=verify, 
            impersonate="chrome110", 
            timeout=15
        )
        response.raise_for_status()
    except Exception as e:
        print(f'無法連線到 {store_url}：{e}')
        return

    soup = BeautifulSoup(response.text, 'html.parser')

    if store in ('可不可', '迷客夏'):
        success = download_pdf_menu(store, soup, store_dict, verify)
        if success:
            update_store_menus_json(store)
        return

    img_url = get_image_url(store, soup, store_dict)
    if not img_url:
        print(f'商家 {store} 沒有找到圖片 URL')
        return

    # 統一輸出為 .jpg，由 download_image 內部用 Pillow 做格式轉換
    success = download_image(img_url, get_output_path(store, '.jpg'))
    if success:
        update_store_menus_json(store)

def main():
    parser = argparse.ArgumentParser(description="下載飲料店菜單圖片")
    parser.add_argument('stores', nargs='+', type=str, help="商家名稱清單（可多個，以空格分隔）")
    args = parser.parse_args()

    _store_list, store_dict = load_store_list()

    for store in args.stores:
        print(f'\n--- 處理商家: {store} ---')
        download_images_from_url(store, store_dict)

# 19 和 阿義 在github action是不能執行的，他們的網站好像有很嚴格檔國外IP，只能本地手動執行
# python scrapy_store_menu.py 19 阿義
if __name__ == '__main__':
    main()