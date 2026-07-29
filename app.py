import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st
import yfinance as yf


st.set_page_config(page_title="股票相關性檢查器", page_icon="📈", layout="wide")


@st.cache_data(ttl=3600)
def load_prices(tickers: tuple[str, ...], period: str) -> pd.DataFrame:
    raw = yf.download(
        list(tickers),
        period=period,
        auto_adjust=True,
        progress=False,
        group_by="column",
    )
    if raw.empty:
        return pd.DataFrame()
    prices = raw["Close"] if "Close" in raw else raw
    if isinstance(prices, pd.Series):
        prices = prices.to_frame(name=tickers[0])
    return prices.dropna(axis=1, how="all").ffill().dropna()


def pair_table(correlation: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for i, left in enumerate(correlation.columns):
        for right in correlation.columns[i + 1 :]:
            value = float(correlation.loc[left, right])
            rows.append(
                {
                    "股票 A": left,
                    "股票 B": right,
                    "相關係數": value,
                    "判讀": (
                        "高度同向"
                        if value >= 0.7
                        else "中度同向"
                        if value >= 0.4
                        else "低相關"
                        if value > -0.4
                        else "反向"
                    ),
                }
            )
    return pd.DataFrame(rows).sort_values("相關係數", ascending=False)


st.title("股票相關性檢查器")
st.caption("用日報酬率檢查持股是否真的分散；相關不代表因果，也不保證未來維持不變。")

with st.sidebar:
    symbols = st.text_area(
        "股票代號（逗號或換行分隔）",
        "AAPL, MSFT, NVDA, JPM, XOM",
        help="台股請使用 Yahoo Finance 格式，例如 2330.TW、2317.TW。",
    )
    period = st.selectbox(
        "歷史期間",
        options=["6mo", "1y", "2y", "5y"],
        index=2,
        format_func={"6mo": "6 個月", "1y": "1 年", "2y": "2 年", "5y": "5 年"}.get,
    )
    threshold = st.slider("高相關警戒值", 0.50, 0.95, 0.70, 0.05)
    run = st.button("開始分析", type="primary", use_container_width=True)

tickers = tuple(
    dict.fromkeys(
        item.strip().upper()
        for item in symbols.replace("\n", ",").split(",")
        if item.strip()
    )
)

if not run:
    st.info("輸入至少兩個股票代號，再按「開始分析」。")
    st.stop()
if len(tickers) < 2:
    st.error("請輸入至少兩個不同的股票代號。")
    st.stop()

try:
    prices = load_prices(tickers, period)
except Exception as exc:
    st.error(f"下載行情失敗：{exc}")
    st.stop()

missing = sorted(set(tickers) - set(prices.columns))
if missing:
    st.warning("找不到或資料不足：" + "、".join(missing))
if prices.shape[1] < 2:
    st.error("有效股票不足兩檔，無法計算相關性。")
    st.stop()

returns = prices.pct_change(fill_method=None).dropna()
correlation = returns.corr(method="pearson")
pairs = pair_table(correlation)
high_pairs = pairs[pairs["相關係數"] >= threshold]
mean_pair_correlation = float(
    correlation.where(~np.eye(len(correlation), dtype=bool)).stack().mean()
)

col1, col2, col3 = st.columns(3)
col1.metric("有效股票", f"{prices.shape[1]} 檔")
col2.metric("平均兩兩相關", f"{mean_pair_correlation:.2f}")
col3.metric("高相關配對", f"{len(high_pairs)} 組")

if high_pairs.empty:
    st.success(f"沒有配對高於 {threshold:.2f}；以這段歷史資料看，分散效果較佳。")
else:
    st.warning(
        f"有 {len(high_pairs)} 組配對高於 {threshold:.2f}。"
        "這些股票可能同時漲跌，不能只靠增加檔數來分散風險。"
    )

heatmap = px.imshow(
    correlation,
    text_auto=".2f",
    zmin=-1,
    zmax=1,
    color_continuous_scale="RdBu_r",
    aspect="auto",
    title="日報酬率相關矩陣",
)
st.plotly_chart(heatmap, use_container_width=True)

left, right = st.columns([1, 1])
with left:
    st.subheader("股票配對排名")
    st.dataframe(
        pairs.style.format({"相關係數": "{:.3f}"}),
        hide_index=True,
        use_container_width=True,
    )
with right:
    st.subheader("標準化價格走勢")
    normalized = prices.div(prices.iloc[0]).mul(100)
    st.line_chart(normalized, use_container_width=True)

st.download_button(
    "下載配對結果 CSV",
    data=pairs.to_csv(index=False).encode("utf-8-sig"),
    file_name="stock_correlation_pairs.csv",
    mime="text/csv",
)
