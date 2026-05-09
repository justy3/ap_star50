from help import *

def download_and_save(ticker):
	# create a Ticker object for the given ticker symbol
	tik = yf.Ticker(f"{ticker}.SS")
	filename = f"../ohlcv/{ticker}.csv"

	# skip if file already exists
	if os.path.exists(filename):
		qt.log.info(f"File {filename} already exists, skipping")
		return

	# load and format history
	hist = tik.history(period="max")
	hist = hist.reset_index('Date')
	hist.columns = ['date', 'open', 'high', 'low', 'close', 'volume', 'dividends', 'stock_splits']
	hist['date'] = hist['date'].dt.date

	# save
	qt.log.info(f"Saving {len(hist)} rows to {filename}")
	hist.to_csv(filename, index=False)
	time.sleep(0.1)


star_board = pd.read_csv('../data/star_board.csv')
tickers = star_board['stock_code'].tolist()

for i in range(len(tickers)):
	qt.log.info(f"downloading {tickers[i]} ({i+1}/{len(tickers)}), ticker = {tickers[i]}")
	download_and_save(tickers[i])


def download_info_and_save(ticker):
	# create a Ticker object for the given ticker symbol
	tik = yf.Ticker(f"{ticker}.SS")
	filename = f"../sse_info/{ticker}.json"

	# skip if file already exists
	if os.path.exists(filename):
		qt.log.info(f"File {filename} already exists, skipping")
		return

	# load info
	info = tik.info

	# save
	qt.log.info(f"Saving info to {filename}")
	with open(filename, "w") as f:
		json.dump(info, f)
	time.sleep(0.1)


for i in range(len(tickers)):
	qt.log.info(f"downloading {tickers[i]} ({i+1}/{len(tickers)}), ticker = {tickers[i]}")
	download_info_and_save(tickers[i])


# import akshare as ak

# df = ak.stock_individual_info_em(symbol="688062")
# print(df)

def download_corp_actions(ticker):
	# create a Ticker object for the given ticker symbol
	tik = yf.Ticker(f"{ticker}.SS")
	filename = f"../corp_actions/{ticker}.csv"

	# skip if file already exists
	if os.path.exists(filename):
		qt.log.info(f"File {filename} already exists, skipping")
		return

	# load and format history
	hist = tik.actions
	if hist.empty:
		qt.log.info(f"No corporate actions found for {ticker}, skipping")
		return
	hist = hist.reset_index('Date')
	if not 'Dividends' in hist.columns:
		hist['Dividends'] = 0
	if not 'stock_splits' in hist.columns:
		hist['Stock Splits'] = 0
	hist = hist[['Date', 'Dividends', 'Stock Splits']]
	hist.columns = ['date', 'dividends', 'stock_splits']
	hist['date'] = hist['date'].dt.date

	# save
	qt.log.info(f"Saving {len(hist)} rows to {filename}")
	hist.to_csv(filename, index=False)
	time.sleep(0.1)

for tik in tickers:
	print(tik)
	download_corp_actions(tik)