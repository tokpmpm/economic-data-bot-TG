import requests
import pandas as pd
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
from tabulate import tabulate
import os  # <--- 新增導入 os 模組

# --- 從環境變數讀取 Secrets (更安全) ---
# GitHub Actions 會在執行時將您設定的 Secrets 注入為環境變數
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
FRED_API_KEY = os.environ.get("FRED_API_KEY")

# --- 1. 精準定義您想顯示的數據關鍵字 ---
TARGET_KEYWORDS = {
    '消費者物價指數 (CPI)', '個人消費支出 (PCE)', '生產者物價指数 (PPI)',
    '初領失業金人數', '初請失業金人數', '非農就業報告',
    '失業率', '零售銷售', '個人支出', '國內生產毛額 (GDP)',
    'FOMC', 'ISM製造業PMI', 'ISM非製造業PMI'
}

# --- 2. 為需要被 FRED 權威數據覆蓋的指標建立精簡的對照表 ---
SERIES_MAPPING = {
    'CPI': {'id': 'CPIAUCSL', 'calc': 'yoy', 'unit': '%', 'investing_kw': '消費者物價指數 (CPI)'},
    'PCE': {'id': 'PCEPI', 'calc': 'yoy', 'unit': '%', 'investing_kw': '個人消費支出 (PCE)'},
    'PPI': {'id': 'PPIACO', 'calc': 'yoy', 'unit': '%', 'investing_kw': '生產者物價指数 (PPI)'},
    'Jobless Claims': {'id': 'ICSA', 'calc': 'latest', 'unit': 'K', 'investing_kw': '失業金人數'},
    'NFP': {'id': 'PAYEMS', 'calc': 'level_change', 'unit': 'K', 'investing_kw': '非農就業報告'},
    'Unemployment': {'id': 'UNRATE', 'calc': 'latest', 'unit': '%', 'investing_kw': '失業率'},
    'Retail Sales': {'id': 'RSXFS', 'calc': 'mom', 'unit': '%', 'investing_kw': '零售銷售'},
    'Personal Spending': {'id': 'PCEC96', 'calc': 'mom', 'unit': '%', 'investing_kw': '個人支出'},
    'GDP': {'id': 'A191RL1Q225SBEA', 'calc': 'latest', 'unit': '%', 'investing_kw': '國內生產毛額 (GDP)'},
    'FOMC': {'id': 'DFEDTARU', 'calc': 'latest', 'unit': '%', 'investing_kw': 'FOMC'},
    'ISM Mfg': {'id': 'NAPM', 'calc': 'latest', 'unit': '', 'investing_kw': 'ISM製造業PMI'},
    'ISM Non-Mfg': {'id': 'NMFCI', 'calc': 'latest', 'unit': '', 'investing_kw': 'ISM非製造業PMI'},
}

def send_to_telegram(message):
    """將格式化的訊息發送到指定的 Telegram 聊天室"""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("Telegram 的 Token 或 Chat ID 未設定，跳過發送。")
        return
    formatted_message = f"<pre><code>{message}</code></pre>"
    api_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {'chat_id': TELEGRAM_CHAT_ID, 'text': formatted_message, 'parse_mode': 'HTML'}
    try:
        response = requests.post(api_url, json=payload)
        response.raise_for_status()
        print("\n訊息已成功發送到 Telegram！")
    except requests.exceptions.RequestException as e:
        print(f"\n發送訊息到 Telegram 失敗: {e}")

def get_filtered_calendar_data():
    """從 Investing.com 過濾並獲取指定的財經日曆數據"""
    print("步驟 1/3: 從 Investing.com 獲取指定的日曆事件...")
    api_url = "https://hk.investing.com/economic-calendar/Service/getCalendarFilteredData"
    headers = {"User-Agent": "Mozilla/5.0", "Referer": "https://hk.investing.com/economic-calendar/", "X-Requested-With": "XMLHttpRequest"}
    today = datetime.now()
    start_date, end_date = today - timedelta(days=8), today + timedelta(days=8)
    payload = {"country[]": "5", "importance[]": ["2", "3"], "dateFrom": start_date.strftime('%Y-%m-%d'), "dateTo": end_date.strftime('%Y-%m-%d'), "timeZone": "55"}
    try:
        response = requests.post(api_url, data=payload, headers=headers)
        response.raise_for_status()
        html_content = response.json().get('data', '')
        if not html_content: return pd.DataFrame()
        soup = BeautifulSoup(html_content, 'lxml')
        results = []
        for row in soup.find_all('tr', class_='js-event-item'):
            event_name_tag = row.find('td', class_='event')
            if not event_name_tag: continue
            event_name = event_name_tag.text.strip()
            if any(keyword in event_name for keyword in TARGET_KEYWORDS):
                actual = (row.find('td', class_='act').text.strip() if row.find('td', class_='act') else '').replace('\xa0', '')
                forecast = (row.find('td', class_='fore').text.strip() if row.find('td', class_='fore') else '').replace('\xa0', '')
                previous = (row.find('td', class_='prev').text.strip() if row.find('td', class_='prev') else '').replace('\xa0', '')
                event_timestamp = row.get('data-event-datetime', '').replace('/', '-')
                dt_obj = datetime.strptime(event_timestamp, '%Y-%m-%d %H:%M:%S')
                event_date_str = dt_obj.strftime('%m-%d')
                results.append({'日期': event_date_str, '經濟數據': event_name, '實際': actual or '---', '預計': forecast, '前期': previous or '---'})
        return pd.DataFrame(results)
    except Exception as e:
        print(f"從 Investing.com 獲取數據時出錯: {e}")
        return pd.DataFrame()

def get_fred_data(series_id, calc_method):
    """從 FRED 獲取單一指標的權威實際值和前期值"""
    base_url = "https://api.stlouisfed.org/fred/series/observations"
    limit = 3
    if calc_method == 'yoy': limit = 15
    params = {'series_id': series_id, 'api_key': FRED_API_KEY, 'file_type': 'json', 'sort_order': 'desc', 'limit': limit}
    try:
        response = requests.get(base_url, params=params)
        response.raise_for_status()
        data = response.json().get('observations', [])
        if len(data) < 2: return None
        for item in data: item['value'] = float(item['value']) if item['value'] != '.' else None
        info = next(item for item in SERIES_MAPPING.values() if item['id'] == series_id)
        actual_display = format_fred_value(data[0]['value'], data[12]['value'] if calc_method == 'yoy' and len(data) > 12 else data[1]['value'], info)
        prev_display = format_fred_value(data[1]['value'], data[13]['value'] if calc_method == 'yoy' and len(data) > 13 else data[2]['value'], info)
        return {'Actual': actual_display, 'Previous': prev_display}
    except Exception:
        return None

def format_fred_value(current, previous, info):
    """格式化 FRED 數據"""
    if current is None: return "暫無"
    calc, unit = info['calc'], info['unit']
    if calc == 'latest':
        val = current / 1000 if unit == 'K' else current
        return f"{val:.2f}{unit}" if '%' in unit else (f"{val:.0f}{unit}" if unit == 'K' else f"{val:.1f}")
    if previous is None or previous == 0: return "N/A"
    if calc in ['yoy', 'mom']: return f"{((current - previous) / previous) * 100:.1f}{unit}"
    elif calc == 'level_change': return f"{(current - previous):.0f}{unit}"
    return "N/A"

def main():
    """主函數，整合數據並發送"""
    pd.set_option('display.unicode.east_asian_width', True)
    pd.set_option('display.width', 200)

    calendar_df = get_filtered_calendar_data()
    if calendar_df.empty:
        message = "在指定的時間範圍內，未找到您指定的任何經濟數據。"
        print(message)
        send_to_telegram(message)
        return

    print("步驟 2/3: 匹配需要被 FRED 權威數據覆蓋的指標...")
    calendar_df['_fred_id'], calendar_df['_fred_calc'] = None, None
    for index, row in calendar_df.iterrows():
        best_match_key, best_match_len = None, 0
        for key, info in SERIES_MAPPING.items():
            kw = info['investing_kw']
            if kw in row['經濟數據'] and len(kw) > best_match_len:
                best_match_key, best_match_len = key, len(kw)
        if best_match_key:
            info = SERIES_MAPPING[best_match_key]
            calendar_df.at[index, '_fred_id'], calendar_df.at[index, '_fred_calc'] = info['id'], info['calc']

    print("步驟 3/3: 獲取 FRED 數據並覆蓋 (僅限過去和今天的數據)...")
    today = datetime.now()
    for index, row in calendar_df.iterrows():
        if pd.notna(row['_fred_id']):
            date_str = row['日期']
            event_month = int(date_str.split('-')[0])
            year = today.year if event_month <= today.month else today.year - 1
            event_date = datetime.strptime(f"{year}-{date_str}", '%Y-%m-%d')
            if event_date.date() > today.date():
                print(f"  -> 跳過未來事件的 FRED 更新: '{row['經濟數據']}'")
                continue
            print(f"  -> 正在用 FRED 數據更新: '{row['經濟數據']}'")
            fred_values = get_fred_data(row['_fred_id'], row['_fred_calc'])
            if fred_values:
                calendar_df.at[index, '實際'] = fred_values['Actual']
                calendar_df.at[index, '前期'] = fred_values['Previous']
    
    final_df = calendar_df.drop(columns=['_fred_id', '_fred_calc']).drop_duplicates().reset_index(drop=True)
    
    start_date, end_date = today - timedelta(days=7), today + timedelta(days=7)
    
    header = f"--- 美國核心經濟數據 ({start_date.strftime('%Y-%m-%d')} 至 {end_date.strftime('%Y-%m-%d')}) ---"
    source_line = "數據來源: Investing.com (預計值/基礎值) + FRED (權威值覆蓋)"
    
    table_string = tabulate(
        final_df, headers='keys', tablefmt='simple', showindex=False,
        colalign=("left", "left", "right", "right", "right")
    )
    
    full_message = f"{header}\n{source_line}\n{table_string}"

    print("\n" + full_message)
    send_to_telegram(full_message)

if __name__ == "__main__":
    main()
