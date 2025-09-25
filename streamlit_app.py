"""
engineering_calculator.py
Engineering Calculator Suite — Tkinter GUI with embedded Matplotlib.

Features:
- Torque calculator (force [N] * lever [m]).
- Beam deflection (Cantilever end load, Simply supported center load).
- Section inertia for rectangle and circle.
- Small materials database (queryable).
- Plotting and saving a project report (PNG + text). Optionally convert PNG to PDF if Pillow installed.
- Designed to be extended and used as a polished portfolio project.

"""
import os
import math
import sqlite3
from datetime import datetime
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

try:
    from PIL import Image
    PIL_AVAILABLE = True
except Exception:
    PIL_AVAILABLE = False

# ---------- Utility & DB ----------
DATA_FOLDER = os.path.join(os.path.expanduser("~"), "EngineeringCalculatorProjects")
os.makedirs(DATA_FOLDER, exist_ok=True)

DB_PATH = os.path.join(DATA_FOLDER, "materials.db")
conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()
cur.execute("""CREATE TABLE IF NOT EXISTS materials (
    name TEXT PRIMARY KEY, E REAL, density REAL, yield_strength REAL, cost_per_kg REAL
)""")
# Seed some materials if not present
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

# ---------- Calculations ----------
def I_rect(b, h):
    """Moment of inertia for rectangle (b width, h height) about centroidal axis."""
    return b * h**3 / 12.0

def I_circle(d):
    """Moment of inertia for circle diameter d."""
    return math.pi * d**4 / 64.0

def cantilever_deflection_profile(F, L, E, I, num=300):
    """Cantilever with end load: deflection profile from root x=0 to tip x=L."""
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

# ---------- Save / Report ----------
def safe_filename(s):
    return "".join(c for c in s if (c.isalnum() or c in (" ", "_", "-"))).rstrip().replace(" ", "_")

def save_report(project_name, inputs_summary, fig):
    """Save PNG and TXT report. Optionally convert to PDF if Pillow installed."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    base = f"{safe_filename(project_name)}_{timestamp}"
    png_path = os.path.join(DATA_FOLDER, base + ".png")
    txt_path = os.path.join(DATA_FOLDER, base + ".txt")
    fig.savefig(png_path, bbox_inches='tight', dpi=150)
    with open(txt_path, "w") as f:
        f.write(f"Project: {project_name}\nSaved: {datetime.now().isoformat()}\n\nInputs & summary:\n")
        for k, v in inputs_summary.items():
            f.write(f"{k}: {v}\n")
    pdf_path = None
    if PIL_AVAILABLE:
        try:
            img = Image.open(png_path)
            rgb = img.convert('RGB')
            pdf_path = os.path.join(DATA_FOLDER, base + ".pdf")
            rgb.save(pdf_path)
        except Exception as e:
            print("PDF export failed:", e)
            pdf_path = None
    return {"png": png_path, "txt": txt_path, "pdf": pdf_path}

# ---------- GUI ----------
class EngineeringApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Engineering Calculator Suite")
        self.geometry("1100x720")
        self.create_widgets()

    def create_widgets(self):
        # Left frame: controls
        left = ttk.Frame(self)
        left.pack(side=tk.LEFT, fill=tk.Y, padx=8, pady=8)

        ttk.Label(left, text="Engineering Calculator Suite", font=("Helvetica", 16, "bold")).pack(pady=(0,10))

        # Torque frame
        torque_frame = ttk.LabelFrame(left, text="Torque Calculator")
        torque_frame.pack(fill=tk.X, pady=6)
        ttk.Label(torque_frame, text="Force (N):").grid(row=0, column=0, sticky=tk.W, padx=4, pady=2)
        self.force_var = tk.DoubleVar(value=150.0)
        ttk.Entry(torque_frame, textvariable=self.force_var, width=12).grid(row=0, column=1, padx=4, pady=2)
        ttk.Label(torque_frame, text="Lever arm (m):").grid(row=1, column=0, sticky=tk.W, padx=4, pady=2)
        self.lever_var = tk.DoubleVar(value=0.35)
        ttk.Entry(torque_frame, textvariable=self.lever_var, width=12).grid(row=1, column=1, padx=4, pady=2)
        ttk.Button(torque_frame, text="Compute Torque", command=self.on_compute_torque).grid(row=2, column=0, columnspan=2, pady=6)

        # Beam frame
        beam_frame = ttk.LabelFrame(left, text="Beam Deflection")
        beam_frame.pack(fill=tk.X, pady=6)
        ttk.Label(beam_frame, text="Beam Length L (m):").grid(row=0, column=0, sticky=tk.W, padx=4, pady=2)
        self.length_var = tk.DoubleVar(value=1.0)
        ttk.Entry(beam_frame, textvariable=self.length_var, width=12).grid(row=0, column=1, padx=4, pady=2)

        ttk.Label(beam_frame, text="Load (N):").grid(row=1, column=0, sticky=tk.W, padx=4, pady=2)
        self.load_var = tk.DoubleVar(value=200.0)
        ttk.Entry(beam_frame, textvariable=self.load_var, width=12).grid(row=1, column=1, padx=4, pady=2)

        ttk.Label(beam_frame, text="Section type:").grid(row=2, column=0, sticky=tk.W, padx=4, pady=2)
        self.section_type = tk.StringVar(value="rect")
        ttk.Radiobutton(beam_frame, text="Rect (b,h)", variable=self.section_type, value="rect").grid(row=2, column=1, sticky=tk.W, padx=4)
        ttk.Radiobutton(beam_frame, text="Circle (d)", variable=self.section_type, value="circle").grid(row=3, column=1, sticky=tk.W, padx=4)

        ttk.Label(beam_frame, text="b or d (m):").grid(row=4, column=0, sticky=tk.W, padx=4, pady=2)
        self.s1_var = tk.DoubleVar(value=0.02)
        ttk.Entry(beam_frame, textvariable=self.s1_var, width=12).grid(row=4, column=1, padx=4, pady=2)

        ttk.Label(beam_frame, text="h (m) if rect:").grid(row=5, column=0, sticky=tk.W, padx=4, pady=2)
        self.s2_var = tk.DoubleVar(value=0.04)
        ttk.Entry(beam_frame, textvariable=self.s2_var, width=12).grid(row=5, column=1, padx=4, pady=2)

        ttk.Button(beam_frame, text="Plot Cantilever", command=self.on_plot_cantilever).grid(row=6, column=0, pady=6)
        ttk.Button(beam_frame, text="Plot Simply Supported", command=self.on_plot_simply_supported).grid(row=6, column=1, pady=6)

        # Materials query frame
        mat_frame = ttk.LabelFrame(left, text="Materials DB Query")
        mat_frame.pack(fill=tk.X, pady=6)
        ttk.Label(mat_frame, text="Min E (GPa):").grid(row=0, column=0, sticky=tk.W, padx=4, pady=2)
        self.minE_var = tk.DoubleVar(value=0.0)
        ttk.Entry(mat_frame, textvariable=self.minE_var, width=12).grid(row=0, column=1, padx=4, pady=2)
        ttk.Label(mat_frame, text="Max density (kg/m3):").grid(row=1, column=0, sticky=tk.W, padx=4, pady=2)
        self.maxD_var = tk.DoubleVar(value=10000.0)
        ttk.Entry(mat_frame, textvariable=self.maxD_var, width=12).grid(row=1, column=1, padx=4, pady=2)
        ttk.Button(mat_frame, text="Query Materials", command=self.on_query_materials).grid(row=2, column=0, columnspan=2, pady=6)

        # Save/export
        export_frame = ttk.LabelFrame(left, text="Save / Export")
        export_frame.pack(fill=tk.X, pady=6)
        ttk.Label(export_frame, text="Project name:").grid(row=0, column=0, sticky=tk.W, padx=4, pady=2)
        self.project_name_var = tk.StringVar(value="my_project")
        ttk.Entry(export_frame, textvariable=self.project_name_var, width=20).grid(row=0, column=1, padx=4, pady=2)
        ttk.Button(export_frame, text="Save current figure & summary", command=self.on_save_report).grid(row=1, column=0, columnspan=2, pady=6)
        self.last_report = None

        # Right frame: plotting area
        right = ttk.Frame(self)
        right.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=8, pady=8)

        self.fig = Figure(figsize=(7,6), dpi=100)
        self.ax = self.fig.add_subplot(111)
        self.ax.set_title("Plots will appear here")
        self.canvas = FigureCanvasTkAgg(self.fig, master=right)
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

        # Bottom: status / materials table
        bottom = ttk.Frame(self)
        bottom.pack(side=tk.BOTTOM, fill=tk.X, padx=8, pady=6)
        self.status_label = ttk.Label(bottom, text=f"Saved projects folder: {DATA_FOLDER}")
        self.status_label.pack(side=tk.LEFT)

    # ---------- event handlers ----------
    def on_compute_torque(self):
        try:
            F = float(self.force_var.get())
            l = float(self.lever_var.get())
        except Exception as e:
            messagebox.showerror("Invalid input", "Check Force and Lever inputs.")
            return
        torque = calc_torque(F, l)
        self.ax.clear()
        self.ax.bar(["Torque (N·m)"], [torque])
        self.ax.set_ylabel("N·m")
        self.ax.set_title(f"Torque = {torque:.4f} N·m")
        self.canvas.draw()
        self.current_summary = {"type": "torque", "force_N": F, "lever_m": l, "torque_Nm": torque}
        self.status_label.config(text=f"Computed torque: {torque:.4f} N·m")

    def on_plot_cantilever(self):
        try:
            L = float(self.length_var.get())
            F = float(self.load_var.get())
            st = self.section_type.get()
            s1 = float(self.s1_var.get())
            s2 = float(self.s2_var.get())
        except Exception:
            messagebox.showerror("Invalid input", "Check beam inputs.")
            return
        if st == "rect":
            I = I_rect(s1, s2)
        else:
            I = I_circle(s1)
        # default material: Aluminum 6061
        cur.execute("SELECT E FROM materials WHERE name = ?", ("Aluminum 6061",))
        row = cur.fetchone()
        E = row[0] if row else 69e9
        xs, ys = cantilever_deflection_profile(F, L, E, I)
        max_defl = max(ys)
        self.ax.clear()
        self.ax.plot(xs, ys, linewidth=2)
        self.ax.set_xlabel("x (m)")
        self.ax.set_ylabel("deflection (m)")
        self.ax.set_title(f"Cantilever deflection (max = {max_defl:.6e} m)")
        self.canvas.draw()
        self.current_summary = {
            "type": "cantilever",
            "F_N": F,
            "L_m": L,
            "section_I_m4": I,
            "E_Pa": E,
            "max_deflection_m": max_defl
        }
        self.status_label.config(text=f"Cantilever max deflection: {max_defl:.6e} m")

    def on_plot_simply_supported(self):
        try:
            L = float(self.length_var.get())
            P = float(self.load_var.get())
            st = self.section_type.get()
            s1 = float(self.s1_var.get())
            s2 = float(self.s2_var.get())
        except Exception:
            messagebox.showerror("Invalid input", "Check beam inputs.")
            return
        if st == "rect":
            I = I_rect(s1, s2)
        else:
            I = I_circle(s1)
        cur.execute("SELECT E FROM materials WHERE name = ?", ("Aluminum 6061",))
        row = cur.fetchone()
        E = row[0] if row else 69e9
        xs, ys = simply_supported_center_load_profile(P, L, E, I)
        max_defl = max(ys)
        self.ax.clear()
        self.ax.plot(xs, ys, linewidth=2)
        self.ax.set_xlabel("x (m)")
        self.ax.set_ylabel("deflection (m)")
        self.ax.set_title(f"Simply supported center load (max = {max_defl:.6e} m)")
        self.canvas.draw()
        self.current_summary = {
            "type": "simply_supported_center",
            "P_N": P,
            "L_m": L,
            "section_I_m4": I,
            "E_Pa": E,
            "max_deflection_m": max_defl
        }
        self.status_label.config(text=f"Simply supported max deflection: {max_defl:.6e} m")

    def on_query_materials(self):
        try:
            minE_GPa = float(self.minE_var.get())
            maxD = float(self.maxD_var.get())
        except Exception:
            messagebox.showerror("Invalid input", "Check material query inputs.")
            return
        df = query_materials(min_E=minE_GPa*1e9 if minE_GPa>0 else None,
                             max_density=maxD if maxD>0 else None,
                             min_yield=None)
        # Show top results in a popup window with a small table
        popup = tk.Toplevel(self)
        popup.title("Materials Query Results")
        text = tk.Text(popup, wrap=tk.NONE, width=80, height=10)
        text.insert("1.0", df.to_string(index=False))
        text.configure(state="disabled")
        text.pack(fill=tk.BOTH, expand=True)
        ttk.Button(popup, text="Close", command=popup.destroy).pack(pady=4)

    def on_save_report(self):
        if not hasattr(self, "current_summary"):
            messagebox.showwarning("Nothing to save", "Compute or plot something first.")
            return
        proj_name = self.project_name_var.get().strip()
        if proj_name == "":
            proj_name = "unnamed_project"
        # Save current figure and summary
        saved = save_report(proj_name, self.current_summary, self.fig)
        msg = f"Saved PNG: {saved['png']}\nSaved TXT: {saved['txt']}"
        if saved.get("pdf"):
            msg += f"\nSaved PDF: {saved['pdf']}"
        messagebox.showinfo("Saved report", msg)
        self.last_report = saved
        self.status_label.config(text=f"Saved report: {os.path.basename(saved['png'])}")

# Run app
def main():
    app = EngineeringApp()
    app.mainloop()

if __name__ == "__main__":
    main()
