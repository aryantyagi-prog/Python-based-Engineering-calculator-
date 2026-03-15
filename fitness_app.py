# fitness_app.py
# Fitness Tracker — Analytics Dashboard (Streamlit)
#
# Tech mapping from the problem statement:
#   Supabase backend  →  local SQLite with an identical schema (tables: workouts, lifts, runs)
#   Recharts / Victory charts → Plotly (animated, interactive line graphs & pie charts)
#   Next.js dark-mode UI  →  Streamlit with a custom dark CSS theme
#
# Run:  streamlit run fitness_app.py

import os
import math
import sqlite3
from datetime import date, datetime, timedelta

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Fitness Tracker",
    page_icon="🏋️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Dark-mode CSS (minimalist) ────────────────────────────────────────────────
DARK_CSS = """
<style>
/* ---- base ---- */
html, body, [data-testid="stAppViewContainer"], [data-testid="stApp"] {
    background-color: #0d0d0d !important;
    color: #e0e0e0 !important;
}
[data-testid="stSidebar"] {
    background-color: #111111 !important;
    border-right: 1px solid #222;
}
/* ---- headings ---- */
h1, h2, h3, h4 { color: #ffffff !important; letter-spacing: 0.02em; }
/* ---- metric cards ---- */
[data-testid="metric-container"] {
    background: #1a1a1a;
    border: 1px solid #2a2a2a;
    border-radius: 10px;
    padding: 12px 16px;
}
[data-testid="stMetricValue"] { color: #7ee8a2 !important; font-size: 1.6rem !important; }
[data-testid="stMetricLabel"] { color: #888 !important; font-size: 0.8rem !important; }
/* ---- input widgets ---- */
[data-baseweb="input"] input,
[data-baseweb="select"] div,
[data-baseweb="textarea"] textarea {
    background-color: #1e1e1e !important;
    color: #e0e0e0 !important;
    border: 1px solid #333 !important;
    border-radius: 6px !important;
}
/* ---- buttons ---- */
[data-testid="stButton"] button {
    background: #1a6b3a !important;
    color: #fff !important;
    border: none !important;
    border-radius: 6px !important;
    font-weight: 600 !important;
}
[data-testid="stButton"] button:hover {
    background: #228b4c !important;
}
/* ---- tabs ---- */
[data-baseweb="tab-list"] { background: #111 !important; }
[data-baseweb="tab"] { color: #888 !important; }
[aria-selected="true"] { color: #7ee8a2 !important; border-bottom: 2px solid #7ee8a2 !important; }
/* ---- dividers ---- */
hr { border-color: #222 !important; }
/* ---- dataframe ---- */
[data-testid="stDataFrameResizable"] { background: #1a1a1a !important; }
</style>
"""
st.markdown(DARK_CSS, unsafe_allow_html=True)

# ── Database setup (mirrors the Supabase schema) ──────────────────────────────
DB_PATH = os.path.join(os.path.dirname(__file__), "fitness_tracker.db")
conn = sqlite3.connect(DB_PATH, check_same_thread=False)
cur = conn.cursor()

cur.executescript("""
CREATE TABLE IF NOT EXISTS workouts (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    title        TEXT    NOT NULL,
    workout_type TEXT    NOT NULL CHECK (workout_type IN ('lifting','run','mixed')),
    date         TEXT    NOT NULL DEFAULT (DATE('now')),
    notes        TEXT,
    created_at   TEXT    NOT NULL DEFAULT (DATETIME('now'))
);

CREATE TABLE IF NOT EXISTS lifts (
    id            INTEGER  PRIMARY KEY AUTOINCREMENT,
    workout_id    INTEGER  NOT NULL REFERENCES workouts(id) ON DELETE CASCADE,
    exercise_name TEXT     NOT NULL,
    sets          INTEGER  NOT NULL CHECK (sets > 0),
    reps          INTEGER  NOT NULL CHECK (reps > 0),
    weight_kg     REAL     NOT NULL DEFAULT 0 CHECK (weight_kg >= 0),
    rpe           REAL     CHECK (rpe BETWEEN 1 AND 10),
    notes         TEXT,
    logged_at     TEXT     NOT NULL DEFAULT (DATETIME('now'))
);

CREATE TABLE IF NOT EXISTS runs (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    workout_id       INTEGER NOT NULL REFERENCES workouts(id) ON DELETE CASCADE,
    run_type         TEXT    NOT NULL CHECK (run_type IN ('track','road','trail','treadmill')),
    distance_km      REAL    NOT NULL CHECK (distance_km > 0),
    duration_seconds INTEGER NOT NULL CHECK (duration_seconds > 0),
    avg_heart_rate   INTEGER,
    max_heart_rate   INTEGER,
    elevation_gain_m REAL    DEFAULT 0,
    notes            TEXT,
    logged_at        TEXT    NOT NULL DEFAULT (DATETIME('now'))
);
""")
conn.commit()

# ── Helpers ───────────────────────────────────────────────────────────────────

def fmt_pace(sec_per_km: float) -> str:
    """Return pace as mm:ss /km string."""
    m, s = divmod(int(sec_per_km), 60)
    return f"{m}:{s:02d} /km"


def seed_demo_data():
    """Insert a few weeks of sample data so the dashboard is never empty."""
    cur.execute("SELECT COUNT(*) FROM workouts")
    if cur.fetchone()[0] > 0:
        return  # already seeded

    today = date.today()
    demo = [
        # (days_ago, title, type, exercise/distance, sets/reps/weight or duration)
        (0,  "Upper Body A",   "lifting", [("Bench Press", 4, 8, 80), ("OHP", 3, 10, 50), ("Rows", 4, 10, 70)]),
        (2,  "5 km Track Run", "run",     [("track", 5.0, 22*60)]),
        (4,  "Lower Body A",   "lifting", [("Squat", 5, 5, 100), ("Romanian DL", 3, 10, 80), ("Leg Press", 3, 12, 120)]),
        (7,  "Upper Body B",   "lifting", [("Pull-ups", 4, 8, 0), ("Incline DB", 3, 10, 32), ("Face Pulls", 3, 15, 20)]),
        (9,  "10 km Road Run", "run",     [("road", 10.0, 52*60)]),
        (11, "Lower Body B",   "lifting", [("Deadlift", 4, 5, 120), ("Front Squat", 3, 8, 60), ("Calf Raises", 4, 15, 40)]),
        (14, "Upper Body A",   "lifting", [("Bench Press", 4, 8, 82.5), ("OHP", 3, 10, 52.5), ("Rows", 4, 10, 72.5)]),
        (16, "5 km Track Run", "run",     [("track", 5.0, 21*60+30)]),
        (18, "Lower Body A",   "lifting", [("Squat", 5, 5, 102.5), ("Romanian DL", 3, 10, 82.5), ("Leg Press", 3, 12, 125)]),
        (21, "Upper Body B",   "lifting", [("Pull-ups", 4, 9, 0), ("Incline DB", 3, 10, 34), ("Face Pulls", 3, 15, 20)]),
        (23, "8 km Trail Run", "run",     [("trail", 8.0, 48*60)]),
        (25, "Lower Body B",   "lifting", [("Deadlift", 4, 5, 125), ("Front Squat", 3, 8, 62.5), ("Calf Raises", 4, 15, 40)]),
        (28, "5 km Track Run", "run",     [("track", 5.0, 21*60)]),
    ]

    for days_ago, title, wtype, exercises in demo:
        wdate = (today - timedelta(days=days_ago)).isoformat()
        cur.execute(
            "INSERT INTO workouts (title, workout_type, date) VALUES (?, ?, ?)",
            (title, wtype, wdate),
        )
        wid = cur.lastrowid
        for ex in exercises:
            if wtype == "run":
                run_type, dist, dur = ex
                cur.execute(
                    "INSERT INTO runs (workout_id, run_type, distance_km, duration_seconds) VALUES (?, ?, ?, ?)",
                    (wid, run_type, dist, dur),
                )
            else:
                ename, sets, reps, weight = ex
                cur.execute(
                    "INSERT INTO lifts (workout_id, exercise_name, sets, reps, weight_kg) VALUES (?, ?, ?, ?, ?)",
                    (wid, ename, sets, reps, weight),
                )
    conn.commit()


seed_demo_data()

# ── Sidebar navigation ────────────────────────────────────────────────────────
st.sidebar.markdown("# 🏋️ Fitness Tracker")
st.sidebar.markdown("---")
page = st.sidebar.radio(
    "Navigate",
    ["📊 Analytics Dashboard", "➕ Log Workout", "➕ Log Run", "📋 History"],
    label_visibility="collapsed",
)
st.sidebar.markdown("---")
st.sidebar.markdown(
    "<small style='color:#555'>Data stored locally in SQLite, mirroring the Supabase schema "
    "defined in <code>supabase_schema.sql</code>.</small>",
    unsafe_allow_html=True,
)

# ═════════════════════════════════════════════════════════════════════════════
# PAGE: Analytics Dashboard
# ═════════════════════════════════════════════════════════════════════════════
if page == "📊 Analytics Dashboard":
    st.title("📊 Analytics Dashboard")
    st.markdown("<p style='color:#888;margin-top:-10px'>Your training at a glance · last 30 days</p>",
                unsafe_allow_html=True)
    st.markdown("---")

    # ── KPI row ──────────────────────────────────────────────────────────────
    since = (date.today() - timedelta(days=30)).isoformat()

    cur.execute("SELECT COUNT(*) FROM workouts WHERE date >= ?", (since,))
    total_sessions = cur.fetchone()[0]

    cur.execute("SELECT COALESCE(SUM(distance_km),0) FROM runs r "
                "JOIN workouts w ON w.id=r.workout_id WHERE w.date >= ?", (since,))
    total_km = cur.fetchone()[0]

    cur.execute("SELECT COALESCE(SUM(l.sets * l.reps * l.weight_kg),0) FROM lifts l "
                "JOIN workouts w ON w.id=l.workout_id WHERE w.date >= ?", (since,))
    total_volume = cur.fetchone()[0]

    cur.execute(
        "SELECT COALESCE(AVG(CAST(duration_seconds AS REAL)/distance_km),0) "
        "FROM runs r JOIN workouts w ON w.id=r.workout_id WHERE w.date >= ?", (since,)
    )
    avg_pace_raw = cur.fetchone()[0]

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Workouts", total_sessions)
    k2.metric("Total Distance", f"{total_km:.1f} km")
    k3.metric("Lift Volume", f"{total_volume:,.0f} kg")
    k4.metric("Avg Pace", fmt_pace(avg_pace_raw) if avg_pace_raw else "—")

    st.markdown("---")

    # ── Charts row ───────────────────────────────────────────────────────────
    left, right = st.columns([3, 2], gap="large")

    # ── Line chart: Track pace history ───────────────────────────────────────
    with left:
        st.subheader("🏃 Track Pace History")

        cur.execute(
            """
            SELECT w.date,
                   r.distance_km,
                   r.duration_seconds,
                   CAST(r.duration_seconds AS REAL) / r.distance_km AS pace_sec_per_km,
                   r.run_type
            FROM runs r
            JOIN workouts w ON w.id = r.workout_id
            ORDER BY w.date ASC
            """,
        )
        runs_rows = cur.fetchall()
        runs_df = pd.DataFrame(
            runs_rows,
            columns=["date", "distance_km", "duration_seconds", "pace_sec_per_km", "run_type"],
        )

        if runs_df.empty:
            st.info("No runs logged yet. Head to **Log Run** to add your first run!")
        else:
            runs_df["date"] = pd.to_datetime(runs_df["date"])
            runs_df["pace_min_km"] = runs_df["pace_sec_per_km"] / 60
            runs_df["pace_label"] = runs_df["pace_sec_per_km"].apply(fmt_pace)
            runs_df["run_type"] = runs_df["run_type"].str.capitalize()

            fig_line = px.line(
                runs_df,
                x="date",
                y="pace_min_km",
                color="run_type",
                markers=True,
                custom_data=["pace_label", "distance_km", "run_type"],
                color_discrete_map={
                    "Track": "#7ee8a2",
                    "Road":  "#60b4f5",
                    "Trail": "#f0a868",
                    "Treadmill": "#c084fc",
                },
            )
            fig_line.update_traces(
                line=dict(width=2.5),
                marker=dict(size=8),
                hovertemplate=(
                    "<b>%{customdata[2]}</b><br>"
                    "Date: %{x|%d %b %Y}<br>"
                    "Pace: %{customdata[0]}<br>"
                    "Distance: %{customdata[1]:.2f} km"
                    "<extra></extra>"
                ),
            )
            # Y-axis: lower pace number = faster, so invert
            y_min = runs_df["pace_min_km"].min()
            y_max = runs_df["pace_min_km"].max()
            padding = (y_max - y_min) * 0.2 if y_max != y_min else 0.5

            tick_vals = []
            tick_texts = []
            # Create minute:second tick labels
            lo = math.floor(y_min - padding)
            hi = math.ceil(y_max + padding)
            for v in range(max(0, lo), hi + 1):
                tick_vals.append(v)
                m, s = divmod(v * 60, 60)
                tick_texts.append(f"{int(m)}:00")

            fig_line.update_yaxes(
                autorange="reversed",
                range=[y_max + padding, y_min - padding],
                tickvals=tick_vals,
                ticktext=tick_texts,
                title="Pace (min/km)",
                gridcolor="#222",
                zerolinecolor="#333",
            )
            fig_line.update_xaxes(title="Date", gridcolor="#222", zerolinecolor="#333")
            fig_line.update_layout(
                paper_bgcolor="#0d0d0d",
                plot_bgcolor="#0d0d0d",
                font=dict(color="#e0e0e0", family="sans-serif"),
                legend=dict(
                    bgcolor="#111",
                    bordercolor="#333",
                    borderwidth=1,
                    title_text="Run Type",
                ),
                margin=dict(l=10, r=10, t=20, b=10),
                hovermode="x unified",
                transition={"duration": 500, "easing": "cubic-in-out"},
            )
            st.plotly_chart(fig_line, use_container_width=True)

    # ── Pie chart: Workout volume distribution ────────────────────────────────
    with right:
        st.subheader("🥧 Volume Distribution")

        cur.execute(
            """
            SELECT w.workout_type, COUNT(DISTINCT w.id) AS session_count
            FROM workouts w
            WHERE w.date >= ?
            GROUP BY w.workout_type
            """,
            (since,),
        )
        vol_rows = cur.fetchall()
        vol_df = pd.DataFrame(vol_rows, columns=["workout_type", "session_count"])

        if vol_df.empty:
            st.info("No workouts logged yet.")
        else:
            vol_df["label"] = vol_df["workout_type"].str.capitalize()

            fig_pie = go.Figure(
                go.Pie(
                    labels=vol_df["label"],
                    values=vol_df["session_count"],
                    hole=0.45,
                    marker=dict(
                        colors=["#7ee8a2", "#60b4f5", "#f0a868"],
                        line=dict(color="#0d0d0d", width=2),
                    ),
                    textinfo="label+percent",
                    textfont=dict(color="#e0e0e0", size=13),
                    hovertemplate="<b>%{label}</b><br>Sessions: %{value}<extra></extra>",
                )
            )
            fig_pie.update_layout(
                paper_bgcolor="#0d0d0d",
                plot_bgcolor="#0d0d0d",
                font=dict(color="#e0e0e0"),
                showlegend=False,
                margin=dict(l=10, r=10, t=20, b=10),
                annotations=[
                    dict(
                        text="Sessions",
                        x=0.5,
                        y=0.5,
                        font_size=14,
                        font_color="#888",
                        showarrow=False,
                    )
                ],
                transition={"duration": 500, "easing": "cubic-in-out"},
            )
            st.plotly_chart(fig_pie, use_container_width=True)

    st.markdown("---")

    # ── Recent activity table ─────────────────────────────────────────────────
    st.subheader("📅 Recent Workouts")
    cur.execute(
        "SELECT date, title, workout_type, notes FROM workouts ORDER BY date DESC LIMIT 10"
    )
    recent = cur.fetchall()
    if recent:
        df_recent = pd.DataFrame(recent, columns=["Date", "Title", "Type", "Notes"])
        df_recent["Type"] = df_recent["Type"].str.capitalize()
        df_recent["Notes"] = df_recent["Notes"].fillna("—")
        st.dataframe(df_recent, use_container_width=True, hide_index=True)
    else:
        st.write("No workouts logged yet.")


# ═════════════════════════════════════════════════════════════════════════════
# PAGE: Log Workout (lifting session)
# ═════════════════════════════════════════════════════════════════════════════
elif page == "➕ Log Workout":
    st.title("➕ Log a Lifting Workout")
    st.markdown("---")

    with st.form("log_workout"):
        col1, col2 = st.columns(2)
        with col1:
            w_title = st.text_input("Session title", placeholder="e.g. Upper Body A")
            w_date = st.date_input("Date", value=date.today())
            w_type = st.selectbox("Workout type", ["lifting", "mixed"])
        with col2:
            w_notes = st.text_area("Notes (optional)", height=120)

        st.subheader("Exercises")
        num_exercises = st.number_input("Number of exercises", min_value=1, max_value=20, value=3)

        exercises = []
        for i in range(int(num_exercises)):
            st.markdown(f"**Exercise {i+1}**")
            ec1, ec2, ec3, ec4, ec5 = st.columns([2, 1, 1, 1, 1])
            with ec1:
                ename = st.text_input(f"Exercise name #{i+1}", key=f"en_{i}", placeholder="Bench Press")
            with ec2:
                sets = st.number_input("Sets", min_value=1, max_value=20, value=3, key=f"sets_{i}")
            with ec3:
                reps = st.number_input("Reps", min_value=1, max_value=100, value=8, key=f"reps_{i}")
            with ec4:
                weight = st.number_input("Weight (kg)", min_value=0.0, value=0.0, step=2.5, key=f"wt_{i}")
            with ec5:
                rpe = st.number_input("RPE (1–10)", min_value=1.0, max_value=10.0, value=7.0,
                                      step=0.5, key=f"rpe_{i}")
            exercises.append((ename, int(sets), int(reps), float(weight), float(rpe)))

        submitted = st.form_submit_button("💾 Save Workout")

    if submitted:
        if not w_title.strip():
            st.error("Please enter a session title.")
        else:
            cur.execute(
                "INSERT INTO workouts (title, workout_type, date, notes) VALUES (?, ?, ?, ?)",
                (w_title.strip(), w_type, w_date.isoformat(), w_notes.strip() or None),
            )
            wid = cur.lastrowid
            for ename, sets, reps, weight, rpe in exercises:
                if ename.strip():
                    cur.execute(
                        "INSERT INTO lifts (workout_id, exercise_name, sets, reps, weight_kg, rpe) "
                        "VALUES (?, ?, ?, ?, ?, ?)",
                        (wid, ename.strip(), sets, reps, weight, rpe),
                    )
            conn.commit()
            total_vol = sum(s * r * w for _, s, r, w, _ in exercises)
            st.success(f"✅ Saved **{w_title}** — {len(exercises)} exercise(s), "
                       f"{total_vol:,.0f} kg total volume.")


# ═════════════════════════════════════════════════════════════════════════════
# PAGE: Log Run
# ═════════════════════════════════════════════════════════════════════════════
elif page == "➕ Log Run":
    st.title("➕ Log a Run")
    st.markdown("---")

    with st.form("log_run"):
        col1, col2 = st.columns(2)
        with col1:
            r_date = st.date_input("Date", value=date.today())
            r_type = st.selectbox("Run type", ["track", "road", "trail", "treadmill"])
            distance = st.number_input("Distance (km)", min_value=0.1, max_value=200.0,
                                       value=5.0, step=0.1)
        with col2:
            dur_min = st.number_input("Duration — minutes", min_value=0, max_value=600, value=25)
            dur_sec = st.number_input("Duration — seconds", min_value=0, max_value=59, value=0)
            avg_hr = st.number_input("Avg heart rate (bpm, 0=skip)", min_value=0, max_value=250, value=0)
            max_hr = st.number_input("Max heart rate (bpm, 0=skip)", min_value=0, max_value=250, value=0)

        elevation = st.number_input("Elevation gain (m)", min_value=0.0, value=0.0)
        r_notes = st.text_area("Notes (optional)")
        submitted = st.form_submit_button("💾 Save Run")

    if submitted:
        total_secs = dur_min * 60 + dur_sec
        if total_secs <= 0:
            st.error("Duration must be greater than 0.")
        elif distance <= 0:
            st.error("Distance must be greater than 0.")
        else:
            # Create a parent workout row for the run.
            title = f"{distance:.1f} km {r_type.capitalize()} Run"
            cur.execute(
                "INSERT INTO workouts (title, workout_type, date) VALUES (?, 'run', ?)",
                (title, r_date.isoformat()),
            )
            wid = cur.lastrowid
            cur.execute(
                "INSERT INTO runs (workout_id, run_type, distance_km, duration_seconds, "
                "avg_heart_rate, max_heart_rate, elevation_gain_m, notes) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    wid,
                    r_type,
                    float(distance),
                    total_secs,
                    int(avg_hr) if avg_hr > 0 else None,
                    int(max_hr) if max_hr > 0 else None,
                    float(elevation),
                    r_notes.strip() or None,
                ),
            )
            conn.commit()
            pace = total_secs / distance
            st.success(
                f"✅ Logged **{title}** — pace {fmt_pace(pace)}, "
                f"{dur_min}:{dur_sec:02d} total time."
            )


# ═════════════════════════════════════════════════════════════════════════════
# PAGE: History
# ═════════════════════════════════════════════════════════════════════════════
elif page == "📋 History":
    st.title("📋 Full Workout History")
    st.markdown("---")

    tab_workouts, tab_lifts, tab_runs = st.tabs(["Workouts", "Lifts", "Runs"])

    with tab_workouts:
        cur.execute(
            "SELECT id, date, title, workout_type, notes, created_at FROM workouts ORDER BY date DESC"
        )
        rows = cur.fetchall()
        df = pd.DataFrame(rows, columns=["ID", "Date", "Title", "Type", "Notes", "Created"])
        df["Type"] = df["Type"].str.capitalize()
        df["Notes"] = df["Notes"].fillna("—")
        st.dataframe(df, use_container_width=True, hide_index=True)

    with tab_lifts:
        cur.execute(
            """
            SELECT w.date, w.title AS workout, l.exercise_name, l.sets, l.reps,
                   l.weight_kg, l.rpe, l.sets * l.reps * l.weight_kg AS volume_kg
            FROM lifts l
            JOIN workouts w ON w.id = l.workout_id
            ORDER BY w.date DESC, l.id
            """
        )
        rows = cur.fetchall()
        df = pd.DataFrame(
            rows,
            columns=["Date", "Workout", "Exercise", "Sets", "Reps",
                     "Weight (kg)", "RPE", "Volume (kg)"],
        )
        st.dataframe(df, use_container_width=True, hide_index=True)

    with tab_runs:
        cur.execute(
            """
            SELECT w.date, r.run_type,
                   r.distance_km, r.duration_seconds,
                   CAST(r.duration_seconds AS REAL) / r.distance_km AS pace_sec_per_km,
                   r.avg_heart_rate, r.max_heart_rate, r.elevation_gain_m
            FROM runs r
            JOIN workouts w ON w.id = r.workout_id
            ORDER BY w.date DESC
            """
        )
        rows = cur.fetchall()
        df = pd.DataFrame(
            rows,
            columns=["Date", "Type", "Distance (km)", "Duration (s)",
                     "Pace (s/km)", "Avg HR", "Max HR", "Elevation (m)"],
        )
        df["Pace"] = df["Pace (s/km)"].apply(fmt_pace)
        df["Duration"] = df["Duration (s)"].apply(
            lambda s: f"{s//3600}h {(s%3600)//60}m {s%60}s" if s >= 3600
            else f"{s//60}m {s%60}s"
        )
        df = df[["Date", "Type", "Distance (km)", "Duration", "Pace",
                 "Avg HR", "Max HR", "Elevation (m)"]]
        df["Type"] = df["Type"].str.capitalize()
        st.dataframe(df, use_container_width=True, hide_index=True)
