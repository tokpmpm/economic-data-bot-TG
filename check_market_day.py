import pandas_market_calendars as mcal
from datetime import datetime, timedelta
import pytz
import os

def check_if_yesterday_was_trading_day():
    """
    檢查美東時間的 "昨天" 是否為 NYSE 的交易日。
    """
    # 獲取紐約證券交易所 (NYSE) 的市場日曆
    nyse = mcal.get_calendar('NYSE')

    # 設定時區為美東時間，以準確計算 "今天" 和 "昨天"
    tz = pytz.timezone('America/New_York')
    today_in_ny = datetime.now(tz).date()
    yesterday_in_ny = today_in_ny - timedelta(days=1)

    # 獲取最近的交易日列表
    # 查詢一個小範圍（例如過去7天）以確保日曆數據是有效的
    schedule = nyse.schedule(start_date=yesterday_in_ny - timedelta(days=7), end_date=today_in_ny)
    trading_days = schedule.index.date.tolist()

    # 判斷昨天是否在交易日列表中
    if yesterday_in_ny in trading_days:
        print(f"✅ {yesterday_in_ny} 是 NYSE 的交易日。腳本將繼續執行。")
        return True
    else:
        print(f"❌ {yesterday_in_ny} 不是 NYSE 的交易日 (週末或假日)。將跳過本次執行。")
        return False

def set_github_output(name, value):
    """
    設定 GitHub Actions 的輸出變數，用於步驟間的通訊。
    """
    # GITHUB_OUTPUT 是 Actions Runner 提供的環境變數
    if 'GITHUB_OUTPUT' in os.environ:
        with open(os.environ['GITHUB_OUTPUT'], 'a') as f:
            # 寫入 'key=value' 格式的字串
            print(f"{name}={value}", file=f)
    else:
        # 如果在本機執行，只印出結果
        print(f"本機環境，模擬輸出: {name}={value}")

if __name__ == "__main__":
    should_run = check_if_yesterday_was_trading_day()
    # 將檢查結果 (true/false) 設為 GitHub Actions 的輸出變數
    set_github_output('should_run', str(should_run).lower())
