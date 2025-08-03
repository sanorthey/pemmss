"""
============================================================================================
Web Application for the Primary Exploration, Mining and Metal Supply Scenario (PEMMSS) Model
============================================================================================

This script implements a prototype Shiny for Python web application for the PEMMSS model.

It provides an interactive user interface for input management, simulation execution, output visualisation (including regional mapping).

This app.py file should exist in the same directory as the pemmss.py file.

To run the app, in the terminal run the command 'shiny run app.py', or 'python app.py'.

Author: Jayden Hyman
Date: 2025-08-03
Version: 0.3.0
Compatability: PEMMSS Version 1.4.0
License: BSD 3-Clause License
Dependencies: shiny, pandas, matplotlib, ipyleaflet, ipywidgets, shinywidgets, plotly, anywidget
"""

# ==================== Imports and Setup ====================

import sys
import os
import subprocess
import asyncio
import shutil
import pandas as pd
import matplotlib.pyplot as plt
import plotly.graph_objects as go
import charset_normalizer
from shiny import App, render, ui, reactive
from pathlib import Path
from threading import Thread
from modules.post_processing import generate_figure
from modules.file_import import import_graphs, import_graphs_formatting, import_static_files
from ipyleaflet import Map, CircleMarker, TileLayer, LayersControl, LayerGroup
from ipywidgets import HTML
from shinywidgets import output_widget, render_widget

current_dir = Path.cwd()
input_files_path = current_dir / "input_files"
input_files_cache_path = current_dir / "input_files" / "_cached_input_files"
output_files_path = current_dir / "output_files"
input_files_path.mkdir(parents=True, exist_ok=True)
input_files_cache_path.mkdir(parents=True, exist_ok=True)
output_files_path.mkdir(parents=True, exist_ok=True)

STATUS_LABELS = {
    -3: 'Development Probability Test Failed',
    -2: 'Not Valuable Enough to Mine',
    -1: 'Depleted',
    0: 'Undeveloped',
    1: 'Care and Maintenance',
    2: 'Producing',
    3: 'Produced and Depleted'
}

STATUS_COLORS = {
    'Development Probability Test Failed': 'gray',
    'Not Valuable Enough to Mine': 'black',
    'Depleted': 'red',
    'Undeveloped': 'blue',
    'Care and Maintenance': 'orange',
    'Producing': 'green',
    'Produced and Depleted': 'purple'
}

# ==================== Shared Functions ====================

def get_project_status_info(project_id, status_df, year):
    """Get status information for a project at a given year."""
    year_str = str(year)

    if year_str in status_df.columns:
        status_df[year_str] = pd.to_numeric(status_df[year_str], errors='coerce').fillna(0)
    else:
        return {}, ""

    project_status_data = status_df[status_df['P_ID_NUMBER'] == project_id]

    total_simulations = project_status_data[year_str].sum()

    status_info = {}
    max_percentage = 0
    max_status = ""

    for status_code, status_label in STATUS_LABELS.items():
        # Filter rows where STATUS matches and year column > 0 safely
        filtered = project_status_data[
            (project_status_data['STATUS'] == status_label) &
            (project_status_data[year_str] > 0)
        ]
        status_count = filtered[year_str].sum()

        status_percentage = (status_count / total_simulations * 100) if total_simulations > 0 else 0
        status_info[status_label] = status_percentage

        if status_percentage > max_percentage:
            max_percentage = status_percentage
            max_status = status_label

    return status_info, max_status


def prepare_all_project_data(projects_df, status_df):
    """Prepare project data for all years at once for caching."""
    required_columns = ['LATITUDE', 'LONGITUDE', 'NAME', 'P_ID_NUMBER', 'REGION',
                       'DEPOSIT_TYPE', 'COMMODITY', 'REMAINING_RESOURCE', 'GRADE', 'STATUS', 
                       'RECOVERY', 'DEVELOPMENT_PROBABILITY', 'START_YEAR']
    
    missing_columns = [col for col in required_columns if col not in projects_df.columns]
    if missing_columns:
        return None, None, []
    
    year_columns = [col for col in status_df.columns if col.isdigit()]
    if not year_columns:
        return None, None, []
    
    for col in year_columns:
        status_df[col] = pd.to_numeric(status_df[col], errors='coerce').fillna(0)
    
    valid_projects = projects_df.copy()
    valid_projects['LATITUDE'] = pd.to_numeric(valid_projects['LATITUDE'], errors='coerce')
    valid_projects['LONGITUDE'] = pd.to_numeric(valid_projects['LONGITUDE'], errors='coerce')
    valid_projects = valid_projects.dropna(subset=['LATITUDE', 'LONGITUDE', 'REMAINING_RESOURCE', 'GRADE'])
    valid_projects = valid_projects[
        (valid_projects['LATITUDE'].between(-90, 90)) & 
        (valid_projects['LONGITUDE'].between(-180, 180))
    ]
    
    if valid_projects.empty:
        return None, None, []
    
    has_semicolons = (
        valid_projects['REMAINING_RESOURCE'].str.contains(';', na=False).any() or
        valid_projects['GRADE'].str.contains(';', na=False).any()
    )
    
    year_data = {}
    grouped_status = status_df.groupby('P_ID_NUMBER')
    
    for year in year_columns:
        year_int = int(year)
        total_sims = grouped_status[year].sum().to_dict()
        status_percentages = []
        for project_id in valid_projects['P_ID_NUMBER']:
            if project_id in total_sims and total_sims[project_id] > 0:
                project_data = status_df[status_df['P_ID_NUMBER'] == project_id]
                status_counts = project_data.groupby('STATUS')[year].sum()
                percentages = (status_counts / total_sims[project_id] * 100).to_dict()
                max_pct = 0
                max_status = ""
                for status, pct in percentages.items():
                    if pct > max_pct:
                        max_pct = pct
                        max_status = status
                
                status_percentages.append({
                    'status_info': percentages,
                    'max_status': max_status,
                    'marker_color': STATUS_COLORS.get(max_status, 'gray')
                })
            else:
                status_percentages.append({
                    'status_info': {},
                    'max_status': "",
                    'marker_color': 'gray'
                })
        year_data[year_int] = pd.DataFrame(status_percentages)
    return valid_projects, year_data, [int(y) for y in year_columns], has_semicolons


def create_hover_text(row, status_info, year):
    """Create hover text for project information."""
    try:
        status_text = "<br>".join([
            f"{label}: {percentage:.2f}%" 
            for label, percentage in status_info.items() 
            if isinstance(percentage, (int, float))
        ])
        
        return (
            f"<b>{row.get('NAME', 'Unknown')}</b><br>"
            f"<b>Project ID:</b> {row.get('P_ID_NUMBER', 'N/A')}<br>"
            f"<b>Region:</b> {row.get('REGION', 'N/A')}<br>"
            f"<b>Deposit type:</b> {row.get('DEPOSIT_TYPE', 'N/A')}<br>"
            f"<b>Commodity:</b> {row.get('COMMODITY', 'N/A')}<br>"
            f"<b>Initial resource:</b> {row.get('REMAINING_RESOURCE', 'N/A')}<br>"
            f"<b>Grade:</b> {row.get('GRADE', 'N/A')}<br>"
            f"<b>Recovery:</b> {row.get('RECOVERY', 'N/A')}<br>"
            f"<b>Initial status:</b> {row.get('STATUS', 'N/A')}<br>"
            f"<b>Development probability:</b> {row.get('DEVELOPMENT_PROBABILITY', 'N/A')}<br>"
            f"<b>Start year:</b> {row.get('START_YEAR', 'N/A')}<br>"
            f"<b>Status percentages for {year}:</b><br>"
            f"{status_text}"
        )
    except Exception as e:
        print(f"Error creating hover text: {e}")
        return f"<b>{row.get('NAME', 'Unknown Project')}</b><br>Error loading project details"

def safe_read_csv(path):
    """Ensures csv files are read by pandas even when non-standard CSV encodings used"""
    with open(path, 'rb') as f:
        raw = f.read(32768)
        detected = charset_normalizer.detect(raw)
        encodings = [detected["encoding"], "utf-8-sig", "latin1", "cp1252"]

    for enc in encodings:
        try:
            df = pd.read_csv(path, dtype=str, encoding=enc)
            print(f"Read with encoding: {enc}")
            return df
        except UnicodeDecodeError:
            print(f"Failed with encoding: {enc}")
            continue
    print("All encoding attempts failed.")
    return pd.DataFrame()

# ==================== User Interface ====================

app_ui = ui.page_fluid(ui.tags.style(
    """ 
    .leaflet-container {height: 900px !important;}
    .plotly-container {height: 900px !important;}
    """),
    ui.navset_tab(
        ui.nav_panel("Inputs",
            ui.layout_sidebar(
                ui.sidebar(
                    ui.output_ui("scenario_selector_ui"),
                    ui.input_action_button("load_scenario_btn", "Load scenario"),
                    ui.hr(),
                    ui.output_ui("csv_inputs"),
                    ui.input_action_button("open_csv", "Open file"),
                    ui.input_action_button("btn", "Run simulation", class_="btn-primary"),
                ),
                ui.output_data_frame("editable_df"),
            width=2

            )
        ),
        ui.nav_panel("Outputs",
            ui.layout_sidebar(
                ui.sidebar(
                    ui.output_ui("folder_ui"),
                    ui.input_action_button("rename_folder_btn", "Rename folder"),
                    ui.output_ui("png_files_ui"),
                    ui.input_action_button("reprocess_btn", "Reprocess outputs"),
                ),
                ui.output_image("image", height="100%", width="100%"),
            width=2
            )
        ),
        ui.nav_panel("Projects",
            ui.layout_sidebar(
                ui.sidebar(
                    ui.output_ui("map_folder_ui"),
                    ui.output_ui("subfolder_ui"),
                    ui.output_ui("year_slider"),

                ),
                ui.navset_tab(
                    ui.nav_panel("Geographic distribution",
                        ui.div(
                            output_widget("map"),
                            class_="map-container"
                        )
                    ),
                    ui.nav_panel("Resource and grade",
                        ui.output_ui("commodity_selector_ui"),
                        ui.div(
                            output_widget("scatter_plot"),
                            class_="plotly-container"
                        )
                    )
                ),
            width=2
            )
        ),
        ui.nav_panel("About",
            ui.layout_sidebar(
                ui.sidebar(
                    ui.input_dark_mode(),
                    width=2
                ),
                ui.markdown(Path("README.md").read_text(encoding="utf-8"))
            )
        )
    )
)

# ==================== Server Logic ====================

def server(input, output, session):
    log_content = reactive.Value("")
    current_year = reactive.Value(None)
    input_source = reactive.Value("default")
    cached_data = reactive.Value(None)
    map_state = reactive.Value({})
    selected_commodity = reactive.Value(None)

    current_selections = reactive.Value({
        "png_file": None
    })

    # ==================== Folder and File Selection Logic ====================

    @reactive.Effect
    @reactive.event(input.png_file)
    def update_current_selections():
        current_selections.set({
            "png_file": input.png_file()
        })

    @reactive.Effect
    @reactive.event(input.folder)
    def update_selections():
        new_folder = input.folder()
        if new_folder:
            update_file_list("png_file", get_png_files())

    def update_file_list(file_type, new_files):
        current_file = current_selections()[file_type]
        if current_file in new_files:
            ui.update_select(file_type, choices=new_files, selected=current_file)
        elif new_files:
            ui.update_select(file_type, choices=new_files, selected=new_files[0])
        else:
            ui.update_select(file_type, choices=[], selected=None)
        current_selections.set({**current_selections(), file_type: input[file_type]()})

    @reactive.Calc
    def get_folders():
        if output_files_path.exists():
            return sorted([f.name for f in output_files_path.iterdir() if f.is_dir()], reverse=True)
        else:
            print(f"Output files directory not found: {output_files_path}")
            return []

    @reactive.Calc
    def get_png_files():
        folder = input.folder()
        if folder:
            graphs_folder = output_files_path / folder / "_graphs"
            return [f for f in os.listdir(graphs_folder) if f.endswith(('.png', '.gif'))] if graphs_folder.exists() else []
        return []

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

    @reactive.Effect
    @reactive.event(input.confirm_rename)
    def confirm_rename():
        current_folder = input.folder()
        new_name = input.new_folder_name()
        if new_name and new_name != current_folder:
            old_path = output_files_path / current_folder
            new_path = output_files_path / new_name
            if old_path.exists() and not new_path.exists():
                old_path.rename(new_path)
                ui.update_select("folder", choices=get_folders(), selected=new_name)
                ui.notification_show(f"Folder renamed to: {new_name}", duration=3)
            elif new_path.exists():
                ui.notification_show("A folder with this name already exists.", type="error", duration=3)
            else:
                ui.notification_show("Error renaming folder.", type="error", duration=3)
        ui.modal_remove()
    
    # ==================== UI Rendering Functions ====================

    @output
    @render.ui
    def folder_ui():
        folders = get_folders()
        if folders:
            return ui.input_select("folder", "Output folder:", choices=folders)
        else:
            return ui.div(f"No output folders found in {output_files_path}")

    @output
    @render.ui
    def png_files_ui():
        files = sorted(get_png_files())
        if files:
            selected = current_selections()["png_file"] if current_selections()["png_file"] in files else files[0]
            return ui.input_select("png_file", "Output figures:", choices=files, selected=selected)
        return ui.div("No PNG files found in the selected folder.")


    @output
    @render.ui
    def scenario_selector_ui():
        folders = get_folders()
        if folders:
            choices = ["Current input files"] + folders
            return ui.input_select("scenario_selector", "Source:", choices=choices, selected="Current input files")
        else:
            return ui.input_select("scenario_selector", "Source:", choices=["Current input files"], selected="Current input files")

    @reactive.Effect
    @reactive.event(input.scenario_selector)
    def update_input_source():
        if input.scenario_selector() == "Current input files":
            input_source.set("default")
        else:
            input_source.set(input.scenario_selector())
        ui.update_select("csv_input", choices=get_current_csv_files())

    # ==================== CSV Input Handling ====================

    @reactive.Calc
    def get_current_csv_files():
        if input_source.get() == "default":
            try:
                return sorted([f for f in os.listdir(input_files_path) if f.endswith('.csv')])
            except FileNotFoundError:
                return []
        else:
            scenario_input_path = output_files_path / input_source.get() / "_input_files"
            if scenario_input_path.exists():
                try:
                    return sorted([f for f in os.listdir(scenario_input_path) if f.endswith('.csv')])
                except FileNotFoundError:
                    return []
            return []

    @output
    @render.ui
    def csv_inputs():
        csv_files = get_current_csv_files()
        if csv_files:
            select_input = ui.input_select("csv_input", "Input files:", choices=csv_files)
            if input_source.get() != "default":
                return ui.tags.div(
                    ui.tags.small(f"Viewing from: {input_source.get()}", class_="text-warning"),
                    select_input
                )
            return ui.tags.div(select_input)
        else:
            return ui.div("No CSV files found")

    @reactive.Calc
    def load_csv():
        if input_source.get() == "default":
            csv_path = input_files_path / input.csv_input()
        else:
            csv_path = output_files_path / input_source.get() / "_input_files" / input.csv_input()
        
        if csv_path.exists():
            return safe_read_csv(csv_path)
        else:
            return pd.DataFrame()

    @reactive.effect
    def open_selected_csv():
        if input.open_csv() > 0:
            with reactive.isolate():
                if input_source.get() == "default":
                    selected_file_path = input_files_path / input.csv_input()
                else:
                    selected_file_path = output_files_path / input_source.get() / "_input_files" / input.csv_input()
                
                if selected_file_path.exists():
                    if sys.platform == "win32":
                        subprocess.run(f'start "" "{selected_file_path}"', shell=True)
                    elif sys.platform == "darwin":
                        subprocess.run(["open", str(selected_file_path)])
                    else:
                        subprocess.run(["xdg-open", str(selected_file_path)])

    @output
    @render.data_frame
    def editable_df():
        df = load_csv()
        editable = (input_source.get() == "default")
        return render.DataGrid(
            data=df,
            editable=editable,
            height="900px",
        )

    @editable_df.set_patch_fn
    def _(*, patch: render.CellPatch) -> render.CellValue:
        if input_source.get() != "default":
            ui.notification_show("Cannot edit files from scenario folders. Load them first.", type="warning", duration=3)
            return patch["value"]
        
        csv_path = input_files_path / input.csv_input()
        df = safe_read_csv(csv_path)
        df = df.astype('object')
        column_name = df.columns[patch["column_index"]]
        df.at[patch["row_index"], column_name] = patch["value"]
        df.to_csv(csv_path, index=False)
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
                shutil.copy2(src, dst)
            
            ui.update_select("scenario_selector", selected="Current input files")
            input_source.set("default")
            ui.update_select("csv_input", choices=get_current_csv_files())
            
            ui.notification_show(f"Successfully loaded {len(csv_files)} files from '{scenario_folder}'", type="success", duration=5)
            
        except Exception as e:
            ui.notification_show(f"Error loading files: {str(e)}", type="error", duration=5)
        
        ui.modal_remove()

    @reactive.Effect
    @reactive.event(input.cancel_load)
    def cancel_load():
        ui.modal_remove()

    # ==================== Simulation and Processing ====================

    @reactive.Effect
    @reactive.event(input.btn)
    async def run_pemmss():
        if input_source.get() != "default":
            ui.notification_show("Please switch to 'Current input files' before running simulation.", type="warning", duration=5)
            return
        
        static_files = import_static_files(input_files_path, input_files_cache_path)
        parameters = static_files['parameters']
        total_simulations = sum(param['iterations'] for param in parameters.values())
        with ui.Progress(min=0, max=total_simulations) as p:
            p.set(0, message="Running simulations...", detail=f"0 / {total_simulations}")
            async def run_and_update():
                os.chdir(current_dir)
                process = await asyncio.create_subprocess_exec(
                    sys.executable, "pemmss.py",
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                simulation_count = 0
                while True:
                    line = await process.stdout.readline()
                    if not line:
                        break
                    line = line.decode().strip()
                    if line.startswith("Scenario"):
                        simulation_count += 1
                        p.set(simulation_count, message="Processing output...", detail=f"{simulation_count} scenarios processed")
                await process.wait()
                if process.returncode != 0:
                    stderr = await process.stderr.read()
                    ui.modal_show(ui.modal(f"Error: {stderr.decode()}", easy_close=True, footer=None))
                else:
                    ui.notification_show("Process completed", duration=5)
                p.set(total_simulations, message="Completed", detail=f"{total_simulations} / {total_simulations}")
                update_log_content(input.folder())
            await run_and_update()
        ui.update_select("folder", choices=get_folders())

    def update_log_content(folder):
        if folder:
            log_file_path = output_files_path / folder / "log.txt"
            if log_file_path.exists():
                with open(log_file_path, "r") as log_file:
                    log_content.set(log_file.read())
            else:
                log_content.set(f"No log file found in folder: {folder}")

    @reactive.Effect
    @reactive.event(input.folder)
    def update_log():
        folder = input.folder()
        update_log_content(folder)



    @reactive.Effect
    @reactive.event(input.reprocess_btn)
    def reprocess_output_files():
        folder_input = input.folder()
        if folder_input:
            ui.notification_show("Reprocessing output files...", duration=None)
            def run_reprocess():
                input_files_directory = Path(input_files_path)
                custom_graphs = import_graphs(input_files_directory / 'input_graphs.csv')
                custom_graphs_formatting = import_graphs_formatting(input_files_directory / 'input_graphs_formatting.csv')
                output_stats_directory = output_files_path / folder_input / "_statistics"
                output_graphs_directory = output_files_path / folder_input / "_graphs"
                output_input_files_directory = output_files_path / folder_input / "_input_files"
                output_input_files_directory.mkdir(exist_ok=True)
                shutil.copy(input_files_path / "input_graphs.csv", output_input_files_directory)
                shutil.copy(input_files_path / "input_graphs_formatting.csv", output_input_files_directory)
                statistics_files = {}
                for file_name in os.listdir(output_stats_directory):
                    if file_name.endswith(".csv"):
                        scenario_name = file_name.split(".")[0]
                        file_path = output_stats_directory / file_name
                        statistics_files[scenario_name] = {"path": file_path}
                for graph in custom_graphs:
                    generate_figure(statistics_files, graph, custom_graphs_formatting, output_graphs_directory)
                ui.update_select("folder", choices=get_folders())
            thread = Thread(target=run_reprocess)
            thread.start()
        else:
            ui.notification_show("No folder selected for reprocessing.", duration=5, type="warning")

    # ==================== Output Rendering ====================

    @output
    @render.image
    def image():
        selected_png = input.png_file()
        folder = input.folder()
        if selected_png and folder:
            full_path = output_files_path / folder / "_graphs" / selected_png
            return {"src": str(full_path), "alt": "Selected Plot", "style": "width: 100%; height: auto;"}
        return None

    # ==================== Map and Scatter Plot Rendering ====================
    
    @output
    @render.ui
    def map_folder_ui():
        folders = get_folders()
        if folders:
            return ui.div(
                ui.input_select("map_folder", "Output folder:", choices=folders),
                ui.output_ui("subfolder_ui"),
                ui.output_ui("year_slider")
            )
        else:
            return ui.div(f"No output folders found in {output_files_path}")

    @output
    @render.ui
    def subfolder_ui():
        folder = input.map_folder()
        if folder:
            subfolders = [f for f in os.listdir(output_files_path / folder) 
                        if (output_files_path / folder / f).is_dir() 
                        and not f.startswith("_")]
            if subfolders:
                return ui.input_select("subfolder", "Subfolder:", choices=subfolders)
            else:
                return ui.div("No valid subfolders found.")
        return ui.div()
    
    @output
    @render.ui
    def year_slider():
        folder = input.map_folder()
        subfolder = input.subfolder()
        if folder and subfolder:
            _, _, years, _ = cached_project_data()
            if years:
                selected_year = current_year.get()
                if selected_year is None or selected_year not in years:
                    selected_year = min(years)
                    current_year.set(selected_year)
                min_year, max_year = min(years), max(years)
                if selected_year is None or selected_year not in years:
                    selected_year = min_year
                return ui.input_slider("year", "Select Year:", min=min_year, max=max_year, value=selected_year, sep='')
        return ui.div()

    @output
    @render.ui
    def commodity_selector_ui():
        projects, _, _, _ = cached_project_data()
        if projects is not None:
            current_selection = selected_commodity.get()
            commodities = sorted(projects['COMMODITY'].unique().tolist())
            if commodities and current_selection not in commodities:
                current_selection = commodities[0]
                selected_commodity.set(commodities[0])
            if commodities:
                if current_selection not in commodities:
                    current_selection = commodities[0]
                return ui.input_select("commodity", "Select Commodity:", choices=commodities, selected=current_selection)
        return ui.div()

    @reactive.Effect
    @reactive.event(input.year)
    def update_current_year():
        if input.year() is not None:
            current_year.set(input.year())

    @reactive.Effect
    @reactive.event(input.commodity)
    def update_selected_commodity():
        if input.commodity() is not None:
            selected_commodity.set(input.commodity())

    @reactive.Effect
    @reactive.event(input.map_folder, input.subfolder)
    def reset_cache_on_folder_change():
        cached_data.set(None)
        current_year.set(None)
        map_state.set({})
        selected_commodity.set(None)

    @reactive.Calc
    def cached_project_data():
        folder = input.map_folder()
        subfolder = input.subfolder()
        
        if not folder or not subfolder:
            cached_data.set(None)
            return None, None, [], False
            
        cache_key = f"{folder}_{subfolder}"
        cache = cached_data.get()
        
        if cache and cache.get('key') == cache_key:
            return cache['projects'], cache['year_data'], cache['years'], cache.get('has_semicolons', False)
        
        try:
            projects_file_path = output_files_path / folder / "_input_files" / "input_projects.csv"
            status_file = output_files_path / folder / subfolder / "_status.csv"
            
            if not projects_file_path.exists() or not status_file.exists():
                cached_data.set(None)
                return None, None, [], False
            
            projects_df = safe_read_csv(projects_file_path)
            status_df = safe_read_csv(status_file)
            
            valid_projects, year_data, years, has_semicolons = prepare_all_project_data(projects_df, status_df)
            
            if valid_projects is not None:
                cached_data.set({
                    'key': cache_key,
                    'projects': valid_projects,
                    'year_data': year_data,
                    'years': years,
                    'has_semicolons': has_semicolons
                })
                return valid_projects, year_data, years, has_semicolons
            else:
                cached_data.set(None)
                return None, None, [], False
                
        except Exception as e:
            print(f"Error caching data: {str(e)}")
            cached_data.set(None)
            return None, None, [], False

    @reactive.Calc
    def projects_for_year():
        projects, year_data, years, has_semicolons = cached_project_data()
        year = input.year()
        
        if projects is None or year_data is None or year is None or year not in years:
            return None, None, None, False
        
        year_df = year_data[year]
        result = projects.copy()
        result['STATUS_INFO'] = year_df['status_info']
        result['MAX_STATUS'] = year_df['max_status']
        result['MARKER_COLOR'] = year_df['marker_color']
        
        return result, year_data, years, has_semicolons

    @render_widget
    def map():
        try:
            projects, _, _, _ = projects_for_year()
            year = input.year()
            
            if projects is None or projects.empty or year is None:
                return Map(center=(0, 0), zoom=2, layout={'height': '900px'})

            folder_key = f"{input.map_folder()}_{input.subfolder()}"
            current_map_state = map_state.get()
            
            if current_map_state.get('folder_key') != folder_key:
                center_lat = projects["LATITUDE"].mean()
                center_lon = projects["LONGITUDE"].mean()
                if pd.isna(center_lat) or pd.isna(center_lon):
                    center_lat, center_lon = 0, 0

                base_map = Map(
                    center=(center_lat, center_lon), 
                    zoom=2, 
                    scroll_wheel_zoom=True, 
                    layout={'height': '900px'}
                )

                tile_layers = [
                    TileLayer(
                        url='https://mt1.google.com/vt/lyrs=s,h&x={x}&y={y}&z={z}', 
                        name='Google Satellite', 
                        base=True
                    ),
                ]
                for tile in tile_layers:
                    base_map.add(tile)

                base_map.add(LayersControl(position='topright'))
                
                markers = {}
                marker_layer = LayerGroup(name='Projects')
                
                for _, row in projects.iterrows():
                    try:
                        popup_html = create_hover_text(row, row['STATUS_INFO'], year)
                        popup = HTML(popup_html)

                        marker = CircleMarker(
                            location=(row["LATITUDE"], row["LONGITUDE"]),
                            radius=7,
                            color=row['MARKER_COLOR'],
                            fill_color=row['MARKER_COLOR'],
                            fill_opacity=0.8,
                            weight=0
                        )
                        marker.popup = popup
                        marker_layer.add(marker)
                        markers[row['P_ID_NUMBER']] = marker
                    except Exception as e:
                        print(f"Error creating marker for project {row.get('P_ID_NUMBER', 'unknown')}: {e}")
                        continue
                
                base_map.add(marker_layer)
                
                new_state = {
                    'folder_key': folder_key,
                    'base_map': base_map,
                    'marker_layer': marker_layer,
                    'markers': markers
                }
                map_state.set(new_state)
                
                return base_map
            
            else:
                base_map = current_map_state['base_map']
                markers = current_map_state['markers']
                
                for _, row in projects.iterrows():
                    if row['P_ID_NUMBER'] in markers:
                        try:
                            marker = markers[row['P_ID_NUMBER']]
                            marker.color = row['MARKER_COLOR']
                            marker.fill_color = row['MARKER_COLOR']
                            popup_html = create_hover_text(row, row['STATUS_INFO'], year)
                            marker.popup = HTML(popup_html)
                        except Exception as e:
                            print(f"Error updating marker for project {row['P_ID_NUMBER']}: {e}")
                            continue
                
                return base_map
                
        except Exception as e:
            print(f"Error rendering map: {e}")
            return Map(center=(0, 0), zoom=2, layout={'height': '900px'})

    @render_widget
    def scatter_plot():
        projects, _, _, has_semicolons = projects_for_year()
        year = input.year()
        commodity = selected_commodity.get()
        
        if has_semicolons:
            fig = go.Figure()
            fig.update_layout(
                title="Warning: Resource grade plot does not support ore tranche functionality",
                height=900,
                width=1200,
                template="simple_white",
                annotations=[
                    dict(
                        text="Data contains semicolons (;) indicating ore tranches.<br>This plot cannot display tranche data properly.",
                        xref="paper", yref="paper",
                        x=0.5, y=0.5, xanchor='center', yanchor='middle',
                        showarrow=False,
                        font=dict(size=16, color="orange")
                    )
                ]
            )
            return fig
        
        if projects is None or projects.empty or year is None or commodity is None:
            fig = go.Figure()
            fig.update_layout(
                title="No data available",
                height=900,
                width=1200,
                template="simple_white",
            )
            return fig

        projects = projects[projects['COMMODITY'] == commodity]

        if projects.empty:
            fig = go.Figure()
            fig.update_layout(
                title=f"No data available for {commodity}",
                height=900,
                width=1200,
                template="simple_white",
            )
            return fig

        fig = go.Figure()

        for status in STATUS_LABELS.values():
            status_projects = projects[projects['MAX_STATUS'] == status]

            if status_projects.empty:
                continue

            hover_texts = [
                create_hover_text(row, row['STATUS_INFO'], year)
                for _, row in status_projects.iterrows()
            ]
            sizes = 10

            fig.add_trace(go.Scatter(
                x=status_projects['REMAINING_RESOURCE'].astype(float),
                y=status_projects['GRADE'].astype(float),
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
            xaxis=dict(
                title="Remaining resource (metric tons)",
                type="log",
            ),
            yaxis=dict(
                title="Grade (mass ratio)",
            ),
            height=900,
            width=1200,
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