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

_TMC = {"AITC", "AITMC", "TMC", "TRINAMOOL", "ALL INDIA TRINAMOOL CONGRESS"}
_BJP = {"BJP", "BHARATIYA JANATA PARTY"}
_NOTA = {"NOTA", "NONE OF THE ABOVE"}

def norm(p):
    if pd.isna(p):
        return "UNKNOWN"
    s = str(p).strip().upper()
    if s in _TMC:  return "TMC"
    if s in _BJP:  return "BJP"
    if s in _NOTA: return "NOTA"
    return s

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


@st.cache_data(show_spinner="Reading SIR deletion data …")
def load_sir():
    df = pd.read_csv("SIR 27 lakh deletion.csv", encoding="cp1252", header=1, skiprows=[0])
    df.columns = df.columns.str.strip()
    df = df.rename(columns={"AC No.": "ac_no", "SIR 27 lakh deletions": "sir_27l"})
    df["ac_no"]  = pd.to_numeric(df["ac_no"], errors="coerce")
    df["sir_27l"] = pd.to_numeric(
        df["sir_27l"].astype(str).str.replace(",", "", regex=False), errors="coerce"
    ).fillna(0)
    return df[["ac_no", "sir_27l"]]


@st.cache_data(show_spinner="Reading 2026 results …")
def load_results():
    df = pd.read_csv("results.csv")
    df.columns = df.columns.str.strip()
    df = df.rename(columns={"Constituency No.": "ac_no"})
    df["ac_no"]  = pd.to_numeric(df["ac_no"], errors="coerce")
    df["Votes"]  = pd.to_numeric(df["Votes"], errors="coerce").fillna(0)
    df["Party"]  = df["Party"].apply(norm)

    rows = []
    for ac_no, g in df.groupby("ac_no"):
        tv  = g["Votes"].sum()
        tmc = g.loc[g["Party"] == "TMC", "Votes"].sum()
        bjp = g.loc[g["Party"] == "BJP", "Votes"].sum()
        won = g[g["Status"] == "won"]
        winner = won.iloc[0]["Party"] if len(won) else None
        sorted_votes = g.sort_values("Votes", ascending=False)
        winner_votes = sorted_votes.iloc[0]["Votes"] if len(sorted_votes) > 0 else 0
        runner_votes = sorted_votes.iloc[1]["Votes"] if len(sorted_votes) > 1 else 0
        margin_26 = winner_votes - runner_votes
        top3 = (g[~g["Party"].isin({"TMC", "BJP", "NOTA", "UNKNOWN"})]
                .groupby("Party")["Votes"].sum().nlargest(3))
        r = {"ac_no": int(ac_no), "tv_26": tv,
             "tmc_26": tmc, "bjp_26": bjp, "winner_26": winner, "margin_26": margin_26}
        for i, (p, v) in enumerate(top3.items(), 1):
            r[f"p{i}_26"] = p
            r[f"v{i}_26"] = v
        rows.append(r)
    return pd.DataFrame(rows)


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


@st.cache_data(show_spinner="Reading prediction data …")
def load_prediction():
    df = pd.read_csv("Prediction.csv")
    df.columns = df.columns.str.strip()
    comma_cols = [
        "TMC_margin_2024", "TMC_margin_2021",
        "BJP_trend_2021_2024", "TMC_trend_2021_2024", "BJP_vs_TMC_trend",
    ]
    for c in comma_cols:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c].astype(str).str.replace(",", "", regex=False), errors="coerce")
    vote_cols = [c for c in df.columns if any(y in c for y in ["2019", "2021", "2024", "2026"])]
    for c in vote_cols:
        df[c] = pd.to_numeric(df[c].astype(str).str.replace(",", "", regex=False), errors="coerce")
    for col in ["Muslim %", "Hindu %", "Christian %", "Buddhist/Other %"]:
        if col in df.columns:
            df[col + "_n"] = pd.to_numeric(df[col].astype(str).str.replace("%", "", regex=False), errors="coerce")
    return df


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
    res = load_results()
    m = m.merge(res, on="ac_no", how="left")
    m.loc[m["tv_26"].notna(), "votes_26"] = m.loc[m["tv_26"].notna(), "tv_26"]
    m = m.merge(load_sir(), on="ac_no", how="left")
    return m


# ── Parliamentary loaders ──────────────────────────────────────────────────────

@st.cache_data(show_spinner="Reading 2019 PC data …")
def _raw_2019_pc():
    df = pd.read_excel(
        "425581050_34.DetailsOfAssemblySegmentOfPC 2019.xls",
        header=2, dtype=str, engine="calamine",
    )
    df.columns = ["state","pc_no","pc_name","ac_no","ac_name",
                  "electors","_ts","nota","cand","party","votes"]
    df = df[df["state"].str.contains("West Bengal", case=False, na=False)].copy()
    for c in ["ac_no","pc_no","electors","nota","votes"]:
        df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0)
    df["party"] = df["party"].apply(norm)
    return df


@st.cache_data(show_spinner="Reading 2024 PC data …")
def _raw_2024_pc():
    df = pd.read_excel(
        "34-Details-Of-Assembly-Segment-Of-PC 2024.xls",
        header=1, dtype=str, engine="calamine",
    )
    df.columns = ["state","pc_no","pc_name","_elpc","ac_no","ac_name",
                  "electors","_ts","nota","cand","party","votes"]
    df = df[df["state"].str.contains("West Bengal", case=False, na=False)].copy()
    for c in ["ac_no","pc_no","electors","nota","votes"]:
        df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0)
    df["party"] = df["party"].apply(norm)
    return df


def _agg_ls_to_pc(df, has_nota):
    rows = []
    for (pc_no, pc_name), g in df.groupby(["pc_no","pc_name"]):
        g_ac = g.drop_duplicates("ac_no")
        el   = g_ac["electors"].sum()
        nota = g_ac["nota"].sum() if has_nota else 0
        tv   = g["votes"].sum() + nota
        tmc  = g.loc[g["party"]=="TMC","votes"].sum()
        bjp  = g.loc[g["party"]=="BJP","votes"].sum()
        top3 = (g[~g["party"].isin({"TMC","BJP","NOTA","UNKNOWN"})]
                .groupby("party")["votes"].sum().nlargest(3))
        winner = "TMC" if tmc > bjp else ("BJP" if bjp > tmc else "Other")
        margin = abs(int(tmc) - int(bjp))
        r = {"pc_no": int(pc_no), "pc_name": str(pc_name),
             "electors": el, "total_votes": tv, "tmc": tmc, "bjp": bjp,
             "winner": winner, "margin": margin}
        for i, (p, v) in enumerate(top3.items(), 1):
            r[f"p{i}"] = str(p); r[f"v{i}"] = float(v)
        rows.append(r)
    return pd.DataFrame(rows).sort_values("pc_no").reset_index(drop=True)


@st.cache_data(show_spinner="Building parliamentary dataset …")
def load_parliament():
    r19 = _raw_2019_pc()
    r24 = _raw_2024_pc()

    pc_map = r19[["ac_no","pc_no","pc_name"]].drop_duplicates("ac_no")

    ls19 = _agg_ls_to_pc(r19, has_nota=True)
    ls24 = _agg_ls_to_pc(r24, has_nota=True)

    # 2021 VS: aggregate AC-level results to PC
    a21 = agg_year(raw_2021(), False).merge(pc_map, on="ac_no", how="left")

    def _ac_winner(row):
        tmc = float(row.get("tmc") or 0)
        bjp = float(row.get("bjp") or 0)
        v1  = float(row.get("v1")  or 0)
        mx  = max(tmc, bjp, v1)
        if mx == 0: return None
        return "TMC" if mx == tmc else ("BJP" if mx == bjp else "Other")

    a21["ac_winner"] = a21.apply(_ac_winner, axis=1)

    vs21_rows = []
    for (pc_no, pc_name), g in a21.groupby(["pc_no","pc_name"]):
        el   = g["electors"].sum(); tv = g["total_votes"].sum()
        tmc  = g["tmc"].sum();      bjp = g["bjp"].sum()
        tmc_s = (g["ac_winner"]=="TMC").sum()
        bjp_s = (g["ac_winner"]=="BJP").sum()
        oth_s = g["ac_winner"].notna().sum() - tmc_s - bjp_s
        winner = "TMC" if tmc_s > bjp_s else ("BJP" if bjp_s > tmc_s else "Split")
        ov = {}
        for _, row in g.iterrows():
            for i in range(1, 4):
                p, v = row.get(f"p{i}"), row.get(f"v{i}")
                if pd.notna(p) and pd.notna(v):
                    try: ov[str(p)] = ov.get(str(p), 0) + float(v)
                    except: pass
        top3 = sorted(ov.items(), key=lambda x: -x[1])[:3]
        r = {"pc_no": int(pc_no), "pc_name": str(pc_name),
             "electors": el, "total_votes": tv, "tmc": tmc, "bjp": bjp,
             "tmc_seats": int(tmc_s), "bjp_seats": int(bjp_s), "other_seats": int(oth_s),
             "winner": winner, "margin": abs(int(tmc) - int(bjp))}
        for i, (p, v) in enumerate(top3, 1):
            r[f"p{i}"] = p; r[f"v{i}"] = v
        vs21_rows.append(r)
    vs21 = pd.DataFrame(vs21_rows).sort_values("pc_no").reset_index(drop=True)

    # 2026 VS: aggregate from master
    master = load_master()
    a26 = master[["ac_no","electors_26","votes_26","tmc_26","bjp_26","winner_26",
                   "p1_26","v1_26","p2_26","v2_26","p3_26","v3_26"]].copy()
    a26 = a26.merge(pc_map, on="ac_no", how="left")

    vs26_rows = []
    for (pc_no, pc_name), g in a26.groupby(["pc_no","pc_name"]):
        el   = pd.to_numeric(g["electors_26"], errors="coerce").sum()
        tv   = pd.to_numeric(g["votes_26"],    errors="coerce").sum()
        tmc  = pd.to_numeric(g["tmc_26"],      errors="coerce").sum()
        bjp  = pd.to_numeric(g["bjp_26"],      errors="coerce").sum()
        tmc_s = (g["winner_26"]=="TMC").sum()
        bjp_s = (g["winner_26"]=="BJP").sum()
        oth_s = g["winner_26"].notna().sum() - tmc_s - bjp_s
        winner = "TMC" if tmc_s > bjp_s else ("BJP" if bjp_s > tmc_s else "Split")
        ov = {}
        for _, row in g.iterrows():
            for i in range(1, 4):
                p, v = row.get(f"p{i}_26"), row.get(f"v{i}_26")
                if pd.notna(p) and pd.notna(v):
                    try: ov[str(p)] = ov.get(str(p), 0) + float(v)
                    except: pass
        top3 = sorted(ov.items(), key=lambda x: -x[1])[:3]
        r = {"pc_no": int(pc_no), "pc_name": str(pc_name),
             "electors": el, "total_votes": tv, "tmc": tmc, "bjp": bjp,
             "tmc_seats": int(tmc_s), "bjp_seats": int(bjp_s), "other_seats": int(oth_s),
             "winner": winner, "margin": abs(int(tmc) - int(bjp))}
        for i, (p, v) in enumerate(top3, 1):
            r[f"p{i}"] = p; r[f"v{i}"] = float(v)
        vs26_rows.append(r)
    vs26 = pd.DataFrame(vs26_rows).sort_values("pc_no").reset_index(drop=True)

    return {
        "ls19": ls19, "vs21": vs21, "ls24": ls24, "vs26": vs26,
        "pc_names": sorted(ls19["pc_name"].tolist()),
    }


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

_TMC_COLOR = "#2CA02C"   # green
_BJP_COLOR = "#FF9933"   # saffron
_PARTY_COLORS = {"TMC": _TMC_COLOR, "BJP": _BJP_COLOR}

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


def show_voter_roll_info(el24, el26, sir_27l):
    """Render voter roll reduction and SIR deletions as metric cards."""
    st.markdown("#### Voter Roll Change (2024 → 2026)")
    drop = el24 - el26 if (el24 and el26) else 0
    try:
        drop_pct = drop / el24 * 100
    except (TypeError, ZeroDivisionError):
        drop_pct = 0.0
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Registered Voters 2024", fmt(el24))
    c2.metric("Registered Voters 2026", fmt(el26))
    c3.metric("Voter Roll Reduction",   fmt(drop),
              delta=f"−{drop_pct:.1f}%", delta_color="inverse")
    c4.metric("SIR 27-lakh Deletions",  fmt(sir_27l))


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

    el26  = row.get("electors_26")
    tv26  = row.get("votes_26")
    tmc26 = row.get("tmc_26")
    bjp26 = row.get("bjp_26")
    win26 = row.get("winner_26")
    others26 = []
    for i in range(1, 4):
        p, v = row.get(f"p{i}_26"), row.get(f"v{i}_26")
        if pd.notna(p) and pd.notna(v):
            others26.append(f"{p}: {fmt(v)} ({pct(v, tv26)})")
    result_note = f"  ✓ {win26} won" if pd.notna(win26) else ""
    table.append({
        "Year": f"2026{result_note}", "Election": "Vidhan Sabha",
        "Voters": fmt(el26), "Votes Cast": fmt(tv26), "Turnout": pct(tv26, el26),
        "TMC": fmt(tmc26), "TMC %": pct(tmc26, tv26),
        "BJP": fmt(bjp26), "BJP %": pct(bjp26, tv26),
        "Others": "  |  ".join(others26) or "—",
    })
    try:
        bar_data += [
            {"Year": "2026", "Party": "TMC", "Vote %": float(tmc26) / float(tv26) * 100},
            {"Year": "2026", "Party": "BJP", "Vote %": float(bjp26) / float(tv26) * 100},
        ]
    except (TypeError, ValueError):
        pass

    st.dataframe(pd.DataFrame(table), use_container_width=True, hide_index=True, height=210)

    if bar_data:
        tab1, tab2, tab3 = st.tabs(["TMC vs BJP Trend", "2024 Vote Breakdown", "2026 Vote Breakdown"])
        with tab1:
            fig = px.bar(
                pd.DataFrame(bar_data), x="Year", y="Vote %", color="Party",
                barmode="group",
                color_discrete_map=_PARTY_COLORS,
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
                    color="Party",
                    color_discrete_map=_PARTY_COLORS,
                    title="2024 (Lok Sabha) Vote Breakdown",
                )
                fig2.update_layout(height=360)
                st.plotly_chart(fig2, use_container_width=True)
        with tab3:
            pie26 = []
            for key, label in [("tmc_26", "TMC"), ("bjp_26", "BJP")]:
                v = row.get(key)
                if pd.notna(v) and float(v) > 0:
                    pie26.append({"Party": label, "Votes": float(v)})
            for i in range(1, 4):
                p, v = row.get(f"p{i}_26"), row.get(f"v{i}_26")
                if pd.notna(p) and pd.notna(v):
                    pie26.append({"Party": p, "Votes": float(v)})
            if pie26:
                fig3 = px.pie(
                    pd.DataFrame(pie26), names="Party", values="Votes",
                    color="Party",
                    color_discrete_map=_PARTY_COLORS,
                    title="2026 (Vidhan Sabha) Vote Breakdown",
                )
                fig3.update_layout(height=360)
                st.plotly_chart(fig3, use_container_width=True)
            else:
                st.caption("2026 results not yet available for this constituency.")

    st.divider()
    show_voter_roll_info(
        pd.to_numeric(row.get("electors_24"), errors="coerce"),
        pd.to_numeric(row.get("electors_26"), errors="coerce"),
        pd.to_numeric(row.get("sir_27l"),     errors="coerce"),
    )

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

    el26  = pd.to_numeric(sub["electors_26"], errors="coerce").sum()
    tv26  = pd.to_numeric(sub["votes_26"],    errors="coerce").sum()
    tmc26 = pd.to_numeric(sub["tmc_26"],      errors="coerce").sum()
    bjp26 = pd.to_numeric(sub["bjp_26"],      errors="coerce").sum()
    sum_rows.append({
        "Year": "2026", "Election": "Vidhan Sabha",
        "Voters": fmt(el26), "Votes Cast": fmt(tv26), "Turnout": pct(tv26, el26),
        "TMC": fmt(tmc26), "TMC %": pct(tmc26, tv26),
        "BJP": fmt(bjp26), "BJP %": pct(bjp26, tv26),
    })
    try:
        bar_data += [
            {"Year": "2026", "Party": "TMC", "Vote %": tmc26 / tv26 * 100},
            {"Year": "2026", "Party": "BJP", "Vote %": bjp26 / tv26 * 100},
        ]
    except (TypeError, ValueError, ZeroDivisionError):
        pass

    st.markdown("**District Totals**")
    st.dataframe(pd.DataFrame(sum_rows), use_container_width=True, hide_index=True, height=210)

    if bar_data:
        fig = px.bar(
            pd.DataFrame(bar_data), x="Year", y="Vote %", color="Party",
            barmode="group",
            color_discrete_map=_PARTY_COLORS,
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
        row["2026 TMC %"]  = pct(r.get("tmc_26"), r.get("votes_26"))
        row["2026 BJP %"]  = pct(r.get("bjp_26"), r.get("votes_26"))
        row["2026 Turnout"] = pct(r.get("votes_26"), r.get("electors_26"))
        row["2026 Winner"] = r.get("winner_26") or "—"
        for col, lbl in _DEMO_LABELS.items():
            row[lbl] = r.get(col)
        rows.append(row)
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    st.divider()
    el24_d  = pd.to_numeric(sub["electors_24"], errors="coerce").sum()
    el26_d  = pd.to_numeric(sub["electors_26"], errors="coerce").sum()
    sir27_d = pd.to_numeric(sub["sir_27l"],     errors="coerce").sum()
    show_voter_roll_info(el24_d, el26_d, sir27_d)

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

    el26  = pd.to_numeric(df["electors_26"], errors="coerce").sum()
    tv26  = pd.to_numeric(df["votes_26"],    errors="coerce").sum()
    tmc26 = pd.to_numeric(df["tmc_26"],      errors="coerce").sum()
    bjp26 = pd.to_numeric(df["bjp_26"],      errors="coerce").sum()
    sum_rows.append({
        "Year": "2026", "Election": "Vidhan Sabha",
        "Total Voters": fmt(el26), "Votes Cast": fmt(tv26), "Turnout": pct(tv26, el26),
        "TMC": fmt(tmc26), "TMC %": pct(tmc26, tv26),
        "BJP": fmt(bjp26), "BJP %": pct(bjp26, tv26),
    })
    try:
        bar_data += [
            {"Year": "2026", "Party": "TMC", "Vote %": tmc26 / tv26 * 100},
            {"Year": "2026", "Party": "BJP", "Vote %": bjp26 / tv26 * 100},
        ]
    except (TypeError, ValueError, ZeroDivisionError):
        pass

    st.dataframe(pd.DataFrame(sum_rows), use_container_width=True, hide_index=True, height=210)

    if bar_data:
        fig = px.bar(
            pd.DataFrame(bar_data), x="Year", y="Vote %", color="Party",
            barmode="group",
            color_discrete_map=_PARTY_COLORS,
            title="State-wide TMC vs BJP Vote Share (%)",
        )
        fig.update_layout(yaxis_range=[0, 100])
        st.plotly_chart(fig, use_container_width=True)

    el24_tot  = pd.to_numeric(df["electors_24"], errors="coerce").sum()
    el26_tot  = pd.to_numeric(df["electors_26"], errors="coerce").sum()
    sir27_tot = pd.to_numeric(df["sir_27l"],     errors="coerce").sum()
    show_voter_roll_info(el24_tot, el26_tot, sir27_tot)

    work = compute_impacts(df)

    # Compute margin analysis columns
    work["voter_roll_drop"] = (
        pd.to_numeric(work["electors_24"], errors="coerce") -
        pd.to_numeric(work["electors_26"], errors="coerce")
    ).clip(lower=0).fillna(0)
    work["margin_26_n"] = pd.to_numeric(work["margin_26"], errors="coerce")
    work["roll_margin_ratio"] = (work["voter_roll_drop"] / work["margin_26_n"].replace(0, float("nan"))).round(2)
    work["sir_margin_ratio"]  = (pd.to_numeric(work["sir_27l"], errors="coerce") / work["margin_26_n"].replace(0, float("nan"))).round(2)

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
    cols += ["electors_26", "votes_26", "tmc_26", "bjp_26", "winner_26",
             "margin_26_n", "voter_roll_drop", "roll_margin_ratio",
             "sir_27l", "sir_margin_ratio"] + _DEMO_COLS
    renames.update({
        "electors_26":       "2026 Total Voters",
        "votes_26":          "2026 Votes Cast",
        "tmc_26":            "2026 TMC",
        "bjp_26":            "2026 BJP",
        "winner_26":         "2026 Winner",
        "margin_26_n":       "2026 Margin",
        "voter_roll_drop":   "Roll Deletion (24→26)",
        "roll_margin_ratio": "Roll Del / Margin",
        "sir_27l":           "SIR Deletions",
        "sir_margin_ratio":  "SIR Del / Margin",
        **_DEMO_LABELS,
    })

    _skip = {"AC No", "Constituency", "District", "2026 Winner"} | set(_DEMO_LABELS.values())
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


# ── Prediction view ───────────────────────────────────────────────────────────

_PRED_ORDER = ["TMC Win", "TMC Contested", "BJP Possible", "BJP Contested", "BJP Win"]
_PRED_COLORS = {
    "TMC Win":       "#1a7a1a",
    "TMC Contested": "#5cb85c",
    "BJP Possible":  "#FFD580",
    "BJP Contested": "#FF9933",
    "BJP Win":       "#CC5500",
}


def show_prediction():
    st.subheader("2026 Seat Predictions")

    try:
        pred = load_prediction()
    except Exception as e:
        st.error(f"Could not load Prediction.csv: {e}")
        return

    total  = len(pred)
    counts = pred["Prediction"].value_counts()

    tmc_total = counts.get("TMC Win", 0) + counts.get("TMC Contested", 0)
    bjp_total = counts.get("BJP Win", 0) + counts.get("BJP Contested", 0) + counts.get("BJP Possible", 0)

    # ── Summary metrics ────────────────────────────────────────────────────────
    st.markdown(
        f"**TMC leaning: {tmc_total} seats &nbsp;|&nbsp; "
        f"BJP leaning / possible: {bjp_total} seats &nbsp;|&nbsp; Total: {total}**",
        unsafe_allow_html=True,
    )
    cols = st.columns(5)
    for i, label in enumerate(_PRED_ORDER):
        n = counts.get(label, 0)
        cols[i].metric(label, f"{n}  ({n/total*100:.0f}%)")

    st.divider()

    # ── Tabs ──────────────────────────────────────────────────────────────────
    tab_ov, tab_an, tab_seats = st.tabs(["Overview", "Analysis", "Seat List"])

    # ── Tab 1: Overview ───────────────────────────────────────────────────────
    with tab_ov:
        col_a, col_b = st.columns([1, 2])

        with col_a:
            pie_df = (pred["Prediction"].value_counts()
                      .reindex(_PRED_ORDER).dropna().reset_index())
            pie_df.columns = ["Prediction", "Seats"]
            fig_pie = px.pie(
                pie_df, names="Prediction", values="Seats",
                color="Prediction", color_discrete_map=_PRED_COLORS,
                title="Overall Seat Outlook", hole=0.45,
                category_orders={"Prediction": _PRED_ORDER},
            )
            fig_pie.update_layout(height=340, margin=dict(t=40, b=10))
            st.plotly_chart(fig_pie, use_container_width=True)

        with col_b:
            dist_df = (pred.groupby(["District", "Prediction"])
                       .size().reset_index(name="Seats"))
            fig_dist = px.bar(
                dist_df, x="District", y="Seats", color="Prediction",
                barmode="stack",
                color_discrete_map=_PRED_COLORS,
                category_orders={"Prediction": _PRED_ORDER},
                title="Prediction by District",
            )
            fig_dist.update_layout(
                height=340, xaxis_tickangle=-45,
                legend_title="", margin=dict(t=40, b=100),
            )
            st.plotly_chart(fig_dist, use_container_width=True)

        # Rule breakdown
        rule_order = (pred.groupby("Rule Used").size()
                      .sort_values(ascending=True).index.tolist())
        rule_df = (pred.groupby(["Rule Used", "Prediction"])
                   .size().reset_index(name="Seats"))
        fig_rule = px.bar(
            rule_df, x="Seats", y="Rule Used", color="Prediction",
            orientation="h",
            color_discrete_map=_PRED_COLORS,
            category_orders={"Prediction": _PRED_ORDER, "Rule Used": rule_order},
            title="Seats per Classification Rule",
            text="Seats",
        )
        fig_rule.update_layout(
            height=max(360, len(rule_order) * 30),
            margin=dict(t=40, b=10, l=10, r=30),
            legend_title="",
        )
        fig_rule.update_traces(textposition="outside")
        st.plotly_chart(fig_rule, use_container_width=True)

    # ── Tab 2: Analysis ───────────────────────────────────────────────────────
    with tab_an:
        sc1, sc2 = st.columns(2)

        with sc1:
            sc_df = pred.dropna(subset=["Muslim %_n", "voter_drop_pct"])
            fig_sc1 = px.scatter(
                sc_df,
                x="Muslim %_n", y="voter_drop_pct",
                color="Prediction",
                color_discrete_map=_PRED_COLORS,
                category_orders={"Prediction": _PRED_ORDER},
                hover_name="Constituency",
                hover_data={"District": True, "Rule Used": True,
                            "Muslim %_n": False, "voter_drop_pct": ":.1f"},
                labels={"Muslim %_n": "Muslim %", "voter_drop_pct": "Voter Roll Drop %"},
                title="Muslim % vs Voter Roll Drop",
            )
            fig_sc1.update_layout(height=400, legend_title="", margin=dict(t=40, b=10))
            st.plotly_chart(fig_sc1, use_container_width=True)

        with sc2:
            sc_df2 = pred.dropna(subset=["TMC_trend_2021_2024", "BJP_trend_2021_2024"])
            fig_sc2 = px.scatter(
                sc_df2,
                x="BJP_trend_2021_2024", y="TMC_trend_2021_2024",
                color="Prediction",
                color_discrete_map=_PRED_COLORS,
                category_orders={"Prediction": _PRED_ORDER},
                hover_name="Constituency",
                hover_data={"District": True, "Muslim %": True,
                            "BJP_trend_2021_2024": ":,", "TMC_trend_2021_2024": ":,"},
                labels={
                    "BJP_trend_2021_2024": "BJP Vote Change 2021→2024",
                    "TMC_trend_2021_2024": "TMC Vote Change 2021→2024",
                },
                title="Vote Swing 2021→2024  (BJP vs TMC)",
            )
            fig_sc2.add_hline(y=0, line_dash="dot", line_color="grey", opacity=0.4)
            fig_sc2.add_vline(x=0, line_dash="dot", line_color="grey", opacity=0.4)
            fig_sc2.update_layout(height=400, legend_title="", margin=dict(t=40, b=10))
            st.plotly_chart(fig_sc2, use_container_width=True)

        # Voter drop histogram by prediction
        hist_df = pred.dropna(subset=["voter_drop_pct"])
        fig_hist = px.histogram(
            hist_df, x="voter_drop_pct", color="Prediction",
            color_discrete_map=_PRED_COLORS,
            category_orders={"Prediction": _PRED_ORDER},
            barmode="overlay", opacity=0.7,
            nbins=30,
            labels={"voter_drop_pct": "Voter Roll Drop %"},
            title="Distribution of Voter Roll Drop % by Prediction",
        )
        fig_hist.update_layout(height=320, legend_title="", margin=dict(t=40, b=10))
        st.plotly_chart(fig_hist, use_container_width=True)

        # Key contests callout
        contested = pred[pred["Prediction"].isin(["TMC Contested", "BJP Contested"])]
        if not contested.empty:
            st.markdown(f"**Closely Contested Seats — {len(contested)} constituencies**")
            st.caption("These seats are within striking distance for either party.")
            con_rows = []
            for _, r in contested.sort_values("District").iterrows():
                con_rows.append({
                    "AC No":         int(r["AC No"]),
                    "Constituency":  r["Constituency"],
                    "District":      r["District"],
                    "Prediction":    r["Prediction"],
                    "Muslim %":      r.get("Muslim %", "—"),
                    "TMC Margin 24": r.get("TMC_margin_2024"),
                    "Voter Drop 24→26": r.get("voter_drop_24_26"),
                    "Voter Drop %":  f"{r.get('voter_drop_pct', 0):.1f}%",
                    "Rule":          r.get("Rule Used", "—"),
                })
            st.dataframe(pd.DataFrame(con_rows), use_container_width=True, hide_index=True)

    # ── Tab 3: Seat List ──────────────────────────────────────────────────────
    with tab_seats:
        f1, f2, f3 = st.columns(3)
        with f1:
            pred_filter = st.multiselect("Prediction", options=_PRED_ORDER, default=[])
        with f2:
            rule_opts = sorted(pred["Rule Used"].unique().tolist())
            rule_filter = st.multiselect("Rule", options=rule_opts, default=[])
        with f3:
            dist_opts = sorted(pred["District"].unique().tolist())
            dist_filter = st.multiselect("District", options=dist_opts, default=[])

        view = pred.copy()
        if pred_filter:  view = view[view["Prediction"].isin(pred_filter)]
        if rule_filter:  view = view[view["Rule Used"].isin(rule_filter)]
        if dist_filter:  view = view[view["District"].isin(dist_filter)]

        st.caption(f"Showing {len(view)} of {total} constituencies")

        disp_cols = [
            "AC No", "Constituency", "District", "Prediction", "Rule Used",
            "Muslim %", "Hindu %",
            "TMC_margin_2024", "TMC_margin_2021",
            "voter_drop_24_26", "voter_drop_pct",
            "voter_increase_votes_cast",
            "BJP_trend_2021_2024", "TMC_trend_2021_2024",
        ]
        disp_cols = [c for c in disp_cols if c in view.columns]
        disp = (view[disp_cols]
                .sort_values("AC No")
                .rename(columns={
                    "Rule Used":                  "Rule",
                    "TMC_margin_2024":             "TMC Margin 2024",
                    "TMC_margin_2021":             "TMC Margin 2021",
                    "voter_drop_24_26":            "Voter Drop (24→26)",
                    "voter_drop_pct":              "Voter Drop %",
                    "voter_increase_votes_cast":   "Vote Increase",
                    "BJP_trend_2021_2024":         "BJP Trend 21→24",
                    "TMC_trend_2021_2024":         "TMC Trend 21→24",
                }))
        st.dataframe(disp, use_container_width=True, hide_index=True)


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
            color_discrete_map={"TMC": _TMC_COLOR, "BJP possible": _BJP_COLOR},
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
            color_discrete_map={"TMC": _TMC_COLOR, "BJP possible": _BJP_COLOR},
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
        color_discrete_map={"TMC": _TMC_COLOR, "BJP possible": _BJP_COLOR},
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


# ── Margin vs Deletion analysis ───────────────────────────────────────────────

def _show_margin_analysis(df, deletion_col, deletion_label, title, description):
    st.subheader(title)
    st.caption(description)

    work = df.copy()
    work["margin_26"]  = pd.to_numeric(work["margin_26"],  errors="coerce")
    work[deletion_col] = pd.to_numeric(work[deletion_col], errors="coerce").fillna(0)

    valid = work[work["margin_26"].notna() & (work["margin_26"] > 0)].copy()
    valid["winner_26"] = valid["winner_26"].fillna("Others")
    valid["status"]    = (valid["margin_26"] < valid[deletion_col]).map(
        {True: "Margin < Deletion", False: "Margin ≥ Deletion"}
    )
    valid["ratio"] = (valid[deletion_col] / valid["margin_26"]).round(2)

    total   = len(valid)
    vuln    = (valid["status"] == "Margin < Deletion").sum()
    tmc_tot = (valid["winner_26"] == "TMC").sum()
    bjp_tot = (valid["winner_26"] == "BJP").sum()
    tmc_v   = ((valid["winner_26"] == "TMC") & (valid["status"] == "Margin < Deletion")).sum()
    bjp_v   = ((valid["winner_26"] == "BJP") & (valid["status"] == "Margin < Deletion")).sum()

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Seats (2026 results)", total)
    c2.metric(f"Margin < {deletion_label}", vuln,
              delta=f"{vuln/max(total,1)*100:.0f}% of seats", delta_color="inverse")
    c3.metric("TMC Seats: Margin < Deletion", f"{tmc_v} / {tmc_tot}",
              delta=f"{tmc_v/max(tmc_tot,1)*100:.0f}% of TMC wins", delta_color="inverse")
    c4.metric("BJP Seats: Margin < Deletion", f"{bjp_v} / {bjp_tot}",
              delta=f"{bjp_v/max(bjp_tot,1)*100:.0f}% of BJP wins", delta_color="inverse")

    st.info(
        f"**{vuln} of {total} seats** have a 2026 victory margin smaller than the {deletion_label}.  "
        f"Of these, **{tmc_v} are TMC-won** and **{bjp_v} are BJP-won** seats."
    )

    col_a, col_b = st.columns([1, 2])
    main_winners = valid[valid["winner_26"].isin(["TMC", "BJP"])].copy()

    with col_a:
        party_df = (main_winners
                    .groupby(["winner_26", "status"])
                    .size().reset_index(name="Seats"))
        party_df.columns = ["Party", "Status", "Seats"]
        fig_bar = px.bar(
            party_df, x="Party", y="Seats", color="Status",
            barmode="stack",
            color_discrete_map={"Margin < Deletion": "#D62728", "Margin ≥ Deletion": "#2CA02C"},
            title=f"Margin vs {deletion_label} by Party",
            text="Seats",
        )
        fig_bar.update_traces(textposition="inside", textfont_size=13)
        fig_bar.update_layout(height=360, legend_title="", margin=dict(t=40, b=10))
        st.plotly_chart(fig_bar, use_container_width=True)

    with col_b:
        dist_df = (main_winners
                   .groupby(["district", "status"])
                   .size().reset_index(name="Seats"))
        dist_df.columns = ["District", "Status", "Seats"]
        fig_dist = px.bar(
            dist_df, x="District", y="Seats", color="Status",
            barmode="stack",
            color_discrete_map={"Margin < Deletion": "#D62728", "Margin ≥ Deletion": "#2CA02C"},
            title=f"Margin vs {deletion_label} by District",
        )
        fig_dist.update_layout(
            height=360, xaxis_tickangle=-45, legend_title="",
            margin=dict(t=40, b=100),
        )
        st.plotly_chart(fig_dist, use_container_width=True)

    # Scatter: deletion vs margin, diagonal = equality line
    max_val = max(
        float(main_winners[deletion_col].max() or 0),
        float(main_winners["margin_26"].max() or 0),
    ) * 1.05
    fig_sc = px.scatter(
        main_winners, x=deletion_col, y="margin_26",
        color="winner_26",
        color_discrete_map=_PARTY_COLORS,
        hover_name="ac_name",
        hover_data={"district": True, "winner_26": False,
                    deletion_col: ":,", "margin_26": ":,", "ratio": ":.2f"},
        labels={
            deletion_col: deletion_label,
            "margin_26":  "2026 Victory Margin",
            "winner_26":  "Winner",
        },
        title=f"2026 Margin vs {deletion_label}  (each dot = one constituency)",
    )
    fig_sc.add_shape(type="line", x0=0, y0=0, x1=max_val, y1=max_val,
                     line=dict(color="grey", dash="dot", width=1.5))
    fig_sc.add_annotation(
        x=max_val * 0.6, y=max_val * 0.6,
        text="Margin = Deletion",
        showarrow=False,
        font=dict(color="grey", size=11),
    )
    fig_sc.update_layout(height=450, legend_title="Winner", margin=dict(t=40, b=10))
    st.plotly_chart(fig_sc, use_container_width=True)

    st.divider()

    f1, f2 = st.columns(2)
    with f1:
        status_filter = st.radio(
            "Filter by status:",
            ["All", "Margin < Deletion (Vulnerable)", "Margin ≥ Deletion (Safe)"],
            horizontal=True, index=0,
            key=f"sf_{deletion_col}",
        )
    with f2:
        party_filter = st.radio(
            "Filter by winner:",
            ["All", "TMC", "BJP"],
            horizontal=True, index=0,
            key=f"pf_{deletion_col}",
        )

    view = valid.copy()
    if status_filter == "Margin < Deletion (Vulnerable)":
        view = view[view["status"] == "Margin < Deletion"]
    elif status_filter == "Margin ≥ Deletion (Safe)":
        view = view[view["status"] == "Margin ≥ Deletion"]
    if party_filter != "All":
        view = view[view["winner_26"] == party_filter]

    rows = []
    for _, r in view.sort_values("margin_26", ascending=True).iterrows():
        rows.append({
            "AC No":             int(r["ac_no"]),
            "Constituency":      r["ac_name"],
            "District":          r["district"],
            "Winner":            r["winner_26"],
            "Margin 2026":       int(r["margin_26"]),
            deletion_label:      int(r[deletion_col]) if r[deletion_col] > 0 else 0,
            "Ratio (Del/Margin)":r["ratio"],
            "Status":            r["status"],
            "Muslim %":          r.get("muslim_pct", "—"),
        })
    st.caption(f"Showing {len(rows)} seats — sorted by margin ascending (most vulnerable first)")
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)


def show_margin_vs_roll(df):
    work = df.copy()
    work["voter_roll_drop"] = (
        pd.to_numeric(work["electors_24"], errors="coerce") -
        pd.to_numeric(work["electors_26"], errors="coerce")
    ).clip(lower=0).fillna(0)
    _show_margin_analysis(
        work,
        deletion_col="voter_roll_drop",
        deletion_label="Voter Roll Reduction",
        title="2026 Victory Margin vs Voter Roll Reduction (2024 → 2026)",
        description=(
            "Compares each constituency's 2026 winning margin against the total voter roll reduction "
            "between 2024 and 2026. Seats where the margin is **less than** the voter roll reduction "
            "are marked Vulnerable — the number of removed voters exceeds the winning margin."
        ),
    )


def show_margin_vs_sir(df):
    _show_margin_analysis(
        df,
        deletion_col="sir_27l",
        deletion_label="SIR Deletions",
        title="2026 Victory Margin vs SIR 27-Lakh Deletions",
        description=(
            "Compares each constituency's 2026 winning margin against the SIR-identified deletions "
            "from the 27-lakh voter roll purge. Seats where the margin is **less than** the SIR "
            "deletions are marked Vulnerable — the purge alone could have swung the result."
        ),
    )


# ── Parliamentary views ────────────────────────────────────────────────────────

_PC_EL = [
    ("ls19", "2019", "Lok Sabha",    True),
    ("vs21", "2021", "Vidhan Sabha", False),
    ("ls24", "2024", "Lok Sabha",    True),
    ("vs26", "2026", "Vidhan Sabha", False),
]
_WIN_COLORS = {**_PARTY_COLORS, "Split": "#AEC7E8", "Other": "#7F7F7F"}


def show_parliament_summary(pc_data):
    st.subheader("West Bengal — Parliamentary Constituencies (42 seats)")
    st.caption(
        "2019 & 2024: actual Lok Sabha results.  "
        "2021 & 2026: Vidhan Sabha assembly results aggregated to PC boundary."
    )

    # ── State-level summary table ─────────────────────────────────────────────
    sum_rows, bar_data, seat_rows = [], [], []
    for key, year, etype, is_ls in _PC_EL:
        d = pc_data[key]
        tmc_w = int((d["winner"] == "TMC").sum())
        bjp_w = int((d["winner"] == "BJP").sum())
        oth_w = len(d) - tmc_w - bjp_w
        tmc_v = d["tmc"].sum(); bjp_v = d["bjp"].sum()
        tv    = d["total_votes"].sum(); el = d["electors"].sum()
        if is_ls:
            won = f"TMC: {tmc_w}  |  BJP: {bjp_w}  |  Other: {oth_w}"
        else:
            tmc_s = int(d["tmc_seats"].sum()); bjp_s = int(d["bjp_seats"].sum())
            won = f"TMC ACs: {tmc_s}  |  BJP ACs: {bjp_s}"
        sum_rows.append({
            "Year": year, "Election": etype, "Winners / PCs": won,
            "TMC Votes": fmt(tmc_v), "TMC %": pct(tmc_v, tv),
            "BJP Votes": fmt(bjp_v), "BJP %": pct(bjp_v, tv),
            "Total Votes": fmt(tv),  "Turnout": pct(tv, el),
        })
        try:
            bar_data += [
                {"Year": year, "Party": "TMC", "Vote %": tmc_v / tv * 100},
                {"Year": year, "Party": "BJP", "Vote %": bjp_v / tv * 100},
            ]
        except ZeroDivisionError:
            pass
        lbl = f"{year} ({etype[:2]})"
        seat_rows += [
            {"Election": lbl, "Party": "TMC", "Count": tmc_w},
            {"Election": lbl, "Party": "BJP", "Count": bjp_w},
        ]
        if oth_w: seat_rows.append({"Election": lbl, "Party": "Other/Split", "Count": oth_w})

    st.markdown("**State-level summary across 4 elections**")
    st.dataframe(pd.DataFrame(sum_rows), use_container_width=True, hide_index=True, height=210)

    col_a, col_b = st.columns(2)
    with col_a:
        if bar_data:
            fig = px.bar(
                pd.DataFrame(bar_data), x="Year", y="Vote %", color="Party",
                barmode="group", color_discrete_map=_PARTY_COLORS,
                title="TMC vs BJP Vote Share (%) — all elections",
            )
            fig.update_layout(yaxis_range=[0, 100], height=340, margin=dict(t=40, b=10))
            st.plotly_chart(fig, use_container_width=True)
    with col_b:
        fig2 = px.bar(
            pd.DataFrame(seat_rows), x="Election", y="Count", color="Party",
            barmode="stack",
            color_discrete_map={**_PARTY_COLORS, "Other/Split": "#7F7F7F"},
            text="Count",
            title="PC-level seat outcome (42 total PCs per election)",
        )
        fig2.update_traces(textposition="inside", textfont_size=13)
        fig2.update_layout(height=340, legend_title="", margin=dict(t=40, b=10))
        st.plotly_chart(fig2, use_container_width=True)

    # ── All-42-PCs table ─────────────────────────────────────────────────────
    st.markdown("**All 42 Parliamentary Constituencies — winner & vote share per election**")
    ls19 = pc_data["ls19"]

    def _g(d, pc, col):
        sub = d[d["pc_name"] == pc]
        return sub.iloc[0][col] if len(sub) else None

    rows = []
    for _, r in ls19.sort_values("pc_no").iterrows():
        pc = r["pc_name"]
        rows.append({
            "PC No":       int(r["pc_no"]),
            "PC Name":     pc,
            "2019 Winner": _g(pc_data["ls19"], pc, "winner"),
            "2019 TMC %":  pct(_g(pc_data["ls19"],pc,"tmc"), _g(pc_data["ls19"],pc,"total_votes")),
            "2019 BJP %":  pct(_g(pc_data["ls19"],pc,"bjp"), _g(pc_data["ls19"],pc,"total_votes")),
            "2021 Winner": _g(pc_data["vs21"], pc, "winner"),
            "2021 TMC ACs": _g(pc_data["vs21"], pc, "tmc_seats"),
            "2021 BJP ACs": _g(pc_data["vs21"], pc, "bjp_seats"),
            "2024 Winner": _g(pc_data["ls24"], pc, "winner"),
            "2024 TMC %":  pct(_g(pc_data["ls24"],pc,"tmc"), _g(pc_data["ls24"],pc,"total_votes")),
            "2024 BJP %":  pct(_g(pc_data["ls24"],pc,"bjp"), _g(pc_data["ls24"],pc,"total_votes")),
            "2026 Winner": _g(pc_data["vs26"], pc, "winner"),
            "2026 TMC ACs": _g(pc_data["vs26"], pc, "tmc_seats"),
            "2026 BJP ACs": _g(pc_data["vs26"], pc, "bjp_seats"),
        })
    _skip_pc = {"PC No", "PC Name", "2019 Winner", "2021 Winner", "2024 Winner", "2026 Winner"}
    disp = pd.DataFrame(rows)
    for c in disp.columns:
        if c not in _skip_pc and c not in ("2019 TMC %","2019 BJP %","2024 TMC %","2024 BJP %"):
            disp[c] = pd.to_numeric(disp[c], errors="coerce")
    st.dataframe(disp, use_container_width=True, hide_index=True)


def show_parliament_seat(pc_name, pc_data):
    def _r(key):
        d = pc_data[key]; sub = d[d["pc_name"] == pc_name]
        return sub.iloc[0] if len(sub) else None

    r19 = _r("ls19"); r21 = _r("vs21"); r24 = _r("ls24"); r26 = _r("vs26")
    pc_no = int(r19["pc_no"]) if r19 is not None else "?"

    st.subheader(f"Parliamentary Constituency {pc_no}: {pc_name}")

    # ── Summary table ─────────────────────────────────────────────────────────
    table, bar_data, seat_data = [], [], []
    els = [(r19,"2019","Lok Sabha",True), (r21,"2021","Vidhan Sabha",False),
           (r24,"2024","Lok Sabha",True), (r26,"2026","Vidhan Sabha",False)]

    for r, year, etype, is_ls in els:
        if r is None: continue
        tv  = float(r.get("total_votes") or 0)
        tmc = float(r.get("tmc") or 0)
        bjp = float(r.get("bjp") or 0)
        el  = float(r.get("electors") or 0)
        others = []
        for i in range(1, 4):
            p, v = r.get(f"p{i}"), r.get(f"v{i}")
            if pd.notna(p) and pd.notna(v) and float(v) > 0:
                others.append(f"{p}: {fmt(v)} ({pct(v, tv)})")
        row = {
            "Year": year, "Election": etype,
            "Registered Voters": fmt(el), "Total Votes": fmt(tv), "Turnout": pct(tv, el),
            "TMC Votes": fmt(tmc), "TMC %": pct(tmc, tv),
            "BJP Votes": fmt(bjp), "BJP %": pct(bjp, tv),
            "Winner": r.get("winner", "—"), "Margin": fmt(r.get("margin")),
        }
        if not is_ls:
            row["TMC ACs"] = int(r.get("tmc_seats", 0))
            row["BJP ACs"] = int(r.get("bjp_seats", 0))
            row["Other ACs"] = int(r.get("other_seats", 0))
            seat_data.append({
                "Election": f"{year} ({etype[:2]})",
                "TMC": int(r.get("tmc_seats", 0)),
                "BJP": int(r.get("bjp_seats", 0)),
                "Other": int(r.get("other_seats", 0)),
            })
        row["Top Others"] = "  |  ".join(others) or "—"
        table.append(row)
        try:
            bar_data += [
                {"Year": year, "Party": "TMC", "Vote %": tmc / tv * 100},
                {"Year": year, "Party": "BJP", "Vote %": bjp / tv * 100},
            ]
        except ZeroDivisionError:
            pass

    st.dataframe(pd.DataFrame(table), use_container_width=True, hide_index=True, height=210)

    # ── Charts row ────────────────────────────────────────────────────────────
    col_a, col_b = st.columns(2)
    with col_a:
        if bar_data:
            fig = px.bar(
                pd.DataFrame(bar_data), x="Year", y="Vote %", color="Party",
                barmode="group", color_discrete_map=_PARTY_COLORS,
                title="TMC vs BJP Vote Share (%) across Elections",
            )
            fig.update_layout(yaxis_range=[0, 100], height=360, margin=dict(t=40, b=10))
            st.plotly_chart(fig, use_container_width=True)
    with col_b:
        if seat_data:
            sd_melt = pd.melt(
                pd.DataFrame(seat_data), id_vars="Election",
                value_vars=["TMC","BJP","Other"], var_name="Party", value_name="Seats",
            )
            fig2 = px.bar(
                sd_melt, x="Election", y="Seats", color="Party",
                barmode="stack",
                color_discrete_map={**_PARTY_COLORS, "Other": "#7F7F7F"},
                text="Seats",
                title="Assembly Seats Won per Party (Vidhan Sabha elections)",
            )
            fig2.update_traces(textposition="inside")
            fig2.update_layout(height=360, legend_title="", margin=dict(t=40, b=10))
            st.plotly_chart(fig2, use_container_width=True)

    # ── Per-election breakdown tabs ───────────────────────────────────────────
    tab19, tab21, tab24, tab26 = st.tabs(["2019 Lok Sabha", "2021 Vidhan Sabha",
                                           "2024 Lok Sabha", "2026 Vidhan Sabha"])
    for tab, r, year, etype, is_ls in [
        (tab19, r19, "2019", "Lok Sabha",    True),
        (tab21, r21, "2021", "Vidhan Sabha", False),
        (tab24, r24, "2024", "Lok Sabha",    True),
        (tab26, r26, "2026", "Vidhan Sabha", False),
    ]:
        with tab:
            if r is None:
                st.caption("No data available.")
                continue
            tv  = float(r.get("total_votes") or 0)
            tmc = float(r.get("tmc") or 0)
            bjp = float(r.get("bjp") or 0)

            pie_rows = [{"Party": "TMC", "Votes": tmc}, {"Party": "BJP", "Votes": bjp}]
            for i in range(1, 4):
                p, v = r.get(f"p{i}"), r.get(f"v{i}")
                if pd.notna(p) and pd.notna(v) and float(v) > 0:
                    pie_rows.append({"Party": str(p), "Votes": float(v)})

            c1, c2 = st.columns([3, 2])
            with c1:
                fig = px.pie(
                    pd.DataFrame(pie_rows), names="Party", values="Votes",
                    color="Party", color_discrete_map=_PARTY_COLORS,
                    title=f"{year} {etype} — {pc_name}",
                    hole=0.35,
                )
                fig.update_layout(height=360, margin=dict(t=40, b=10))
                st.plotly_chart(fig, use_container_width=True)
            with c2:
                win = r.get("winner", "—")
                win_color = _TMC_COLOR if win == "TMC" else (_BJP_COLOR if win == "BJP" else "#7F7F7F")
                st.markdown(
                    f"<div style='font-size:1.3rem;font-weight:bold;"
                    f"color:{win_color};padding:8px 0'>Winner: {win}</div>",
                    unsafe_allow_html=True,
                )
                st.metric("TMC Votes",   fmt(tmc), delta=pct(tmc, tv), delta_color="off")
                st.metric("BJP Votes",   fmt(bjp), delta=pct(bjp, tv), delta_color="off")
                st.metric("Margin",      fmt(r.get("margin")))
                st.metric("Total Votes", fmt(tv))
                st.metric("Turnout",     pct(tv, r.get("electors") or 1))
                if not is_ls:
                    st.metric("TMC ACs Won", int(r.get("tmc_seats", 0)))
                    st.metric("BJP ACs Won", int(r.get("bjp_seats", 0)))


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

    try:
        pc_data = load_parliament()
    except Exception as e:
        pc_data = None
        st.sidebar.warning(f"Parliamentary data unavailable: {e}")

    if "active_section" not in st.session_state:
        st.session_state.active_section = "summary"

    def _on_summary(): st.session_state.active_section = "summary"
    def _on_pred():    st.session_state.active_section = "prediction"

    with st.sidebar:
        st.header("Select View")
        view = st.radio("", [
                            "State Summary", "District Summary", "Constituency Summary",
                            "Margin vs Roll Deletion", "Margin vs SIR Deletion",
                            "Parliament Summary", "Parliament Seat",
                        ],
                        label_visibility="collapsed", on_change=_on_summary)

        sel_dist, sel_const, sel_pc = None, None, None
        if view == "District Summary":
            districts = sorted(df["district"].dropna().unique().tolist())
            sel_dist = st.selectbox("District", districts)
        elif view == "Constituency Summary":
            opts = sorted(
                f"{int(r.ac_no):03d} – {r.ac_name} ({r.district})"
                for _, r in df.iterrows()
            )
            sel_const = st.selectbox("Constituency", opts)
        elif view == "Parliament Seat":
            pc_names = pc_data["pc_names"] if pc_data else []
            sel_pc = st.selectbox("Parliamentary Constituency", pc_names)

        st.divider()
        st.header("Predictions")
        pred_view = st.radio("", ["Predictions", "Possibilities",
                                   "SIR Impact 21→26", "SIR Impact 24→26"],
                             label_visibility="collapsed", key="pred_radio", on_change=_on_pred)

    if st.session_state.active_section == "summary":
        if view == "State Summary":
            show_state(df)
        elif view == "District Summary" and sel_dist:
            show_district(df, sel_dist)
        elif view == "Constituency Summary" and sel_const:
            ac_no = int(sel_const.split("–")[0].strip())
            row = df[df["ac_no"] == ac_no].iloc[0]
            show_constituency(row)
        elif view == "Margin vs Roll Deletion":
            show_margin_vs_roll(df)
        elif view == "Margin vs SIR Deletion":
            show_margin_vs_sir(df)
        elif view == "Parliament Summary":
            if pc_data: show_parliament_summary(pc_data)
            else: st.error("Parliamentary data could not be loaded.")
        elif view == "Parliament Seat" and sel_pc:
            if pc_data: show_parliament_seat(sel_pc, pc_data)
            else: st.error("Parliamentary data could not be loaded.")
    else:
        if pred_view == "Predictions":
            show_prediction()
        elif pred_view == "Possibilities":
            show_possibilities(df)
        elif pred_view == "SIR Impact 21→26":
            show_sir_impact(df)
        elif pred_view == "SIR Impact 24→26":
            show_sir_impact_2024(df)


if __name__ == "__main__":
    main()
