import os
import json
import time
import re
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

print("正在启动伪装浏览器抓取，请稍候...")
with sync_playwright() as p:
    # 使用 channel="chrome" 强制调用服务器上的真实 Chrome，并加上深度防检测参数
    browser = p.chromium.launch(
        headless=True, 
        channel="chrome",
        args=[
            '--no-sandbox', 
            '--disable-setuid-sandbox',
            '--disable-blink-features=AutomationControlled',
            '--disable-infobars',
            '--window-size=1920,1080'
        ]
    )
    
    context = browser.new_context(
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        viewport={"width": 1920, "height": 1080},
        device_scale_factor=1,
        is_mobile=False,
        has_touch=False
    )
    
    # 注入终极防检测脚本（抹除 webdriver 痕迹）
    context.add_init_script("""
        Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
        window.navigator.chrome = { runtime: {} };
        Object.defineProperty(navigator, 'languages', { get: () => ['zh-CN', 'zh'] });
        Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
    """)
    
    if cookies:
        context.add_cookies(cookies)
    
    page = context.new_page()

    for item in skus:
        sku_id = str(item['sku'])
        print(f"[{datetime.now().strftime('%H:%M:%S')}] 处理 {sku_id} 【{item['name']}】")
        url = f"https://item.jd.com/{sku_id}.html"
        
        try:
            # 使用 networkidle 等待所有网络请求彻底结束，确保价格渲染完毕
            page.goto(url, timeout=60000, wait_until="networkidle")
            time.sleep(3) 
            
            # 如果遇到风控拦截页，尝试重新加载一次
            if "pc-frequent-pro" in page.url or "risk_handler" in page.url:
                print("  -> 触发拦截，尝试重新加载...")
                page.goto(url, timeout=60000, wait_until="domcontentloaded")
                time.sleep(3)

            # 多维度获取价格
            price_text = ""
            try:
                # 方案 A：常规 Web 端价格类
                price_text = page.locator(".price").first.inner_text(timeout=8000)
            except:
                try:
                    # 方案 B：京东移动端/特殊活动页面价格类
                    price_text = page.locator(".p-price .price").first.inner_text(timeout=5000)
                except:
                    # 方案 C：直接扒网页源码用正则强搜
                    content = page.content()
                    match = re.search(r'"p":"(\d+\.\d+)"', content)
                    if match:
                        price_text = match.group(1)

            if price_text:
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
            else:
                print(f"  -> ❌ 抓取失败：页面未找到价格元素")
            
        except Exception as e:
            print(f"  -> ❌ 抓取失败: 页面加载超时或异常")
            
        time.sleep(2)

    browser.close()

# 保存数据
with open(DATA_FILE, 'w', encoding='utf-8') as f:
    json.dump(data, f, ensure_ascii=False, indent=2)

print("完成，数据已写入 data/prices.json")
