import os
import json
import time
from datetime import datetime
from playwright.sync_api import sync_playwright

CONFIG_FILE = 'config.json'
DATA_FILE = 'data/prices.json'

with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
    config = json.load(f)
skus = config.get('skus', [])

# 优先从环境变量读取（GitHub Secrets），其次读取配置文件
cookie_str = os.environ.get("JD_COOKIE", "").strip()
if not cookie_str:
    cookie_str = config.get('cookie', '').strip()

cookies = []
if cookie_str:
    for item in cookie_str.split(';'):
        if '=' in item:
            name, value = item.strip().split('=', 1)
            cookies.append({'name': name, 'value': value, 'domain': '.jd.com', 'path': '/'})

if os.path.exists(DATA_FILE):
    with open(DATA_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)
else:
    data = {}

today = datetime.now().strftime('%Y-%m-%d')

print("正在启动云端无头浏览器，开始抓取...")
with sync_playwright() as p:
    # 云端运行必须加 --no-sandbox 参数
    browser = p.chromium.launch(headless=True, args=['--no-sandbox', '--disable-setuid-sandbox'])
    
    context = browser.new_context(
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        viewport={"width": 1920, "height": 1080}
    )
    
    # 注入防检测脚本
    context.add_init_script("""
        Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
    """)
    
    if cookies:
        context.add_cookies(cookies)
    
    page = context.new_page()

    for item in skus:
        sku_id = str(item['sku'])
        print(f"[{datetime.now().strftime('%H:%M:%S')}] 处理 {sku_id} 【{item['name']}】")
        url = f"https://item.jd.com/{sku_id}.html"
        
        try:
            page.goto(url, timeout=30000, wait_until="domcontentloaded")
            time.sleep(2) # 等待页面渲染
            
            # 如果触发了风控页面，重新加载一次
            if "pc-frequent-pro" in page.url:
                page.goto(url, timeout=30000)
                time.sleep(2)

            price_text = page.locator(".price").first.inner_text(timeout=5000)
            price = float(''.join(c for c in price_text if c.isdigit() or c == '.'))
            
            print(f"  -> 🎉 成功获取价格: ¥{price}")
            
            if sku_id not in data:
                data[sku_id] = {"records": []}
                
            records = data[sku_id].get("records", [])
            records = [r for r in records if r.get('date') != today]
            records.append({
                "date": today,
                "list_price": price,
                "final_price": price,
                "coupon": 0,
                "market_price": price
            })
            data[sku_id]["records"] = records
            
        except Exception as e:
            print(f"  -> ❌ 抓取失败: 页面未找到价格元素或加载超时")
            
        time.sleep(2)

    browser.close()

with open(DATA_FILE, 'w', encoding='utf-8') as f:
    json.dump(data, f, ensure_ascii=False, indent=2)

print("完成，数据已写入 data/prices.json")
