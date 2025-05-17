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
    console.print(f"[bold cyan]🔍 SPY Weekly ITM Call Screener[/bold cyan]")
    console.print(f"[bold]📅 {datetime.now().strftime('%A, %B %d, %Y %I:%M %p')}[/bold]\n")

    try:
        # Pull real-time SPY data
        spy_price, vwap, upper_band, lower_band, mfi = get_vwap_mfi()

        if spy_price is None:
            console.print("[red]❌ Unable to retrieve VWAP/MFI data.[/red]")
            return

        console.print(f"[green]📈 SPY Price: ${spy_price:.2f} | VWAP: ${vwap:.2f} | MFI: {mfi:.2f}[/green]")

        # Signal logic
        momentum_buy = spy_price > vwap and mfi > 50
        reversal_buy = spy_price < lower_band and mfi < 30
        buy_signal = momentum_buy or reversal_buy
        signal_type = "Momentum Breakout" if momentum_buy else "Reversal Bounce" if reversal_buy else None

        if buy_signal:
            console.print(f"[bold green]✅ Buy Signal: {signal_type}[/bold green]\n")
        else:
            console.print("[bold red]❌ No Buy Signal: SPY not meeting criteria[/bold red]\n")

        spy = yf.Ticker("SPY")
        expirations = spy.options

        if not expirations:
            console.print("[red]❌ No expiration dates found. Try again later.[/red]")
            return

        this_friday = expirations[0]
        options_chain = spy.option_chain(this_friday)
        calls = options_chain.calls
        
        console.print(f"[bold]🗓 Expiration: {this_friday}[/bold]")

        itm_calls = calls[calls['strike'] < spy_price]
        near_itm = itm_calls[(spy_price - itm_calls['strike']) <= 5.00]
        
        if near_itm.empty:
            console.print("[yellow]⚠️ No ITM calls within $5 of SPY price found.[/yellow]")
            return

        display = near_itm[['contractSymbol', 'strike', 'lastPrice', 'impliedVolatility', 'volume', 'openInterest']].copy()
        display.columns = ['Contract', 'Strike', 'Last Price', 'IV', 'Volume', 'OI']
        display['Liquidity'] = (display['Volume'] / display['Last Price']).round(2)
        display['% ITM'] = ((spy_price - display['Strike']) / spy_price * 100).round(2)
        display = display.sort_values(by='Liquidity', ascending=False)

        table = Table(title="📊 Top ITM Calls Near Spot", show_lines=True)
        for column in display.columns:
            table.add_column(column, justify="right" if column != "Contract" else "left")

        for _, row in display.head(5).iterrows():
            table.add_row(
                row['Contract'],
                f"${row['Strike']:.2f}",
                f"${row['Last Price']:.2f}",
                f"{row['IV']:.4f}",
                f"{row['Volume']:.0f}",
                f"{row['OI']:.0f}",
                f"{row['Liquidity']:.2f}",
                f"{row['% ITM']:.2f}%"
            )

        console.print(table)

        best = display.iloc[0]
        console.print(f"\n[bold magenta]🔥 Suggested Contract to Buy: {best['Contract']} (Strike: ${best['Strike']:.2f})[/bold magenta]")

        if buy_signal:
            contract_symbol = best['Contract']
            strike = best['Strike']
            exp_date = this_friday
            premium = best['Last Price']
            volume = best['Volume']
            option_type = "Call" if "C" in contract_symbol else "Put"

            alert = (
                f"🚨 SPY Buy Signal [{signal_type}]\n\n"
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

        display.to_csv("spy_calls_log.csv", index=False)

    except Exception as e:
        console.print(f"[red]❌ Error: {e}[/red]")

if __name__ == "__main__":
    main()
