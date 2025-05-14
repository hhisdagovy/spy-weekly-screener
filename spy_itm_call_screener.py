import yfinance as yf
import pandas as pd
from datetime import datetime
import os
from rich.console import Console
from rich.table import Table
from ta.volume import MFIIndicator
import requests
import matplotlib.pyplot as plt
from matplotlib.dates import DateFormatter

def generate_spy_chart(): #CHARTING
    df = yf.download("SPY", interval="5m", period="1d", progress=False)

    if df.empty:
        return None

    # Calculate rolling VWAP with a 7-period window
    typical_price = (df['High'] + df['Low'] + df['Close']) / 3
    df['VWAP'] = (typical_price * df['Volume']).rolling(window=7).sum() / df['Volume'].rolling(window=7).sum()

    # Calculate ATR(20)
    high_low = df['High'] - df['Low']
    high_close = (df['High'] - df['Close'].shift()).abs()
    low_close = (df['Low'] - df['Close'].shift()).abs()
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    df['ATR'] = tr.rolling(window=20).mean()

    # VWAP Bands using Mult = 4, ATR Multiplier = 0.2
    band_offset = df['ATR'] * 0.2 * 4
    df['UpperBand'] = df['VWAP'] + band_offset
    df['LowerBand'] = df['VWAP'] - band_offset

    # Plot
    fig, ax = plt.subplots(figsize=(10, 4))
    ax.plot(df.index, df['Close'], label='SPY Price', linewidth=1.5)
    ax.plot(df.index, df['VWAP'], label='VWAP (7-period)', linestyle='--')
    ax.plot(df.index, df['UpperBand'], label='Upper VWAP Band', linestyle=':', linewidth=1)
    ax.plot(df.index, df['LowerBand'], label='Lower VWAP Band', linestyle=':', linewidth=1)

    ax.set_title('SPY Price with VWAP Bands')
    ax.set_ylabel('Price')
    ax.legend()
    ax.grid(True)
    ax.xaxis.set_major_formatter(DateFormatter("%H:%M"))

    plt.tight_layout()
    plt.savefig('spy_chart.png')
    plt.close()
    return 'spy_chart.png'

def send_telegram_image(caption, image_path): #TELLY ALERTS
    token = '7500825997:AAEXiLITgtjBTiehSeRti6RctKmVVGddoNg'
    chat_id = '-1002532416599'
    url = f'https://api.telegram.org/bot{token}/sendPhoto'
    with open(image_path, 'rb') as photo:
        response = requests.post(url, data={'chat_id': chat_id, 'caption': caption}, files={'photo': photo})
        if response.ok:
            print("✅ Chart image sent.")
        else:
            print(f"❌ Failed to send image: {response.text}")

def send_telegram_alert(message): #TELLY ALERTS MESSAGE
    token = '7500825997:AAEXiLITgtjBTiehSeRti6RctKmVVGddoNg'
    chat_id = '-1002532416599'
    url = f'https://api.telegram.org/bot{token}/sendMessage'
    payload = {'chat_id': chat_id, 'text': message}
    try:
        response = requests.post(url, data=payload)
        response.raise_for_status()
        print(f"✅ Telegram alert sent: {message}")
    except requests.exceptions.RequestException as e:
        print(f"❌ Telegram alert failed: {e}")
        print(f"🔎 Response: {response.text}")

def clear_terminal(): 
    os.system('cls' if os.name == 'nt' else 'clear')

def get_vwap_mfi(): #VWAP BANDS INSTRUCTIONS
    df = yf.download("SPY", interval="5m", period="1d", progress=False)

    if df.empty or len(df) < 20:
        return None, None, None, None, None

    high = df['High'].squeeze()
    low = df['Low'].squeeze()
    close = df['Close'].squeeze()
    volume = df['Volume'].squeeze()

    # Calculate rolling VWAP with a 7-period window
    typical_price = (high + low + close) / 3
    vwap = (typical_price * volume).rolling(window=7).sum() / volume.rolling(window=7).sum()

    # Calculate ATR(20)
    high_low = high - low
    high_close = (high - close.shift()).abs()
    low_close = (low - close.shift()).abs()
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    atr = tr.rolling(window=20).mean()

    # Calculate VWAP Bands
    band_offset = atr * 0.2 * 4
    upper_band = vwap + band_offset
    lower_band = vwap - band_offset

    # Calculate MFI
    mfi = MFIIndicator(high=high, low=low, close=close, volume=volume).money_flow_index()

    latest = df.index[-1]
    return float(close[latest]), float(vwap[latest]), float(upper_band[latest]), float(lower_band[latest]), float(mfi[latest])

def main():
    clear_terminal()
    console = Console()
    console.print(f"[bold cyan]🔍 SPY Weekly ITM Call Screener [TEST MODE][/bold cyan]")
    console.print(f"[bold]📅 {datetime.now().strftime('%A, %B %d, %Y %I:%M %p')}[/bold]\n")

    try:
        # 🔧 Test data — Reversal setup (Price < Lower Band, MFI < 30)
        spy_price, vwap, upper_band, lower_band, mfi = 579, 585, 589, 581, 25

        console.print(f"[green]📈 TEST → SPY Price: ${spy_price:.2f} | VWAP: ${vwap:.2f} | MFI: {mfi:.2f}[/green]")

        # Buy Signal Logic
        momentum_buy = spy_price > vwap and mfi > 50
        reversal_buy = spy_price < lower_band and mfi < 30
        buy_signal = momentum_buy or reversal_buy
        signal_type = "Momentum Breakout" if momentum_buy else "Reversal Bounce" if reversal_buy else None

        if buy_signal:
            console.print(f"[bold green]✅ Test Buy Signal Triggered: {signal_type}[/bold green]\n")
        else:
            console.print("[bold red]❌ No Buy Signal Triggered[/bold red]\n")

        # Mock contract for testing (no API calls)
        contract_symbol = "SPYTESTCALL"
        strike = 580.00
        exp_date = "2025-05-17"
        premium = 2.15
        volume = 420
        option_type = "Call"

        # Define reason
        reason = ""
        if momentum_buy:
            reason = "📈 Price is above VWAP and MFI > 50 — indicating strong buying momentum."
        elif reversal_buy:
            reason = "🔁 Price is below lower VWAP band and MFI < 30 — potential oversold reversal."

        alert = (
            f"🚨 SPY Buy Signal [TEST MODE: {signal_type}]\n\n"
            f"{reason}\n\n"
            f"Price: ${spy_price:.2f}\n"
            f"VWAP: ${vwap:.2f}\n"
            f"MFI: {mfi:.2f}\n\n"
            f"Suggested Contract:\n"
            f"Ticker: SPY\n"
            f"C/P: {option_type}\n"
            f"Strike Price: ${strike:.2f}\n"
            f"Premium: ${premium:.2f}\n"
            f"Volume: {int(volume)}\n"
            f"Exp: {exp_date}"
        )

        chart_path = generate_spy_chart()
        send_telegram_image(alert, chart_path)

    except Exception as e:
        console.print(f"[red]❌ Error: {e}[/red]")
