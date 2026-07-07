"""Univers US large-cap (S&P 500) — le vivier d'actions tradables en autonome sur Alpaca.

But : quand le trading autonome tourne sur Alpaca, on ne se limite plus à la petite
watchlist de l'utilisateur — le bot scanne TOUT le S&P 500 (les ~500 plus grosses
sociétés US, toutes tradables sur Alpaca) et achète les plus fortes du moment
(classement par momentum dans le cycle de trading). Liste figée pour rester rapide et
robuste ; les micro-caps illiquides sont volontairement exclues (mauvais signaux, ordres
qui échouent). Vérifiée : 503 tickers, tous avec données Yahoo (récupération ~30 s).

Symboles au format Yahoo/interne (BRK-B, BF-B…). `to_alpaca_symbol` fait la conversion.
"""

from __future__ import annotations

# S&P 500 (constituants). Point (.) remplacé par tiret (-) pour Yahoo (BRK-B, BF-B…).
SP500 = [
    "A", "AAPL", "ABBV", "ABNB", "ABT", "ACGL", "ACN", "ADBE", "ADI", "ADM", "ADP", "ADSK",
    "AEE", "AEP", "AES", "AFL", "AIG", "AIZ", "AJG", "AKAM", "ALB", "ALGN", "ALL", "ALLE",
    "AMAT", "AMCR", "AMD", "AME", "AMGN", "AMP", "AMT", "AMZN", "ANET", "AON", "AOS", "APA",
    "APD", "APH", "APO", "APP", "APTV", "ARE", "ARES", "ATO", "AVB", "AVGO", "AVY", "AWK",
    "AXON", "AXP", "AZO", "BA", "BAC", "BALL", "BAX", "BBY", "BDX", "BEN", "BF-B", "BG", "BIIB",
    "BKNG", "BKR", "BLDR", "BLK", "BMY", "BNY", "BR", "BRK-B", "BRO", "BSX", "BX", "BXP", "C",
    "CAH", "CARR", "CASY", "CAT", "CB", "CBOE", "CBRE", "CCI", "CCL", "CDNS", "CDW", "CEG",
    "CF", "CFG", "CHD", "CHRW", "CHTR", "CI", "CIEN", "CINF", "CL", "CLX", "CMCSA", "CME",
    "CMG", "CMI", "CMS", "CNC", "CNP", "COF", "COHR", "COIN", "COO", "COP", "COR", "COST",
    "CPAY", "CPRT", "CPT", "CRH", "CRL", "CRM", "CRWD", "CSCO", "CSGP", "CSX", "CTAS", "CTSH",
    "CTVA", "CVNA", "CVS", "CVX", "D", "DAL", "DASH", "DD", "DDOG", "DE", "DECK", "DELL", "DG",
    "DGX", "DHI", "DHR", "DIS", "DLR", "DLTR", "DOC", "DOV", "DOW", "DPZ", "DRI", "DTE", "DUK",
    "DVA", "DVN", "DXCM", "EA", "EBAY", "ECHO", "ECL", "ED", "EFX", "EG", "EIX", "EL", "ELV",
    "EME", "EMR", "EOG", "EQIX", "EQR", "EQT", "ERIE", "ES", "ESS", "ETN", "ETR", "EVRG", "EW",
    "EXC", "EXE", "EXPD", "EXPE", "EXR", "F", "FANG", "FAST", "FCX", "FDS", "FDX", "FDXF", "FE",
    "FFIV", "FICO", "FIS", "FISV", "FITB", "FIX", "FLEX", "FOX", "FOXA", "FRT", "FSLR", "FTNT",
    "FTV", "GD", "GDDY", "GE", "GEHC", "GEN", "GEV", "GILD", "GIS", "GL", "GLW", "GM", "GNRC",
    "GOOG", "GOOGL", "GPC", "GPN", "GRMN", "GS", "GWW", "HAL", "HAS", "HBAN", "HCA", "HD",
    "HIG", "HII", "HLT", "HON", "HONA", "HOOD", "HPE", "HPQ", "HRL", "HSIC", "HST", "HSY",
    "HUBB", "HUM", "HWM", "IBKR", "IBM", "ICE", "IDXX", "IEX", "IFF", "INCY", "INTC", "INTU",
    "INVH", "IP", "IQV", "IR", "IRM", "ISRG", "IT", "ITW", "IVZ", "J", "JBHT", "JBL", "JCI",
    "JKHY", "JNJ", "JPM", "KDP", "KEY", "KEYS", "KHC", "KIM", "KKR", "KLAC", "KMB", "KMI", "KO",
    "KR", "KVUE", "L", "LDOS", "LEN", "LH", "LHX", "LII", "LIN", "LITE", "LLY", "LMT", "LNT",
    "LOW", "LRCX", "LULU", "LUV", "LVS", "LYB", "LYV", "MA", "MAA", "MAR", "MAS", "MCD", "MCHP",
    "MCK", "MCO", "MDLZ", "MDT", "MET", "META", "MGM", "MKC", "MLM", "MMM", "MNST", "MO", "MOS",
    "MPC", "MPWR", "MRK", "MRNA", "MRSH", "MRVL", "MS", "MSCI", "MSFT", "MSI", "MTB", "MTD",
    "MU", "NCLH", "NDAQ", "NDSN", "NEE", "NEM", "NFLX", "NI", "NKE", "NOC", "NOW", "NRG", "NSC",
    "NTAP", "NTRS", "NUE", "NVDA", "NVR", "NWS", "NWSA", "NXPI", "O", "ODFL", "OKE", "OMC",
    "ON", "ORCL", "ORLY", "OTIS", "OXY", "PANW", "PAYX", "PCAR", "PCG", "PEG", "PEP", "PFE",
    "PFG", "PG", "PGR", "PH", "PHM", "PKG", "PLD", "PLTR", "PM", "PNC", "PNR", "PNW", "PODD",
    "PPG", "PPL", "PRU", "PSA", "PSKY", "PSX", "PTC", "PWR", "PYPL", "Q", "QCOM", "RCL", "REG",
    "REGN", "RF", "RJF", "RL", "RMD", "ROK", "ROL", "ROP", "ROST", "RSG", "RTX", "RVTY", "SBAC",
    "SBUX", "SCHW", "SHW", "SJM", "SLB", "SMCI", "SNA", "SNDK", "SNPS", "SO", "SOLV", "SPG",
    "SPGI", "SRE", "STE", "STLD", "STT", "STX", "STZ", "SW", "SWK", "SWKS", "SYF", "SYK", "SYY",
    "T", "TAP", "TDG", "TDY", "TECH", "TEL", "TER", "TFC", "TGT", "TJX", "TKO", "TMO", "TMUS",
    "TPL", "TPR", "TRGP", "TRMB", "TROW", "TRV", "TSCO", "TSLA", "TSN", "TT", "TTD", "TTWO",
    "TXN", "TXT", "TYL", "UAL", "UBER", "UDR", "UHS", "ULTA", "UNH", "UNP", "UPS", "URI", "USB",
    "V", "VEEV", "VICI", "VLO", "VLTO", "VMC", "VRSK", "VRSN", "VRT", "VRTX", "VST", "VTR",
    "VTRS", "VZ", "WAB", "WAT", "WBD", "WDAY", "WDC", "WEC", "WELL", "WFC", "WM", "WMB", "WMT",
    "WRB", "WSM", "WST", "WTW", "WY", "WYNN", "XEL", "XOM", "XYL", "XYZ", "YUM", "ZBH", "ZBRA",
    "ZTS",
]


# Source publique des constituants à jour (dataset maintenu, format CSV stable).
SP500_URL = "https://raw.githubusercontent.com/datasets/s-and-p-500-companies/main/data/constituents.csv"


def fetch_sp500() -> list[str] | None:
    """Télécharge la liste À JOUR des constituants du S&P 500 (None si échec/anormal).

    Garde-fous : une liste tronquée ou farfelue (moins de 450 ou plus de 550 valeurs,
    symboles invalides) est rejetée — on garde alors la liste précédente.
    """
    import csv
    import io

    import requests
    try:
        r = requests.get(SP500_URL, timeout=20)
        r.raise_for_status()
        rows = csv.DictReader(io.StringIO(r.text))
        syms = sorted({row["Symbol"].strip().replace(".", "-")
                       for row in rows if row.get("Symbol", "").strip()})
    except Exception:  # noqa: BLE001
        return None
    if not (450 <= len(syms) <= 550):
        return None
    if not all(s.replace("-", "").isalnum() for s in syms):
        return None
    return syms


def us_trading_universe(extra: list[str] | None = None,
                        symbols: list[str] | None = None) -> list[str]:
    """Univers de trading autonome Alpaca : S&P 500 (STOCK:*) + éventuels actifs en plus.

    `symbols` = liste de tickers à jour (mise à jour hebdo stockée en base) ; à défaut,
    la liste figée SP500 sert de secours. `extra` = actifs de la watchlist utilisateur
    déjà tradables Alpaca (ex. cryptos BTC/ETH). Dédoublonné en gardant l'ordre.
    """
    out = [f"STOCK:{t}" for t in (symbols or SP500)]
    seen = set(out)
    for a in extra or []:
        if a not in seen:
            out.append(a)
            seen.add(a)
    return out
