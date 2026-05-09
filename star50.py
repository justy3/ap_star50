# %%
from _lib import *
from data import *

# %% [markdown]
# - load all the historical data and universe

# %%
boa = load_star_board()
tickers = boa["ticker"].tolist()
qt.log.info(f"no of tickers on STAR board - [{len(tickers)}]")

# %% [markdown]
# - rebalance parameters

# %%
eff_date = dt.date(2026, 6, 13)
annc_date = dt.date(2026, 5, 30)
cutoff_date = dt.date(2026, 4, 30)
hist_start = dt.date(2025, 5, 1)
cutoff_10 = (cutoff_date + pd.offsets.BDay(10)).date()

# %%
sse_holidays = load_sse_holidays()

# %% [markdown]
# - get listing date

# %%
history = load_historical_data_ohlcv(tickers, hist_start, cutoff_date)

# %% [markdown]
# - add scraped data from sse

# %%
# merge info_df and tu on ticker
t_ld = get_listing_dates(tickers)

# add listing date to star board
boa = pd.merge(boa, t_ld, on="ticker", how="outer")

# %% [markdown]
# - special treatment securities

# %%
st_securities = boa[boa['st']]['ticker'].tolist()
qt.log.info(f"[{len(st_securities)}] ST securities: {st_securities}")

# %% [markdown]
# - eligibility
# 	- Listing time > 6 months. 
# 		1. If no of securities listed > 12 months is b/w 100 to 150 then requirement changes to > 12 months
# 	- For securities with daily avg total market_cap since initial listing in top 5, listing time should be > 3 months as of 10th trading days after end date of data (cutoff date)
# 	- For securities with daily avg total market_cap since initial listing in top 3, listint time should be > 1 month
# 	- Non-* ST securities
# 	- No violation of laws/reg, no financial problems etc

# %%
history_after_cof = history.copy()

# %%
univ = boa[[
	'ticker', 'listing_date', 'name', 'market_cap', 'st', 'shares_total', 
	# 'shares_tradable'
	]].copy()
univ = univ[~univ['st']].reset_index(drop=True)
univ['month_to_cof'] = univ['listing_date'].apply(lambda d: (cutoff_date.year - d.year) * 12 + (cutoff_date.month - d.month)  - int(cutoff_date.day < d.day))
univ['month_to_cof10'] = univ['listing_date'].apply(lambda d: (cutoff_10.year - d.year) * 12 + (cutoff_10.month - d.month)  - int(cutoff_10.day < d.day))

# add shares outstanding from yfinance
t_yf = get_yf_info(tickers=univ['ticker'].tolist())
univ = pd.merge(
	univ, 
	t_yf[[
		'ticker', 'shs_os_yf', 
		# 'shs_ff_yf'
		]], 
	on='ticker', how='left')

# if shs_os_yf is not null, use it as shs_total, otherwise use shares_total
# univ.loc[univ['shs_os_yf'] != 0, 'shs_for_avg'] = univ['shs_os_yf']
# univ.loc[univ['shs_os_yf'] == 0, 'shs_for_avg'] = univ['shares_total']
univ['shs_for_avg'] = univ['shares_total']

# add avg total mcap and avg value traded
avg_val_traded_n_mcap = get_avg_vol_mcap(history, univ, tickers=univ['ticker'].unique().tolist(), shs_col='shs_for_avg')

univ = pd.merge(univ, avg_val_traded_n_mcap, on='ticker', how='left')
univ['tmcap_rank'] = univ['avg_total_mcap'].rank(ascending=False, method='min')
univ['vtrad_rank'] = univ['avg_val_traded'].rank(ascending=False, method='min')

# read weight of existing index
curr_s50 = load_star50_weights()

# add weight column
univ = pd.merge(univ, curr_s50[['ticker', 'curr_weight']], on='ticker', how='left')

# %% [markdown]
# - add eligibility

# %%
no_of_securities_mt_12m = len(univ[univ['month_to_cof'] >= 12])
listing_month_cutoff = 12 if no_of_securities_mt_12m > 100 else 6
qt.log.info(f"Listing month cutoff: {listing_month_cutoff} months (securities with month_to_cof >= {listing_month_cutoff}: {no_of_securities_mt_12m})")

univ['listing_elig'] = (
	((univ['tmcap_rank'] <= 3) & (univ['month_to_cof'] >= 1)) |
	((univ['tmcap_rank'] <= 5) & (univ['month_to_cof10'] >= 3)) |
	(univ['month_to_cof'] >= listing_month_cutoff)
)

univ = univ[univ['listing_elig']].reset_index(drop=True)
univ['vtrad_rank2'] = univ['avg_val_traded'].rank(ascending=False, method='min')

# drop 10% stocks based on avg value traded rank
univ = univ[univ['vtrad_rank2'] <= 0.9*len(univ)].reset_index(drop=True)
univ['tmcap_rank2'] = univ['avg_total_mcap'].rank(ascending=False, method='min')
univ = univ.sort_values('tmcap_rank2').reset_index(drop=True)

# %%
# univ.set_index('ticker')[['shares_total', 'shares_tradable', 'shs_os_yf', 'shs_ff_yf']].plot()

# %%
incl = univ[
	(univ['tmcap_rank2'] <= 40) &
	(univ['curr_weight'].isna())
]
excl = univ[
	(univ['tmcap_rank2'] > 60) &
	(~univ['curr_weight'].isna())
]
print(f"inclusion stocks : \n")
qt.view2(incl)
print(f"exclusion stocks : \n")
qt.view2(excl)

# %%
univ[univ['ticker'].isin(
	[
		'688498', '688110', '688002',
		'688114', '688278', '688349'	
  	]
)]

# %% [markdown]
# - march testing

# %%
excls = ['688220', '688301', '688385']
incls = ['688213', '688278', '688578']
res_list = ["688608", "688425", "688361", "688568", "688172",]
univ[univ['ticker'].isin(excls)]
univ[univ['ticker'].isin(incls)]
univ[univ['ticker'].isin(res_list)]

# %%


