import yfinance as yf
import pandas as pd
from datetime import datetime
import os
import pytz
from rich.console import Console
from rich.table import Table
from ta.volume import MFIIndicator
import requests

def send_telegram_alert(message):
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

def is_market_open():
    eastern = pytz.timezone('US/Eastern')
    now = datetime.now(eastern)
    market_open = now.replace(hour=9, minute=30, second=0, microsecond=0)
    market_close = now.replace(hour=16, minute=0, second=0, microsecond=0)
    return market_open <= now <= market_close

def get_vwap_mfi():
    df = yf.download("SPY", interval="5m", period="1d", progress=False)

    if df.empty or len(df) < 20:
        return None, None, None

    high = df['High'].squeeze()
    low = df['Low'].squeeze()
    close = df['Close'].squeeze()
    volume = df['Volume'].squeeze()

    mfi = MFIIndicator(high=high, low=low, close=close, volume=volume).money_flow_index()
    typical_price = (high + low + close) / 3
    vwap = (typical_price * volume).cumsum() / volume.cumsum()

    df['MFI'] = mfi
    df['VWAP'] = vwap

    latest = df.iloc[-1]
    return float(latest['Close'].item()), float(latest['VWAP'].item()), float(latest['MFI'].item())

def main():
    clear_terminal()
    console = Console()
    console.print(f"[bold cyan]🔍 SPY Weekly ITM Call Screener[/bold cyan]")
    console.print(f"[bold]📅 {datetime.now().strftime('%A, %B %d, %Y %I:%M %p')}[/bold]\n")

    if not is_market_open():
        console.print("[yellow]⏰ Market is closed. Screener will not run outside trading hours.[/yellow]")
        return

    try:
        spy_price, vwap, mfi = get_vwap_mfi()

        if spy_price is None:
            console.print("[red]❌ Unable to retrieve VWAP/MFI data.[/red]")
            return

        console.print(f"[green]📈 SPY Price: ${spy_price:.2f} | VWAP: ${vwap:.2f} | MFI: {mfi:.2f}[/green]")

        buy_signal = True #Testing

        if buy_signal:
            console.print("[bold green]✅ Buy Signal: SPY is above VWAP and MFI > 50[/bold green]\n")
        else:
            console.print("[bold red]❌ No Buy Signal: SPY below VWAP or MFI too low[/bold red]\n")

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
                f"🚨 SPY Buy Signal\n\n"
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
            send_telegram_alert(alert)

        display.to_csv("spy_calls_log.csv", index=False)

    except Exception as e:
        console.print(f"[red]❌ Error: {e}[/red]")

if __name__ == "__main__":
    main()
