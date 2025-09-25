# streamlit_app.py
# Streamlit port of the Engineering Calculator Suite (replaces the Tkinter GUI)
# Features: torque, beam deflection (cantilever/simply-supported), section inertia,
# small materials DB, plotting, and downloadable PNG/TXT reports.

import os
import io
import math
import sqlite3
from datetime import datetime

import streamlit as st
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from PIL import Image

st.set_page_config(page_title="Engineering Calculator Suite", layout="wide")

# ----------------- Utility & DB -----------------
DATA_FOLDER = os.path.join(os.getcwd(), "EngineeringCalculatorProjects")
os.makedirs(DATA_FOLDER, exist_ok=True)

DB_PATH = os.path.join(os.getcwd(), "materials.db")
conn = sqlite3.connect(DB_PATH, check_same_thread=False)
cur = conn.cursor()
cur.execute("""CREATE TABLE IF NOT EXISTS materials (
    name TEXT PRIMARY KEY, E REAL, density REAL, yield_strength REAL, cost_per_kg REAL
)""")
seed_materials = [
    ("Aluminum 6061", 69e9, 2700, 276e6, 2.5),
    ("Steel A36", 200e9, 7850, 250e6, 0.8),
    ("Titanium Ti-6Al-4V", 114e9, 4420, 880e6, 35.0),
    ("PLA (3D Print)", 3.5e9, 1250, 60e6, 1.8),
    ("ABS (3D Print)", 2.1e9, 1040, 40e6, 1.6),
]
for m in seed_materials:
    try:
        cur.execute("INSERT INTO materials (name, E, density, yield_strength, cost_per_kg) VALUES (?, ?, ?, ?, ?)", m)
    except sqlite3.IntegrityError:
        pass
conn.commit()

def query_materials(min_E=None, max_density=None, min_yield=None):
    q = "SELECT name, E, density, yield_strength, cost_per_kg FROM materials WHERE 1=1"
    params = []
    if min_E is not None:
        q += " AND E >= ?"
        params.append(min_E)
    if max_density is not None:
        q += " AND density <= ?"
        params.append(max_density)
    if min_yield is not None:
        q += " AND yield_strength >= ?"
        params.append(min_yield)
    cur.execute(q, params)
    rows = cur.fetchall()
    df = pd.DataFrame(rows, columns=["name", "E (Pa)", "density (kg/m3)", "yield_strength (Pa)", "cost ($/kg)"])
    return df

# ----------------- Calculations -----------------
def I_rect(b, h):
    return b * h**3 / 12.0

def I_circle(d):
    return math.pi * d**4 / 64.0

def cantilever_deflection_profile(F, L, E, I, num=300):
    xs = np.linspace(0, L, num)
    ys = (F * xs**2 * (3*L - xs)) / (6 * E * I)
    return xs, ys

def simply_supported_center_load_profile(P, L, E, I, num=300):
    xs = np.linspace(0, L, num)
    ys = np.zeros_like(xs)
    for i, x in enumerate(xs):
        if x <= L/2:
            ys[i] = (P * x * (L**2 - x**2)) / (16 * E * I)
        else:
            x2 = L - x
            ys[i] = (P * x2 * (L**2 - x2**2)) / (16 * E * I)
    return xs, ys

def calc_torque(force, lever):
    return force * lever

def safe_filename(s):
    return "".join(c for c in s if (c.isalnum() or c in (" ", "_", "-"))).rstrip().replace(" ", "_")

def fig_to_png_bytes(fig):
    buf = io.BytesIO()
    fig.savefig(buf, bbox_inches='tight', dpi=150)
    buf.seek(0)
    return buf

def save_txt_summary(project_name, inputs_summary):
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    base = f"{safe_filename(project_name)}_{timestamp}"
    txt_path = os.path.join(DATA_FOLDER, base + ".txt")
    with open(txt_path, "w") as f:
        f.write(f"Project: {project_name}\nSaved: {datetime.now().isoformat()}\n\nInputs & summary:\n")
        for k, v in inputs_summary.items():
            f.write(f"{k}: {v}\n")
    return txt_path

# ----------------- UI -----------------
st.title("Engineering Calculator Suite (Web)")

col1, col2 = st.columns([1, 1.4])

with col1:
    st.header("Inputs")
    st.subheader("Torque Calculator")
    force = st.number_input("Force (N)", value=150.0, format="%.6f")
    lever = st.number_input("Lever arm (m)", value=0.35, format="%.6f")
    if st.button("Compute Torque"):
        torque = calc_torque(force, lever)
        st.success(f"Torque = {torque:.6f} N·m")
        fig = plt.figure(figsize=(5,3))
        ax = fig.add_subplot(111)
        ax.bar(["Torque (N·m)"], [torque])
        ax.set_ylabel("N·m")
        ax.set_title(f"Torque = {torque:.6f} N·m")
        st.pyplot(fig)
        # prepare downloads
        png_buf = fig_to_png_bytes(fig)
        txt_path = save_txt_summary("torque_project", {"force_N": force, "lever_m": lever, "torque_Nm": torque})
        st.download_button("Download PNG", data=png_buf, file_name="torque_plot.png", mime="image/png")
        with open(txt_path, "rb") as f:
            txt_bytes = f.read()
        st.download_button("Download TXT summary", data=txt_bytes, file_name=os.path.basename(txt_path), mime="text/plain")
        plt.close(fig)

    st.markdown("---")
    st.subheader("Beam Deflection")
    L = st.number_input("Beam length L (m)", value=1.0, format="%.6f")
    load = st.number_input("Load (N)", value=200.0, format="%.6f")
    section_type = st.radio("Section type", ("rect", "circle"))
    if section_type == "rect":
        s1 = st.number_input("b (width) in m", value=0.02, format="%.6f")
        s2 = st.number_input("h (height) in m", value=0.04, format="%.6f")
    else:
        s1 = st.number_input("d (diameter) in m", value=0.02, format="%.6f")
        s2 = 0.0

    col_bs1, col_bs2 = st.columns(2)
    with col_bs1:
        if st.button("Plot Cantilever"):
            if section_type == "rect":
                I = I_rect(s1, s2)
            else:
                I = I_circle(s1)
            cur.execute("SELECT E FROM materials WHERE name = ?", ("Aluminum 6061",))
            row = cur.fetchone()
            E = row[0] if row else 69e9
            xs, ys = cantilever_deflection_profile(load, L, E, I)
            max_defl = float(max(ys))
            fig = plt.figure(figsize=(7,3))
            ax = fig.add_subplot(111)
            ax.plot(xs, ys, linewidth=2)
            ax.set_xlabel("x (m)")
            ax.set_ylabel("deflection (m)")
            ax.set_title(f"Cantilever deflection (max = {max_defl:.6e} m)")
            st.pyplot(fig)
            inputs = {"type":"cantilever","F_N": load, "L_m": L, "I_m4": I, "E_Pa": E, "max_deflection_m": max_defl}
            png_buf = fig_to_png_bytes(fig)
            txt_path = save_txt_summary("cantilever_project", inputs)
            st.download_button("Download Cantilever PNG", data=png_buf, file_name="cantilever.png", mime="image/png")
            with open(txt_path, "rb") as f: txt_bytes = f.read()
            st.download_button("Download Cantilever TXT", data=txt_bytes, file_name=os.path.basename(txt_path), mime="text/plain")
            plt.close(fig)

    with col_bs2:
        if st.button("Plot Simply Supported"):
            if section_type == "rect":
                I = I_rect(s1, s2)
            else:
                I = I_circle(s1)
            cur.execute("SELECT E FROM materials WHERE name = ?", ("Aluminum 6061",))
            row = cur.fetchone()
            E = row[0] if row else 69e9
            xs, ys = simply_supported_center_load_profile(load, L, E, I)
            max_defl = float(max(ys))
            fig = plt.figure(figsize=(7,3))
            ax = fig.add_subplot(111)
            ax.plot(xs, ys, linewidth=2)
            ax.set_xlabel("x (m)")
            ax.set_ylabel("deflection (m)")
            ax.set_title(f"Simply supported center load (max = {max_defl:.6e} m)")
            st.pyplot(fig)
            inputs = {"type":"simply_supported","P_N": load, "L_m": L, "I_m4": I, "E_Pa": E, "max_deflection_m": max_defl}
            png_buf = fig_to_png_bytes(fig)
            txt_path = save_txt_summary("simply_supported_project", inputs)
            st.download_button("Download SimplySupported PNG", data=png_buf, file_name="simply_supported.png", mime="image/png")
            with open(txt_path, "rb") as f: txt_bytes = f.read()
            st.download_button("Download SimplySupported TXT", data=txt_bytes, file_name=os.path.basename(txt_path), mime="text/plain")
            plt.close(fig)

    st.markdown("---")
    st.subheader("Materials DB")
    minE = st.number_input("Min E (GPa) - leave 0 for no filter", value=0.0, format="%.6f")
    maxD = st.number_input("Max density (kg/m3)", value=10000.0, format="%.6f")
    if st.button("Query Materials"):
        df = query_materials(min_E=(minE*1e9 if minE>0 else None), max_density=(maxD if maxD>0 else None), min_yield=None)
        st.dataframe(df)

with col2:
    st.header("Materials & Tools")
    st.markdown("You can add materials directly below (name, E (Pa), density, yield_strength (Pa), cost $/kg).")
    with st.form("add_material"):
        nm = st.text_input("Material name")
        E_v = st.number_input("E (Pa)", value=69e9, format="%.6e")
        dens = st.number_input("Density (kg/m3)", value=2700.0)
        yld = st.number_input("Yield strength (Pa)", value=276e6, format="%.6e")
        cost = st.number_input("Cost ($/kg)", value=2.5)
        if st.form_submit_button("Add / Update Material"):
            try:
                cur.execute("INSERT OR REPLACE INTO materials (name, E, density, yield_strength, cost_per_kg) VALUES (?, ?, ?, ?, ?)",
                            (nm, float(E_v), float(dens), float(yld), float(cost)))
                conn.commit()
                st.success(f"Saved material: {nm}")
            except Exception as e:
                st.error("Failed to save: " + str(e))

    st.markdown("### Current materials table")
    try:
        cur.execute("SELECT name, E, density, yield_strength, cost_per_kg FROM materials")
        rows = cur.fetchall()
        df_all = pd.DataFrame(rows, columns=["name", "E (Pa)", "density (kg/m3)", "yield_strength (Pa)", "cost ($/kg)"])
        st.dataframe(df_all)
    except Exception as e:
        st.error("DB read error: " + str(e))

    st.markdown("---")
    st.header("Project Reports")
    st.markdown("Saved reports are stored in the `EngineeringCalculatorProjects` folder in the app working directory.")
    reports = sorted([f for f in os.listdir(DATA_FOLDER) if f.endswith(".txt") or f.endswith(".png")], reverse=True)
    if reports:
        sel = st.selectbox("Pick a saved file to view/download", reports)
        if sel:
            path = os.path.join(DATA_FOLDER, sel)
            if sel.endswith(".png"):
                st.image(path, use_column_width=True)
                with open(path, "rb") as f:
                    st.download_button("Download PNG", f, file_name=sel, mime="image/png")
            else:
                with open(path, "r") as f:
                    txt = f.read()
                st.code(txt)
                with open(path, "rb") as f:
                    st.download_button("Download TXT", f, file_name=sel, mime="text/plain")
    else:
        st.write("No saved reports yet.")

st.sidebar.markdown("## About")
st.sidebar.write("An engineering calculator suite originally written in Python, now deployed as a web app using Streamlit. Designed to handle complex calculations with a simple, intuitive interface.")

# Close DB connection on exit (Streamlit keeps process open; this is safe)
# conn.close()  # don't close here as streamlit re-runs; leaving open is fine for this simple app
