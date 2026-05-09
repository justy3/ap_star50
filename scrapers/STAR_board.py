import sys
sys.path.append("../")
from _lib import *

url = "https://yunhq.sse.com.cn:32042//v1/sh1/list/exchange/kshare"
params = {
    "callback": "jQuery36001552746358891326_1778061972837",
    "select": "code,name,region,pinyin",
    "_": "1778061972839",
}
headers = {
    "Accept": "*/*",
    "Accept-Language": "en-GB,en-US;q=0.9,en;q=0.8",
    "Connection": "keep-alive",
    "Referer": "https://english.sse.com.cn/",
    "Sec-Fetch-Dest": "script",
    "Sec-Fetch-Mode": "no-cors",
    "Sec-Fetch-Site": "same-site",
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36",
    "sec-ch-ua": '"Google Chrome";v="147", "Not.A/Brand";v="8", "Chromium";v="147"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Linux"',
}
cookies = {
    "gdp_user_id": "gioenc-a886c183,d2e7,500a,c17d,d43c09de8d25",
    "ba17301551dcbaf9_gdp_session_id": "9aefd9bb-3dad-4932-ba71-1aa9d0809f60",
    "ba17301551dcbaf9_gdp_session_id_sent": "9aefd9bb-3dad-4932-ba71-1aa9d0809f60",
    "ba17301551dcbaf9_gdp_sequence_ids": '{"globalKey":147,"VISIT":6,"PAGE":24,"VIEW_CLICK":119}',
}

response = requests.get(url, params=params, headers=headers, cookies=cookies)
qt.log.info(f"response status code - [{response.status_code}]")



s = response.text
t = pd.DataFrame(json.loads(s[s.find('{'):s.find('}')+1])['list'], columns=['stock_code', 'cn_name', 'cn1', 'en'])
t['stock_code'] = t['stock_code'].astype(int)
qt.log.info(f"saving {len(t)} records to star_board.csv")
t.to_csv('star_board.csv', index=False)