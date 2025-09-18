import requests
import pandas as pd
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
import io
import os # 引入 os 模組來讀取環境變數

# --- 【圖片生成模組】 ---
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm

# --- 【GitHub Actions 環境】: 使用 os.getenv 讀取 Secrets ---
# 將 Colab 的 userdata.get 改為 GitHub Actions 的標準做法
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TARGET_CHAT_ID = os.getenv("TELEGRAM_MY_CHAT_ID") # 根據 GitHub Actions 的習慣命名


# === 加入詳細的除錯訊息 ===
print("=== 環境變數除錯資訊 ===")
print(f"TELEGRAM_BOT_TOKEN 是否存在: {'是' if TELEGRAM_BOT_TOKEN else '否'}")
print(f"TELEGRAM_CHAT_ID 是否存在: {'是' if TARGET_CHAT_ID else '否'}")

# 顯示部分值（不暴露完整 token）
if TELEGRAM_BOT_TOKEN:
    print(f"Token 長度: {len(TELEGRAM_BOT_TOKEN)}")
    print(f"Token 前10字元: {TELEGRAM_BOT_TOKEN[:10]}...")
else:
    print("TELEGRAM_BOT_TOKEN 為空或未設定")

if TARGET_CHAT_ID:
    print(f"Chat ID: {TARGET_CHAT_ID}")
else:
    print("TELEGRAM_TEST_CHAT_ID 為空或未設定")

print("=== 除錯資訊結束 ===\n")


# --- 數據抓取相關設定 (只保留關鍵字用於篩選) ---
TARGET_KEYWORDS = {
    '消費者物價指數 (CPI)', '個人消費支出 (PCE)', '生產者物價指数 (PPI)',
    '初領失業金人數', '初請失業金人數', '非農就業報告',
    '失業率', '零售銷售', '個人支出', '國內生產毛額 (GDP)',
    'FOMC', 'ISM製造業PMI', 'ISM非製造業PMI',
    '核心消費價格指數', '居民消費價格指數', '持續申請失業救濟人數',
    '原油庫存', '利率決議',
    '核心零售銷售', '庫欣原油庫存',	'製造業PMI', '服務業PMI', '新屋銷售', '國內生產總值(GDP)'
}


def create_table_image(df):
    """將 DataFrame 轉換為一張精美的圖片"""
    font_path = None
    # 在 Linux 環境 (GitHub Actions 預設) 中，需要確保字體存在
    # 可以在 workflow 中安裝字體，或使用 matplotlib 預設字體
    for font in fm.findSystemFonts(fontpaths=None, fontext='ttf'):
        if 'NotoSansCJK' in font or 'Noto Sans CJK' in font:
            font_path = font
            break
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
    the_table.set_fontsize(40)
    for (row, col), cell in the_table.get_celld().items():
        cell.set_edgecolor(bg_color)
        cell.set_height(0.04)
        if row == 0:
            cell.set_facecolor(header_color)
            cell.set_text_props(fontproperties=prop, color=text_color, weight='bold', ha='left', va='center', size=24)
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
        # 修改成功訊息，使其更通用
        print(f"\n圖片已成功發送到 Telegram (ID: {TARGET_CHAT_ID})！")
    except requests.exceptions.RequestException as e:
        print(f"\n發送圖片到 Telegram 失敗: {e}")
        if e.response is not None:
            print(f"錯誤內容: {e.response.text}")


def get_investing_calendar_data():
    """從 Investing.com 獲取並篩選財經日曆數據"""
    print("步驟 1/2: 從 Investing.com 獲取指定的日曆事件...")
    api_url = "https://hk.investing.com/economic-calendar/Service/getCalendarFilteredData"
    headers = {"User-Agent": "Mozilla/5.0", "Referer": "https://hk.investing.com/economic-calendar/", "X-Requested-With": "XMLHttpRequest"}
    today = datetime.now()
    start_date, end_date = today - timedelta(days=7), today + timedelta(days=7)
    payload = {
        "country[]": "5",
        "importance[]": ["2", "3"],
        "dateFrom": start_date.strftime('%Y-%m-%d'),
        "dateTo": end_date.strftime('%Y-%m-%d'),
        "timeZone": "55"
    }
    try:
        response = requests.post(api_url, data=payload, headers=headers)
        response.raise_for_status()
        html_content = response.json().get('data', '')
        if not html_content:
            return pd.DataFrame()

        soup = BeautifulSoup(html_content, 'lxml')
        results = []
        for row in soup.find_all('tr', class_='js-event-item'):
            event_name_tag = row.find('td', class_='event')
            if not event_name_tag:
                continue
            event_name = event_name_tag.text.strip()
            if any(keyword in event_name for keyword in TARGET_KEYWORDS):
                actual = (row.find('td', class_='act').text.strip() if row.find('td', 'act') else '').replace('\xa0', '')
                forecast = (row.find('td', class_='fore').text.strip() if row.find('td', 'fore') else '').replace('\xa0', '')
                previous = (row.find('td', class_='prev').text.strip() if row.find('td', 'prev') else '').replace('\xa0', '')
                event_timestamp = row.get('data-event-datetime', '').replace('/', '-')
                dt_obj = datetime.strptime(event_timestamp, '%Y-%m-%d %H:%M:%S')
                event_date_str = f"{dt_obj.month}/{dt_obj.day}"

                results.append({
                    '日期': event_date_str,
                    '經濟數據': event_name,
                    '實際': actual or '---',
                    '預估': forecast or '---',
                    '前期': previous or '---'
                })
        return pd.DataFrame(results)
    except Exception as e:
        print(f"從 Investing.com 獲取數據時出錯: {e}")
        return pd.DataFrame()


def main():
    final_df = get_investing_calendar_data()
    if final_df.empty:
        message = "在指定的時間範圍內，未找到您指定的任何經濟數據。"
        print(message)
        if TELEGRAM_BOT_TOKEN and TARGET_CHAT_ID:
            requests.post(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
                          data={'chat_id': TARGET_CHAT_ID, 'text': message})
        return

    print("\n步驟 2/2: 數據已獲取，準備生成圖片...")
    today = datetime.now()
    start_date, end_date = today - timedelta(days=7), today + timedelta(days=7)

    # --- 修改 Telegram 訊息標題，使其更適合自動化腳本 ---
    # 移除了 "Colab 測試訊息" 的標頭
    title_part = f"美國核心經濟數據 ({start_date.strftime('%Y-%m-%d')} 至 {end_date.strftime('%Y-%m-%d')})\n"
    source_part = "by 美股菜雞實驗室 數據來源: Investing.com"
    image_caption = f"{title_part}{source_part}"

    column_order = ['日期', '經濟數據', '實際', '預估', '前期']
    df_for_display_sorted = final_df[column_order]

    print("替換報告顯示文字：同比 -> 年增率, 月環比 -> 月增率,  季度環比 -> 季增率")
    df_for_display_sorted['經濟數據'] = df_for_display_sorted['經濟數據'].str.replace('(同比)', '(年增率)', regex=False)
    df_for_display_sorted['經濟數據'] = df_for_display_sorted['經濟數據'].str.replace('(月環比)', '(月增率)', regex=False)

    print("\n正在生成數據圖片...")
    table_image_buffer = create_table_image(df_for_display_sorted)

    print("正在發送圖片到 Telegram...")
    send_image_to_telegram(table_image_buffer, image_caption)

if __name__ == "__main__":
    main()
