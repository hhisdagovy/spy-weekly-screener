import yfinance as yf
import pandas as pd
from datetime import datetime
import os
from rich.console import Console
from rich.table import Table
from ta.volume import MFIIndicator

def clear_terminal():
    os.system('cls' if os.name == 'nt' else 'clear')

def get_vwap_mfi():
    df = yf.download("SPY", interval="5m", period="1d", progress=False)

    if df.empty or len(df) < 20:
        return None, None, None

    # Make sure all columns are 1D Series (not 2D arrays)
    high = df['High'].squeeze()
    low = df['Low'].squeeze()
    close = df['Close'].squeeze()
    volume = df['Volume'].squeeze()

    # Calculate indicators
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

    try:
        # VWAP + MFI logic
        spy_price, vwap, mfi = get_vwap_mfi()

        if spy_price is None:
            console.print("[red]❌ Unable to retrieve VWAP/MFI data.[/red]")
            return

        console.print(f"[green]📈 SPY Price: ${spy_price:.2f} | VWAP: ${vwap:.2f} | MFI: {mfi:.2f}[/green]")

        buy_signal = spy_price > vwap and mfi > 50

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

        # Filter ITM calls within ~$5 of current price
        itm_calls = calls[calls['strike'] < spy_price]
        near_itm = itm_calls[(spy_price - itm_calls['strike']) <= 5.00]

        if near_itm.empty:
            console.print("[yellow]⚠️ No ITM calls within $5 of SPY price found.[/yellow]")
            return

        # Prepare display DataFrame
        display = near_itm[['contractSymbol', 'strike', 'lastPrice', 'impliedVolatility', 'volume', 'openInterest']].copy()
        display.columns = ['Contract', 'Strike', 'Last Price', 'IV', 'Volume', 'OI']

        # Add calculated columns
        display['Liquidity'] = (display['Volume'] / display['Last Price']).round(2)
        display['% ITM'] = ((spy_price - display['Strike']) / spy_price * 100).round(2)

        # Sort by Liquidity
        display = display.sort_values(by='Liquidity', ascending=False)

        # Create rich table
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

        # Suggested contract
        best = display.iloc[0]
        console.print(f"\n[bold magenta]🔥 Suggested Contract to Buy: {best['Contract']} (Strike: ${best['Strike']:.2f})[/bold magenta]")

        # Save to CSV
        display.to_csv("spy_calls_log.csv", index=False)

    except Exception as e:
        console.print(f"[red]❌ Error: {e}[/red]")

if __name__ == "__main__":
    main()
