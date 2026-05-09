from _lib import *


def get_yf_info(tickers):
	info_l = []

	for tik in tickers:
		tik_i = json.load(open(f"sse_info/{tik}.json", "r"))
		shs_titak = tik_i.get("sharesOutstanding", 0)
		shs_float = tik_i.get("floatShares", 0)
		exch = tik_i["exchange"]
		sector = tik_i.get("sector", "")

		d = {
			"ticker": tik,
			"shs_os_yf": shs_titak,
			"shs_ff_yf": shs_float,
			"exchange": exch,
			"sector": sector
		}
		info_l.append(d)

	# create dataframe from info_l
	info_yf = pd.DataFrame(info_l)
	info_yf['ticker'] = info_yf['ticker'].astype(str)
	info_yf['shs_os_yf'] = info_yf['shs_os_yf']/1e6
	info_yf['shs_ff_yf'] = info_yf['shs_ff_yf']/1e6

	return info_yf

def load_ohlcv_one_ticker(ticker):
	try:
		tik = ticker.split(".")[0]
		t = pd.read_csv(f"ohlcv/{ticker}")
		t['ticker'] = tik
		return t
	except Exception as e:
		qt.log.warning(f"error loading ohlcv data for {ticker}: {e}")
		return pd.DataFrame()

def load_historical_data_ohlcv(tickers, start_date=None, end_date=None):
	if isinstance(tickers, str):
		tickers = [tickers]

	history = pd.concat([load_ohlcv_one_ticker(f) for f in os.listdir("ohlcv") if f.endswith(".csv")])
	history["date"] = pd.to_datetime(history["date"]).dt.date

	if start_date is not None:
		history = history[history["date"] >= start_date]

	if end_date is not None:
		history = history[history["date"] <= end_date]

	history = history.sort_values(["ticker", "date"]).reset_index(drop=True)
	return history

def load_sse_holidays(year=None):
	sse_holidays_t = pd.read_csv("data/sse_holidays.csv")
	sse_holidays_t['date'] = pd.to_datetime(sse_holidays_t['date']).dt.date
	sse_holidays = set(sse_holidays_t['date'].tolist())
	
	# filter by year if provided
	if year is not None:
		sse_holidays = set([d for d in sse_holidays if d.year == year])
	return sse_holidays

def load_star50_weights(query_date=None):
	weights = pd.read_csv("data/star50_etf.csv")
	weights['ticker'] = weights['ticker'].astype(str)
	weights['curr_weight'] = weights['weight']
	return weights

def load_star50_march_weights():
	weights = pd.read_csv("data/star50_etf.csv")
	weights['ticker'] = weights['ticker'].astype(str)
	weights['curr_weight'] = weights['weight']
	excls = ['688220', '688301', '688385']
	incls = ['688213', '688278', '688578']

	after_rebal_tickers = weights['ticker'].tolist()
	after_rebal_tickers += excls
	after_rebal_tickers = [x for x in after_rebal_tickers if x not in incls]
	res_list = ["688608", "688425", "688361", "688568", "688172",]
	return after_rebal_tickers

def get_avg_vol_mcap(history, t_shs:pd.DataFrame|None=None, tickers=None, shs_col='shs_os_yf', start_date=None, end_date=None):
	history = history.copy()
	history['date'] = pd.to_datetime(history['date']).dt.date

	if start_date is not None:
		history = history[history["date"] >= start_date]

	if end_date is not None:
		history = history[history["date"] <= end_date]

	# merge share count into history if not already present
	if len(t_shs) > 0 and shs_col not in history.columns:
		history = pd.merge(history, t_shs[['ticker', shs_col]], on='ticker', how='left')

	if shs_col not in history.columns:
		qt.log.error(f"shares column '{shs_col}' not found in history and t_shs is empty or None")
		sys.exit(1)

	# total_mcap [B CNY] = close [CNY] × shares_total [M shares] / 1e3
	# val_traded [M CNY] = close [CNY] × volume [shares] / 1e6
	history['total_mcap'] = (history['close'] * history[shs_col]) / 1e3
	history['val_traded'] = (history['close'] * history['volume']) / 1e6

	if tickers is not None:
		history = history[history['ticker'].isin(tickers)]

	avg_tmcap = (
		history.groupby('ticker')
		.agg(avg_total_mcap=('total_mcap', 'mean'),
		     avg_val_traded=('val_traded', 'mean'),
		     count_data_pts=('date', 'count'))
		.reset_index()
		.sort_values('avg_total_mcap', ascending=False)
		.reset_index(drop=True)
	)

	return avg_tmcap


def load_star_board():
	boa = pd.read_csv("data/sse.csv")
	boa['ticker'] = boa['ticker'].astype(str)
	boa['shares_total'] 	= np.round(boa['shares_total']/1e6)
	boa['shares_tradable']	= np.round(boa['shares_tradable']/1e6)

	# convert market cap to billions
	boa['market_cap'] = boa['market_cap']/1e5
	boa['tradable_market_cap'] = boa['tradable_market_cap']/1e5
	return boa

def get_listing_dates(tickers):
	history = load_historical_data_ohlcv(tickers)
	t_ld = pd.DataFrame(history.groupby('ticker')['date'].min()).reset_index()
	t_ld.columns = ['ticker', 'listing_date']
	return t_ld

def get_months_from_cutoff(d, cutoff):
	months = (cutoff.year - d.year) * 12 + (cutoff.month - d.month)
	
	if cutoff.day < d.day:
		_, last_day_of_cutoff_month = calendar.monthrange(cutoff.year, cutoff.month)
		
		if cutoff.day != last_day_of_cutoff_month:
			months -= 1
		elif d.day < last_day_of_cutoff_month:
			pass 

	return max(0, months)