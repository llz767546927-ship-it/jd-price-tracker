import os
import json
import time
from datetime import datetime
from curl_cffi import requests  # 核心就在这里，引进了伪装库

CONFIG_FILE = 'config.json'
DATA_FILE = 'data/prices.json'

# 读取配置
with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
    config = json.load(f)

# 优先从环境变量读取（GitHub 用），其次读配置文件（本地用）
cookie_str = os.environ.get("JD_COOKIE", "").strip()
if not cookie_str:
    cookie_str = config.get('cookie', '').strip()

skus = config.get('skus', [])

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9",
    "Cookie": cookie_str,
    "Referer": "https://item.jd.com/"
}

def fetch_price(sku_id):
    url = f"https://p.3.cn/prices/mgets?skuIds=J_{sku_id}&type=1"
    try:
        # impersonate="chrome120" 是灵魂，假装自己是真实的 Chrome 浏览器
        res = requests.get(url, headers=headers, impersonate="chrome120", timeout=15)
        data = res.json()
        if data and len(data) > 0:
            return float(data[0].get('p', 0))
        return None
    except Exception as e:
        print(f"  -> 接口请求异常: {e}")
        return None

# 读取历史数据
if os.path.exists(DATA_FILE):
    with open(DATA_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)
else:
    data = {}

today = datetime.now().strftime('%Y-%m-%d')

print("开始通过超级浏览器指纹抓取价格...")
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
        print(f"  -> ❌ 抓取失败：接口返回空数据")
    
    time.sleep(2)

# 保存数据
with open(DATA_FILE, 'w', encoding='utf-8') as f:
    json.dump(data, f, ensure_ascii=False, indent=2)

print("完成，数据已写入 data/prices.json")
