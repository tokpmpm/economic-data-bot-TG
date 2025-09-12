import requests
import pandas as pd
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
import io
import os # <--- 【修改點 1】: 匯入 os 模組

# --- 【圖片生成模組】 ---
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm

# --- 【GitHub Actions 環境】: 使用 os.getenv 讀取 Secrets ---
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
FRED_API_KEY = os.getenv("FRED_API_KEY")
TARGET_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# --- 數據抓取相關設定 (無需修改) ---
# ... (這裡的 TARGET_KEYWORDS 和 SERIES_MAPPING 內容保持不變，為節省空間故省略) ...
TARGET_KEYWORDS = {
    '消費者物價指數 (CPI)', '個人消費支出 (PCE)', '生產者物價指数 (PPI)',
    '初領失業金人數', '初請失業金人數', '非農就業報告',
    '失業率', '零售銷售', '個人支出', '國內生產毛額 (GDP)',
    'FOMC', 'ISM製造業PMI', 'ISM非製造業PMI',
    '核心消費價格指數', '居民消費價格指數', '持續申請失業救濟人數',
    '原油庫存', '利率決議'
}
SERIES_MAPPING = {
    'CPI YoY': {'id': 'CPIAUCSL', 'calc': 'yoy', 'unit': '%', 'investing_kw': '消費價格指數 (同比)'},
    'CPI MoM': {'id': 'CPIAUCSL', 'calc': 'mom', 'unit': '%', 'investing_kw': '消費價格指數 (月環比)'},
    'Core CPI YoY': {'id': 'CPILFESL', 'calc': 'yoy', 'unit': '%', 'investing_kw': '核心消費價格指數 (同比)'},
    'Core CPI MoM': {'id': 'CPILFESL', 'calc': 'mom', 'unit': '%', 'investing_kw': '核心消費價格指數 (月環比)'},
    'Initial Jobless Claims': {'id': 'ICSA', 'calc': 'latest', 'unit': 'K', 'investing_kw': '初請失業金人數'},
    'Continuing Claims': {'id': 'CCSA', 'calc': 'latest', 'unit': 'K', 'investing_kw': '持續申請失業救濟人數'},
    'NFP': {'id': 'PAYEMS', 'calc': 'level_change', 'unit': 'K', 'investing_kw': '非農就業報告'},
    'Unemployment': {'id': 'UNRATE', 'calc': 'latest', 'unit': '%', 'investing_kw': '失業率'},
    'PCE': {'id': 'PCEPI', 'calc': 'yoy', 'unit': '%', 'investing_kw': '個人消費支出 (PCE)'},
    'PPI': {'id': 'PPIACO', 'calc': 'yoy', 'unit': '%', 'investing_kw': '生產者物價指数 (PPI)'},
    'Retail Sales': {'id': 'RSXFS', 'calc': 'mom', 'unit': '%', 'investing_kw': '零售銷售'},
    'Personal Spending': {'id': 'PCEC96', 'calc': 'mom', 'unit': '%', 'investing_kw': '個人支出'},
    'GDP': {'id': 'A191RL1Q225SBEA', 'calc': 'latest', 'unit': '%', 'investing_kw': '國內生產毛額 (GDP)'},
    'FOMC': {'id': 'DFEDTARU', 'calc': 'latest', 'unit': '%', 'investing_kw': '利率決議'},
    'ISM Mfg': {'id': 'NAPM', 'calc': 'latest', 'unit': '', 'investing_kw': 'ISM製造業PMI'},
    'ISM Non-Mfg': {'id': 'NMFCI', 'calc': 'latest', 'unit': '', 'investing_kw': 'ISM非製造業PMI'},
    'Crude Oil': {'id': 'WCRSTUS1', 'calc': 'level_change', 'unit': 'K', 'investing_kw': '原油庫存'},
}

def create_table_image(df):
    """將 DataFrame 轉換為一張精美的圖片"""
    # 這段尋找字體的程式碼在 GitHub Actions 中也能正常工作，因為我們會在 workflow 中安裝字體
    font_path = None
    # 優先尋找 Noto Sans CJK，這是我們在 GitHub Actions 中安裝的字體
    for font in fm.findSystemFonts(fontpaths=None, fontext='ttf'):
        if 'NotoSansCJK' in font or 'Noto Sans CJK' in font:
            font_path = font
            break
    # 如果找不到，使用 matplotlib 的預設無襯線字體作為備案
    if not font_path:
        print("警告：未找到 NotoSansCJK 字體，將使用預設字體。")
        font_path = fm.findfont(fm.FontProperties(family='sans-serif'))

    prop = fm.FontProperties(fname=font_path)
    
    num_rows = len(df)
    fig_height = max(10, num_rows * 0.3) 
    fig, ax = plt.subplots(figsize=(8, fig_height))
    ax.axis('off')

    bg_color = '#212121'
    text_color = '#FFFFFF'
    header_color = '#424242'
    fig.patch.set_facecolor(bg_color)

    the_table = ax.table(cellText=df.values,
                         colLabels=df.columns,
                         loc='center',
                         cellLoc='left',
                         colWidths=[0.12, 0.45, 0.13, 0.13, 0.13]) 

    the_table.auto_set_font_size(False)
    the_table.set_fontsize(40) # 數據字體
    
    for (row, col), cell in the_table.get_celld().items():
        cell.set_edgecolor(bg_color)
        cell.set_height(0.04)
        if row == 0:
            cell.set_facecolor(header_color)
            cell.set_text_props(fontproperties=prop, color=text_color, weight='bold', ha='left', va='center', size=24) # 表頭字體
        else:
            cell.set_facecolor(bg_color)
            cell.set_text_props(fontproperties=prop, color=text_color, ha='left', va='center')
            if col > 1:
                cell.set_text_props(fontproperties=prop, color=text_color, ha='right', va='center')

    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=200, bbox_inches='tight', facecolor=bg_color)
    buf.seek(0)
    plt.close(fig)
    return buf

# --- send_image_to_telegram 和其他數據處理函數保持不變 ---
# ... (這裡的函數內容保持不變，為節省空間故省略) ...
def send_image_to_telegram(image_buffer, caption):
    """將圖片和標題發送到 Telegram"""
    if not TELEGRAM_BOT_TOKEN or not TARGET_CHAT_ID:
        print("Telegram 的 Token 或目標 Chat ID 未設定，跳過發送。")
        return

    api_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto"
    payload = {'chat_id': TARGET_CHAT_ID, 'caption': caption}
    files = {'photo': ('economic_data.png', image_buffer, 'image/png')}

    try:
        response = requests.post(api_url, data=payload, files=files)
        response.raise_for_status()
        print(f"\n圖片已成功發送到 Telegram (ID: {TARGET_CHAT_ID})！")
    except requests.exceptions.RequestException as e:
        print(f"\n發送圖片到 Telegram 失敗: {e}")
        if e.response is not None:
            print(f"錯誤內容: {e.response.text}")
            
def get_filtered_calendar_data():
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
                actual = (row.find('td', class_='act').text.strip() if row.find('td', 'act') else '').replace('\xa0', '')
                forecast = (row.find('td', class_='fore').text.strip() if row.find('td', 'fore') else '').replace('\xa0', '')
                previous = (row.find('td', class_='prev').text.strip() if row.find('td', 'prev') else '').replace('\xa0', '')
                event_timestamp = row.get('data-event-datetime', '').replace('/', '-')
                dt_obj = datetime.strptime(event_timestamp, '%Y-%m-%d %H:%M:%S')
                event_date_str = f"{dt_obj.month}/{dt_obj.day}"
                results.append({'日期': event_date_str, '經濟數據': event_name, '實際': actual or '---', '預計': forecast, '前期': previous or '---'})
        return pd.DataFrame(results)
    except Exception as e:
        print(f"從 Investing.com 獲取數據時出錯: {e}")
        return pd.DataFrame()

def get_fred_data(series_id, calc_method):
    base_url = "https://api.stlouisfed.org/fred/series/observations"
    limit = 3
    if calc_method == 'yoy': limit = 15
    if calc_method == 'mom': limit = 4
    params = {'series_id': series_id, 'api_key': FRED_API_KEY, 'file_type': 'json', 'sort_order': 'desc', 'limit': limit}
    try:
        response = requests.get(base_url, params=params)
        response.raise_for_status()
        data = response.json().get('observations', [])
        if len(data) < 2: return None
        for item in data: item['value'] = float(item['value']) if item['value'] != '.' else None
        info_list = [v for v in SERIES_MAPPING.values() if v['id'] == series_id]
        info = next((item for item in info_list if item['calc'] == calc_method), info_list[0])
        actual_prev_value = None
        if calc_method == 'yoy' and len(data) > 12: actual_prev_value = data[12]['value']
        elif calc_method in ['mom', 'level_change']: actual_prev_value = data[1]['value']
        prev_prev_value = None
        if calc_method == 'yoy' and len(data) > 13: prev_prev_value = data[13]['value']
        elif calc_method in ['mom', 'level_change'] and len(data) > 2: prev_prev_value = data[2]['value']
        actual_display = format_fred_value(data[0]['value'], actual_prev_value, info)
        prev_display = format_fred_value(data[1]['value'], prev_prev_value, info)
        return {'Actual': actual_display, 'Previous': prev_display}
    except Exception:
        return None

def format_fred_value(current, previous, info):
    if current is None: return "暫無"
    calc, unit = info['calc'], info['unit']
    if calc == 'latest':
        val = current / 1000 if unit == 'K' else current
        if unit == 'K': return f"{val:.0f}{unit}"
        if '%' in unit: return f"{val:.2f}{unit}"
        return f"{val:.1f}"
    if previous is None or previous == 0: return "N/A"
    if calc in ['yoy', 'mom']: return f"{((current / previous) - 1) * 100:.1f}{unit}"
    elif calc == 'level_change': 
        change = current - previous
        return f"{change:.0f}{unit}" if unit == 'K' else f"{change:.0f}"
    return "N/A"

def main():
    calendar_df = get_filtered_calendar_data()
    if calendar_df.empty:
        message = "在指定的時間範圍內，未找到您指定的任何經濟數據。"
        print(message)
        # 在自動化腳本中，如果沒數據就發送一則文字訊息通知
        if TELEGRAM_BOT_TOKEN and TARGET_CHAT_ID:
            requests.post(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
                          data={'chat_id': TARGET_CHAT_ID, 'text': message})
        return
    
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

    today = datetime.now()
    for index, row in calendar_df.iterrows():
        if pd.notna(row['_fred_id']):
            date_str = row['日期']
            event_month = int(date_str.split('/')[0])
            year = today.year if event_month <= today.month else today.year - 1
            event_date = datetime.strptime(f"{year}/{date_str}", '%Y/%m/%d')
            if event_date.date() > today.date():
                continue
            fred_values = get_fred_data(row['_fred_id'], row['_fred_calc'])
            if fred_values:
                calendar_df.at[index, '實際'] = fred_values['Actual']
                calendar_df.at[index, '前期'] = fred_values['Previous']
    
    final_df = calendar_df.drop(columns=['_fred_id', '_fred_calc']).drop_duplicates().reset_index(drop=True)
    
    start_date, end_date = today - timedelta(days=7), today + timedelta(days=7)
    
    # <--- 【修改點 2】: 修改 Telegram 訊息標題，使其更通用 ---
    header = "--- 🤖 GitHub Actions 自動化報告 🤖 ---\n"
    title_part = f"--- 美國核心經濟數據 ({start_date.strftime('%Y-%m-%d')} 至 {end_date.strftime('%Y-%m-%d')}) ---\n"
    source_part = "數據來源: Investing.com + FRED"
    image_caption = f"{header}{title_part}{source_part}"

    df_for_display = final_df.copy()
    column_order = ['日期', '經濟數據', '實際', '預計', '前期']
    df_for_display_sorted = df_for_display[[col for col in column_order if col in df_for_display.columns]]
    
    print("\n正在生成數據圖片...")
    table_image_buffer = create_table_image(df_for_display_sorted)
    
    print("正在發送圖片到 Telegram...")
    send_image_to_telegram(table_image_buffer, image_caption)

if __name__ == "__main__":
    main()
