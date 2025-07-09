#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
最终工作版原价屋商品报价解析器
基于简化测试版本的成功逻辑
"""

import re
import json
import csv
import html
from typing import List, Dict, Any
import argparse
import urllib.request
import urllib.error

class WorkingCoolPCParser:
    def __init__(self, html_file: str):
        self.html_file = html_file
        self.categories = []
    
    @staticmethod
    def download_html(output_file: str = 'evaluate.html') -> bool:
        """從 CoolPC 網站下載並轉換 HTML 文件"""
        url = 'https://www.coolpc.com.tw/evaluate.php'
        
        try:
            print(f"正在從 {url} 下載資料...")
            
            # 設置請求標頭，模擬瀏覽器
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            
            # 創建請求
            request = urllib.request.Request(url, headers=headers)
            
            # 下載資料
            with urllib.request.urlopen(request) as response:
                # 讀取 BIG5 編碼的內容
                content_bytes = response.read()
                
                # 嘗試用 BIG5 解碼，如果失敗則嘗試其他編碼
                try:
                    content = content_bytes.decode('big5')
                except UnicodeDecodeError:
                    try:
                        content = content_bytes.decode('big5-hkscs')
                    except UnicodeDecodeError:
                        # 如果還是失敗，使用 ignore 參數忽略無法解碼的字符
                        content = content_bytes.decode('big5', errors='ignore')
            
            # 寫入文件
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(content)
            
            print(f"成功下載並保存到 {output_file}")
            return True
            
        except urllib.error.URLError as e:
            print(f"網路錯誤: {e}")
            return False
        except Exception as e:
            print(f"發生錯誤: {e}")
            return False
        
    def parse_html(self) -> List[Dict[str, Any]]:
        """解析 HTML 文件並提取商品數據"""
        
        with open(self.html_file, 'r', encoding='utf-8') as f:
            html_content = f.read()
        
        # 使用与简化版本相同的逻辑
        select_pattern = r'<SELECT[^>]*name=n(\d+)[^>]*>(.*?)</SELECT>'
        select_matches = re.findall(select_pattern, html_content, re.DOTALL | re.IGNORECASE)
        
        categories = []
        
        for select_id, select_content in select_matches:
            category_data = self._parse_category(select_content, select_id)
            if category_data:
                categories.append(category_data)
        
        self.categories = categories
        return categories
    
    def _get_category_name(self, select_id: str) -> str:
        """获取类别名称 - 使用完整映射表"""
        
        category_mapping = {
            '1': '品牌小主機、AIO|VR虛擬',
            '2': '筆電|平板|穿戴配件',
            '3': '酷！PC 套裝產線',
            '4': '處理器 CPU',
            '5': '主機板 MB',
            '6': '記憶體 RAM',
            '7': '固態硬碟 M.2|SSD',
            '8': '2.5/3.5 傳統內接硬碟HDD',
            '9': '隨身碟|隨身硬碟|記憶卡',
            '10': '散熱器|散熱墊|散熱膏',
            '11': '封閉式|開放式水冷',
            '12': '顯示卡VGA',
            '13': '螢幕|投影機|壁掛',
            '14': 'CASE 機殼(+電源)',
            '15': '電源供應器',
            '16': '機殼風扇|機殼配件',
            '17': '鍵盤+鼠|搖桿|桌+椅',
            '18': '滑鼠|鼠墊|數位板',
            '19': 'IP分享器|網卡|網通設備',
            '20': '網路NAS|網路IPCAM',
            '21': '音效卡|電視卡(盒)|影音',
            '22': '喇叭|耳機|麥克風',
            '23': '燒錄器 CD/DVD/BD',
            '24': 'USB週邊|硬碟座|讀卡機',
            '25': '行車紀錄器|USB視訊鏡頭',
            '26': 'UPS不斷電|印表機|掃描',
            '27': '介面擴充卡|專業Raid卡',
            '28': '網路、傳輸線、轉頭|KVM',
            '29': 'OS+應用軟體|禮物卡',
            '30': '福利品出清'
        }
        
        return category_mapping.get(select_id, f"類別 {select_id}")
    
    def _parse_category(self, select_content: str, select_id: str) -> Dict[str, Any]:
        """解析類別內容"""
        
        # 獲取類別名稱
        category_name = self._get_category_name(select_id)
        
        # 先找到所有的 OPTGROUP 和 OPTION 元素
        # 解析 OPTGROUP
        optgroup_pattern = r'<OPTGROUP\s+LABEL=[\'"](.*?)[\'"]>'
        optgroup_matches = list(re.finditer(optgroup_pattern, select_content, re.IGNORECASE))
        
        # 建立 OPTGROUP 位置索引
        optgroup_positions = [(match.start(), match.end(), match.group(1)) for match in optgroup_matches]
        
        # 找到所有 OPTION 元素（處理沒有關閉標籤的情況）
        # 先找到所有 OPTION 標籤的位置
        option_starts = list(re.finditer(r'<OPTION([^>]*?)>', select_content, re.IGNORECASE))
        option_matches = []
        
        for i, match in enumerate(option_starts):
            attrs = match.group(1)
            start_pos = match.end()
            
            # 找到下一個標籤的開始位置
            next_tag_match = re.search(r'<(?:OPTION|OPTGROUP|/SELECT|/OPTGROUP|/OPTION)', select_content[start_pos:], re.IGNORECASE)
            if next_tag_match:
                end_pos = start_pos + next_tag_match.start()
            else:
                end_pos = len(select_content)
            
            content = select_content[start_pos:end_pos].strip()
            
            # Remove any remaining HTML tags from content
            content = re.sub(r'<[^>]*>', '', content)
            
            # 確定這個 OPTION 屬於哪個 OPTGROUP
            option_pos = match.start()
            current_optgroup = None
            for og_start, og_end, og_label in optgroup_positions:
                if option_pos > og_start:
                    current_optgroup = og_label
            
            option_matches.append((attrs, content, current_optgroup))
        
        if not option_matches:
            return None
        
        # 處理每個 option，提取屬性
        parsed_options = []
        for attrs_str, content, optgroup_label in option_matches:
            # 提取 value
            value_match = re.search(r'value=([^>\s]*)', attrs_str)
            value = value_match.group(1) if value_match else ''
            
            # 提取 class
            class_match = re.search(r'class=([^>\s]*)', attrs_str)
            css_class = class_match.group(1) if class_match else ''
            
            # 檢查是否 disabled
            is_disabled = 'disabled' in attrs_str
            
            # 檢查是否為補充說明（特定樣式）
            is_supplement = ('style=\'font-size:9pt;color:#222;background-color:transparent\'' in attrs_str or 
                           'style="font-size:9pt;color:#222;background-color:transparent"' in attrs_str)
            
            parsed_options.append({
                'value': value,
                'class': css_class,
                'content': html.unescape(content).strip(),
                'is_disabled': is_disabled,
                'is_supplement': is_supplement,
                'optgroup': optgroup_label
            })
        
        # 第一個 option 通常是類別摘要
        first_option = parsed_options[0] if parsed_options else {'content': ''}
        category_summary = first_option['content']
        
        # 解析類別摘要中的統計數據
        stats = self._parse_category_stats(category_summary)
        
        # 按子分類組織商品
        subcategories = {}
        current_group = None
        
        for i, option in enumerate(parsed_options):
            content = option['content']
            
            # 跳過第一個摘要選項
            if i == 0 and ('共有商品' in content or option['value'] == '0'):
                continue
            
            # 跳過補充說明行
            if option['is_supplement'] and '↪' in content:
                continue
            
            # 判斷是否為群組標題
            if self._is_group_header(content):
                current_group = content
            else:
                # 這是商品
                product = self._parse_product(str(i), content, option['class'], current_group)
                if product:
                    # 確定子分類
                    subcategory = option['optgroup'] if option['optgroup'] else '其他'
                    
                    if subcategory not in subcategories:
                        subcategories[subcategory] = {
                            'name': subcategory,
                            'products': []
                        }
                    
                    subcategories[subcategory]['products'].append(product)
        
        # 對某些類別的產品進行優先排序
        if select_id == '12':  # 顯示卡VGA
            for subcategory in subcategories.values():
                subcategory['products'] = self._prioritize_vga_products(subcategory['products'])
        
        return {
            'category_id': select_id,
            'category_name': category_name,
            'summary': category_summary,
            'stats': stats,
            'subcategories': list(subcategories.values())
        }
    
    def _is_group_header(self, content: str) -> bool:
        """判斷是否為群組標題"""
        
        # 如果包含價格，通常是商品
        if '$' in content and re.search(r'\$[0-9,]+', content):
            return False
        
        # 如果包含型號格式【xxx】，通常是商品
        if '【' in content and '】' in content:
            return False
        
        # 群組標題的特徵
        group_indicators = [
            '❤',  # 心型符號開頭
            '※',  # 註記符號
            '↪',  # 箭頭符號（通常是附加說明）
            '推薦用於',  # 推薦說明
            '系列',  # 系列名稱
            '專區',  # 專區標題
            '配件',  # 配件分類
            '周邊',  # 周邊分類
        ]
        
        # 檢查是否包含群組指示符
        if any(indicator in content for indicator in group_indicators):
            return True
        
        # 檢查是否是純標題格式（沒有具體商品信息）
        if len(content) < 50 and not any(char in content for char in ['/', 'G', 'GB', 'TB', 'Hz', 'W']):
            if not any(word in content for word in ['ASUS', 'MSI', 'Intel', 'AMD', 'NVIDIA']):
                return True
        
        return False
    
    def _parse_product(self, index: str, text: str, css_class: str, group_name: str = None) -> Dict[str, Any]:
        """解析商品數據"""
        
        if not text:
            return None
        
        # 解析價格
        price_match = re.search(r'\$([0-9,]+)', text)
        price = None
        if price_match:
            price = int(price_match.group(1).replace(',', ''))
        
        # 解析品牌和型號
        brand_model = self._extract_brand_model(text)
        
        # 解析規格
        specs = self._extract_specs(text)
        
        # 檢查特殊標記
        markers = self._extract_markers(text, css_class)
        
        # 解析折扣信息
        discount = self._extract_discount(text)
        
        return {
            'index': index,
            'group': group_name,
            'brand': brand_model.get('brand'),
            'model': brand_model.get('model'),
            'specs': specs,
            'price': price,
            'original_price': discount.get('original_price') if discount else None,
            'discount_amount': discount.get('discount_amount') if discount else None,
            'markers': markers,
            'raw_text': text
        }
    
    def _parse_category_stats(self, summary_text: str) -> Dict[str, int]:
        """解析類別統計數據"""
        stats = {}
        
        patterns = {
            'total_items': r'共有商品\s*(\d+)\s*樣',
            'hot_items': r'熱賣\s*(\d+)',
            'with_images': r'圖片\s*(\d+)',
            'with_discussions': r'討論\s*(\d+)',
            'price_changes': r'價格異動\s*(\d+)',
            'time_limited': r'限時下殺▼(\d+)'
        }
        
        for key, pattern in patterns.items():
            match = re.search(pattern, summary_text)
            stats[key] = int(match.group(1)) if match else 0
        
        return stats
    
    def _extract_brand_model(self, text: str) -> Dict[str, str]:
        """提取品牌和型號"""
        # Remove price and special symbols from the end to clean up text
        clean_text = re.sub(r'\$[0-9,]+.*$', '', text)
        clean_text = re.sub(r'[◆★↓→].*', '', clean_text)
        clean_text = clean_text.strip()
        
        # Handle promotional prefixes like "[精選78X3D]", "[強勢精選7500F]"
        clean_text = re.sub(r'^\[[^\]]+\]\s*', '', clean_text)
        
        # Handle both English and Chinese brand names
        # Pattern 1: Chinese brand followed by English brand (e.g., "威剛 ADATA")
        chinese_english_match = re.match(r'^([\u4e00-\u9fff]+)\s+([A-Za-z]+)', clean_text.strip())
        if chinese_english_match:
            chinese_brand = chinese_english_match.group(1)
            english_brand = chinese_english_match.group(2)
            brand = f"{chinese_brand} {english_brand}"  # Keep both Chinese and English names
            # Look for model after the brand names
            # Pattern: 威剛 ADATA LEGEND 900 512GB
            model_pattern = rf'^[\u4e00-\u9fff]+\s+{english_brand}\s+([A-Za-z0-9\s\-]+?)(?:\s+\d+(?:GB|TB|G)|/)'
            model_match = re.search(model_pattern, clean_text.strip())
            if model_match:
                model = model_match.group(1).strip()
            else:
                model = None
            return {'brand': brand, 'model': model}
        
        # Pattern 2: English brand only (like AMD, Intel, etc.)
        brand_match = re.match(r'^([A-Za-z]+)', clean_text.strip())
        brand = brand_match.group(1) if brand_match else None
        
        model = None
        if brand:
            # Special handling for CPU brands (AMD, Intel)
            if brand in ['AMD', 'Intel']:
                # For CPUs, extract the full model including series and specific model
                # Examples: "AMD R7 7800X3D", "Intel i5-14400F", "AMD R5 3400G"
                # Updated pattern to capture full CPU model names including X3D suffix
                # Fixed: Handle various patterns - space before some keywords, no space before others
                cpu_model_pattern = rf'^{brand}\s+([A-Za-z0-9\-X3D]+(?:\s+[A-Za-z0-9\-X3D]+)*?)(?:\s*(?:代理盒裝|盒)|(?:\s+MPK)|【)'
                cpu_model_match = re.search(cpu_model_pattern, clean_text)
                if cpu_model_match:
                    model = cpu_model_match.group(1).strip()
                else:
                    # Fallback: try to extract everything after brand until common CPU description words
                    # Updated to match the main pattern for consistency
                    fallback_pattern = rf'^{brand}\s+([A-Za-z0-9\-X3D]+(?:\s+[A-Za-z0-9\-X3D]+)*?)(?:\s*(?:代理盒裝|盒|含風扇)|(?:\s+MPK)|【)'
                    fallback_match = re.search(fallback_pattern, clean_text)
                    if fallback_match:
                        model = fallback_match.group(1).strip()
            else:
                # For non-CPU products, use the original logic
                # Pattern: Brand ModelName Capacity/Specs
                model_pattern = rf'^{brand}\s+([A-Za-z0-9\-]+)\s+(?:\d+(?:GB|TB|G)|/)'
                model_match = re.search(model_pattern, clean_text.strip())
                if model_match:
                    model = model_match.group(1)
        
        # If no model found yet, try the bracket method but exclude warranty info and CPU specs
        if not model:
            # Find all bracket contents
            bracket_matches = re.findall(r'【([^】]+)】', clean_text)
            for bracket_content in bracket_matches:
                # Skip if it's warranty info, CPU specs, or memory specs
                if any(skip_pattern in bracket_content for skip_pattern in [
                    '年保', '保固', '核/', '緒', 'GB', 'TB', 'MHz', 'W/', 'nm'
                ]):
                    continue
                model = bracket_content
                break
        
        return {'brand': brand, 'model': model}
    
    def _extract_specs(self, text: str) -> List[str]:
        """提取規格信息"""
        spec_match = re.search(r'】([^$]+)\$', text)
        if spec_match:
            spec_text = spec_match.group(1).strip()
            specs = [spec.strip() for spec in spec_text.split('/') if spec.strip()]
            return specs
        
        # 如果沒有找到型號】格式，嘗試其他方式提取規格
        clean_text = re.sub(r'^[A-Za-z]+\s*', '', text)
        clean_text = re.sub(r'\$[0-9,]+.*$', '', clean_text)
        clean_text = re.sub(r'[◆★↓→].*', '', clean_text)
        
        if '/' in clean_text:
            specs = [spec.strip() for spec in clean_text.split('/') if spec.strip()]
            return specs
        
        return []
    
    def _extract_markers(self, text: str, css_class: str) -> List[str]:
        """提取特殊標記"""
        markers = []
        
        if '◆' in text:
            markers.append('discussion')
        if '★' in text:
            markers.append('image')
        if 'r' in css_class or '熱賣' in text:
            markers.append('hot')
        if 'g' in css_class or '價格異動' in text or '↘' in text:
            markers.append('price_change')
        if 'b' in css_class:
            markers.append('hot_and_price_change')
        if '限時' in text or '下殺' in text:
            markers.append('time_limited')
        if '【訂】' in text:
            markers.append('pre_order')
        if '酷幣' in text:
            markers.append('cool_coin_discount')
        
        return markers
    
    def _extract_discount(self, text: str) -> Dict[str, Any]:
        """提取折扣信息"""
        discount_match = re.search(r'\$([0-9,]+)↘\$([0-9,]+)', text)
        if discount_match:
            original = int(discount_match.group(1).replace(',', ''))
            current = int(discount_match.group(2).replace(',', ''))
            return {
                'original_price': original,
                'current_price': current,
                'discount_amount': original - current
            }
        
        cool_coin_match = re.search(r'酷幣(\d+)', text)
        if cool_coin_match:
            return {
                'cool_coin_discount': int(cool_coin_match.group(1))
            }
        
        return None
    
    def _prioritize_vga_products(self, products):
        """對顯卡產品進行優先排序，將主流顯卡排在前面"""
        
        # 定義優先級權重
        def get_vga_priority(product):
            text = product.get('raw_text', '').upper()
            priority = 0
            
            # RTX 50系列 - 最高優先級
            if 'RTX 50' in text or 'RTX5' in text:
                priority += 1000
                if 'RTX 5090' in text or 'RTX5090' in text:
                    priority += 900
                elif 'RTX 5080' in text or 'RTX5080' in text:
                    priority += 800
                elif 'RTX 5070' in text or 'RTX5070' in text:
                    priority += 700
                elif 'RTX 5060' in text or 'RTX5060' in text:
                    priority += 600
            
            # RTX 40系列 - 次高優先級
            elif 'RTX 40' in text or 'RTX4' in text:
                priority += 800
                if 'RTX 4090' in text or 'RTX4090' in text:
                    priority += 900
                elif 'RTX 4080' in text or 'RTX4080' in text:
                    priority += 800
                elif 'RTX 4070' in text or 'RTX4070' in text:
                    priority += 700
                elif 'RTX 4060' in text or 'RTX4060' in text:
                    priority += 600
            
            # AMD RX 7000系列
            elif 'RX 7' in text:
                priority += 700
                if 'RX 7900' in text:
                    priority += 900
                elif 'RX 7800' in text:
                    priority += 800
                elif 'RX 7700' in text:
                    priority += 700
                elif 'RX 7600' in text:
                    priority += 600
            
            # AMD RX 9000系列 - 最新
            elif 'RX 9' in text:
                priority += 900
                if 'RX 9070' in text:
                    priority += 800
                elif 'RX 9060' in text:
                    priority += 700
            
            # RTX 30系列 - 中等優先級
            elif 'RTX 30' in text or 'RTX3' in text:
                priority += 500
                if 'RTX 3090' in text or 'RTX3090' in text:
                    priority += 400
                elif 'RTX 3080' in text or 'RTX3080' in text:
                    priority += 300
                elif 'RTX 3070' in text or 'RTX3070' in text:
                    priority += 200
                elif 'RTX 3060' in text or 'RTX3060' in text:
                    priority += 100
            
            # Intel ARC系列
            elif 'ARC' in text:
                priority += 400
                if 'B580' in text:
                    priority += 100
                elif 'B570' in text:
                    priority += 80
                elif 'A770' in text:
                    priority += 60
            
            # 降低配件的優先級
            if any(keyword in text for keyword in ['支撐架', '支架', 'HOLDER', 'SUPPORT']):
                priority -= 2000
            
            # 降低低階顯卡的優先級
            if any(keyword in text for keyword in ['GT710', 'GT730', 'GT1030']):
                priority -= 1000
            
            # 熱賣商品加分
            if product.get('markers') and 'hot' in product.get('markers'):
                priority += 50
            
            # 有價格異動的商品加分
            if product.get('markers') and 'price_change' in product.get('markers'):
                priority += 30
            
            return priority
        
        # 排序產品：按優先級降序，然後按原始順序
        sorted_products = sorted(products, key=lambda p: (-get_vga_priority(p), products.index(p)))
        return sorted_products
    
    def export_to_json(self, output_file: str):
        """匯出為 JSON 格式"""
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(self.categories, f, ensure_ascii=False, indent=2)
        print(f"數據已匯出到 {output_file}")
    
    def export_to_csv(self, output_file: str):
        """匯出為 CSV 格式"""
        rows = []
        
        for category in self.categories:
            for subcategory in category.get('subcategories', []):
                for product in subcategory['products']:
                    row = {
                        'category_id': category['category_id'],
                        'category': category['category_name'],
                        'subcategory': subcategory['name'],
                        'group': product.get('group', ''),
                        'brand': product.get('brand', ''),
                        'model': product.get('model', ''),
                        'specs': ' / '.join(product.get('specs', [])),
                        'price': product.get('price'),
                        'original_price': product.get('original_price'),
                        'discount_amount': product.get('discount_amount'),
                        'markers': ', '.join(product.get('markers', [])),
                        'raw_text': product.get('raw_text', '')
                    }
                    rows.append(row)
        
        with open(output_file, 'w', encoding='utf-8', newline='') as f:
            if rows:
                writer = csv.DictWriter(f, fieldnames=rows[0].keys())
                writer.writeheader()
                writer.writerows(rows)
        print(f"數據已匯出到 {output_file}")
    
    def print_summary(self):
        """列印解析摘要"""
        total_categories = len(self.categories)
        total_products = 0
        
        # 計算總商品數
        for cat in self.categories:
            for subcat in cat.get('subcategories', []):
                total_products += len(subcat['products'])
        
        print(f"\n=== 解析摘要 ===")
        print(f"類別總數: {total_categories}")
        print(f"商品總數: {total_products}")
        print(f"\n各類別商品數量:")
        
        for category in self.categories:
            category_total = sum(len(subcat['products']) for subcat in category.get('subcategories', []))
            print(f"  {category['category_name']}: {category_total} 項商品")
            
            # 顯示子分類
            for subcategory in category.get('subcategories', []):
                print(f"    └─ {subcategory['name']}: {len(subcategory['products'])} 項商品")
            
            if category['stats']:
                stats = category['stats']
                print(f"    統計數據:")
                print(f"      - 熱賣: {stats.get('hot_items', 0)}")
                print(f"      - 價格異動: {stats.get('price_changes', 0)}")
                print(f"      - 限時下殺: {stats.get('time_limited', 0)}")

def main():
    parser = argparse.ArgumentParser(description='最終工作版原價屋商品報價解析器')
    parser.add_argument('input_file', nargs='?', default='evaluate.html', help='輸入的 HTML 文件路徑 (預設: evaluate.html)')
    parser.add_argument('--download', action='store_true', help='從 CoolPC 網站下載最新資料')
    parser.add_argument('--json', help='匯出 JSON 文件路徑')
    parser.add_argument('--csv', help='匯出 CSV 文件路徑')
    parser.add_argument('--summary', action='store_true', help='顯示解析摘要')
    
    args = parser.parse_args()
    
    # 如果指定了 --download，先下載 HTML
    if args.download:
        if not WorkingCoolPCParser.download_html(args.input_file):
            print("下載失敗，程式結束")
            return
    
    # 檢查文件是否存在
    import os
    if not os.path.exists(args.input_file):
        print(f"錯誤: 找不到文件 '{args.input_file}'")
        print("提示: 使用 --download 參數可以從網站下載最新資料")
        return
    
    coolpc_parser = WorkingCoolPCParser(args.input_file)
    print("正在解析 HTML 文件...")
    coolpc_parser.parse_html()
    
    if args.summary:
        coolpc_parser.print_summary()
    
    if args.json:
        coolpc_parser.export_to_json(args.json)
    
    if args.csv:
        coolpc_parser.export_to_csv(args.csv)
    
    if not args.json and not args.csv and not args.summary:
        print("請指定輸出格式 (--json 或 --csv) 或使用 --summary 查看摘要")

if __name__ == "__main__":
    main()
