# app.py
# Streamlit dashboard for BIST100 Final State distributions (PARQUET-BASED, no DB locks)
# Requirements: streamlit, pandas, plotly, duckdb
#
# Data expectation:
#   - A parquet file exported from your aggregation step, e.g. final_state_daily_bist100.parquet
#   - Columns: tarih, islem_kodu, final_state, emir_sayisi, yuzde
#
# Run:
#   streamlit run app.py
#
# Optional:
#   export PARQUET_PATH env var to point to your parquet
#   export SHOW_TABLE=1 to show raw tables by default

import os
import duckdb
import pandas as pd
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go

st.set_page_config(page_title="BIST100 Final State Dashboard", layout="wide")

# -----------------------------
# Config
# -----------------------------
PARQUET_PATH = os.getenv("PARQUET_PATH", "final_state_daily_bist100.parquet")
SHOW_TABLE_DEFAULT = os.getenv("SHOW_TABLE", "0") == "1"

METRIC_DETAILS_MD = {
    "EQS (w.avg)": r"""
**Formül**
\[
EQS = Trade\% - CanceledByUser\% - Expired\%
\]

**Yorum**
- **Yüksek EQS** ⇒ daha fazla execution, daha az iptal/expire
- Günlük hesaplanır, seçilen tarih aralığı için **emir sayısı ile ağırlıklı ortalama** alınır.
""",
    "Trade% (w.avg)": r"""
**Formül**
\[
Trade\% = \frac{Trade\ Emir\ Sayısı}{Toplam\ Emir\ Sayısı} \times 100
\]

**Yorum**
- **Yüksek Trade%** ⇒ daha yüksek fill/execution oranı
- Seçilen tarih aralığı için **emir sayısı ile ağırlıklı ortalama** alınır.
""",
    "CanceledByUser% (w.avg)": r"""
**Formül**
\[
CanceledByUser\% = \frac{CanceledByUser\ Emir\ Sayısı}{Toplam\ Emir\ Sayısı} \times 100
\]

**Yorum**
- **Düşük Cancel% daha iyidir**
- Cancel artışı genelde *refresh / sabırsızlık / execution zorluğu* ile ilişkilidir.
- Seçilen tarih aralığı için **emir sayısı ile ağırlıklı ortalama** alınır.
""",
    "Expired% (w.avg)": r"""
**Formül**
\[
Expired\% = \frac{Expired\ Emir\ Sayısı}{Toplam\ Emir\ Sayısı} \times 100
\]

**Yorum**
- **Düşük Expired% daha iyidir**
- Expired artışı genelde *emirlerin pasif kalması / fill olamaması* ile ilişkilidir.
- Seçilen tarih aralığı için **emir sayısı ile ağırlıklı ortalama** alınır.
""",
    "Cancel/Trade (w.avg)": r"""
**Formül**
\[
Cancel/Trade = \frac{CanceledByUser\%}{Trade\%}
\]

**Yorum**
- **Düşük oran daha iyidir**
- Trade düşükken Cancel yüksekse bu oran büyür ⇒ execution verimsizliği sinyali
- Seçilen tarih aralığı için **emir sayısı ile ağırlıklı ortalama** alınır.
""",
}


# -----------------------------
# BIST100 list (with .E suffix)
# -----------------------------
BIST100 = [
    "AEFES.E", "AGHOL.E", "AKBNK.E", "AKSA.E", "AKSEN.E", "ALARK.E", "ALTNY.E", "ANSGR.E", "ARCLK.E", "ASELS.E", "ASTOR.E", "BALSU.E",
    "BIMAS.E", "BRSAN.E", "BRYAT.E", "BSOKE.E", "BTCIM.E", "CANTE.E", "CCOLA.E", "CIMSA.E", "CWENE.E", "DAPGM.E", "DOAS.E", "DOHOL.E",
    "DSTKF.E", "ECILC.E", "EFOR.E", "EGEEN.E", "EKGYO.E", "ENERY.E", "ENJSA.E", "ENKAI.E", "EREGL.E", "EUPWR.E", "FENER.E", "FROTO.E",
    "GARAN.E", "GENIL.E", "GESAN.E", "GLRMK.E", "GRSEL.E", "GRTHO.E", "GSRAY.E", "GUBRF.E", "HALKB.E", "HEKTS.E", "ISCTR.E", "ISMEN.E",
    "IZENR.E", "KCAER.E", "KCHOL.E", "KLRHO.E", "KONTR.E", "KRDMD.E", "KTLEV.E", "KUYAS.E", "MAGEN.E", "MAVI.E", "MGROS.E", "MIATK.E",
    "MPARK.E", "OBAMS.E", "ODAS.E", "OTKAR.E", "OYAKC.E", "PASEU.E", "PATEK.E", "PETKM.E", "PGSUS.E", "QUAGR.E", "RALYH.E", "REEDR.E",
    "SAHOL.E", "SASA.E", "SISE.E", "SKBNK.E", "SOKM.E", "TABGD.E", "TAVHL.E", "TCELL.E", "THYAO.E", "TKFEN.E", "TOASO.E", "TRALT.E",
    "TRENJ.E", "TRMET.E", "TSKB.E", "TSPOR.E", "TTKOM.E", "TTRAK.E", "TUKAS.E", "TUPRS.E", "TUREX.E", "TURSG.E", "ULKER.E", "VAKBN.E",
    "VESTL.E", "YEOTK.E", "YKBNK.E", "ZOREN.E"
]

# -----------------------------
# Metrics
# -----------------------------
METRICS = {
    "EQS (w.avg)": {
        "label": "EQS = Trade% - CanceledByUser% - Expired% (volume-weighted)",
        "better_high": True,
    },
    "Trade% (w.avg)": {
        "label": "Trade% (volume-weighted)",
        "better_high": True,
    },
    "CanceledByUser% (w.avg)": {
        "label": "CanceledByUser% (volume-weighted) — lower is better",
        "better_high": False,
    },
    "Expired% (w.avg)": {
        "label": "Expired% (volume-weighted) — lower is better",
        "better_high": False,
    },
    "Cancel/Trade (w.avg)": {
        "label": "CanceledByUser% / Trade% (volume-weighted) — lower is better",
        "better_high": False,
    },
}

# -----------------------------
# Load parquet (cached)
# -----------------------------
@st.cache_data(show_spinner=False)
def load_all_daily_states(parquet_path: str) -> pd.DataFrame:
    # NOTE: DuckDB cannot open ":memory:" in read_only mode
    con = duckdb.connect(database=":memory:")
    df = con.execute(f"SELECT * FROM read_parquet('{parquet_path}')").fetchdf()

    df["tarih"] = pd.to_datetime(df["tarih"])
    df["yuzde"] = pd.to_numeric(df["yuzde"], errors="coerce").fillna(0.0)
    df["emir_sayisi"] = pd.to_numeric(df["emir_sayisi"], errors="coerce").fillna(0.0)
    df["islem_kodu"] = df["islem_kodu"].astype(str)
    df["final_state"] = df["final_state"].astype(str)

    return df


# -----------------------------
# Helpers
# -----------------------------
def metric_card(title: str, value: str, subtitle: str = ""):
    subtitle_html = f'<div style="font-size:12px; opacity:0.75; margin-top:6px;">{subtitle}</div>' if subtitle else ""
    st.markdown(
        f"""
        <div style="
            padding: 14px 16px;
            border-radius: 14px;
            border: 1px solid rgba(49, 51, 63, 0.18);
            background: rgba(240, 242, 246, 0.70);
            margin-bottom: 10px;
        ">
            <div style="font-size:13px; opacity:0.75; margin-bottom:6px;">
                {title}
            </div>
            <div style="font-size:28px; font-weight:800; line-height:1.15;">
                {value}
            </div>
            {subtitle_html}
        </div>
        """,
        unsafe_allow_html=True
    )

def add_week_index(df: pd.DataFrame, n_days: int = 20) -> pd.DataFrame:
    out = df.copy()
    out["tarih"] = pd.to_datetime(out["tarih"])
    days = sorted(out["tarih"].unique())[:n_days]
    day2idx = {d: i for i, d in enumerate(days)}
    out = out[out["tarih"].isin(days)].copy()
    out["gun_idx"] = out["tarih"].map(day2idx)
    out["hafta"] = (out["gun_idx"] // 5) + 1
    out["tarih_str"] = out["tarih"].dt.strftime("%Y-%m-%d")
    return out

def calc_month_references(df_daily: pd.DataFrame):
    d = df_daily.copy()
    d["tarih"] = pd.to_datetime(d["tarih"])
    n_days = int(d["tarih"].nunique()) if d["tarih"].nunique() else 1

    month_cnt = d.groupby("final_state", as_index=False)["emir_sayisi"].sum()
    total = float(month_cnt["emir_sayisi"].sum())
    month_pct = month_cnt.copy()
    month_pct["yuzde"] = (100.0 * month_pct["emir_sayisi"] / total) if total else 0.0

    month_cnt_daily_avg = month_cnt.copy()
    month_cnt_daily_avg["emir_sayisi"] = month_cnt_daily_avg["emir_sayisi"] / n_days

    return month_pct, month_cnt_daily_avg, n_days

def black_ref_bar(name: str, x, y):
    return go.Bar(
        name=name,
        x=x,
        y=y,
        marker=dict(color="black", opacity=0.45, line=dict(color="black", width=3)),
    )

def filter_period(df_all: pd.DataFrame, start_date: pd.Timestamp, end_date: pd.Timestamp) -> pd.DataFrame:
    return df_all[(df_all["tarih"] >= start_date) & (df_all["tarih"] <= end_date)].copy()

def compute_bist100_metric(df_all: pd.DataFrame, stocks: list[str], start_date: pd.Timestamp, end_date: pd.Timestamp, metric_key: str):
    df = df_all[
        (df_all["islem_kodu"].isin(stocks)) &
        (df_all["tarih"] >= start_date) &
        (df_all["tarih"] <= end_date)
    ].copy()

    if df.empty:
        return pd.DataFrame(columns=["islem_kodu", "metric_wavg", "total_emir_period"]), METRICS[metric_key]["better_high"]

    # daily pivot: percentages and counts per state
    daily = (df.pivot_table(index=["tarih", "islem_kodu"], columns="final_state",
                            values=["yuzde", "emir_sayisi"], aggfunc="sum")
             .fillna(0))
    daily.columns = [f"{a}_{b}" for a, b in daily.columns]
    daily = daily.reset_index()

    daily["trade_pct"] = daily.get("yuzde_Trade", 0.0)
    daily["cancel_pct"] = daily.get("yuzde_CanceledByUser", 0.0)
    daily["expired_pct"] = daily.get("yuzde_Expired", 0.0)

    emir_cols = [c for c in daily.columns if c.startswith("emir_sayisi_")]
    daily["total_emir"] = daily[emir_cols].sum(axis=1)

    if metric_key == "EQS (w.avg)":
        daily["metric_value"] = daily["trade_pct"] - daily["cancel_pct"] - daily["expired_pct"]
    elif metric_key == "Trade% (w.avg)":
        daily["metric_value"] = daily["trade_pct"]
    elif metric_key == "CanceledByUser% (w.avg)":
        daily["metric_value"] = daily["cancel_pct"]
    elif metric_key == "Expired% (w.avg)":
        daily["metric_value"] = daily["expired_pct"]
    elif metric_key == "Cancel/Trade (w.avg)":
        daily["metric_value"] = daily["cancel_pct"] / daily["trade_pct"].replace(0, pd.NA)
        daily["metric_value"] = daily["metric_value"].fillna(0.0)
    else:
        daily["metric_value"] = daily["trade_pct"] - daily["cancel_pct"] - daily["expired_pct"]

    better_high = METRICS[metric_key]["better_high"]

    # volume-weighted average over the period
    def wavg(g):
        w = g["total_emir"]
        denom = float(w.sum())
        if denom <= 0:
            return pd.Series({"metric_wavg": 0.0, "total_emir_period": 0.0})
        return pd.Series({
            "metric_wavg": float((g["metric_value"] * w).sum() / denom),
            "total_emir_period": float(denom),
        })

    out = daily.groupby("islem_kodu", as_index=False).apply(wavg).reset_index(drop=True)
    out = out.sort_values("metric_wavg", ascending=better_high is False)  # if better_high False, sort ascending

    return out, better_high

# -----------------------------
# Sidebar
# -----------------------------

# -----------------------------
# Load parquet once (cached)
# -----------------------------
try:
    df_all = load_all_daily_states(PARQUET_PATH)
except Exception as e:
    st.error(f"Parquet okunamadı: {e}")
    st.stop()

# Auto date range from data (no UI)
min_date = df_all["tarih"].min()
max_date = df_all["tarih"].max()
start_date = min_date
end_date = max_date

# Available BIST100 tickers in parquet
available_stocks = sorted(set(df_all["islem_kodu"].unique()).intersection(BIST100))
if not available_stocks:
    available_stocks = sorted(df_all["islem_kodu"].unique())
st.title("BIST100 Emir Defteri Final State Analizi (Kasım 2025)")
st.markdown("## 📌 Dashboard Hakkında")
st.markdown("""
Bu dashboard, **BIST 100 endeksinde yer alan hisselerin 2025 Kasım ayı boyunca işlem gören emir defteri verileri**
üzerinden hazırlanmıştır. Amaç, emirlerin gün içindeki davranışlarını ve sonuçlarını **emir yaşam döngüsü (order lifecycle)**
perspektifinden incelemektir.

Emirler gün içinde birden fazla güncellenebilir ve farklı ara durumlara uğrayabilir. Ancak bu uygulamada temel yaklaşım,
emirlerin gün sonunda ulaştığı **final state (son durum)** dağılımını analiz etmektir.

Beklenti çoğu hisse için emirlerin büyük bölümünün **Trade** veya **CanceledByUser** ile sonlanmasıdır.
Gün sonuna kadar işleme dönüşmeyen emirler **Expired** olarak kapanır.

Bu final state dağılımlarından türetilen metrikler ile **hisseler arası karşılaştırma** ve hisse bazında
**günlük/haftalık detay analiz** yapılabilir.
""")
st.markdown("## 🧾 Final State Tanımları")

s1, s2, s3, s4 = st.columns(4)

with s1:
    metric_card("Trade", "İşlem gördü", "Emir karşı tarafla eşleşerek gerçekleşti.")

with s2:
    metric_card("CanceledByUser", "Kullanıcı iptali", "Emir kullanıcı tarafından iptal edilerek sonlandı.")

with s3:
    metric_card("Expired", "Süresi doldu", "Gün sonuna kadar işleme dönüşmedi ve kapandı.")

with s4:
    metric_card("New", "Açık/başlangıç", "Bazı emirler final state olarak New kalabilir (snapshot/veri nedeni).")




# -----------------------------
# Top controls (no sidebar)
# -----------------------------
ctrl1, ctrl2, ctrl3 = st.columns([1.4, 1.4, 1.2])

with ctrl1:
    metric_key = st.selectbox("Ana sayfa metriği", list(METRICS.keys()), index=0)


with ctrl2:
    st.markdown("**Kapsam**")
    st.markdown(
        f"""
        <div style="
            display:inline-block;
            padding: 8px 12px;
            border-radius: 999px;
            border: 1px solid rgba(49, 51, 63, 0.20);
            background: rgba(240, 242, 246, 0.70);
            font-size: 14px;
            font-weight: 700;
        ">
            {start_date.strftime('%Y-%m-%d')} → {end_date.strftime('%Y-%m-%d')}
        </div>
        """,
        unsafe_allow_html=True
    )

st.markdown(
    f"""
<div style="
    padding: 14px 16px;
    border-radius: 12px;
    border: 1px solid rgba(49, 51, 63, 0.2);
    background: rgba(240, 242, 246, 0.65);
    margin-top: 10px;
    margin-bottom: 10px;
">
    <div style="font-size: 13px; opacity: 0.8; margin-bottom: 6px;">
        Ana sayfa metriği
    </div>
    <div style="font-size: 18px; font-weight: 700; margin-bottom: 6px;">
        {metric_key}
    </div>
    <div style="font-size: 14px; opacity: 0.95;">
        {METRICS[metric_key]['label']}
    </div>
</div>
""",
    unsafe_allow_html=True
)

with st.expander("Metrik detayı (formül ve yorum)", expanded=False):
    detail_md = METRIC_DETAILS_MD.get(metric_key, "")
    if detail_md:
        st.markdown(detail_md)
    else:
        st.write("Detay bulunamadı.")


# -----------------------------
# 1) Comparison
# -----------------------------
st.subheader("1) BIST100 Karşılaştırma")

metric_df, _ = compute_bist100_metric(df_all, available_stocks if available_stocks else BIST100, start_date, end_date, metric_key)

k1, k2, k3 = st.columns(3)

with k1:
    metric_card("Hisse Sayısı", str(len(metric_df)), "BIST100 içinde hesaplanan")

with k2:
    total_emir_all = int(metric_df["total_emir_period"].sum()) if not metric_df.empty else 0
    metric_card("Toplam Emir", f"{total_emir_all:,}".replace(",", "."), "Seçili kapsam (tüm hisseler)")

with k3:
    direction = "Yüksek daha iyi" if METRICS[metric_key]["better_high"] else "Düşük daha iyi"
    metric_card("Metrik Yönü", direction, metric_key)


tabA, tabB, tabC = st.tabs(["Bar (Ranking)", "Scatter (Metrik vs Hacim)", "Tablo"])

with tabA:
    if metric_df.empty:
        st.warning("Bu aralıkta veri yok.")
    else:
        fig = px.bar(
            metric_df,
            x="islem_kodu",
            y="metric_wavg",
            hover_data=["total_emir_period"],
            title=METRICS[metric_key]["label"],
            labels={"islem_kodu": "Hisse", "metric_wavg": metric_key, "total_emir_period": "Toplam Emir (Period)"},
        )
        fig.update_layout(xaxis_tickangle=-45, height=520)
        st.plotly_chart(fig, use_container_width=True)

with tabB:
    if metric_df.empty:
        st.warning("Bu aralıkta veri yok.")
    else:
        fig = px.scatter(
            metric_df,
            x="total_emir_period",
            y="metric_wavg",
            hover_name="islem_kodu",
            title=f"{metric_key} vs Toplam Emir (Period)",
            labels={"total_emir_period": "Toplam Emir (Period)", "metric_wavg": metric_key},
        )
        fig.update_layout(height=520)
        st.plotly_chart(fig, use_container_width=True)

with tabC:
    st.dataframe(metric_df, use_container_width=True)

# -----------------------------
# 2) Stock detail
# -----------------------------
st.subheader("2) Hisse Detayı")

default_hisse = "AKBNK.E" if "AKBNK.E" in available_stocks else available_stocks[0]
hisse = st.selectbox("Hisse seç", available_stocks, index=available_stocks.index(default_hisse))

df_period = filter_period(df_all, start_date, end_date)
dfh = df_period[df_period["islem_kodu"] == hisse].copy()

if dfh.empty:
    st.warning("Seçili hisse ve tarih aralığı için veri bulunamadı.")
    st.stop()

month_pct, month_cnt_daily_avg, n_days = calc_month_references(dfh)
state_order = month_pct.sort_values("emir_sayisi", ascending=False)["final_state"].tolist()

c1, c2, c3 = st.columns(3)

with c1:
    metric_card("Seçili Hisse", hisse, "Detay analiz")

with c2:
    metric_card("Gün Sayısı", str(n_days), "Seçili kapsam içinde")

with c3:
    total_emir_period = int(dfh.groupby("tarih")["emir_sayisi"].sum().sum())
    metric_card("Toplam Emir", f"{total_emir_period:,}".replace(",", "."), "Seçili kapsam içinde")


# Weekly (assume first 20 trading days => 4 weeks)
dfw = add_week_index(dfh, n_days=20)


st.markdown("### Hafta hafta ortalama Final State %")
weekly_pct = dfw.groupby(["hafta", "final_state"], as_index=False)["yuzde"].mean()

fig1 = go.Figure()
for w in [1, 2, 3, 4]:
    sub = (weekly_pct[weekly_pct["hafta"] == w]
            .set_index("final_state")
            .reindex(state_order)
            .fillna(0))
    fig1.add_trace(go.Bar(name=f"Hafta {w} (Ort.)", x=state_order, y=sub["yuzde"].values))

mref_pct = (month_pct.set_index("final_state").reindex(state_order).fillna(0))
fig1.add_trace(black_ref_bar(f"Ay Toplamı ({start_date.strftime('%Y-%m-%d')}→{end_date.strftime('%Y-%m-%d')})",
                                state_order, mref_pct["yuzde"].values))

fig1.update_layout(
    barmode="group",
    height=520,
    title="Hafta Hafta Ortalama % + Ay Toplamı",
    xaxis_title="Final State",
    yaxis_title="Yüzde",
    yaxis=dict(range=[0, 100]),
    legend_title="Seriler",
)
st.plotly_chart(fig1, use_container_width=True)

st.markdown("### Hafta hafta Final State Emir Sayısı")
weekly_cnt = dfw.groupby(["hafta", "final_state"], as_index=False)["emir_sayisi"].sum()

fig2 = go.Figure()
for w in [1, 2, 3, 4]:
    sub = (weekly_cnt[weekly_cnt["hafta"] == w]
            .set_index("final_state")
            .reindex(state_order)
            .fillna(0))
    fig2.add_trace(go.Bar(name=f"Hafta {w} (Toplam)", x=state_order, y=sub["emir_sayisi"].values))

# Monthly reference for weekly counts: daily avg * 5 (benchmark)
mref_week = (month_cnt_daily_avg.set_index("final_state").reindex(state_order).fillna(0)).copy()
mref_week["emir_sayisi"] = mref_week["emir_sayisi"] * 5
fig2.add_trace(black_ref_bar("Ay Ort. (5 gün beklenen)", state_order, mref_week["emir_sayisi"].values))

fig2.update_layout(
    barmode="group",
    height=520,
    title="Hafta Hafta Toplam Emir + Ay Ort. (5 gün beklenen)",
    xaxis_title="Final State",
    yaxis_title="Emir Sayısı",
    legend_title="Seriler",
)
st.plotly_chart(fig2, use_container_width=True)

# Daily views (select week)
st.markdown("### Günlük Görünüm")
week_sel = st.radio("Hafta seç", [1, 2, 3, 4], horizontal=True, index=0)

df_week = dfw[dfw["hafta"] == week_sel].copy()
days = sorted(df_week["tarih"].unique())


st.markdown(f"#### Hafta {week_sel} — Günlük Final State %")
fig3 = go.Figure()
for d in days:
    dstr = pd.to_datetime(d).strftime("%Y-%m-%d")
    sub = (df_week[df_week["tarih"] == d]
            .set_index("final_state")
            .reindex(state_order)
            .fillna(0))
    fig3.add_trace(go.Bar(name=dstr, x=state_order, y=sub["yuzde"].values))

fig3.add_trace(black_ref_bar("Ay Toplamı", state_order, mref_pct["yuzde"].values))
fig3.update_layout(
    barmode="group",
    height=520,
    title=f"Hafta {week_sel} — Günlük % + Ay Toplamı",
    xaxis_title="Final State",
    yaxis_title="Yüzde",
    yaxis=dict(range=[0, 100]),
    legend_title="Seriler",
)
st.plotly_chart(fig3, use_container_width=True)

st.markdown(f"#### Hafta {week_sel} — Günlük Final State Emir Sayısı")
fig4 = go.Figure()
for d in days:
    dstr = pd.to_datetime(d).strftime("%Y-%m-%d")
    sub = (df_week[df_week["tarih"] == d]
            .set_index("final_state")
            .reindex(state_order)
            .fillna(0))
    fig4.add_trace(go.Bar(name=dstr, x=state_order, y=sub["emir_sayisi"].values))

# Monthly reference for daily counts: daily avg per state
mref_daily = (month_cnt_daily_avg.set_index("final_state").reindex(state_order).fillna(0))
fig4.add_trace(black_ref_bar("Ay Günlük Ort.", state_order, mref_daily["emir_sayisi"].values))

fig4.update_layout(
    barmode="group",
    height=520,
    title=f"Hafta {week_sel} — Günlük Emir Sayısı + Ay Günlük Ort.",
    xaxis_title="Final State",
    yaxis_title="Emir Sayısı",
    legend_title="Seriler",
)
st.plotly_chart(fig4, use_container_width=True)

# Raw table (optional)
with st.expander("Seçili hisse için ham aggregated veri", expanded=SHOW_TABLE_DEFAULT):
    st.dataframe(dfh.sort_values(["tarih", "emir_sayisi"], ascending=[True, False]), use_container_width=True)
