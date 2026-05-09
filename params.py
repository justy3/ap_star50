from help import *

# JUNE REBALANCE
eff_date = dt.date(2026, 6, 13)
annc_date = dt.date(2026, 5, 30)
cutoff_date = dt.date(2026, 4, 30)
hist_start = dt.date(2025, 5, 1)
cutoff_10 = (cutoff_date + pd.offsets.BDay(10)).date()

# MARCH REBALANCE
eff_date = dt.date(2026, 3, 14)
annc_date = dt.date(2026, 2, 28)
cutoff_date = dt.date(2026, 1, 31)
hist_start = dt.date(2025, 2, 1)
cutoff_10 = (cutoff_date + pd.offsets.BDay(10)).date()