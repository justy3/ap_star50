from _lib import *
from data import *
from st_fmt import show_grid, grid_height


st.set_page_config(page_title="STAR50 Rebalance Prediction", layout="wide")


REVIEW_PARAMS = {
	"June 2026": {
		"eff_date": dt.date(2026, 6, 13),
		"annc_date": dt.date(2026, 5, 30),
		"cutoff_date": dt.date(2026, 4, 30),
		"hist_start": dt.date(2025, 5, 1),
	},
	"March 2026": {
		"eff_date": dt.date(2026, 3, 14),
		"annc_date": dt.date(2026, 2, 28),
		"cutoff_date": dt.date(2026, 1, 31),
		"hist_start": dt.date(2025, 2, 1),
	},
}

SHS_COL_MAP = {
	"shares_tradable_sse": "shares_tradable",
	"shares_total_sse": "shares_total",
	"shs_os_yf": "shs_os_yf",
}


@st.cache_data(show_spinner=False)
def cached_load_board():
	boa = load_star_board()
	return boa


@st.cache_data(show_spinner=False)
def cached_history(tickers, hist_start, cutoff_date):
	return load_historical_data_ohlcv(tickers, hist_start, cutoff_date)


@st.cache_data(show_spinner=False)
def cached_listing_dates(tickers):
	return get_listing_dates(tickers)


@st.cache_data(show_spinner=False)
def cached_yf_info(tickers):
	return get_yf_info(tickers=tickers)


@st.cache_data(show_spinner=False)
def cached_star50_weights():
	return load_star50_weights()


@st.cache_data(show_spinner=False)
def cached_star50_march():
	return load_star50_march_weights()


# ------------------------------- sidebar inputs -------------------------------
st.sidebar.header("Inputs")
review = st.sidebar.selectbox("Review month", list(REVIEW_PARAMS.keys()), index=0)
shs_choice = st.sidebar.selectbox(
	"Shares column for avg market-cap",
	list(SHS_COL_MAP.keys()),
	index=0,
	help="shares_tradable_sse → tradable shares from SSE; shares_total_sse → total shares from SSE; shs_os_yf → shares outstanding from yfinance",
)
shs_col = SHS_COL_MAP[shs_choice]


# ------------------------------- params display -------------------------------
p = REVIEW_PARAMS[review]
eff_date = p["eff_date"]
annc_date = p["annc_date"]
cutoff_date = p["cutoff_date"]
hist_start = p["hist_start"]
cutoff_10 = (cutoff_date + pd.offsets.BDay(10)).date()

st.title("STAR50 Rebalance Prediction")
st.caption(f"Review: {review} | shares column: {shs_choice}")

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Effective date", eff_date.strftime("%Y-%m-%d"))
c2.metric("Announcement date", annc_date.strftime("%Y-%m-%d"))
c3.metric("Cutoff date", cutoff_date.strftime("%Y-%m-%d"))
c4.metric("Cutoff +10 BDays", cutoff_10.strftime("%Y-%m-%d"))
c5.metric("History start", hist_start.strftime("%Y-%m-%d"))


# --------------------------------- load data ----------------------------------
with st.spinner("Loading STAR board…"):
	boa = cached_load_board()
	tickers = boa["ticker"].tolist()

with st.spinner("Loading historical OHLCV…"):
	history = cached_history(tuple(tickers), hist_start, cutoff_date)

with st.spinner("Computing listing dates / merging…"):
	t_ld = cached_listing_dates(tuple(tickers))
	boa = pd.merge(boa, t_ld, on="ticker", how="outer")

st_securities = boa[boa['st']]['ticker'].tolist()


# --------------------------------- universe ----------------------------------
univ = boa[[
	'ticker', 'listing_date', 'name', 'market_cap', 'st',
	'shares_total', 'shares_tradable',
]].copy()

univ['month_to_cof']   = univ['listing_date'].apply(lambda d: get_months_from_cutoff(d, cutoff=cutoff_date))
univ['month_to_cof10'] = univ['listing_date'].apply(lambda d: get_months_from_cutoff(d, cutoff=cutoff_10))

with st.spinner("Loading yfinance info…"):
	t_yf = cached_yf_info(tuple(univ['ticker'].tolist()))
univ = pd.merge(univ, t_yf[['ticker', 'shs_os_yf']], on='ticker', how='left')

univ['shs_for_avg'] = univ[shs_col]

with st.spinner("Computing avg val-traded and total mcap…"):
	avg_t = get_avg_vol_mcap(history, univ, tickers=univ['ticker'].unique().tolist(), shs_col='shs_for_avg')
univ = pd.merge(univ, avg_t, on='ticker', how='left')
univ['tmcap_rank'] = univ['avg_total_mcap'].rank(ascending=False, method='min')
univ['vtrad_rank'] = univ['avg_val_traded'].rank(ascending=False, method='min')

# current index weights
if eff_date.month == 6:
	curr_s50 = cached_star50_weights()
	univ = pd.merge(univ, curr_s50[['ticker', 'curr_weight']], on='ticker', how='left')
else:
	curr_s50 = cached_star50_march()
	univ['curr_weight'] = univ['ticker'].isin(curr_s50).astype(float)
	univ.loc[univ['curr_weight'] == 0, 'curr_weight'] = np.nan


# --------------------------------- eligibility --------------------------------
no_ge_12 = len(univ[univ['month_to_cof'] >= 12])
listing_month_cutoff = 12 if 150 >= no_ge_12 >= 100 else 6

univ['listing_elig'] = (
	((univ['tmcap_rank'] <= 3) & (univ['month_to_cof'] >= 1)) |
	((univ['tmcap_rank'] <= 5) & (univ['month_to_cof10'] >= 3)) |
	(univ['month_to_cof'] >= listing_month_cutoff)
)

st_univ = univ[univ['st']].copy()
univ_ne = univ[~univ['st']].reset_index(drop=True)

ineligible_univ = univ_ne[~univ_ne['listing_elig']].copy()
univ_e = univ_ne[univ_ne['listing_elig']].reset_index(drop=True)
univ_e['vtrad_rank2'] = univ_e['avg_val_traded'].rank(ascending=False, method='min')

low_val_traded_univ = univ_e[univ_e['vtrad_rank2'] > 0.9 * len(univ_e)].copy()
univ_kept = univ_e[univ_e['vtrad_rank2'] <= 0.9 * len(univ_e)].reset_index(drop=True)
univ_kept['tmcap_rank2'] = univ_kept['avg_total_mcap'].rank(ascending=False, method='min')
univ_kept = univ_kept.sort_values('tmcap_rank2').reset_index(drop=True)

univ_full = pd.concat([univ_kept, st_univ, ineligible_univ, low_val_traded_univ], ignore_index=True)
univ_full = univ_full.sort_values(['tmcap_rank2', 'vtrad_rank2', 'listing_elig', 'st']).reset_index(drop=True)


# --------------------------- rebalance summary stats --------------------------
in_index = univ_kept['curr_weight'].notna().sum()
not_in_index = univ_kept['curr_weight'].isna().sum()

s1, s2, s3, s4, s5 = st.columns(5)
s1.metric("STAR board tickers", len(tickers))
s2.metric("ST securities (dropped)", len(st_securities))
s3.metric("Ineligible (listing rule)", len(ineligible_univ))
s4.metric("Low value traded (bottom 10%)", len(low_val_traded_univ))
s5.metric("Final eligible universe", len(univ_kept))

st.info(f"Listing-month cutoff applied: **{listing_month_cutoff} months** "
		f"(securities with month_to_cof ≥ 12: {no_ge_12})")


# --------------------------- 40 / 60 cutoffs ----------------------------------
tmcap_40 = univ_kept.loc[univ_kept['tmcap_rank2'] == 40, 'avg_total_mcap']
tmcap_60 = univ_kept.loc[univ_kept['tmcap_rank2'] == 60, 'avg_total_mcap']
tmcap_40_v = float(tmcap_40.values[0]) if len(tmcap_40) else np.nan
tmcap_60_v = float(tmcap_60.values[0]) if len(tmcap_60) else np.nan

co1, co2 = st.columns(2)
co1.metric("40th avg total mcap (B CNY)", f"{tmcap_40_v:,.3f}")
co2.metric("60th avg total mcap (B CNY)", f"{tmcap_60_v:,.3f}")

univ_kept.loc[univ_kept['curr_weight'].fillna(0) == 0, 'dist_to_40'] = (
	univ_kept['avg_total_mcap'].apply(lambda x: 100 * (tmcap_40_v - x) / tmcap_40_v)
)
univ_kept.loc[univ_kept['curr_weight'].fillna(0) != 0, 'dist_to_60'] = (
	univ_kept['avg_total_mcap'].apply(lambda x: 100 * (tmcap_60_v - x) / tmcap_60_v)
)


# --------------------------- inclusions / exclusions --------------------------
# Use univ_full so that ST and listing-ineligible names (which still carry
# curr_weight from the merge) can show up as compulsory exclusions.
comp_incl = univ_full[
	(univ_full['tmcap_rank2'] <= 40) & (univ_full['curr_weight'].isna())
].copy()

comp_excl = pd.concat([
	univ_full[
		univ_full['curr_weight'].notna() &
		(univ_full['st'] | (~univ_full['listing_elig']))
	],
	univ_full[
		univ_full['curr_weight'].notna() &
		(univ_full['tmcap_rank2'] > 60)
	],
]).drop_duplicates(subset=['ticker']).reset_index(drop=True)

# extra inclusions / exclusions to balance the count
xtra_excl = pd.DataFrame(columns=univ_full.columns)
xtra_incl = pd.DataFrame(columns=univ_full.columns)

if len(comp_incl) > len(comp_excl):
	# need extra exclusions: pick worst-ranked current-index names not already excluded
	xtra_excl = univ_full[
		univ_full['curr_weight'].notna() &
		(~univ_full['ticker'].isin(comp_excl['ticker']))
	].iloc[-(len(comp_incl) - len(comp_excl)):]
elif len(comp_incl) < len(comp_excl):
	# need extra inclusions: pick best-ranked non-index names not already included
	xtra_incl = univ_full[
		univ_full['curr_weight'].isna() &
		(~univ_full['ticker'].isin(comp_incl['ticker']))
	].iloc[: len(comp_excl) - len(comp_incl)]

incl = pd.concat([comp_incl, xtra_incl], ignore_index=True)
excl = pd.concat([comp_excl, xtra_excl], ignore_index=True)

new_constituents = univ_full[
	univ_full['ticker'].isin(incl['ticker']) |
	(univ_full['curr_weight'].notna() & univ_full['ticker'].isin(excl['ticker']))
].sort_values('tmcap_rank2').reset_index(drop=True)


# ---- header summary
sc1, sc2, sc3, sc4, sc5, sc6 = st.columns(6)
sc1.metric("Compulsory inclusions", len(comp_incl))
sc2.metric("Compulsory exclusions", len(comp_excl))
sc3.metric("Extra inclusions",     len(xtra_incl))
sc4.metric("Extra exclusions",     len(xtra_excl))
sc5.metric("Final inclusions",     len(incl))
sc6.metric("Final exclusions",     len(excl))


def _side_by_side(left_df, left_label, left_caption, left_key,
                  right_df, right_label, right_caption, right_key):
	lc, rc = st.columns(2)
	with lc:
		st.markdown(f"**{left_label} ({len(left_df)})**")
		st.caption(left_caption)
		if len(left_df):
			show_grid(left_df, key=left_key, height=grid_height(len(left_df)))
		else:
			st.write("_none_")
	with rc:
		st.markdown(f"**{right_label} ({len(right_df)})**")
		st.caption(right_caption)
		if len(right_df):
			show_grid(right_df, key=right_key, height=grid_height(len(right_df)))
		else:
			st.write("_none_")


st.markdown("### Inclusions / exclusions")
ie_tabs = st.tabs([
	f"Final ({len(incl)} / {len(excl)})",
	f"Compulsory ({len(comp_incl)} / {len(comp_excl)})",
	f"Extra ({len(xtra_incl)} / {len(xtra_excl)})",
])

with ie_tabs[0]:
	_side_by_side(
		incl, "Final inclusions",
		"Compulsory + extra inclusions",
		"final_incl",
		excl, "Final exclusions",
		"Compulsory + extra exclusions",
		"final_excl",
	)

with ie_tabs[1]:
	_side_by_side(
		comp_incl, "Compulsory inclusions",
		"Not in index AND tmcap_rank2 ≤ 40",
		"comp_incl",
		comp_excl, "Compulsory exclusions",
		"In index AND (ST/ineligible OR tmcap_rank2 > 60)",
		"comp_excl",
	)

with ie_tabs[2]:
	_side_by_side(
		xtra_incl, "Extra inclusions",
		"Best-ranked non-index names added when comp_excl > comp_incl",
		"xtra_incl",
		xtra_excl, "Extra exclusions",
		"Worst-ranked current-index names added when comp_incl > comp_excl",
		"xtra_excl",
	)


st.markdown(f"### New constituents ({len(new_constituents)})")
st.caption("All names changing in this rebalance (final inclusions + final exclusions), sorted by tmcap_rank2")
if len(new_constituents):
	show_grid(new_constituents, key="new_const", height=grid_height(len(new_constituents), cap=500))
else:
	st.write("_none_")


# --------------------------- detailed tables ----------------------------------
tabs = st.tabs([
	"Eligible universe (ranked)",
	"Full universe (with dropped)",
	"ST securities",
	"Ineligible (listing)",
	"Low value-traded (bottom 10%)",
	"Current index constituents",
])

with tabs[0]:
	st.caption(f"{len(univ_kept)} eligible names sorted by avg total mcap rank")
	show_grid(univ_kept, key="kept", height=600)

with tabs[1]:
	st.caption(f"{len(univ_full)} names — eligible + dropped categories")
	show_grid(univ_full, key="full", height=600)

with tabs[2]:
	st.caption(f"{len(st_univ)} ST/*ST securities (dropped before ranking)")
	show_grid(st_univ, key="st", height=300)

with tabs[3]:
	st.caption(f"{len(ineligible_univ)} names failing the listing-time rule")
	show_grid(ineligible_univ, key="inelig", height=400)

with tabs[4]:
	st.caption(f"{len(low_val_traded_univ)} names dropped by bottom-10% value-traded filter")
	show_grid(low_val_traded_univ, key="lowvt", height=400)

with tabs[5]:
	curr = univ_full[univ_full['curr_weight'].notna()].copy()
	st.caption(f"{len(curr)} current STAR50 constituents found in universe")
	show_grid(curr, key="curr", height=600)
