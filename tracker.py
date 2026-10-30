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

# 读取 Cookie
cookie_str = os.environ.get("JD_COOKIE", "").strip()
if not cookie_str:
    cookie_str = config.get('cookie', '').strip()

# 伪装成京东 App 的请求头
headers = {
    "User-Agent": "JD4iPhone/167169 (iPhone; iOS 13.4.1; Scale/3.00)",
    "Cookie": cookie_str,
    "Accept": "*/*",
    "Connection": "keep-alive"
}

def fetch_price(sku_id):
    # 使用京东 App 端商品详情接口
    url = "https://api.m.jd.com/client.action"
    params = {
        "functionId": "wareBusiness",
        "appid": "wareBusiness",
        "body": json.dumps({"skuId": str(sku_id), "cat": ["10", "20", "30"]}),
        "client": "apple",
        "clientVersion": "13.0.0",
        "networkType": "wifi",
    }
    
    try:
        res = requests.get(url, headers=headers, params=params, timeout=10, verify=False)
        res_json = res.json()
        
        # 尝试提取价格
        price_info = None
        if "price" in res_json and "p" in res_json["price"]:
            price_info = res_json["price"]["p"]
        elif "price" in res_json and "price" in res_json["price"]:
            price_info = res_json["price"]["price"]
            
        if price_info:
            return float(price_info)
        return None
    except Exception as e:
        return None

# 读取旧数据
if os.path.exists(DATA_FILE):
    with open(DATA_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)
else:
    data = {}

today = datetime.now().strftime('%Y-%m-%d')

print("开始通过京东接口抓取价格...")
for item in skus:
    sku_id = str(item['sku'])
    print(f"[{datetime.now().strftime('%H:%M:%S')}] 处理 {sku_id} 【{item['name']}】")
    
    price = fetch_price(sku_id)
    if price:
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
        print(f"  -> ❌ 抓取失败：接口返回空数据 (Cookie 失效或被风控)")
    
    time.sleep(2)

with open(DATA_FILE, 'w', encoding='utf-8') as f:
    json.dump(data, f, ensure_ascii=False, indent=2)

print("完成，数据已写入 data/prices.json")
