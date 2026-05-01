import streamlit as st
import pandas as pd
import plotly.express as px

st.set_page_config(
    page_title="West Bengal Elections 2019–2026",
    layout="wide",
    initial_sidebar_state="expanded",
)

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


# ── Gender helpers ─────────────────────────────────────────────────────────────

def gender_metrics(male, female, third):
    """Render male/female/third-gender voter counts and M:F ratio as st.metrics."""
    try:
        ratio = float(male) / float(female) * 1000
        ratio_str = f"{ratio:.0f} per 1,000 females"
    except (TypeError, ValueError, ZeroDivisionError):
        ratio_str = "—"

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Male voters",        fmt(male))
    c2.metric("Female voters",      fmt(female))
    c3.metric("Third-gender voters", fmt(third))
    c4.metric("M : F ratio (2026)", ratio_str)


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

    c1, c2 = st.columns([1, 2])
    with c1:
        st.dataframe(
            row.reset_index().rename(columns={"index": "Religion", dem_district: "%"}),
            use_container_width=True, hide_index=True,
        )
    with c2:
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
        c1, c2 = st.columns(2)
        with c1:
            fig = px.bar(
                pd.DataFrame(bar_data), x="Year", y="Vote %", color="Party",
                barmode="group",
                color_discrete_map={"TMC": "#2CA02C", "BJP": "#FF7F0E"},
                title="TMC vs BJP Vote Share (%)",
            )
            fig.update_layout(yaxis_range=[0, 100], height=360)
            st.plotly_chart(fig, use_container_width=True)
        with c2:
            pie_rows = []
            yr = "24"
            tv24 = row.get(f"total_votes_{yr}")
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
    show_demography(row["district"])


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
        rows.append(row)
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    st.divider()
    st.markdown("#### 2026 Voter Demographics")
    male  = pd.to_numeric(sub["male_26"],   errors="coerce").sum()
    female= pd.to_numeric(sub["female_26"], errors="coerce").sum()
    third = pd.to_numeric(sub["third_26"],  errors="coerce").sum()
    gender_metrics(male, female, third)
    show_demography(district)


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

    st.markdown("**All 294 Constituencies**")
    cols = ["ac_no", "ac_name", "district"]
    renames = {"ac_no": "AC No", "ac_name": "Constituency", "district": "District"}
    for yr, full, _ in YEARS:
        cols += [f"total_votes_{yr}", f"tmc_{yr}", f"bjp_{yr}"]
        renames.update({
            f"total_votes_{yr}": f"{full} Votes",
            f"tmc_{yr}": f"{full} TMC",
            f"bjp_{yr}": f"{full} BJP",
        })
    cols += ["votes_26", "electors_26"]
    renames.update({"votes_26": "2026 Votes Cast", "electors_26": "2026 Voters"})

    disp = df[cols].rename(columns=renames).copy()
    for c in list(renames.values())[3:]:
        disp[c] = pd.to_numeric(disp[c], errors="coerce")
    st.dataframe(disp, use_container_width=True, hide_index=True)


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
        view = st.radio("", ["State Summary", "By District", "By Constituency"],
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
    elif view == "By District" and sel_dist:
        show_district(df, sel_dist)
    elif view == "By Constituency" and sel_const:
        ac_no = int(sel_const.split("–")[0].strip())
        row = df[df["ac_no"] == ac_no].iloc[0]
        show_constituency(row)


if __name__ == "__main__":
    main()
