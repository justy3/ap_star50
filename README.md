# ap_star50

Streamlit app that predicts the constituents of the upcoming **SSE STAR50** index rebalance.
Two files do the work:

- [data.py](data.py) — data loaders and the metric computation.
- [st_prediction.py](st_prediction.py) — the Streamlit UI, eligibility rules and inclusion/exclusion logic.

Run with:

```bash
streamlit run st_prediction.py
```

---

## What the app does

For a chosen review month it reproduces the official STAR50 rebalance methodology:

1. Loads the STAR board universe ([data/sse.csv](data/sse.csv)) and historical OHLCV ([ohlcv/](ohlcv/)).
2. Computes each name's **average total market cap** and **average value traded** over the
   review's lookback window (`hist_start` → `cutoff_date`).
3. Drops ST/\*ST securities, names that fail the listing-time rule, and the
   bottom 10% by value traded.
4. Ranks the remaining names by average total mcap, locates the **40th** and
   **60th** percentile cutoffs.
5. Builds compulsory inclusions (rank ≤ 40 and not currently in the index) and
   compulsory exclusions (currently in the index and ST / ineligible / rank > 60),
   then balances the two lists with extra inclusions or exclusions so the count
   matches.

---

## Sidebar inputs

### 1. Review month
Three review windows are pre-configured in `REVIEW_PARAMS` ([st_prediction.py:9](st_prediction.py#L9)):

| Review | Effective | Announcement | Cutoff | History start |
|---|---|---|---|---|
| June 2026  | 2026-06-13 | 2026-05-30 | 2026-04-30 | 2025-05-01 |
| March 2026 | 2026-03-14 | 2026-02-28 | 2026-01-31 | 2025-02-01 |
| Dec 2025   | 2025-12-12 | 2025-11-28 | 2025-10-30 | 2024-11-01 |

### 2. Shares column for avg market-cap
The shares count used in `total_mcap = close × shares` has three options
(`SHS_COL_MAP`, [st_prediction.py:30](st_prediction.py#L30)):

1. **`shares_total_sse`** — total shares outstanding sourced from SSE
   ([data/sse.csv](data/sse.csv), loaded by `load_star_board`).
2. **`shares_tradable_sse`** — sharable (tradable / free-float) shares sourced
   from SSE (same file).
3. **`shs_os_yf`** — shares outstanding sourced from yfinance JSON snapshots in
   [sse_info/](sse_info/) (loaded by `get_yf_info` in [data.py:4](data.py#L4)).

The choice is wired into `univ['shs_for_avg']` and fed to `get_avg_vol_mcap`
([data.py:96](data.py#L96)) so every downstream rank reflects the selected shares basis.

---

## Pipeline (st_prediction.py)

| Step | What happens | Key call |
|---|---|---|
| Load board | STAR-board tickers + SSE shares + market cap | `cached_load_board` → `load_star_board` |
| Load OHLCV | Per-ticker daily history clipped to `[hist_start, cutoff_date]` | `cached_history` → `load_historical_data_ohlcv` |
| Listing dates | First trading date per ticker, used for the listing rule | `cached_listing_dates` → `get_listing_dates` |
| yfinance info | Adds `shs_os_yf`, exchange, sector | `cached_yf_info` → `get_yf_info` |
| Metrics | `avg_total_mcap`, `avg_val_traded` and their ranks | `get_avg_vol_mcap` |
| Current index | Merges current STAR50 weights so we know who is currently in | `cached_star50_weights` / `_march` / `_dec25` |
| Eligibility | Listing-time rule + ST drop + bottom-10% value-traded drop | inline in [st_prediction.py:153-176](st_prediction.py#L153-L176) |
| Rebalance | Compulsory + extra inclusions/exclusions, balanced | inline in [st_prediction.py:212-256](st_prediction.py#L212-L256) |

### Eligibility (listing-time rule)
A name is eligible if **any** of the following holds
([st_prediction.py:157](st_prediction.py#L157)):

- Top-3 by `tmcap_rank` and listed ≥ 1 month before cutoff, OR
- Top-5 by `tmcap_rank` and listed ≥ 3 months before cutoff + 10 BDays, OR
- Listed ≥ `listing_month_cutoff` months before cutoff (12 if 100 ≤ count of names with ≥ 12 months ≤ 150, else 6).

### Final eligible universe
After eligibility, the bottom 10% by `avg_val_traded` is dropped, the rest is
re-ranked by `avg_total_mcap` (`tmcap_rank2`), and that ranked frame
(`univ_kept`) drives the 40 / 60 cutoffs.

### Inclusions / exclusions
- **Compulsory inclusions** — `tmcap_rank2 ≤ 40` AND not currently in the index.
- **Compulsory exclusions** — currently in the index AND (ST OR listing-ineligible OR `tmcap_rank2 > 60`).
- If the two counts differ, the shorter side is padded with **extras**
  (best-ranked non-index names, or worst-ranked current-index names) until
  inclusions = exclusions.

---

## UI output

- Header metrics: review dates, board size, ST count, ineligible count, low-value-traded count, final eligible count.
- 40th / 60th avg-total-mcap cutoffs (B CNY).
- Inclusion and exclusion tabs (Final / Compulsory / Extra) plus a "New constituents" grid.
- Detail tabs: eligible universe (ranked), full universe (with dropped flags), ST securities, listing-ineligible, low value-traded, current STAR50 constituents.

All grids render through `show_grid` in [st_fmt.py](st_fmt.py).

---

## data.py reference

| Function | Purpose |
|---|---|
| `load_star_board()` | Reads [data/sse.csv](data/sse.csv); converts shares to millions and market cap to billions CNY. |
| `load_historical_data_ohlcv(tickers, start, end)` | Concatenates every CSV in [ohlcv/](ohlcv/) and clips by date. |
| `get_listing_dates(tickers)` | Earliest OHLCV date per ticker. |
| `get_yf_info(tickers)` | Reads each [sse_info/{ticker}.json](sse_info/) snapshot for `shs_os_yf`, `shs_ff_yf`, exchange, sector. |
| `get_avg_vol_mcap(history, t_shs, tickers, shs_col)` | Joins shares onto OHLCV, computes `total_mcap` (B CNY) and `val_traded` (M CNY), returns per-ticker means. |
| `load_star50_weights()` | Current STAR50 ETF weights from [data/star50_etf.csv](data/star50_etf.csv) — used for the June review. |
| `load_star50_march_weights()` | Applies the March 2026 in/out diff to the ETF list — used for the March review. |
| `load_star50_dec25_tickers()` | Applies the Dec 2025 in/out diff on top of March — used for the Dec review. |
| `load_sse_holidays(year=None)` | Holiday set from [data/sse_holidays.csv](data/sse_holidays.csv). |
| `get_months_from_cutoff(d, cutoff)` | Whole-month gap between listing date and cutoff, with month-end edge handling. |
