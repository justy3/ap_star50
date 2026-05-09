#https://kraneshares.com/etf/kstr/#holdings
from _lib import *

def get_constituents(date):
	"""
	Fetch constituent data for a given date from KraneShares KSTR ETF holdings.
	
	Args:
		date (datetime): The date for which to fetch holdings.
	
	Returns:
		pd.DataFrame or None: DataFrame of holdings if successful, None otherwise.
	"""
	date_str = date.strftime("%m_%d_%Y")
	url = f"https://kraneshares.com/csv/{date_str}_kstr_holdings.csv"
	
	headers = {
		"accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
		"accept-language": "en-GB,en-US;q=0.9,en;q=0.8",
		"priority": "u=1, i",
		"referer": "https://kraneshares.com/etf/kstr/",
		"sec-ch-ua": '"Chromium";v="148", "Google Chrome";v="148", "Not/A)Brand";v="99"',
		"sec-ch-ua-mobile": "?0",
		"sec-ch-ua-platform": '"Linux"',
		"sec-fetch-dest": "document",
		"sec-fetch-mode": "navigate",
		"sec-fetch-site": "none",
		"sec-purpose": "prefetch",
		"sec-speculation-tags": "null",
		"upgrade-insecure-requests": "1",
		"user-agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36",
	}
	
	cookies = {
		"__cf_bm": "mIldNcFjMZfMx0c0mw549my9y_P1_BzpnNj.EGhCpWQ-1778234752.9624455-1.0.1.1-uJozvYKKm3skYyCea1nyALzHSNM7jU3Y1puFbYPQN1_y.dBwU4qAJH73rJjhRkyx6rZE5NhxS3zSRXNye67i7a5STbk_qzBK88RHnV8BcwrMdhpbd6JcqHQytCcDPe_W",
		"footer-pop": "true",
		"the_cookie": "true",
		"_gcl_au": "1.1.219221966.1778234766",
		"_ga": "GA1.1.807024313.1778234766",
		"sa-user-id": "s%253A0-3ad5f650-16ce-599f-4380-183624b5e530.ELgMAaEBVJxwyLjxKt%252FMvqyEoAfihwBXn4178VImRQ8",
		"sa-user-id-v2": "s%253AOtX2UBbOWZ9DgBg2JLXlMDHP6wE.HiF6yNg4Hqb0EOYcbfDywtJqIDl87jx%252BLgm6zBNAKRc",
		"sa-user-id-v4": "s%253A.o6W7wkJsHSTU4%252BLlDruZ%252FwNjVcUZZMvakQpSatDoAgo",
		"_ga_SJH5WMLM5Y": "GS2.1.s1778234765$o1$g0$t1778234794$j60$l0$h915640983",
		"_rdt_uuid": "1778234765618.b07e860f-a777-43aa-b371-3d28fbf24bfa",
		"sa-r-source": "www.google.com",
		"sa-r-date": "2026-05-08T10:06:35.008Z",
		"sa-user-id-v3": "s%253AAQAKIHAVMyUHG13yjUbKZAGMCC4WeoFKnOl9hiIWc3imIvXFEAEYAyCq6_bPBjABOgRoqCJNQgS5UFdh.1Xw7iWF9S9bLXd%252BDFMS8M6rJ1p5nxuN7gzglPVdL8qo",
	}
	
	response = requests.get(url, headers=headers, cookies=cookies)
	
	if response.status_code == 200:
		df = pd.read_csv(io.StringIO(response.text))
		return df
	else:
		print(f"Failed to fetch data for {date_str}: {response.status_code}")
		return None

def scrape_constituents_for_date_range(start_date, end_date):
	"""
	Scrape constituent data for a range of dates.
	
	Args:
		start_date (str): Start date in 'YYYY-MM-DD' format.
		end_date (str): End date in 'YYYY-MM-DD' format.
	
	Returns:
		dict: Dictionary with dates as keys and DataFrames as values.
	"""
	start = datetime.strptime(start_date, "%Y-%m-%d")
	end = datetime.strptime(end_date, "%Y-%m-%d")
	
	all_dates = pd.bdate_range(start, end).date
	n = len(all_dates)

	for i in range(n):
		# get query date
		current = all_dates[i]

		# save constituent data
		curr_s = current.strftime("%Y%m%d")
		filename = f'kstr_star50/{curr_s}.csv'

		if Path(filename).is_file():
			print(f"{filename} already exists")

		else:
			# else get the constituents data
			df = get_constituents(current)
			
			# only save constituents df
			if df is not None:
				#constituents[current.strftime("%Y-%m-%d")] = df
				
				print(f"saving {len(df)} rows to file {filename}")
				df.to_csv(filename, index=False)

			# sleep to avoid bombarding requests
			# time.sleep(1)
	
	return None

if __name__ == "__main__":
	# Example usage
	start_date = "2025-01-01"
	end_date = "2026-05-08"
	
	data = scrape_constituents_for_date_range(start_date, end_date)