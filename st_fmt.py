"""AgGrid presentation helpers for the STAR50 streamlit dashboard."""
from _lib import *
from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode, JsCode


# Number formatter: thousands separators, 2dp, blanks for null/NaN.
NUM_FMT = JsCode("""
function(params) {
	if (params.value === null || params.value === undefined || Number.isNaN(params.value)) return '';
	if (typeof params.value !== 'number') return params.value;
	return params.value.toLocaleString(undefined, {maximumFractionDigits: 2});
}
""")


# ---- width measurement -------------------------------------------------------
# AgGrid's JS-based autoSize is unreliable across versions (the columnApi shape
# changed) and frequently fires before rows are laid out. We pre-compute widths
# from the actual rendered string content, treating CJK glyphs as ~2× ASCII so
# Chinese names get the room they need.

_PX_ASCII = 7   # avg pixels per ASCII char at default streamlit-aggrid font
_PX_CJK   = 14  # pixels per fullwidth/CJK glyph
_PAD      = 30  # cell padding + sort/filter icon
_MIN_W    = 60
_MAX_W    = 320


def _is_cjk(ch):
	o = ord(ch)
	return (
		0x3000 <= o <= 0x303F or  # CJK punctuation
		0x3400 <= o <= 0x4DBF or  # CJK ext A
		0x4E00 <= o <= 0x9FFF or  # CJK unified
		0xF900 <= o <= 0xFAFF or  # CJK compat
		0xFF00 <= o <= 0xFFEF     # halfwidth+fullwidth forms
	)


def _str_pixel_width(s):
	if s is None:
		return 0
	s = str(s)
	w = 0
	for ch in s:
		w += _PX_CJK if _is_cjk(ch) else _PX_ASCII
	return w


def _format_cell_for_width(v, is_numeric):
	"""Mirror what the user will actually see in the cell — applies the same
	thousands-separator + 2dp formatting that NUM_FMT uses on the JS side."""
	if v is None:
		return ""
	if isinstance(v, float) and np.isnan(v):
		return ""
	if is_numeric and isinstance(v, (int, float, np.integer, np.floating)):
		return f"{v:,.2f}"
	if isinstance(v, (dt.date, dt.datetime)):
		return v.strftime("%Y-%m-%d")
	return str(v)


def _col_width(header, values, is_numeric):
	header_w = _str_pixel_width(header)
	data_w = max(
		(_str_pixel_width(_format_cell_for_width(v, is_numeric)) for v in values),
		default=0,
	)
	return min(max(_MIN_W, max(header_w, data_w) + _PAD), _MAX_W)


# ---- helpers -----------------------------------------------------------------

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


def grid_height(n, base=80, row=30, cap=420):
	"""Pick a grid height that fits `n` rows up to `cap` pixels."""
	return min(base + row * max(n, 1), cap)


def show_grid(df, key, height=400):
	"""Render `df` as an AgGrid with columns sized to their longest cell."""
	df = _prep_df_for_grid(df)
	numeric_cols = set(df.select_dtypes(include=[np.number]).columns.tolist())

	gb = GridOptionsBuilder.from_dataframe(df)
	gb.configure_default_column(
		filter=True, sortable=True, resizable=True, floatingFilter=True,
		minWidth=_MIN_W,
	)
	gb.configure_grid_options(
		domLayout='normal',
		enableCellTextSelection=True,
		suppressColumnVirtualisation=True,
	)

	for col in df.columns:
		is_num = col in numeric_cols
		w = _col_width(col, df[col].tolist(), is_num)
		cfg = dict(width=w)
		if is_num:
			cfg["type"] = ["numericColumn", "numberColumnFilter"]
			cfg["valueFormatter"] = NUM_FMT
		gb.configure_column(col, **cfg)

	AgGrid(
		df,
		gridOptions=gb.build(),
		height=height,
		update_mode=GridUpdateMode.NO_UPDATE,
		key=key,
		allow_unsafe_jscode=True,
		theme="streamlit",
		enable_enterprise_modules=False,
		reload_data=False,
	)
