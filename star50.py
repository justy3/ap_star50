from _lib import *
from data import *

# =============================================================================
# STEP 0: Load STAR board universe
#   - sse.csv is scraped from the SSE website and contains all securities on
#     the STAR board with market cap, share counts, ST flag, etc.
# =============================================================================

boa = load_star_board()
tickers = boa["ticker"].tolist()
qt.log.info(f"Total STAR board securities loaded: {len(tickers)}")
qt.log.info(f"Board columns: {boa.columns.tolist()}")

# =============================================================================
# STEP 1: Rebalance date parameters
#
#   Per §5.1: adjustment is effective the next trading day after the 2nd Friday
#   of March, June, September, and December.
#
#   cutoff_date : last trading day of the month before announcement — this is
#                 the "usual end date of data used for periodical review"
#   hist_start  : 1-year lookback from cutoff (§3.2 requires avg over past year)
#   cutoff_10   : 10 SSE trading days after cutoff — used in §3.1(ii) listing
#                 time check. NOTE: pd.offsets.BDay does not exclude SSE holidays;
#                 sse_holidays is loaded below but would need custom logic to apply.
# =============================================================================

eff_date    = dt.date(2026, 6, 13)   # effective date of June rebalance
annc_date   = dt.date(2026, 5, 30)   # announcement date
cutoff_date = dt.date(2026, 4, 30)   # end of 1-year data window
hist_start  = dt.date(2025, 5, 1)    # start of 1-year data window

# §3.1(ii): listing time measured as of 10th trading day after cutoff
cutoff_10 = (cutoff_date + pd.offsets.BDay(10)).date()

qt.log.info(f"Rebalance window: {hist_start} → {cutoff_date}  (eff: {eff_date}, annc: {annc_date})")
qt.log.info(f"cutoff+10 BDays = {cutoff_10}  [§3.1(ii) listing time reference date]")

# =============================================================================
# STEP 2: Load supporting data
# =============================================================================

sse_holidays = load_sse_holidays()
qt.log.info(f"SSE holidays loaded: {len(sse_holidays)} dates")

# Load 1-year OHLCV history for all STAR board tickers
history = load_historical_data_ohlcv(tickers, hist_start, cutoff_date)
qt.log.info(f"OHLCV history: {len(history)} rows  |  {history['ticker'].nunique()} tickers covered")
qt.log.info(f"Date range in history: {history['date'].min()} → {history['date'].max()}")

# =============================================================================
# STEP 3: Enrich board data with listing dates
#   Listing date is proxied by the first date in the OHLCV history for each ticker.
# =============================================================================

t_ld = get_listing_dates(tickers)
boa  = pd.merge(boa, t_ld, on="ticker", how="outer")
qt.log.info(f"Board after listing-date merge: {len(boa)} rows")
missing_ld = boa['listing_date'].isna().sum()
if missing_ld:
    qt.log.warning(f"  {missing_ld} tickers have no listing date (no OHLCV data found)")

# =============================================================================
# STEP 4: Build universe — apply §3.1 eligibility pre-filters
# =============================================================================

# --- 4a. Remove *ST securities (§3.1 iv) ---
st_securities = boa[boa['st']]['ticker'].tolist()
qt.log.info(f"ST securities excluded: {len(st_securities)}  → {st_securities}")

univ = boa[['ticker', 'listing_date', 'name', 'market_cap', 'st', 'shares_total']].copy()
univ = univ[~univ['st']].reset_index(drop=True)
qt.log.info(f"Universe after ST removal: {len(univ)} securities")

# --- 4b. Compute months listed relative to cutoff and cutoff+10 ---
# month_to_cof  : months listed as of cutoff_date  — used in §3.1(i) and §3.1(iii)
# month_to_cof10: months listed as of cutoff+10    — used in §3.1(ii)
univ['month_to_cof'] = univ['listing_date'].apply(
    lambda d: (cutoff_date.year - d.year) * 12
              + (cutoff_date.month - d.month)
              - int(cutoff_date.day < d.day)
)
univ['month_to_cof10'] = univ['listing_date'].apply(
    lambda d: (cutoff_10.year - d.year) * 12
              + (cutoff_10.month - d.month)
              - int(cutoff_10.day < d.day)
)
qt.log.info(f"Months-to-cutoff range: {univ['month_to_cof'].min()} to {univ['month_to_cof'].max()}")
qt.log.info(f"Securities listed < 6 months: {(univ['month_to_cof'] < 6).sum()}")
qt.log.info(f"Securities listed < 12 months: {(univ['month_to_cof'] < 12).sum()}")

# --- 4c. Shares outstanding ---
# shs_os_yf    : sharesOutstanding from yfinance (may include H-shares / CDRs for dual-listed)
# shares_total : total market cap / share price scraped from SSE (A-share total shares)
# shs_for_avg  : column used to compute avg total market cap for ranking
#
# The methodology ranks by A-share total market cap so we use shares_total (SSE-scraped).
# shs_os_yf is retained for reference / cross-check.
t_yf = get_yf_info(tickers=univ['ticker'].tolist())
univ = pd.merge(univ, t_yf[['ticker', 'shs_os_yf']], on='ticker', how='left')
qt.log.info(f"shs_os_yf — null: {univ['shs_os_yf'].isna().sum()}  |  zero: {(univ['shs_os_yf']==0).sum()}")

# Using A-share total shares (SSE-scraped) for market cap calculation
univ['shs_for_avg'] = univ['shares_total']
qt.log.info(f"shs_for_avg set to 'shares_total' (A-share basis from SSE scrape)")
qt.log.info(f"  shares_total range: {univ['shares_total'].min():.1f}M to {univ['shares_total'].max():.1f}M shares")

# --- 4d. Compute avg daily total market cap and avg daily value traded ---
# Per §3.2: both metrics computed over the past 1-year window (hist_start → cutoff_date)
#
# avg_total_mcap : avg of (close × shares_total) over 1 year  [B CNY]
#                  = A-share total market cap per day, averaged
# avg_val_traded : avg of (close × volume) over 1 year  [M CNY]
#                  = daily turnover value in A shares
avg_val_traded_n_mcap = get_avg_vol_mcap(
    history, univ,
    tickers=univ['ticker'].unique().tolist(),
    shs_col='shs_for_avg'
)
qt.log.info(f"Avg metrics computed for {len(avg_val_traded_n_mcap)} tickers")
qt.log.info(f"Top 5 by avg total market cap [B CNY]:\n{avg_val_traded_n_mcap[['ticker','avg_total_mcap','avg_val_traded','count_data_pts']].head().to_string(index=False)}")

univ = pd.merge(univ, avg_val_traded_n_mcap, on='ticker', how='left')
n_null_mcap = univ['avg_total_mcap'].isna().sum()
if n_null_mcap:
    qt.log.warning(f"  {n_null_mcap} tickers have no avg_total_mcap (missing OHLCV data)")

# --- 4e. Initial ranking across full non-ST board ---
# tmcap_rank / vtrad_rank: used ONLY for §3.1(ii)(iii) listing-eligibility checks
# (re-ranked after filtering in Step 6)
univ['tmcap_rank'] = univ['avg_total_mcap'].rank(ascending=False, method='min')
univ['vtrad_rank'] = univ['avg_val_traded'].rank(ascending=False, method='min')
qt.log.info(f"Initial ranks assigned across {len(univ)} non-ST securities")
qt.log.info(f"Top 5 by tmcap_rank: {univ.nsmallest(5,'tmcap_rank')[['ticker','name','tmcap_rank']].to_string(index=False)}")

# --- 4f. Load current STAR 50 index weights (for §5.1 buffer zone logic) ---
curr_s50 = load_star50_weights()
univ = pd.merge(univ, curr_s50[['ticker', 'curr_weight']], on='ticker', how='left')
n_current = univ['curr_weight'].notna().sum()
qt.log.info(f"Current STAR 50 constituents found in universe: {n_current} (expect ~50)")

# =============================================================================
# STEP 5: Listing eligibility filter (§3.1 i, ii, iii)
#
#   §3.1(i):   listing_time >= 6 months as of cutoff_date
#              (threshold changes to >= 12 months if 100-150 securities on the
#               board have been listed for >= 12 months)
#   §3.1(ii):  top-5 by avg total mcap AND listing_time >= 3 months as of cutoff+10
#   §3.1(iii): top-3 by avg total mcap AND listing_time >= 1 month as of cutoff_date
#              (applies to stocks that do not qualify under condition ii)
#
#   A security passes if it satisfies ANY one of the three conditions.
# =============================================================================

# Determine listing-time threshold for §3.1(i)
# Count from the non-ST universe (good approximation of full board count)
no_of_securities_mt_12m = len(univ[univ['month_to_cof'] >= 12])

# PDF: "reaches 100 to 150" means the stricter 12-month rule applies within that range
if 100 <= no_of_securities_mt_12m <= 150:
    listing_month_cutoff = 12
else:
    listing_month_cutoff = 6
qt.log.info(
    f"Securities listed >= 12 months: {no_of_securities_mt_12m}  "
    f"→ §3.1(i) listing cutoff = {listing_month_cutoff} months"
)

univ['listing_elig'] = (
    ((univ['tmcap_rank'] <= 3) & (univ['month_to_cof'] >= 1))     # §3.1(iii): top-3, >1 month
    | ((univ['tmcap_rank'] <= 5) & (univ['month_to_cof10'] >= 3)) # §3.1(ii):  top-5, >3 months at cutoff+10
    | (univ['month_to_cof'] >= listing_month_cutoff)              # §3.1(i):   standard age threshold
)

n_before = len(univ)
n_elig_iii = ((univ['tmcap_rank'] <= 3) & (univ['month_to_cof'] >= 1) & ~(univ['month_to_cof'] >= listing_month_cutoff)).sum()
n_elig_ii  = ((univ['tmcap_rank'] <= 5) & (univ['month_to_cof10'] >= 3) & ~(univ['month_to_cof'] >= listing_month_cutoff)).sum()
qt.log.info(f"  Eligible via §3.1(iii) only (top-3 new listings): {n_elig_iii}")
qt.log.info(f"  Eligible via §3.1(ii)  only (top-5 new listings): {n_elig_ii}")

univ = univ[univ['listing_elig']].reset_index(drop=True)
qt.log.info(f"Listing eligibility: {n_before} → {len(univ)} securities passed  (removed {n_before - len(univ)})")

# =============================================================================
# STEP 6: Constituent selection (§3.2)
#
#   (1) Rank by avg daily value traded (descending); delete bottom 10%
#   (2) Rank remaining by avg daily total market cap (descending); take top 50
# =============================================================================

# §3.2(1): Liquidity screen — drop bottom 10% by avg daily trading value
univ['vtrad_rank2'] = univ['avg_val_traded'].rank(ascending=False, method='min')
n_before = len(univ)
liquidity_cutoff_rank = int(0.9 * len(univ))

univ = univ[univ['vtrad_rank2'] <= liquidity_cutoff_rank].reset_index(drop=True)
qt.log.info(
    f"§3.2(1) Liquidity screen: {n_before} → {len(univ)} "
    f"(dropped bottom 10%, cutoff at rank {liquidity_cutoff_rank})"
)

# §3.2(2): Re-rank by avg total market cap within the liquidity-filtered universe
univ['tmcap_rank2'] = univ['avg_total_mcap'].rank(ascending=False, method='min')
univ = univ.sort_values('tmcap_rank2').reset_index(drop=True)
qt.log.info(f"§3.2(2) Market cap ranking complete. Top 5:\n{univ[['ticker','name','avg_total_mcap','tmcap_rank2']].head().to_string(index=False)}")
qt.log.info(f"Rank 50 security: {univ[univ['tmcap_rank2']==50][['ticker','name','avg_total_mcap']].to_string(index=False)}")

# =============================================================================
# STEP 7: Buffer zone rules (§5.1)
#
#   New candidates ranked <= 40  → priority to be added (not currently in index)
#   Old constituents ranked  > 60 → priority to be removed (currently in index)
#   Old constituents ranked 41-60 → protected by buffer, remain in index
#   New stocks ranked 41-60      → not added (buffer zone exclusion)
# =============================================================================

incl = univ[
    (univ['tmcap_rank2'] <= 40) &
    (univ['curr_weight'].isna())    # not a current constituent
]
excl = univ[
    (univ['tmcap_rank2'] > 60) &
    (univ['curr_weight'].notna())   # is a current constituent
]

qt.log.info(f"Buffer zone results:")
qt.log.info(f"  Inclusion candidates (new stocks, ranked <=40): {len(incl)}")
qt.log.info(f"  Exclusion candidates (existing stocks, ranked >60): {len(excl)}")

buffer_zone = univ[
    (univ['tmcap_rank2'].between(41, 60)) &
    (univ['curr_weight'].notna())
]
qt.log.info(f"  Existing stocks in buffer zone (ranked 41-60, remain): {len(buffer_zone)}")

print(f"\n--- Inclusion candidates (§5.1 buffer zone — new stocks ranked <=40) ---")
qt.view2(incl[['ticker', 'name', 'tmcap_rank2', 'vtrad_rank2', 'avg_total_mcap', 'avg_val_traded', 'month_to_cof']])

print(f"\n--- Exclusion candidates (§5.1 buffer zone — existing stocks ranked >60) ---")
qt.view2(excl[['ticker', 'name', 'tmcap_rank2', 'vtrad_rank2', 'avg_total_mcap', 'avg_val_traded', 'curr_weight']])

# =============================================================================
# STEP 8: Spot-check specific tickers (March 2026 rebalance reference)
# =============================================================================

excls    = ['688220', '688301', '688385']   # expected removals
incls_v  = ['688213', '688278', '688578']   # expected additions
res_list = ['688608', '688425', '688361', '688568', '688172']  # reserve list

spot_tickers = excls + incls_v + res_list
spot = univ[univ['ticker'].isin(spot_tickers)][
    ['ticker', 'name', 'tmcap_rank2', 'vtrad_rank2', 'avg_total_mcap', 'curr_weight', 'month_to_cof', 'listing_elig']
]
print(f"\n--- Spot-check: March 2026 rebalance reference tickers ---")
qt.view2(spot)
