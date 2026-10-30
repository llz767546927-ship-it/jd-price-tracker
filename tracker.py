import os
import json
import time
import requests
import urllib3
from datetime import datetime

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

CONFIG_FILE = 'config.json'
DATA_FILE = 'data/prices.json'

with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
    config = json.load(f)
skus = config.get('skus', [])

# 优先从 GitHub Secrets 读取 Cookie
cookie_str = os.environ.get("JD_COOKIE", "").strip()
if not cookie_str:
    cookie_str = config.get('cookie', '').strip()

# 伪装成手机京东 App 的请求头
headers = {
    "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 JD4iPhone/12.0.0",
    "Cookie": cookie_str,
    "Accept": "application/json",
    "Content-Type": "application/x-www-form-urlencoded"
}

def fetch_price(sku_id):
    # 京东 H5/小程序获取商品详情的接口
    url = f"https://item.m.jd.com/ware/detail.json?wareId={sku_id}"
    try:
        res = requests.get(url, headers=headers, timeout=10, verify=False)
        res_json = res.json()
        
        # 尝试提取价格
        if "price" in res_json and "p" in res_json["price"]:
            return float(res_json["price"]["p"])
        elif "price" in res_json:
            return float(res_json["price"])
        return None
    except Exception as e:
        print(f"  -> 请求异常: {e}")
        return None

if os.path.exists(DATA_FILE):
    with open(DATA_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)
else:
    data = {}

today = datetime.now().strftime('%Y-%m-%d')

print("开始通过手机版接口抓取价格...")
for item in skus:
    sku_id = str(item['sku'])
    print(f"[{datetime.now().strftime('%H:%M:%S')}] 处理 {sku_id} 【{item['name']}】")
    
    price = fetch_price(sku_id)
    if price and price > 0:
        print(f"  -> 🎉 成功获取真实价格: ¥{price}")
        
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
        print(f"  - ❌ 抓取失败：接口返回了空数据。")
    
    time.sleep(1.5)

with open(DATA_FILE, 'w', encoding='utf-8') as f:
    json.dump(data, f, ensure_ascii=False, indent=2)

print("完成，数据已写入 data/prices.json")
