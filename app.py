"""
============================================================================================
Web Application for the Primary Exploration, Mining and Metal Supply Scenario (PEMMSS) Model
============================================================================================

This script implements a prototype Shiny for Python web application for the PEMMSS model.

It provides an interactive user interface for input management, simulation execution, output visualisation (including regional mapping).

This app.py file should exist in the same directory as the pemmss.py file.

To run the app, in the terminal run the command 'shiny run app.py', or 'python app.py'.

Author: Jayden Hyman
Maintainer: Stephen Northey
Date: 2026-10-16
Version: 0.4.0
Compatability: PEMMSS Version 1.4.1
License: BSD 3-Clause License
Dependencies: shiny, pandas, matplotlib, ipyleaflet, ipywidgets, shinywidgets, plotly, anywidget
"""

# ==================== Imports and Setup ====================

import io
import sys
import os
import subprocess
import asyncio
import shutil
import time
import pandas as pd
import plotly.graph_objects as go
from shiny import App, render, ui, reactive
from pathlib import Path
from threading import Thread
import matplotlib
matplotlib.use("Agg")  # non-GUI backend: figures can be drawn off the main thread
from modules.post_processing import generate_figure
from modules.file_import import import_graphs, import_graphs_formatting, import_parameters, decode_csv_bytes, normalise_csv_encoding
from ipyleaflet import Map, GeoJSON, Popup, LayersControl, LegendControl, basemaps, basemap_to_tiles
from ipywidgets import HTML
from shinywidgets import output_widget, render_widget
from html import escape
from collections import deque

APP_DIR = Path(__file__).resolve().parent
input_files_path = APP_DIR / "input_files"
output_files_path = APP_DIR / "output_files"
input_files_path.mkdir(parents=True, exist_ok=True)
output_files_path.mkdir(parents=True, exist_ok=True)

POINT_STYLE = {"radius": 7, "fillOpacity": 0.8, "weight": 0}

STATUS_COLORS = {
    'Development Probability Test Failed': 'gray',
    'Not Valuable Enough to Mine': 'black',
    'Depleted': 'red',
    'Undeveloped': 'blue',
    'Care and Maintenance': 'orange',
    'Producing': 'green',
    'Produced and Depleted': 'purple',
    'Undiscovered': 'lightgray'
}

# ==================== Shared Functions ====================

def compute_status_shares(status_df):
    """Percentage of iterations in each status, indexed by (YEAR, P_ID_NUMBER, STATUS)."""
    years = [c for c in status_df.columns if str(c).isdigit()]
    if not years:
        return None, []
    long = status_df.melt(id_vars=['P_ID_NUMBER', 'STATUS'], value_vars=years,
                          var_name='YEAR', value_name='N')
    long['N'] = pd.to_numeric(long['N'], errors='coerce').fillna(0)
    counts = long.groupby(['YEAR', 'P_ID_NUMBER', 'STATUS'])['N'].sum()
    total = counts.groupby(level=['YEAR', 'P_ID_NUMBER']).transform('sum')
    shares = (counts / total * 100)[total > 0]
    return shares, sorted(int(y) for y in years)


def load_project_data(projects_df, status_df):
    """Validate and prepare project data. Returns (projects, shares, years, has_semicolons).
    Raises ValueError with a readable message if the files can't be used."""
    required = ['LATITUDE', 'LONGITUDE', 'NAME', 'P_ID_NUMBER', 'COMMODITY', 'REMAINING_RESOURCE', 'GRADE']
    missing = [c for c in required if c not in projects_df.columns]
    if missing:
        raise ValueError(f"input_projects.csv is missing column(s): {', '.join(missing)}")
    missing = [c for c in ('P_ID_NUMBER', 'STATUS') if c not in status_df.columns]
    if missing:
        raise ValueError(f"_status.csv is missing column(s): {', '.join(missing)}")

    shares, years = compute_status_shares(status_df)
    if not years:
        raise ValueError("_status.csv has no year columns")

    projects = projects_df.copy()
    projects['LATITUDE'] = pd.to_numeric(projects['LATITUDE'], errors='coerce')
    projects['LONGITUDE'] = pd.to_numeric(projects['LONGITUDE'], errors='coerce')
    # Keep every project (the grade-tonnage plot needs them all); only the map needs coordinates
    projects['HAS_COORDS'] = (projects['LATITUDE'].between(-90, 90)
                              & projects['LONGITUDE'].between(-180, 180))
    if projects.empty:
        raise ValueError("input_projects.csv contains no projects")

    has_semicolons = bool(projects['REMAINING_RESOURCE'].str.contains(';', na=False).any()
                          or projects['GRADE'].str.contains(';', na=False).any())
    return projects, shares, years, has_semicolons


def projects_for_year_frame(projects, shares, year):
    """Attach status info for one year, matched by P_ID_NUMBER (never by row position)."""
    try:
        wide = shares.xs(str(year), level='YEAR').unstack('STATUS', fill_value=0.0)
    except KeyError:                      # year with no data at all
        wide = pd.DataFrame()
    max_status = wide.idxmax(axis=1).to_dict() if not wide.empty else {}
    info = {pid: {s: p for s, p in row.items() if p > 0}
            for pid, row in wide.to_dict('index').items()}

    df = projects.copy()
    df['MAX_STATUS'] = df['P_ID_NUMBER'].map(max_status).fillna('')
    df['STATUS_INFO'] = df['P_ID_NUMBER'].map(lambda pid: info.get(pid, {}))
    df['MARKER_COLOR'] = df['MAX_STATUS'].map(STATUS_COLORS).fillna('gray')
    return df


def create_hover_text(row, status_info, year):
    """Create hover text for project information (values HTML-escaped)."""
    def v(key):
        val = row.get(key)
        return 'N/A' if val is None or pd.isna(val) else escape(str(val))

    status_text = "<br>".join(
        f"{escape(str(label))}: {pct:.2f}%"
        for label, pct in (status_info or {}).items()
        if isinstance(pct, (int, float))
    )
    return (
        f"<b>{v('NAME')}</b><br>"
        f"<b>Project ID:</b> {v('P_ID_NUMBER')}<br>"
        f"<b>Region:</b> {v('REGION')}<br>"
        f"<b>Deposit type:</b> {v('DEPOSIT_TYPE')}<br>"
        f"<b>Commodity:</b> {v('COMMODITY')}<br>"
        f"<b>Initial resource:</b> {v('REMAINING_RESOURCE')}<br>"
        f"<b>Grade:</b> {v('GRADE')}<br>"
        f"<b>Recovery:</b> {v('RECOVERY')}<br>"
        f"<b>Initial status:</b> {v('STATUS')}<br>"
        f"<b>Development probability:</b> {v('DEVELOPMENT_PROBABILITY')}<br>"
        f"<b>Start year:</b> {v('START_YEAR')}<br>"
        f"<b>Status percentages for {year}:</b><br>{status_text}"
    )

def parse_tranches(value):
    """'1e6;2.5e6' -> [1000000.0, 2500000.0]; empty or non-numeric -> None."""
    if value is None or (isinstance(value, float) and pd.isna(value)) or str(value).strip() == "":
        return None
    try:
        return [float(x) for x in str(value).split(';')]
    except ValueError:
        return None


def tranche_table(projects):
    """One row per project tranche: P_ID_NUMBER, TRANCHE (0-based, mining order), TONNAGE, GRADE.
    Returns (table, n_skipped); skipped projects have missing/non-numeric values or
    different numbers of tonnage and grade tranches."""
    rows, skipped = [], 0
    for pid, res, grd in projects[['P_ID_NUMBER', 'REMAINING_RESOURCE', 'GRADE']].itertuples(index=False):
        t, g = parse_tranches(res), parse_tranches(grd)
        if not t or not g or len(t) != len(g):
            skipped += 1
            continue
        rows.extend((pid, i, ti, gi) for i, (ti, gi) in enumerate(zip(t, g)))
    return pd.DataFrame(rows, columns=['P_ID_NUMBER', 'TRANCHE', 'TONNAGE', 'GRADE']), skipped


def deposit_totals(tranches):
    """Per project: total tonnage and tonnage-weighted mean grade across tranches."""
    t = tranches.assign(CONTAINED=tranches['TONNAGE'] * tranches['GRADE'])
    agg = t.groupby('P_ID_NUMBER').agg(TONNAGE=('TONNAGE', 'sum'), CONTAINED=('CONTAINED', 'sum'),
                                       N_TRANCHES=('TRANCHE', 'size'))
    agg['GRADE'] = agg['CONTAINED'] / agg['TONNAGE']
    return agg.reset_index()

def build_project_geojson(df):
    """One GeoJSON point per project; colour carried in each feature's style."""
    features = [
        {
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [float(r.LONGITUDE), float(r.LATITUDE)]},
            "properties": {"P_ID_NUMBER": str(r.P_ID_NUMBER),
                           "style": {"color": r.MARKER_COLOR, "fillColor": r.MARKER_COLOR}},
        }
        for r in df[['P_ID_NUMBER', 'LATITUDE', 'LONGITUDE', 'MARKER_COLOR']].itertuples(index=False)
    ]
    return {"type": "FeatureCollection", "features": features}

def safe_read_csv(path):
    """Read a CSV of any supported encoding as all-string columns.
    Only empty cells become NaN, so values like 'NA' (Namibia, North America) survive."""
    path = Path(path)
    text, _ = decode_csv_bytes(path.read_bytes(), path.name)
    return pd.read_csv(io.StringIO(text), dtype=str, keep_default_na=False, na_values=[''])

# ==================== User Interface ====================

app_ui = ui.page_fluid(
    ui.navset_tab(
        ui.nav_panel("Inputs",
            ui.layout_sidebar(
                ui.sidebar(
                    ui.output_ui("scenario_selector_ui"),
                    ui.input_action_button("load_scenario_btn", "Load scenario"),
                    ui.hr(),
                    ui.output_ui("csv_inputs"),
                    ui.input_action_button("open_csv", "Open file"),
                    ui.input_task_button("btn", "Run simulation", label_busy="Running…"),
                    ui.output_ui("run_progress_ui"),
                    ui.output_ui("run_controls_ui"),
                    width=280
                ),
                ui.output_data_frame("editable_df")
            )
        ),
        ui.nav_panel("Outputs",
            ui.layout_sidebar(
                ui.sidebar(
                    ui.output_ui("folder_ui"),
                    ui.input_action_button("rename_folder_btn", "Rename folder"),
                    ui.output_ui("png_files_ui"),
                    ui.input_task_button("reprocess_btn", "Reprocess outputs", label_busy="Reprocessing…"),
                    width=280
                ),
                ui.output_image("image", height="100%", width="100%"),
                ui.accordion(ui.accordion_panel("Run log", ui.output_code("log_text")), open=False),
            )
        ),
        ui.nav_panel("Projects",
            ui.layout_sidebar(
                ui.sidebar(
                    ui.output_ui("map_folder_ui"),
                    ui.output_ui("subfolder_ui"),
                    ui.output_ui("year_slider"),
                    width=280

                ),
                ui.navset_tab(
                    ui.nav_panel("Geographic distribution",
                                 output_widget("project_map", height="80vh"),
                                 ),
                    ui.nav_panel("Resource and grade",
                                 ui.output_ui("commodity_selector_ui"),
                                 output_widget("scatter_plot", height="80vh"),
                                 ),
                ),
            )
        ),
        ui.nav_panel("About",
            ui.layout_sidebar(
                ui.sidebar(
                    ui.input_dark_mode(),
                    width=280
                ),
                ui.markdown(Path(APP_DIR / "README.md").read_text(encoding="utf-8"))
            )
        )
    )
)

# ==================== Server Logic ====================

def server(input, output, session):
    input_source = reactive.Value("default")

    renamed = {}   # old folder name -> new name, so selections follow a rename

    def keep_selection(input_id, choices):
        """The user's current choice if it's still valid (following renames), else the first choice."""
        with reactive.isolate():
            prev = input[input_id]() if input_id in input else None
        prev = renamed.get(prev, prev)
        return prev if prev in choices else (choices[0] if choices else None)


    # ==================== Folder and File Selection Logic ====================

    def _folder_names():
        return tuple(sorted(p.name for p in output_files_path.iterdir() if p.is_dir()))

    @reactive.poll(_folder_names, 2)
    def get_folders():
        return sorted(_folder_names(), reverse=True)

    def _viewable_runs():
        runs = []
        for run in sorted((p for p in output_files_path.iterdir() if p.is_dir()),
                          key=lambda p: p.name, reverse=True):
            if not (run / "_input_files" / "input_projects.csv").exists():
                continue
            scenarios = tuple(sorted(s.name for s in run.iterdir()
                                     if s.is_dir() and not s.name.startswith("_")
                                     and (s / "_status.csv").exists()))
            if scenarios:
                runs.append((run.name, scenarios))
        return tuple(runs)

    @reactive.poll(_viewable_runs, 2)
    def viewable_runs():
        return dict(_viewable_runs())     # {run folder: (scenario, ...)}, newest first

    @render.ui
    def folder_ui():
        folders = get_folders()
        if not folders:
            return ui.div(f"No output folders found in {output_files_path}")
        return ui.input_select("folder", "Output folder:", choices=folders,
                               selected=keep_selection("folder", folders))

    @render.ui
    def scenario_selector_ui():
        choices = ["Current input files"] + get_folders()
        return ui.input_select("scenario_selector", "Source:", choices=choices,
                               selected=keep_selection("scenario_selector", choices))

    @render.ui
    def map_folder_ui():
        runs = list(viewable_runs())
        if not runs:
            return ui.div("No completed runs with project data yet.")
        return ui.input_select("map_folder", "Output folder:", choices=runs,
                               selected=keep_selection("map_folder", runs))

    @render.ui
    def subfolder_ui():
        folder = input.map_folder() if "map_folder" in input else None
        scenarios = list(viewable_runs().get(folder, ()))
        if not scenarios:
            return ui.div()
        return ui.input_select("subfolder", "Subfolder:", choices=scenarios,
                               selected=keep_selection("subfolder", scenarios))


    def _graph_dir():
        folder = input.folder() if "folder" in input else None
        return output_files_path / folder / "_graphs" if folder else None

    def _figure_signature():
        g = _graph_dir()
        if g is None or not g.exists():
            return (str(g), ())
        return (str(g), tuple(sorted((p.name, p.stat().st_mtime_ns) for p in g.iterdir()
                                     if p.suffix.lower() in (".png", ".gif"))))

    @reactive.poll(_figure_signature, 2)
    def get_png_files():
        return [name for name, _ in _figure_signature()[1]]

    @render.ui
    def png_files_ui():
        files = get_png_files()
        if not files:
            return ui.div("No figures found in the selected folder.")
        return ui.input_select("png_file", "Output figures:", choices=files,
                               selected=keep_selection("png_file", files))

    @render.image
    def image():
        files = get_png_files()             # dependency: re-render when figures are regenerated
        selected = input.png_file()
        if selected not in files:
            return None
        path = output_files_path / input.folder() / "_graphs" / selected
        return {"src": str(path), "alt": selected, "style": "width: 100%; height: auto;"}

    @reactive.Effect
    @reactive.event(input.rename_folder_btn)
    def rename_folder():
        current_folder = input.folder()
        if current_folder:
            ui.modal_show(ui.modal(
                ui.input_text("new_folder_name", "Enter new folder name:", value=current_folder),
                ui.input_action_button("confirm_rename", "Rename"),
                title="Rename Folder",
                easy_close=True
            ))
        else:
            ui.notification_show("No folder selected.", type="warning", duration=3)

    INVALID_NAME_CHARS = set('/\\:*?"<>|')

    @reactive.effect
    @reactive.event(input.confirm_rename)
    def confirm_rename():
        old = input.folder()
        new = (input.new_folder_name() or "").strip()
        ui.modal_remove()
        if not new or new == old:
            return
        if new.startswith(".") or INVALID_NAME_CHARS & set(new):
            ui.notification_show('Folder names cannot start with "." or contain / \\ : * ? " < > |',
                                 type="error", duration=5)
            return
        new_path = output_files_path / new
        if new_path.exists():
            ui.notification_show("A folder with this name already exists.", type="error", duration=5)
            return
        try:
            (output_files_path / old).rename(new_path)
        except OSError as e:          # e.g. a file inside is open in another program (Windows)
            ui.notification_show(f"Could not rename: {e}", type="error", duration=8)
            return
        renamed[old] = new
        ui.notification_show(f"Folder renamed to: {new}", duration=3)
    
    # ==================== UI Rendering Functions ====================



    @reactive.Effect
    @reactive.event(input.scenario_selector)
    def update_input_source():
        if input.scenario_selector() == "Current input files":
            input_source.set("default")
        else:
            input_source.set(input.scenario_selector())

    # ==================== CSV Input Handling ====================

    def _csv_dir():
        src = input_source.get()
        return input_files_path if src == "default" else output_files_path / src / "_input_files"

    def selected_csv_path():
        if "csv_input" not in input or not input.csv_input():
            return None
        return _csv_dir() / input.csv_input()

    def _csv_listing():
        d = _csv_dir()
        return (str(d), tuple(sorted(p.name for p in d.glob("*.csv")))) if d.exists() else (str(d), ())

    @reactive.poll(_csv_listing, 2)
    def get_current_csv_files():
        return list(_csv_listing()[1])

    @render.ui
    def csv_inputs():
        csv_files = get_current_csv_files()
        if not csv_files:
            return ui.div("No CSV files found")
        select_input = ui.input_select("csv_input", "Input files:", choices=csv_files,
                                       selected=keep_selection("csv_input", csv_files))
        if input_source.get() != "default":
            return ui.tags.div(ui.tags.small(f"Viewing from: {input_source.get()}", class_="text-warning"),
                               select_input)
        return select_input

    _csv_seen, _own_writes = {}, {}   # path -> (mtime_ns, size)

    def _csv_signature():
        path = selected_csv_path()
        if path is None or not path.exists():
            return (str(path), None)
        st = path.stat()
        key, sig = str(path), (st.st_mtime_ns, st.st_size)
        if _own_writes.get(key) == sig:          # our own cell edit: don't trigger a reload
            return (key, _csv_seen.get(key))
        _csv_seen[key] = sig
        return (key, sig)

    @reactive.poll(_csv_signature, 2)
    def load_csv():
        path = selected_csv_path()
        if path is None or not path.exists():
            return pd.DataFrame()
        try:
            return safe_read_csv(path)
        except ValueError as e:
            ui.notification_show(f"Could not read {path.name}: {e}", type="error", duration=None)
            return pd.DataFrame()

    @reactive.effect
    @reactive.event(input.open_csv)
    def open_selected_csv():
        path = selected_csv_path()
        if path is None:
            return
        if not path.exists():
            ui.notification_show(f"File not found: {path.name}", type="warning", duration=5)
            return
        try:
            if sys.platform == "win32":
                os.startfile(path)
            elif sys.platform == "darwin":
                subprocess.Popen(["open", str(path)])
            else:
                subprocess.Popen(["xdg-open", str(path)])
        except OSError as e:
            ui.notification_show(f"Could not open {path.name}: {e}", type="error", duration=5)

    @render.data_frame
    def editable_df():
        df = load_csv()
        editable = (input_source.get() == "default")
        return render.DataGrid(
            data=df,
            editable=editable,
            height="75vh",
        )

    @editable_df.set_patch_fn
    def _(*, patch: render.CellPatch) -> render.CellValue:
        if input_source.get() != "default":
            ui.notification_show("Cannot edit files from scenario folders. Load them first.", type="warning", duration=3)
            return patch["value"]
        
        csv_path = selected_csv_path()
        df = safe_read_csv(csv_path).astype('object')
        column_name = df.columns[patch["column_index"]]
        df.at[patch["row_index"], column_name] = patch["value"]
        df.to_csv(csv_path, index=False, encoding='utf-8-sig')
        st = csv_path.stat()
        _own_writes[str(csv_path)] = (st.st_mtime_ns, st.st_size)
        return patch["value"]

    @reactive.Effect
    @reactive.event(input.load_scenario_btn)
    def load_scenario_inputs():
        if input.scenario_selector() == "Current input files":
            ui.notification_show("Already using current input files.", type="info", duration=3)
            return
        
        scenario_folder = input.scenario_selector()
        scenario_input_path = output_files_path / scenario_folder / "_input_files"
        
        if not scenario_input_path.exists():
            ui.notification_show(f"No input files found for scenario: {scenario_folder}", type="error", duration=5)
            return
        
        ui.modal_show(ui.modal(
            ui.p(f"This will overwrite all current input files with files from '{scenario_folder}'. Are you sure?"),
            ui.input_action_button("confirm_load", "Yes, load files", class_="btn-warning"),
            ui.input_action_button("cancel_load", "Cancel", class_="btn-secondary"),
            title="Confirm Load Scenario Files",
            easy_close=True
        ))

    @reactive.Effect
    @reactive.event(input.confirm_load)
    def confirm_load_scenario():
        scenario_folder = input.scenario_selector()
        scenario_input_path = output_files_path / scenario_folder / "_input_files"
        
        try:
            csv_files = sorted([f for f in os.listdir(scenario_input_path) if f.endswith('.csv')])
            
            if not csv_files:
                ui.notification_show("No CSV files found in scenario folder.", type="warning", duration=5)
                ui.modal_remove()
                return
            
            for csv_file in csv_files:
                src = scenario_input_path / csv_file
                dst = input_files_path / csv_file
                shutil.copyfile(src, dst)
            
            ui.update_select("scenario_selector", selected="Current input files")
            input_source.set("default")
            
            ui.notification_show(f"Successfully loaded {len(csv_files)} files from '{scenario_folder}'", type="success", duration=5)
            
        except Exception as e:
            ui.notification_show(f"Error loading files: {str(e)}", type="error", duration=5)
        
        ui.modal_remove()

    @reactive.Effect
    @reactive.event(input.cancel_load)
    def cancel_load():
        ui.modal_remove()

    # ==================== Simulation and Processing ====================

    # ==================== Simulation ====================

    run_progress = {"done": 0, "total": 0, "stage": "", "started": 0.0}  # plain dict, written by the task

    @ui.bind_task_button(button_id="btn")
    @reactive.extended_task
    async def run_model(total_iterations):
        run_progress.update(done=0, total=total_iterations, stage="Starting…", started=time.monotonic())
        tail = deque(maxlen=200)
        proc = await asyncio.create_subprocess_exec(
            sys.executable, str(APP_DIR / "pemmss.py"),
            cwd=APP_DIR, env={**os.environ, "PYTHONUNBUFFERED": "1"},
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT)  # merged: no deadlock
        try:
            async for raw in proc.stdout:
                line = raw.decode(errors="replace").rstrip()
                tail.append(line)
                if line.startswith("PEMMSS_PROGRESS "):
                    run_progress["done"] += 1
                    run_progress["stage"] = "Modelling " + line.split(" ", 1)[1]
                elif "Post-processing" in line:
                    run_progress["stage"] = "Post-processing outputs…"
            code = await proc.wait()
        except asyncio.CancelledError:
            proc.terminate()
            await proc.wait()
            raise
        return code, "\n".join(tail)

    @reactive.effect
    @reactive.event(input.btn)
    def _start_run():
        if input_source.get() != "default":
            ui.notification_show("Switch to 'Current input files' before running.", type="warning", duration=5)
            return
        try:
            parameters = import_parameters(input_files_path / "input_parameters.csv")
        except (OSError, ValueError, KeyError) as e:
            ui.notification_show(f"Could not read input_parameters.csv: {e}", type="error", duration=None)
            return
        run_progress["before"] = set(_folder_names())
        run_model(sum(p["iterations"] for p in parameters.values()))

    @render.ui
    def run_progress_ui():
        if run_model.status() != "running":
            return None
        reactive.invalidate_later(1)  # refresh once a second while running
        p = run_progress
        pct = int(100 * p["done"] / p["total"]) if p["total"] else 0
        secs = int(time.monotonic() - p["started"])
        return ui.div(
            ui.div(ui.div(class_="progress-bar", role="progressbar", style=f"width: {pct}%"),
                   class_="progress mt-2 mb-1"),
            ui.tags.small(f"{p['stage']} · {p['done']}/{p['total']} iterations · {secs // 60}:{secs % 60:02d}"),
        )

    def _mark_new_runs(before, suffix):
        """Append `suffix` to output folders created since `before`. Returns the new names."""
        marked = []
        for name in sorted(set(_folder_names()) - before):
            target = output_files_path / f"{name}{suffix}"
            n = 2
            while target.exists():                       # don't overwrite an existing folder
                target = output_files_path / f"{name}{suffix}{n}"
                n += 1
            try:
                (output_files_path / name).rename(target)
            except OSError:                              # e.g. a file still open (Windows); leave as is
                continue
            renamed[name] = target.name                  # dropdowns follow the rename
            marked.append(target.name)
        return marked

    @render.ui
    def run_controls_ui():
        if run_model.status() != "running":
            return None
        return ui.input_action_button("cancel_run", "Cancel run", class_="btn-sm btn-outline-danger mt-2")

    @reactive.effect
    @reactive.event(input.cancel_run)
    def _cancel_run():
        run_model.cancel()

    @reactive.effect
    def _run_finished():
        status = run_model.status()
        if status == "success":
            code, output = run_model.result()
            if code == 0:
                ui.notification_show("Simulation completed.", type="message", duration=8)
            else:
                marked = _mark_new_runs(run_progress.get("before", set()), "_failed")
                ui.modal_show(ui.modal(
                    ui.tags.pre(output, style="max-height: 60vh; overflow: auto; white-space: pre-wrap;"),
                    title=f"Simulation failed (exit code {code})", easy_close=True, size="xl"))
        elif status == "error":
            ui.notification_show(f"Simulation could not run: {run_model.error.get()}", type="error", duration=None)
        elif status == "cancelled":
            marked = _mark_new_runs(run_progress.get("before", set()), "_cancelled")
            if marked:
                ui.notification_show(f"Simulation cancelled. Partial output kept as: {', '.join(marked)}",
                                     type="warning", duration=10)
            else:
                ui.notification_show("Simulation cancelled.", type="warning", duration=10)

    # ==================== Run log ====================

    LOG_TAIL_LINES = 400

    def _log_path():
        folder = input.folder() if "folder" in input else None
        return output_files_path / folder / "log.txt" if folder else None

    def _log_signature():
        p = _log_path()
        return (str(p), p.stat().st_mtime_ns if p is not None and p.exists() else None)

    @reactive.poll(_log_signature, 2)
    def log_tail():
        p = _log_path()
        if p is None or not p.exists():
            return "No log file for this folder."
        lines = p.read_text(encoding="utf-8", errors="replace").splitlines()
        head = f"… showing last {LOG_TAIL_LINES} of {len(lines)} lines\n" if len(lines) > LOG_TAIL_LINES else ""
        return head + "\n".join(lines[-LOG_TAIL_LINES:])

    @render.code
    def log_text():
        return log_tail()



    # ==================== Reprocessing ====================

    def _reprocess(folder):
        """Runs in a worker thread: no ui.* or reactive calls in here."""
        run_dir = output_files_path / folder
        input_copy = run_dir / "_input_files"
        input_copy.mkdir(exist_ok=True)
        graphs_csv = normalise_csv_encoding(input_files_path / "input_graphs.csv", input_copy)
        graphs_fmt_csv = normalise_csv_encoding(input_files_path / "input_graphs_formatting.csv", input_copy)
        custom_graphs = import_graphs(graphs_csv)
        custom_graphs_formatting = import_graphs_formatting(graphs_fmt_csv)
        stats_dir = run_dir / "_statistics"
        statistics_files = {p.stem: {"path": p} for p in stats_dir.glob("*.csv")}
        for graph in custom_graphs:
            generate_figure(statistics_files, graph, custom_graphs_formatting, run_dir / "_graphs")
        return len(custom_graphs)

    @ui.bind_task_button(button_id="reprocess_btn")
    @reactive.extended_task
    async def reprocess_task(folder):
        return await asyncio.to_thread(_reprocess, folder)

    @reactive.effect
    @reactive.event(input.reprocess_btn)
    def _start_reprocess():
        folder = input.folder() if "folder" in input else None
        if not folder:
            ui.notification_show("No folder selected for reprocessing.", type="warning", duration=5)
            return
        reprocess_task(folder)

    @reactive.effect
    def _reprocess_finished():
        status = reprocess_task.status()
        if status == "success":
            ui.notification_show(f"Reprocessed {reprocess_task.result()} graph definitions.", duration=5)
        elif status == "error":
            ui.notification_show(f"Reprocessing failed: {reprocess_task.error.get()}", type="error", duration=None)

    # ==================== Map and Scatter Plot Rendering ====================

    @render.ui
    def year_slider():
        _, _, years, _ = cached_project_data()
        if not years:
            return ui.div()
        with reactive.isolate():
            prev = input.year() if "year" in input else None
        value = prev if prev in years else years[0]
        return ui.input_slider("year", "Year:", min=years[0], max=years[-1],
                               value=value, step=1, sep="",
                               animate={"interval": 1000, "loop": False})

    @render.ui
    def commodity_selector_ui():
        projects, _, _, _ = cached_project_data()
        if projects is None:
            return ui.div()
        commodities = sorted(projects['COMMODITY'].dropna().unique().tolist())
        if not commodities:
            return ui.div()
        with reactive.isolate():
            prev = input.commodity() if "commodity" in input else None
        return ui.input_select("commodity", "Commodity:", choices=commodities,
                               selected=prev if prev in commodities else commodities[0])


    @reactive.calc
    def cached_project_data():
        folder = input.map_folder() if "map_folder" in input else None
        subfolder = input.subfolder() if "subfolder" in input else None
        if not folder or not subfolder:
            return None, None, [], False
        projects_path = output_files_path / folder / "_input_files" / "input_projects.csv"
        status_path = output_files_path / folder / subfolder / "_status.csv"
        if not projects_path.exists() or not status_path.exists():
            return None, None, [], False      # e.g. subfolder from the previously selected folder
        try:
            return load_project_data(safe_read_csv(projects_path), safe_read_csv(status_path))
        except ValueError as e:
            ui.notification_show(f"Cannot load projects for {folder}/{subfolder}: {e}", type="error", duration=8)
            return None, None, [], False

    @reactive.calc
    def projects_for_year():
        projects, shares, years, has_semicolons = cached_project_data()
        year = input.year() if "year" in input else None
        if projects is None or year is None or year not in years:
            return None, None, None, False
        return projects_for_year_frame(projects, shares, year), shares, years, has_semicolons

    map_parts = {}  # plain dict (not reactive): the current map's widgets and data for click handling

    def _on_project_click(feature=None, **kwargs):
        frame, popup, m = map_parts.get("frame"), map_parts.get("popup"), map_parts.get("map")
        if frame is None or popup is None or feature is None:
            return
        pid = feature["properties"]["P_ID_NUMBER"]
        if pid not in frame.index:
            return
        row = frame.loc[pid]
        lon, lat = feature["geometry"]["coordinates"]
        popup.child.value = create_hover_text(row, row["STATUS_INFO"], map_parts.get("year"))
        if popup in m.layers:
            popup.open_popup([lat, lon])
        else:
            popup.location = [lat, lon]
            m.add(popup)

    @render_widget
    def project_map():
        projects, _, _, _ = cached_project_data()  # depends on folder/subfolder only
        m = Map(zoom=2, scroll_wheel_zoom=True, layout={"height": "75vh"})
        m.add(basemap_to_tiles(basemaps.Esri.WorldImagery))
        m.add(LayersControl(position="topright"))
        map_parts.clear()
        if projects is None:
            return m
        on_map = projects[projects['HAS_COORDS']]
        if on_map.empty:
            return m

        with reactive.isolate():  # initial colours only; year changes are handled below
            frame = projects_for_year()[0]
        if frame is None:
            frame = projects.assign(MARKER_COLOR="gray", STATUS_INFO=[{}] * len(projects))

        layer = GeoJSON(data=build_project_geojson(frame[frame['HAS_COORDS']]),
                        point_style=POINT_STYLE, name="Projects")
        layer.on_click(_on_project_click)
        m.add(layer)
        m.add(LegendControl({k: v for k, v in STATUS_COLORS.items()},
                            title="Most likely status", position="bottomright"))
        m.fit_bounds([[on_map["LATITUDE"].min(), on_map["LONGITUDE"].min()],
                      [on_map["LATITUDE"].max(), on_map["LONGITUDE"].max()]])

        map_parts.update(map=m, layer=layer, popup=Popup(child=HTML(), max_width=380),
                         frame=frame.drop_duplicates("P_ID_NUMBER").set_index("P_ID_NUMBER", drop=False),
                         year=None)
        return m

    @reactive.effect
    def _update_project_colours():
        frame = projects_for_year()[0]
        layer = map_parts.get("layer")
        if frame is None or layer is None:
            return
        layer.data = build_project_geojson(frame[frame['HAS_COORDS']])
        map_parts["frame"] = frame.drop_duplicates("P_ID_NUMBER").set_index("P_ID_NUMBER", drop=False)
        map_parts["year"] = input.year()

    @render_widget
    def scatter_plot():
        projects, _, _, has_semicolons = projects_for_year()
        year = input.year() if "year" in input else None
        commodity = input.commodity() if "commodity" in input else None

        if projects is None or projects.empty or year is None or commodity is None:
            fig = go.Figure()
            fig.update_layout(
                title="No data available",
                template="simple_white",
            )
            return fig

        projects = projects[projects['COMMODITY'] == commodity]
        n_total = len(projects)
        tranches, _ = tranche_table(projects)
        totals = deposit_totals(tranches).rename(columns={'TONNAGE': '_X', 'GRADE': '_Y'})
        projects = projects.merge(totals[['P_ID_NUMBER', '_X', '_Y', 'N_TRANCHES']], on='P_ID_NUMBER')
        projects = projects[projects['_X'] > 0]          # log x-axis
        n_dropped = n_total - len(projects)

        if projects.empty:
            fig = go.Figure()
            fig.update_layout(
                title=f"No data available for {commodity}",
                template="simple_white",
            )
            return fig

        fig = go.Figure()

        for status in STATUS_COLORS:
            status_projects = projects[projects['MAX_STATUS'] == status]

            if status_projects.empty:
                continue

            hover_texts = [
                create_hover_text(row, row['STATUS_INFO'], year)
                for _, row in status_projects.iterrows()
            ]
            sizes = 10

            fig.add_trace(go.Scatter(
                x=status_projects['_X'],
                y=status_projects['_Y'],
                mode='markers',
                name=status,
                marker=dict(
                    size=sizes,
                    color=STATUS_COLORS.get(status, 'gray'),
                    line=dict(width=1, color='white')
                ),
                hovertext=hover_texts,
                hoverinfo='text',
                hoverlabel=dict(
                    bgcolor="white",
                    font_size=12,
                    font_family="Arial"
                ),
                legendgroup=status,
                showlegend=True
            ))

        fig.update_layout(
            autosize=True,
            title=f"{commodity}, {year}" + (
                f" ({n_dropped} projects without numeric resource/grade not shown)" if n_dropped else ""),
            xaxis=dict(
                title="Initial Resource (metric tons)",
                type="log",
            ),
            yaxis=dict(
                title="Initial Grade (mass ratio)",
            ),
            template="simple_white",
            hovermode='closest',
            legend=dict(
                yanchor="top",
                y=0.99,
                xanchor="left",
                x=0.01,
                itemsizing='constant',
                bordercolor='rgba(128,128,128,0.2)',
                borderwidth=1
            )
        )

        return fig


# ==================== Server Startup ====================

app = App(app_ui, server)

if __name__ == "__main__":
    app.run(host="localhost", port=8000, launch_browser = True)