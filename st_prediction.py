from _lib import *
from data import *
from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode, JsCode, ColumnsAutoSizeMode


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


NUM_FMT = JsCode("""
function(params) {
	if (params.value === null || params.value === undefined || Number.isNaN(params.value)) return '';
	if (typeof params.value !== 'number') return params.value;
	return params.value.toLocaleString(undefined, {maximumFractionDigits: 2});
}
""")


def _prep_df_for_grid(df):
	"""AgGrid is finicky about non-JSON-serialisable cells (dates, NaN in
	object cols, etc.). Convert dates to strings and replace NaN in object
	columns with empty strings so the grid renders cleanly."""
	out = df.copy().reset_index(drop=True)
	for c in out.columns:
		s = out[c]
		if pd.api.types.is_datetime64_any_dtype(s):
			out[c] = s.dt.strftime("%Y-%m-%d")
		elif s.dtype == object:
			# date objects → iso string; leave the rest, fill NaN with ''
			def _coerce(v):
				if v is None:
					return ""
				if isinstance(v, (dt.date, dt.datetime)):
					return v.strftime("%Y-%m-%d")
				try:
					if pd.isna(v):
						return ""
				except (TypeError, ValueError):
					pass
				return v
			out[c] = s.map(_coerce)
	return out


def show_grid(df, key, height=400, fit_columns=False):
	df = _prep_df_for_grid(df)
	gb = GridOptionsBuilder.from_dataframe(df)
	gb.configure_default_column(
		filter=True, sortable=True, resizable=True, floatingFilter=True,
		minWidth=110,
	)
	gb.configure_grid_options(domLayout='normal', enableCellTextSelection=True)
	for col in df.select_dtypes(include=[np.number]).columns:
		gb.configure_column(
			col,
			type=["numericColumn", "numberColumnFilter"],
			valueFormatter=NUM_FMT,
		)
	autosize = ColumnsAutoSizeMode.FIT_CONTENTS if not fit_columns else ColumnsAutoSizeMode.FIT_ALL_COLUMNS_TO_VIEW
	AgGrid(
		df,
		gridOptions=gb.build(),
		height=height,
		update_mode=GridUpdateMode.NO_UPDATE,
		columns_auto_size_mode=autosize,
		key=key,
		allow_unsafe_jscode=True,
		theme="streamlit",
		enable_enterprise_modules=False,
		reload_data=False,
	)


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
listing_month_cutoff = 12 if no_ge_12 > 100 else 6

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
comp_incl = univ_kept[(univ_kept['tmcap_rank2'] <= 40) & (univ_kept['curr_weight'].isna())].copy()
comp_excl = univ_kept[(univ_kept['tmcap_rank2'] >  60) & (univ_kept['curr_weight'].notna())].copy()

st.subheader(f"Predicted inclusions  ({len(comp_incl)})")
st.caption("Stocks NOT in current index with avg total mcap rank ≤ 40")
if len(comp_incl):
	show_grid(comp_incl, key="incl", height=min(80 + 30 * len(comp_incl), 400))
else:
	st.write("_none_")

st.subheader(f"Predicted exclusions  ({len(comp_excl)})")
st.caption("Stocks IN current index with avg total mcap rank > 60")
if len(comp_excl):
	show_grid(comp_excl, key="excl", height=min(80 + 30 * len(comp_excl), 400))
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
