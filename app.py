import streamlit as st
import pandas as pd
import plotly.express as px

st.set_page_config(
    page_title="West Bengal Elections 2019–2026",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
/* Horizontal scroll on wide tables */
[data-testid="stDataFrame"] > div { overflow-x: auto; }
/* Bigger touch targets for selects and radio buttons */
[data-testid="stSelectbox"] > div,
[data-testid="stRadio"]     > div { min-height: 44px; }
/* Tighten chart padding on small screens */
@media (max-width: 640px) {
    [data-testid="stPlotlyChart"] { padding: 0 !important; }
    h2, h3 { font-size: 1.1rem !important; }
}
</style>
""", unsafe_allow_html=True)

_TMC = {"AITC", "AITMC", "TMC", "TRINAMOOL"}

def norm(p):
    if pd.isna(p):
        return "UNKNOWN"
    s = str(p).strip().upper()
    return "TMC" if s in _TMC else s

# Maps election district names → demography district name
# Newer districts (Alipurduar, Jhargram, Kalimpong) have no demography entry
_DISTRICT_MAP = {
    "Coochbehar":       "Koch Bihar",
    "Paschim Bardhaman": "Barddhaman",
    "Purba Bardhaman":  "Barddhaman",
    "Purbo Medinipur":  "Purba Medinipur",
    "Kolkata North":    "Kolkata",
    "Kolkata South":    "Kolkata",
}


# ── Raw loaders ────────────────────────────────────────────────────────────────

@st.cache_data(show_spinner="Reading 2019 Lok Sabha data …")
def raw_2019():
    df = pd.read_excel(
        "425581050_34.DetailsOfAssemblySegmentOfPC 2019.xls",
        header=2, dtype=str, engine="calamine",
    )
    df.columns = ["state", "pc_no", "pc_name", "ac_no", "ac_name",
                  "electors", "_ts", "nota", "cand", "party", "votes"]
    df = df[df["state"].str.contains("West Bengal", case=False, na=False)].copy()
    for c in ["ac_no", "electors", "nota", "votes"]:
        df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0)
    df["party"] = df["party"].apply(norm)
    return df[["ac_no", "ac_name", "electors", "nota", "party", "votes"]]


@st.cache_data(show_spinner="Reading 2021 Vidhan Sabha data …")
def raw_2021():
    df = pd.read_excel("10-Detailed Results 2021.xlsx", header=3, dtype=str)
    df.columns = df.columns.str.strip()
    df = df[df["STATE/UT NAME"].str.contains("West Bengal", case=False, na=False)].copy()
    df = df.rename(columns={
        "AC NO.": "ac_no", "AC NAME": "ac_name",
        "PARTY": "party", "TOTAL": "votes", "TOTAL ELECTORS": "electors",
    })
    for c in ["ac_no", "electors", "votes"]:
        df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0)
    df["party"] = df["party"].apply(norm)
    return df[["ac_no", "ac_name", "electors", "party", "votes"]]


@st.cache_data(show_spinner="Reading 2024 Lok Sabha data …")
def raw_2024():
    df = pd.read_excel(
        "34-Details-Of-Assembly-Segment-Of-PC 2024.xls",
        header=1, dtype=str, engine="calamine",
    )
    df.columns = ["state", "pc_no", "pc_name", "_elpc", "ac_no", "ac_name",
                  "electors", "_ts", "nota", "cand", "party", "votes"]
    df = df[df["state"].str.contains("West Bengal", case=False, na=False)].copy()
    for c in ["ac_no", "electors", "nota", "votes"]:
        df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0)
    df["party"] = df["party"].apply(norm)
    return df[["ac_no", "ac_name", "electors", "nota", "party", "votes"]]


@st.cache_data(show_spinner="Reading 2026 polling data …")
def raw_2026():
    df = pd.read_csv("combined_wb_election_data_2026.csv")
    df = df.rename(columns={
        "AC No.": "ac_no", "District Name": "district",
        "ac_name": "ac_name", "Total": "electors", "Total Votes": "votes",
        "Male": "male", "Female": "female", "Third Gender": "third_gender",
    })
    df["district"] = df["district"].str.title()
    for c in ["ac_no", "electors", "votes", "male", "female", "third_gender"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    return df[["ac_no", "ac_name", "district", "electors", "votes", "male", "female", "third_gender"]]


@st.cache_data(show_spinner="Reading demography data …")
def load_demography():
    df = pd.read_csv("demography.csv")
    df.columns = df.columns.str.strip()
    df = df.set_index("District")
    return df   # index = demography district name, cols = Hindu(%), Muslim(%), …


@st.cache_data(show_spinner="Reading constituency demography …")
def load_demography_ac():
    df = pd.read_csv("demography new.csv")
    df.columns = df.columns.str.strip()
    df = df.rename(columns={
        "Constituency No.": "ac_no",
        "Hindu %":           "hindu_pct",
        "Muslim %":          "muslim_pct",
        "Christian %":       "christian_pct",
        "Buddhist / Other %": "buddhist_pct",
        "Majority Religion": "majority",
    })
    df["ac_no"] = pd.to_numeric(df["ac_no"], errors="coerce")
    return df[["ac_no", "hindu_pct", "muslim_pct", "christian_pct", "buddhist_pct", "majority"]]


# ── Aggregation ────────────────────────────────────────────────────────────────

def agg_year(df, has_nota):
    rows = []
    for (ac_no, ac_name), g in df.groupby(["ac_no", "ac_name"], sort=True):
        el = g["electors"].iloc[0]
        nota_val = g["nota"].iloc[0] if has_nota else 0
        tv = g["votes"].sum() + nota_val
        tmc = g.loc[g["party"] == "TMC", "votes"].sum()
        bjp = g.loc[g["party"] == "BJP", "votes"].sum()
        top3 = (
            g[~g["party"].isin({"TMC", "BJP", "NOTA", "UNKNOWN"})]
            .groupby("party")["votes"].sum()
            .nlargest(3)
        )
        r = {"ac_no": int(ac_no), "ac_name": str(ac_name),
             "electors": el, "total_votes": tv, "tmc": tmc, "bjp": bjp}
        for i, (p, v) in enumerate(top3.items(), 1):
            r[f"p{i}"] = p
            r[f"v{i}"] = v
        rows.append(r)
    return pd.DataFrame(rows)


@st.cache_data(show_spinner="Building master dataset …")
def load_master():
    a19 = agg_year(raw_2019(), True)
    a21 = agg_year(raw_2021(), False)
    a24 = agg_year(raw_2024(), True)
    r26 = raw_2026()

    m = r26.rename(columns={
        "electors": "electors_26", "votes": "votes_26",
        "male": "male_26", "female": "female_26", "third_gender": "third_26",
    })
    for yr, agg in [("19", a19), ("21", a21), ("24", a24)]:
        tmp = agg.drop(columns=["ac_name"]).rename(
            columns={c: f"{c}_{yr}" for c in agg.columns if c not in ("ac_no", "ac_name")}
        )
        m = m.merge(tmp, on="ac_no", how="left")
    m = m.merge(load_demography_ac(), on="ac_no", how="left")
    return m


# ── Formatting helpers ─────────────────────────────────────────────────────────

def fmt(n):
    try:
        return f"{int(n):,}"
    except (TypeError, ValueError):
        return "—"


def pct(n, d):
    try:
        return f"{float(n) / float(d) * 100:.1f}%"
    except (TypeError, ValueError, ZeroDivisionError):
        return "—"


YEARS = [("19", "2019", "Lok Sabha"), ("21", "2021", "Vidhan Sabha"), ("24", "2024", "Lok Sabha")]

_DEMO_COLS   = ["hindu_pct", "muslim_pct", "christian_pct", "buddhist_pct", "majority"]
_DEMO_LABELS = {
    "hindu_pct":    "Hindu %",
    "muslim_pct":   "Muslim %",
    "christian_pct":"Christian %",
    "buddhist_pct": "Buddhist/Other %",
    "majority":     "Majority",
}


# ── Gender helpers ─────────────────────────────────────────────────────────────

def gender_metrics(male, female, third):
    """Render male/female/third-gender voter counts and M:F ratio as st.metrics."""
    try:
        ratio = float(male) / float(female) * 1000
        ratio_str = f"{ratio:.0f} per 1,000 females"
    except (TypeError, ValueError, ZeroDivisionError):
        ratio_str = "—"

    c1, c2 = st.columns(2)
    c1.metric("Male voters",         fmt(male))
    c2.metric("Female voters",       fmt(female))
    c3, c4 = st.columns(2)
    c3.metric("Third-gender voters", fmt(third))
    c4.metric("M : F ratio (2026)",  ratio_str)


# ── Demography helper ──────────────────────────────────────────────────────────

def show_demography(election_district):
    dem = load_demography()
    dem_district = _DISTRICT_MAP.get(election_district, election_district)

    st.markdown("#### Religious Demography")
    if dem_district not in dem.index:
        st.caption(f"No demography data for {election_district} (district created after 2011 census).")
        return

    row = dem.loc[dem_district]
    note = f" (census data for undivided {dem_district})" if election_district != dem_district else ""
    st.caption(f"District: **{dem_district}**{note}")

    st.dataframe(
        row.reset_index().rename(columns={"index": "Religion", dem_district: "%"}),
        use_container_width=True, hide_index=True,
    )
    fig = px.pie(
        values=row.values,
        names=row.index,
        color=row.index,
        color_discrete_map={
            "Hindu (%)": "#FF9933", "Muslim (%)": "#009900",
            "Christian (%)": "#3399FF", "Others (%)": "#999999",
        },
        title=f"Religious composition — {dem_district}",
    )
    fig.update_layout(height=280, margin=dict(t=40, b=0))
    st.plotly_chart(fig, use_container_width=True)


# ── Constituency view ──────────────────────────────────────────────────────────

def show_constituency(row):
    st.subheader(f"AC {int(row['ac_no'])}: {row['ac_name']}  —  {row['district']}")

    table, bar_data = [], []
    for yr, full, etype in YEARS:
        el  = row.get(f"electors_{yr}")
        tv  = row.get(f"total_votes_{yr}")
        tmc = row.get(f"tmc_{yr}")
        bjp = row.get(f"bjp_{yr}")
        others = []
        for i in range(1, 4):
            p, v = row.get(f"p{i}_{yr}"), row.get(f"v{i}_{yr}")
            if pd.notna(p) and pd.notna(v):
                others.append(f"{p}: {fmt(v)} ({pct(v, tv)})")
        table.append({
            "Year": full, "Election": etype,
            "Voters": fmt(el), "Votes Cast": fmt(tv), "Turnout": pct(tv, el),
            "TMC": fmt(tmc), "TMC %": pct(tmc, tv),
            "BJP": fmt(bjp), "BJP %": pct(bjp, tv),
            "Others": "  |  ".join(others) or "—",
        })
        try:
            bar_data += [
                {"Year": full, "Party": "TMC", "Vote %": float(tmc) / float(tv) * 100},
                {"Year": full, "Party": "BJP", "Vote %": float(bjp) / float(tv) * 100},
            ]
        except (TypeError, ValueError):
            pass

    el26, tv26 = row.get("electors_26"), row.get("votes_26")
    table.append({
        "Year": "2026", "Election": "Vidhan Sabha",
        "Voters": fmt(el26), "Votes Cast": fmt(tv26), "Turnout": pct(tv26, el26),
        "TMC": "—", "TMC %": "—", "BJP": "—", "BJP %": "—", "Others": "—",
    })

    st.dataframe(pd.DataFrame(table), use_container_width=True, hide_index=True)

    if bar_data:
        tab1, tab2 = st.tabs(["TMC vs BJP Trend", "2024 Vote Breakdown"])
        with tab1:
            fig = px.bar(
                pd.DataFrame(bar_data), x="Year", y="Vote %", color="Party",
                barmode="group",
                color_discrete_map={"TMC": "#2CA02C", "BJP": "#FF7F0E"},
                title="TMC vs BJP Vote Share (%)",
            )
            fig.update_layout(yaxis_range=[0, 100], height=360)
            st.plotly_chart(fig, use_container_width=True)
        with tab2:
            pie_rows = []
            yr = "24"
            for key, label in [(f"tmc_{yr}", "TMC"), (f"bjp_{yr}", "BJP")]:
                v = row.get(key)
                if pd.notna(v):
                    pie_rows.append({"Party": label, "Votes": float(v)})
            for i in range(1, 4):
                p, v = row.get(f"p{i}_{yr}"), row.get(f"v{i}_{yr}")
                if pd.notna(p) and pd.notna(v):
                    pie_rows.append({"Party": p, "Votes": float(v)})
            if pie_rows:
                fig2 = px.pie(
                    pd.DataFrame(pie_rows), names="Party", values="Votes",
                    title="2024 (Lok Sabha) Vote Breakdown",
                    color_discrete_map={"TMC": "#2CA02C", "BJP": "#FF7F0E"},
                )
                fig2.update_layout(height=360)
                st.plotly_chart(fig2, use_container_width=True)

    st.divider()
    st.markdown("#### 2026 Voter Demographics")
    gender_metrics(row.get("male_26"), row.get("female_26"), row.get("third_26"))

    st.markdown("#### Religious Demography")
    dem_vals = {lbl: row.get(col) for col, lbl in _DEMO_LABELS.items()}
    if any(pd.notna(v) for v in dem_vals.values()):
        d1, d2 = st.columns(2)
        with d1:
            st.dataframe(
                pd.DataFrame(list(dem_vals.items()), columns=["Religion / Category", "Share"]),
                use_container_width=True, hide_index=True,
            )
        with d2:
            pie_data = {k: float(str(v).replace("%","")) for k, v in dem_vals.items()
                        if k != "Majority" and pd.notna(v)}
            if pie_data:
                fig = px.pie(
                    values=list(pie_data.values()), names=list(pie_data.keys()),
                    color=list(pie_data.keys()),
                    color_discrete_map={
                        "Hindu %": "#FF9933", "Muslim %": "#009900",
                        "Christian %": "#3399FF", "Buddhist/Other %": "#999999",
                    },
                    title=f"Religious composition — {row['ac_name']}",
                )
                fig.update_layout(height=280, margin=dict(t=40, b=0))
                st.plotly_chart(fig, use_container_width=True)
    else:
        st.caption("No constituency-level demography data available.")


# ── District view ──────────────────────────────────────────────────────────────

def show_district(df, district):
    sub = df[df["district"] == district].copy()
    st.subheader(f"District: {district}  ({len(sub)} constituencies)")

    sum_rows = []
    bar_data = []
    for yr, full, etype in YEARS:
        el  = pd.to_numeric(sub[f"electors_{yr}"],   errors="coerce").sum()
        tv  = pd.to_numeric(sub[f"total_votes_{yr}"], errors="coerce").sum()
        tmc = pd.to_numeric(sub[f"tmc_{yr}"],         errors="coerce").sum()
        bjp = pd.to_numeric(sub[f"bjp_{yr}"],         errors="coerce").sum()
        sum_rows.append({
            "Year": full, "Election": etype,
            "Voters": fmt(el), "Votes Cast": fmt(tv), "Turnout": pct(tv, el),
            "TMC": fmt(tmc), "TMC %": pct(tmc, tv),
            "BJP": fmt(bjp), "BJP %": pct(bjp, tv),
        })
        try:
            bar_data += [
                {"Year": full, "Party": "TMC", "Vote %": tmc / tv * 100},
                {"Year": full, "Party": "BJP", "Vote %": bjp / tv * 100},
            ]
        except (TypeError, ValueError, ZeroDivisionError):
            pass

    el26 = pd.to_numeric(sub["electors_26"], errors="coerce").sum()
    tv26 = pd.to_numeric(sub["votes_26"],    errors="coerce").sum()
    sum_rows.append({
        "Year": "2026", "Election": "Vidhan Sabha",
        "Voters": fmt(el26), "Votes Cast": fmt(tv26), "Turnout": pct(tv26, el26),
        "TMC": "—", "TMC %": "—", "BJP": "—", "BJP %": "—",
    })

    st.markdown("**District Totals**")
    st.dataframe(pd.DataFrame(sum_rows), use_container_width=True, hide_index=True)

    if bar_data:
        fig = px.bar(
            pd.DataFrame(bar_data), x="Year", y="Vote %", color="Party",
            barmode="group",
            color_discrete_map={"TMC": "#2CA02C", "BJP": "#FF7F0E"},
            title=f"{district}: TMC vs BJP Vote Share (%)",
        )
        fig.update_layout(yaxis_range=[0, 100])
        st.plotly_chart(fig, use_container_width=True)

    st.markdown("**Constituency-wise Vote Share**")
    rows = []
    for _, r in sub.sort_values("ac_no").iterrows():
        row = {"AC No": int(r["ac_no"]), "Constituency": r["ac_name"]}
        for yr, full, _ in YEARS:
            tv  = r.get(f"total_votes_{yr}")
            tmc = r.get(f"tmc_{yr}")
            bjp = r.get(f"bjp_{yr}")
            row[f"TMC {full}%"] = pct(tmc, tv)
            row[f"BJP {full}%"] = pct(bjp, tv)
        row["2026 Turnout"] = pct(r.get("votes_26"), r.get("electors_26"))
        for col, lbl in _DEMO_LABELS.items():
            row[lbl] = r.get(col)
        rows.append(row)
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    st.divider()
    st.markdown("#### 2026 Voter Demographics")
    male  = pd.to_numeric(sub["male_26"],   errors="coerce").sum()
    female= pd.to_numeric(sub["female_26"], errors="coerce").sum()
    third = pd.to_numeric(sub["third_26"],  errors="coerce").sum()
    gender_metrics(male, female, third)
    show_demography(district)


# ── Shared impact computation ─────────────────────────────────────────────────

def compute_impacts(df):
    def _n(v):
        try:    return float(v)
        except: return 0.0

    imp21, imp24 = [], []
    for _, r in df.iterrows():
        tmc21 = _n(r.get("tmc_21")); ru21 = max(_n(r.get("bjp_21")), _n(r.get("v1_21"))); mar21 = tmc21 - ru21
        imp21.append(round((_n(r.get("electors_21")) - _n(r.get("electors_26"))) / mar21, 2) if mar21 > 0 else None)
        tmc24 = _n(r.get("tmc_24")); bjp24 = _n(r.get("bjp_24")); ru24 = max(bjp24, _n(r.get("v1_24"))); mar24 = tmc24 - ru24
        imp24.append(round((_n(r.get("electors_24")) - _n(r.get("electors_26"))) / mar24, 2) if (tmc24 > bjp24 and mar24 > 0) else None)

    out = df.copy()
    out["imp21"] = imp21
    out["imp24"] = imp24
    return out


# ── State summary view ─────────────────────────────────────────────────────────

def show_state(df):
    st.subheader("West Bengal — All Elections Summary")

    sum_rows, bar_data = [], []
    for yr, full, etype in YEARS:
        el  = pd.to_numeric(df[f"electors_{yr}"],   errors="coerce").sum()
        tv  = pd.to_numeric(df[f"total_votes_{yr}"], errors="coerce").sum()
        tmc = pd.to_numeric(df[f"tmc_{yr}"],         errors="coerce").sum()
        bjp = pd.to_numeric(df[f"bjp_{yr}"],         errors="coerce").sum()
        sum_rows.append({
            "Year": full, "Election": etype,
            "Total Voters": fmt(el), "Votes Cast": fmt(tv), "Turnout": pct(tv, el),
            "TMC": fmt(tmc), "TMC %": pct(tmc, tv),
            "BJP": fmt(bjp), "BJP %": pct(bjp, tv),
        })
        try:
            bar_data += [
                {"Year": full, "Party": "TMC", "Vote %": tmc / tv * 100},
                {"Year": full, "Party": "BJP", "Vote %": bjp / tv * 100},
            ]
        except (TypeError, ValueError, ZeroDivisionError):
            pass

    el26 = pd.to_numeric(df["electors_26"], errors="coerce").sum()
    tv26 = pd.to_numeric(df["votes_26"],    errors="coerce").sum()
    sum_rows.append({
        "Year": "2026", "Election": "Vidhan Sabha",
        "Total Voters": fmt(el26), "Votes Cast": fmt(tv26), "Turnout": pct(tv26, el26),
        "TMC": "—", "TMC %": "—", "BJP": "—", "BJP %": "—",
    })

    st.dataframe(pd.DataFrame(sum_rows), use_container_width=True, hide_index=True)

    if bar_data:
        fig = px.bar(
            pd.DataFrame(bar_data), x="Year", y="Vote %", color="Party",
            barmode="group",
            color_discrete_map={"TMC": "#2CA02C", "BJP": "#FF7F0E"},
            title="State-wide TMC vs BJP Vote Share (%)",
        )
        fig.update_layout(yaxis_range=[0, 100])
        st.plotly_chart(fig, use_container_width=True)

    work = compute_impacts(df)

    # ── Build display table ───────────────────────────────────────────────────
    st.markdown("**All 294 Constituencies**")
    cols = ["ac_no", "ac_name", "district"]
    renames = {"ac_no": "AC No", "ac_name": "Constituency", "district": "District"}
    for yr, full, _ in YEARS:
        cols += [f"electors_{yr}", f"total_votes_{yr}", f"tmc_{yr}", f"bjp_{yr}"]
        renames.update({
            f"electors_{yr}":    f"{full} Total Voters",
            f"total_votes_{yr}": f"{full} Votes Cast",
            f"tmc_{yr}":         f"{full} TMC",
            f"bjp_{yr}":         f"{full} BJP",
        })
    cols += ["electors_26", "votes_26", "imp21", "imp24"] + _DEMO_COLS
    renames.update({
        "electors_26": "2026 Total Voters",
        "votes_26":    "2026 Votes Cast",
        "imp21":       "Vote Drop / Margin (21→26)",
        "imp24":       "Vote Drop / Margin (24→26)",
        **_DEMO_LABELS,
    })

    _skip = {"AC No", "Constituency", "District"} | set(_DEMO_LABELS.values())
    disp = work[cols].rename(columns=renames).copy()
    for c in disp.columns:
        if c not in _skip:
            disp[c] = pd.to_numeric(disp[c], errors="coerce")
    disp = disp.sort_values("AC No")
    st.dataframe(disp, use_container_width=True, hide_index=True)

    with st.expander("Formula explanation"):
        st.markdown("""
**Vote Drop / Margin (21→26)** — TMC-won seats in 2021 Vidhan Sabha only
```
Runner-up₂₁    = max(BJP Votes₂₁,  Top Other Party Votes₂₁)
TMC Margin₂₁   = TMC Votes₂₁ − Runner-up₂₁          [only shown when > 0]
Voter Reduction = Total Voters 2021 − Total Voters 2026
Ratio           = Voter Reduction / TMC Margin₂₁
```
Interpretation: if every voter lost from the rolls since 2021 was a TMC voter, a ratio **> 1.0**
means the loss exceeds the margin and TMC would lose the seat. Blank = TMC did not win in 2021.

---

**Vote Drop / Margin (24→26)** — 2024 assembly segments (from Lok Sabha data) where TMC > BJP only
```
Runner-up₂₄    = max(BJP Votes₂₄,  Top Other Party Votes₂₄)
TMC Margin₂₄   = TMC Votes₂₄ − Runner-up₂₄          [only shown when TMC > BJP]
Voter Reduction = Total Voters 2024 − Total Voters 2026
Ratio           = Voter Reduction / TMC Margin₂₄
```
Same interpretation. Blank = TMC did not lead BJP in that segment in 2024.
        """)


# ── SIR Impact shared helper ───────────────────────────────────────────────────

def _risk_band(ratio):
    if ratio is None or pd.isna(ratio): return None
    if ratio > 1.0:  return "At Risk"
    if ratio > 0.5:  return "Vulnerable"
    if ratio >= 0:   return "Safe"
    return "Voter Roll Grew"

_BAND_ORDER  = ["At Risk", "Vulnerable", "Safe", "Voter Roll Grew"]
_BAND_COLORS = {"At Risk": "#D62728", "Vulnerable": "#FF7F0E",
                "Safe": "#2CA02C",    "Voter Roll Grew": "#1F77B4"}


def _show_sir(work, imp_col, yr, arrow, seat_label, election_label):
    """
    Generic SIR impact view.
      imp_col      : "imp21" or "imp24"
      yr           : "21"   or "24"
      arrow        : "21→26" or "24→26"
      seat_label   : label for the first metric card
      election_label: shown in the info box sentence
    """
    seats = work[work[imp_col].notna()].copy()
    seats["band"] = seats[imp_col].apply(_risk_band)
    band_counts   = seats["band"].value_counts()
    total         = len(seats)

    if total == 0:
        st.warning("No seats match the filter for this comparison.")
        return

    at_risk    = band_counts.get("At Risk",        0)
    vulnerable = band_counts.get("Vulnerable",     0)
    safe       = band_counts.get("Safe",           0)
    grew       = band_counts.get("Voter Roll Grew",0)

    st.caption(
        f"Ratio = (Total Voters {yr[:2]}20{yr[1:]} − Total Voters 2026) / TMC Margin {yr[:2]}20{yr[1:]}.  "
        "Ratio > 1.0 means the voter roll drop exceeds the winning margin."
    )

    # Metrics
    c1, c2, c3, c4 = st.columns(4)
    c1.metric(seat_label,               total)
    c2.metric("At Risk  (ratio > 1)",   at_risk,
              delta=f"{at_risk/total*100:.0f}% of seats",    delta_color="inverse")
    c3.metric("Vulnerable  (0.5–1.0)",  vulnerable,
              delta=f"{vulnerable/total*100:.0f}% of seats", delta_color="inverse")
    c4.metric("Safe or Grew",           safe + grew,
              delta=f"{(safe+grew)/total*100:.0f}% of seats", delta_color="normal")

    # Distribution bar chart
    band_df = (seats["band"].value_counts()
               .reindex(_BAND_ORDER).fillna(0).reset_index())
    band_df.columns = ["Risk Band", "Seats"]
    fig = px.bar(
        band_df, x="Seats", y="Risk Band", orientation="h",
        color="Risk Band", color_discrete_map=_BAND_COLORS,
        text="Seats", title=f"TMC seat risk distribution ({arrow})",
    )
    fig.update_layout(showlegend=False, height=220,
                      margin=dict(t=40, b=10, l=10, r=10),
                      yaxis=dict(categoryorder="array", categoryarray=_BAND_ORDER))
    fig.update_traces(textposition="outside")
    st.plotly_chart(fig, use_container_width=True)

    # Statewide drop note
    total_drop = (pd.to_numeric(seats[f"electors_{yr}"], errors="coerce")
                - pd.to_numeric(seats["electors_26"],    errors="coerce")).sum()
    total_margin = (
        pd.to_numeric(seats[f"tmc_{yr}"], errors="coerce")
        - seats.apply(lambda r: max(
              pd.to_numeric(r.get(f"bjp_{yr}"), errors="coerce") or 0,
              pd.to_numeric(r.get(f"v1_{yr}"),  errors="coerce") or 0,
          ), axis=1)
    ).sum()
    pct = total_drop / total_margin * 100 if total_margin else 0
    st.info(
        f"Across all {total} {election_label} seats, the voter roll changed by "
        f"**{fmt(total_drop)}** voters between {yr[:2]}20{yr[1:]} and 2026 — "
        f"equivalent to **{pct:.1f}%** of the combined TMC winning margin across those seats."
    )

    st.divider()

    # Detail table
    imp_label = f"Vote Drop / Margin ({arrow})"
    cols = ["ac_no", "ac_name", "district", imp_col,
            f"electors_{yr}", f"total_votes_{yr}", f"tmc_{yr}", f"bjp_{yr}",
            "electors_26", "votes_26"] + _DEMO_COLS
    fy = f"20{yr}" if len(yr) == 2 else yr
    renames = {
        "ac_no":              "AC No",
        "ac_name":            "Constituency",
        "district":           "District",
        imp_col:              imp_label,
        f"electors_{yr}":     f"Total Voters {fy}",
        f"total_votes_{yr}":  f"Votes Cast {fy}",
        f"tmc_{yr}":          f"TMC {fy}",
        f"bjp_{yr}":          f"BJP {fy}",
        "electors_26":        "Total Voters 2026",
        "votes_26":           "Votes Cast 2026",
        **_DEMO_LABELS,
    }
    cols = [c for c in cols if c in work.columns]
    _skip = {"AC No", "Constituency", "District"} | set(_DEMO_LABELS.values())
    disp = work[cols].rename(columns=renames).copy()
    for c in disp.columns:
        if c not in _skip:
            disp[c] = pd.to_numeric(disp[c], errors="coerce")
    disp = disp.sort_values(imp_label, ascending=False, na_position="last")
    st.dataframe(disp, use_container_width=True, hide_index=True)


def show_sir_impact(df):
    st.subheader("SIR Impact — Voter Roll Change vs TMC Margin (2021 vs 2026)")
    _show_sir(compute_impacts(df),
              imp_col="imp21", yr="21", arrow="21→26",
              seat_label="TMC seats won (2021)",
              election_label="TMC-won 2021 Vidhan Sabha")


def show_sir_impact_2024(df):
    st.subheader("SIR Impact — Voter Roll Change vs TMC Margin (2024 vs 2026)")
    _show_sir(compute_impacts(df),
              imp_col="imp24", yr="24", arrow="24→26",
              seat_label="Segments TMC led BJP (2024 LS)",
              election_label="TMC-leading 2024 Lok Sabha assembly segment")


# ── Possibilities view ────────────────────────────────────────────────────────

def _parse_m_pct(v):
    try:
        return float(str(v).replace("%", "").strip())
    except Exception:
        return 0.0


def _classify_seat_24(row):
    """Return (classification, reason) using 2024 results + 2026 voter roll data."""
    def _n(v):
        try: return float(v)
        except: return 0.0

    tmc24 = _n(row.get("tmc_24"))
    bjp24 = _n(row.get("bjp_24"))
    v1_24 = _n(row.get("v1_24"))
    el24  = _n(row.get("electors_24"))
    tv24  = _n(row.get("total_votes_24"))
    el26  = _n(row.get("electors_26"))
    tv26  = _n(row.get("votes_26"))
    m     = _parse_m_pct(row.get("muslim_pct"))

    tmc_won = tmc24 > 0 and tmc24 > bjp24
    bjp_won = bjp24 > 0 and bjp24 > tmc24

    if not (tmc_won or bjp_won) or (el24 == 0 and tv24 == 0):
        return "No Data", "Insufficient 2024 data"

    tmc_margin = max(0.0, tmc24 - max(bjp24, v1_24)) if tmc_won else 0.0
    bjp_margin = max(0.0, bjp24 - max(tmc24, v1_24)) if bjp_won else 0.0
    margin_24  = tmc_margin if tmc_won else bjp_margin

    sir_deletion  = max(0.0, el24 - el26)
    vote_increase = max(0.0, tv26 - tv24)

    # Priority rules — first match wins

    # R0: >40% Muslim → TMC always, regardless of 2024 winner
    if m > 40:
        return "TMC", f"More than 40% Muslim — TMC stronghold"

    if tmc_won and tmc_margin > 0 and vote_increase >= 2 * tmc_margin:
        return "BJP possible", "Vote increase double of TMC margin"

    if m >= 30 and tmc_won:
        return "TMC", f"{m:.0f}% Muslim and TMC won in 2024"

    if tmc_won and tmc_margin > 0 and sir_deletion >= 2 * tmc_margin:
        return "BJP possible", "SIR deletion more than double of TMC margin"

    if tmc_won and tmc_margin > 0 and vote_increase > tmc_margin and sir_deletion > tmc_margin:
        return "BJP possible", "Vote increase and SIR deletion both higher than TMC margin"

    if 20 <= m <= 25 and margin_24 > 0 and sir_deletion > margin_24:
        return "BJP possible", f"M population {m:.0f}%. SIR deletion higher than 24 margin"

    if 30 <= m <= 40 and bjp_won and bjp_margin > 0 and sir_deletion >= 2 * bjp_margin:
        return "BJP possible", f"30-40% M but BJP win in 2024 and high SIR deletions — double of BJP margin"

    if 25 < m < 30 and margin_24 > 0 and sir_deletion > margin_24:
        return "BJP possible", f"M population {m:.0f}%. SIR deletion higher than 24 margin"

    if 30 <= m <= 40 and bjp_won and bjp_margin > 0 and sir_deletion > bjp_margin:
        return "BJP possible", f"30-40% M but BJP win in 2024 and high SIR deletions"

    if bjp_won and m < 30:
        return "BJP possible", "BJP win 2024 and M population less than 30%"

    if tmc_won and tmc_margin > 0 and sir_deletion < tmc_margin and vote_increase < tmc_margin:
        return "TMC", "Leaning TMC — high 2024 margin, lower SIR deletion and vote increase vs margin"

    if tmc_won and m > 20:
        return "TMC", "TMC Won in 2024 and more than 20% M"

    if m < 10 and tmc_won and tmc_margin > 0 and sir_deletion > tmc_margin:
        return "BJP possible", "Less than 10%M and deletion higher than TMC 2024 margin"

    if m < 10 and tmc_won and tmc_margin > 0 and vote_increase > tmc_margin:
        return "BJP possible", "Less than 10%M and voting increase higher than TMC 2024 margin"

    if m < 15 and tmc_won and tmc_margin > 0 and sir_deletion > tmc_margin:
        return "BJP possible", "Less than 15%M and SIR deletion higher than TMC 2024 margin"

    if m < 15 and tmc_won and tmc_margin > 0 and vote_increase > tmc_margin:
        return "BJP possible", "Less than 15%M and voting increase higher than TMC 2024 margin"

    if m < 20 and tmc_won and tmc_margin > 0 and sir_deletion > tmc_margin:
        return "BJP possible", "Less than 20%M and SIR deletion higher than TMC 2024 margin"

    if m < 20 and tmc_won and tmc_margin > 0 and vote_increase > tmc_margin:
        return "BJP possible", "Less than 20%M and voting increase higher than TMC 2024 margin"

    if tmc_won:
        return "TMC", "TMC won 2024 — no significant risk factors"

    if bjp_won:
        return "BJP possible", "BJP won 2024"

    return "No Data", "Cannot classify"


def show_possibilities(df):
    st.subheader("2026 Possibilities — Seat Outlook Based on 2024 & SIR Data")
    st.caption(
        "Rules use 2024 Lok Sabha assembly-segment results + 2026 voter roll change. "
        "Applied in priority order — first matching rule determines the classification. "
        "**BJP possible** = BJP is competitive or favoured; **TMC** = TMC expected to hold."
    )

    work = compute_impacts(df).copy()
    classifs, reasons = [], []
    for _, row in work.iterrows():
        c, r = _classify_seat_24(row)
        classifs.append(c)
        reasons.append(r)
    work["classification"] = classifs
    work["reason"] = reasons

    tmc_n    = (work["classification"] == "TMC").sum()
    bjp_n    = (work["classification"] == "BJP possible").sum()
    nodata_n = (work["classification"] == "No Data").sum()
    total    = len(work)

    # ── Summary metrics ────────────────────────────────────────────────────────
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Constituencies", total)
    c2.metric("TMC Likely", tmc_n,
              delta=f"{tmc_n/total*100:.0f}% of seats", delta_color="normal")
    c3.metric("BJP Possible", bjp_n,
              delta=f"{bjp_n/total*100:.0f}% of seats", delta_color="inverse")
    c4.metric("Unclassified", nodata_n)

    # ── Overview pie + district bar ────────────────────────────────────────────
    classified = work[work["classification"] != "No Data"]
    col_a, col_b = st.columns([1, 2])

    with col_a:
        pie_df = classified["classification"].value_counts().reset_index()
        pie_df.columns = ["Outcome", "Seats"]
        fig_pie = px.pie(
            pie_df, names="Outcome", values="Seats",
            color="Outcome",
            color_discrete_map={"TMC": "#2CA02C", "BJP possible": "#FF7F0E"},
            title="Overall Seat Outlook",
            hole=0.45,
        )
        fig_pie.update_layout(height=300, margin=dict(t=40, b=10))
        st.plotly_chart(fig_pie, use_container_width=True)

    with col_b:
        dist_df = (classified
                   .groupby(["district", "classification"])
                   .size().reset_index(name="Seats"))
        fig_dist = px.bar(
            dist_df, x="district", y="Seats", color="classification",
            barmode="stack",
            color_discrete_map={"TMC": "#2CA02C", "BJP possible": "#FF7F0E"},
            title="Outlook by District",
        )
        fig_dist.update_layout(
            height=300,
            xaxis_tickangle=-45,
            legend_title="",
            margin=dict(t=40, b=80),
        )
        st.plotly_chart(fig_dist, use_container_width=True)

    # ── Rule / reason breakdown ────────────────────────────────────────────────
    st.markdown("**Seats by Classification Rule**")
    reason_df = (classified
                 .groupby(["reason", "classification"])
                 .size().reset_index(name="Seats")
                 .sort_values("Seats", ascending=True))
    fig_reason = px.bar(
        reason_df, x="Seats", y="reason", color="classification",
        orientation="h",
        color_discrete_map={"TMC": "#2CA02C", "BJP possible": "#FF7F0E"},
        title="How many seats matched each rule",
        text="Seats",
    )
    fig_reason.update_layout(
        height=max(320, len(reason_df) * 28),
        margin=dict(t=40, b=10, l=10, r=10),
        legend_title="",
        yaxis=dict(autorange="reversed"),
    )
    fig_reason.update_traces(textposition="outside")
    st.plotly_chart(fig_reason, use_container_width=True)

    st.divider()

    # ── Seat-wise table ────────────────────────────────────────────────────────
    filter_opt = st.radio(
        "Filter seats:",
        ["All", "TMC Likely", "BJP Possible", "No Data"],
        horizontal=True, index=0,
    )
    fmap = {
        "All":         None,
        "TMC Likely":  "TMC",
        "BJP Possible":"BJP possible",
        "No Data":     "No Data",
    }
    view = work if fmap[filter_opt] is None else work[work["classification"] == fmap[filter_opt]]

    rows = []
    for _, r in view.sort_values("ac_no").iterrows():
        def _n(v):
            try: return float(v)
            except: return 0.0
        tmc24 = _n(r.get("tmc_24")); bjp24 = _n(r.get("bjp_24"))
        el24  = _n(r.get("electors_24")); tv24 = _n(r.get("total_votes_24"))
        el26  = _n(r.get("electors_26")); tv26 = _n(r.get("votes_26"))
        tmc_won = tmc24 > 0 and tmc24 > bjp24
        winner  = "TMC" if tmc_won else ("BJP" if bjp24 > tmc24 else "—")
        margin  = abs(tmc24 - bjp24) if tmc24 > 0 and bjp24 > 0 else 0
        sir_del = max(0.0, el24 - el26)
        vote_chg = tv26 - tv24
        rows.append({
            "AC No":          int(r["ac_no"]),
            "Constituency":   r["ac_name"],
            "District":       r["district"],
            "Muslim %":       r.get("muslim_pct", "—"),
            "2024 Winner":    winner,
            "TMC Votes 2024": fmt(tmc24) if tmc24 > 0 else "—",
            "BJP Votes 2024": fmt(bjp24) if bjp24 > 0 else "—",
            "Margin 2024":    fmt(margin) if margin > 0 else "—",
            "Voters 2024":    fmt(el24) if el24 > 0 else "—",
            "Voters 2026":    fmt(el26) if el26 > 0 else "—",
            "SIR Deletion":   fmt(sir_del) if sir_del > 0 else "0",
            "Vote Change":    fmt(vote_chg),
            "Outlook":        r["classification"],
            "Rule / Reason":  r["reason"],
        })
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    st.title("West Bengal Elections 2019–2026")
    st.caption(
        "2019 & 2024: Lok Sabha (Parliamentary) results by Assembly segment  |  "
        "2021 & 2026: Vidhan Sabha (State Assembly) elections"
    )

    try:
        df = load_master()
    except Exception as e:
        st.error(f"Failed to load data: {e}")
        st.info("Make sure all data files are in the same folder as app.py and run: pip install -r requirements.txt")
        return

    with st.sidebar:
        st.header("Select View")
        view = st.radio("", ["State Summary", "Possibilities", "SIR Impact 21→26", "SIR Impact 24→26", "By District", "By Constituency"],
                        label_visibility="collapsed")

        sel_dist, sel_const = None, None
        if view == "By District":
            districts = sorted(df["district"].dropna().unique().tolist())
            sel_dist = st.selectbox("District", districts)
        elif view == "By Constituency":
            opts = sorted(
                f"{int(r.ac_no):03d} – {r.ac_name} ({r.district})"
                for _, r in df.iterrows()
            )
            sel_const = st.selectbox("Constituency", opts)

    if view == "State Summary":
        show_state(df)
    elif view == "Possibilities":
        show_possibilities(df)
    elif view == "SIR Impact 21→26":
        show_sir_impact(df)
    elif view == "SIR Impact 24→26":
        show_sir_impact_2024(df)
    elif view == "By District" and sel_dist:
        show_district(df, sel_dist)
    elif view == "By Constituency" and sel_const:
        ac_no = int(sel_const.split("–")[0].strip())
        row = df[df["ac_no"] == ac_no].iloc[0]
        show_constituency(row)


if __name__ == "__main__":
    main()
