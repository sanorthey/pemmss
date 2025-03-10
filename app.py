"""
============================================================================================
Web Application for the Primary Exploration, Mining and Metal Supply Scenario (PEMMSS) Model
============================================================================================

This script implements a prototype Shiny for Python web application for the PEMMSS model.

It provides an interactive user interface for input management, simulation execution, output visualisation (including regional mapping).

This app.py file should exist in the same directory as the pemmss.py file.

To run the app, in the terminal run the command 'shiny run app.py', or 'python app.py'.

Author: Jayden Hyman
Date: 2024-07-29
Version: 0.1.1
Compatability: PEMMSS Version 1.3.1
License: BSD 3-Clause License
Dependencies: shiny, pandas, matplotlib, ipyleaflet, ipywidgets, shinywidgets
"""

# ==================== Imports and Setup ====================

import sys
import os
import asyncio
import shutil
import pandas as pd
import matplotlib.pyplot as plt
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
plt.rcParams['font.size'] = 8

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

# ==================== User Interface ====================

app_ui = ui.page_fluid(ui.tags.style(
    """ .leaflet-container {height: 900px !important;}"""),
    ui.navset_tab(
        ui.nav_panel("Inputs",
            ui.layout_sidebar(
                ui.panel_sidebar(
                    ui.output_ui("csv_inputs"),
                    ui.input_action_button("open_csv", "Open file", class_="btn-success"),
                    ui.input_action_button("btn", "Run simulation", class_="btn-primary"),
                    width=2
                ),
                ui.panel_main(
                    ui.output_data_frame("editable_df")
                )
            )
        ),
        ui.nav_panel("Outputs",
            ui.layout_sidebar(
                ui.panel_sidebar(
                    ui.output_ui("folder_ui"),
                    ui.input_action_button("rename_folder_btn", "Rename folder", class_="btn-primary"),
                    ui.output_ui("png_files_ui"),
                    ui.output_ui("inp_arc_ui"),
                    ui.output_ui("stats_files_ui"),
                    ui.input_action_button("reprocess_btn", "Reprocess outputs", class_="btn-primary"),
                    width=2
                ),
                ui.panel_main(
                    ui.navset_tab(
                        ui.nav_panel("Plots", ui.output_image("image", height="100%", width="100%")),
                        ui.nav_panel("Inputs", ui.output_data_frame("table_inputs")),
                        ui.nav_panel("Statistics", ui.output_data_frame("table_stats")),
                        ui.nav_panel("Log", ui.output_text_verbatim("log_text")),
                    )
                )
            )
        ),
        ui.nav_panel("Map",
            ui.layout_sidebar(
                ui.panel_sidebar(
                    ui.output_ui("map_folder_ui"),
                    ui.input_select("map_layer", "Base layer:", choices=["Satellite", "Street Map"]),
                    ui.output_ui("subfolder_ui"),
                    ui.output_ui("year_slider"),
                    width=2
                ),
                ui.panel_main(
                    ui.div(
                        output_widget("map")
                    )
                )
            )
        ),
        ui.nav_panel("About",
            ui.layout_sidebar(
                ui.panel_sidebar(
                    ui.input_dark_mode(),
                    width=2
                ),
                ui.panel_main(
                    ui.markdown(Path("README.md").read_text(encoding="utf-8"))
                )
            )
        )
    )
)

# ==================== Server Logic ====================

def server(input, output, session):
    log_content = reactive.Value("")

    current_selections = reactive.Value({
        "png_file": None,
        "inp_arc_file": None,
        "stats_file": None
    })

    # ==================== Folder and File Selection Logic ====================

    @reactive.Effect
    @reactive.event(input.png_file, input.inp_arc_file, input.stats_file)
    def update_current_selections():
        current_selections.set({
            "png_file": input.png_file(),
            "inp_arc_file": input.inp_arc_file(),
            "stats_file": input.stats_file()
        })

    @reactive.Effect
    @reactive.event(input.folder)
    def update_selections():
        new_folder = input.folder()
        if new_folder:
            update_file_list("png_file", get_png_files())
            update_file_list("inp_arc_file", get_inp_arc_files())
            update_file_list("stats_file", get_stats_files())

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
            return [f for f in os.listdir(graphs_folder) if f.endswith('.png')] if graphs_folder.exists() else []
        return []

    @reactive.Calc
    def get_inp_arc_files():
        folder = input.folder()
        if folder:
            input_files_folder = output_files_path / folder / "_input_files"
            return [f for f in os.listdir(input_files_folder) if f.endswith('.csv')] if input_files_folder.exists() else []
        return []

    @reactive.Calc
    def get_stats_files():
        folder = input.folder()
        if folder:
            stats_files_folder = output_files_path / folder / "_statistics"
            return [f for f in os.listdir(stats_files_folder) if f.endswith('.csv')] if stats_files_folder.exists() else []
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
        files = get_png_files()
        if files:
            selected = current_selections()["png_file"] if current_selections()["png_file"] in files else files[0]
            return ui.input_select("png_file", "Output figures:", choices=files, selected=selected)
        return ui.div("No PNG files found in the selected folder.")

    @output
    @render.ui
    def stats_files_ui():
        files = get_stats_files()
        if files:
            selected = current_selections()["stats_file"] if current_selections()["stats_file"] in files else files[0]
            return ui.input_select("stats_file", "Output statistics:", choices=files, selected=selected)
        return ui.div("No CSV files found in the selected folder.")

    @output
    @render.ui
    def inp_arc_ui():
        files = get_inp_arc_files()
        if files:
            selected = current_selections()["inp_arc_file"] if current_selections()["inp_arc_file"] in files else files[0]
            return ui.input_select("inp_arc_file", "Inputs archive:", choices=files, selected=selected)
        return ui.div("No CSV files found in the selected folder.")


    # ==================== CSV Input Handling ====================

    @output
    @render.ui
    def csv_inputs():
        try:
            csv_inputs = [f for f in os.listdir(input_files_path) if f.endswith('.csv')]
        except FileNotFoundError:
            print(f"Input files directory not found: {input_files_path}")
            csv_inputs = []
        if csv_inputs:
            select_input = ui.input_select("csv_input", "Input files:", choices=csv_inputs)
            return ui.tags.div(select_input)
        else:
            return ui.div(f"No CSV files found in {input_files_path}")

    @reactive.Calc
    def load_csv():
        csv_path = input_files_path / input.csv_input()
        if csv_path.exists():
            return pd.read_csv(csv_path, dtype=str) 
        else:
            print(f"CSV file not found: {csv_path}")
            return pd.DataFrame()

    @reactive.effect
    def open_selected_csv():
        if input.open_csv() > 0:
            with reactive.isolate():
                selected_file_path = input_files_path / input.csv_input()
                if selected_file_path.exists():
                    os.startfile(selected_file_path)

    @output
    @render.data_frame
    def editable_df():
        return render.DataGrid(
            data=load_csv(),
            editable=True,
            height="900px",
        )

    @editable_df.set_patch_fn
    def _(*, patch: render.CellPatch) -> render.CellValue:
        csv_path = input_files_path / input.csv_input()
        df = pd.read_csv(csv_path) 
        df = df.astype('object')
        column_name = df.columns[patch["column_index"]]
        df.at[patch["row_index"], column_name] = patch["value"]
        df.to_csv(csv_path, index=False)
        return patch["value"]

    # ==================== Simulation and Processing ====================

    @reactive.Effect
    @reactive.event(input.btn)
    async def run_pemmss():
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

    @output
    @render.text
    def log_text():
        return log_content()

    def reprocess_graphs(folder_input):
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

    @reactive.Effect
    @reactive.event(input.reprocess_btn)
    def reprocess_output_files():
        folder_input = input.folder()
        if folder_input:
            ui.notification_show("Reprocessing output files...", duration=None)
            def run_reprocess():
                reprocess_graphs(folder_input)
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

    @output
    @render.data_frame
    def table_inputs():
        selected_csv = input.inp_arc_file()
        folder = input.folder()
        if selected_csv and folder:
            full_path = output_files_path / folder / "_input_files" / selected_csv
            df = pd.read_csv(full_path)
            return render.DataGrid(
                df,
                height="900px",
            )
        else:
            return None

    @output
    @render.data_frame
    def table_stats():
        selected_csv = input.stats_file()
        folder = input.folder()
        if selected_csv and folder:
            full_path = output_files_path / folder / "_statistics" / selected_csv
            df = pd.read_csv(full_path)
            return render.DataGrid(
                df,
                height="900px"
            )
        else:
            return None

    # ==================== Map Rendering ====================
    
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
                        and f not in ["_graphs", "_statistics", "_input_files"]]
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
            status_file = output_files_path / folder / subfolder / "_status.csv"
            if status_file.exists():
                df = pd.read_csv(status_file)
                years = [col for col in df.columns if col.isdigit()]
                min_year, max_year = int(min(years)), int(max(years))
                return ui.input_slider("year", "Select Year:", min=min_year, max=max_year, value=min_year, sep='')
        return ui.div()

    @reactive.Calc
    def load_status_data():
        folder = input.map_folder()
        subfolder = input.subfolder()
        if folder and subfolder:
            status_file = output_files_path / folder / subfolder / "_status.csv"
            if status_file.exists():
                return pd.read_csv(status_file)
        return None

    @render_widget
    def map():
        folder = input.map_folder()
        subfolder = input.subfolder()
        year = input.year()
        map_layer = input.map_layer()
        if not folder or not subfolder:
            return Map(center=(0, 0), zoom=2, layout={'height': '900px'})
        try:
            projects_file_path = output_files_path / folder / "_input_files" / "input_projects.csv"
            if not projects_file_path.exists():
                return Map(center=(0, 0), zoom=2, layout={'height': '900px'})
            projects_df = pd.read_csv(projects_file_path)
            status_df = load_status_data()
            if status_df is None:
                return Map(center=(0, 0), zoom=2, layout={'height': '900px'})
            required_columns = ['LATITUDE', 'LONGITUDE', 'NAME', 'P_ID_NUMBER', 'REGION', 'DEPOSIT_TYPE', 'COMMODITY', 'REMAINING_RESOURCE', 'GRADE', 'STATUS']
            missing_columns = [col for col in required_columns if col not in projects_df.columns]
            if missing_columns:
                return Map(center=(0, 0), zoom=2, layout={'height': '900px'})
            valid_projects = projects_df.dropna(subset=['LATITUDE', 'LONGITUDE', 'REMAINING_RESOURCE', 'GRADE'])
            valid_projects = valid_projects[
                (valid_projects['LATITUDE'].between(-90, 90)) & 
                (valid_projects['LONGITUDE'].between(-180, 180))
            ]
            if valid_projects.empty:
                return Map(center=(0, 0), zoom=2, layout={'height': '900px'})
            center_lat = valid_projects["LATITUDE"].mean()
            center_lon = valid_projects["LONGITUDE"].mean()
            if not hasattr(map, 'base_map'):
                map.base_map = Map(center=(center_lat, center_lon), zoom=2, scroll_wheel_zoom=True, layout={'height': '900px'})
                if map_layer == "Satellite":
                    satellite = TileLayer(
                        url='https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
                        attribution='Esri',
                        name='Esri Satellite'
                    )
                    map.base_map.add_layer(satellite)
                else:
                    osm = TileLayer(
                        url='https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',
                        attribution='OpenStreetMap',
                        name='OpenStreetMap'
                    )
                    map.base_map.add_layer(osm)
                layer_control = LayersControl(position='topright')
                map.base_map.add_control(layer_control)
            if hasattr(map, 'marker_layer'):
                map.base_map.remove_layer(map.marker_layer)
            map.marker_layer = LayerGroup()
            
            def calculate_contained_resource(resource_str, grade_str):
                resources = [float(r) for r in resource_str.split(';')]
                grades = [float(g) for g in grade_str.split(';')]
                return sum(r * g for r, g in zip(resources, grades))
            
            valid_projects['CONTAINED_RESOURCE'] = valid_projects.apply(
                lambda row: calculate_contained_resource(str(row['REMAINING_RESOURCE']), str(row['GRADE'])), 
                axis=1
            )
            
            min_resource = valid_projects['CONTAINED_RESOURCE'].min()
            max_resource = valid_projects['CONTAINED_RESOURCE'].max()
            
            valid_projects['NORMALIZED_RESOURCE'] = (valid_projects['CONTAINED_RESOURCE'] - min_resource) / (max_resource - min_resource)

            for _, row in valid_projects.iterrows():
                project_status_data = status_df[status_df['P_ID_NUMBER'] == row['P_ID_NUMBER']]
                total_simulations = project_status_data[str(year)].sum()
                
                status_info = ""
                max_percentage = 0
                max_status = ""
                
                for status_code, status_label in STATUS_LABELS.items():
                    status_count = project_status_data[
                        (project_status_data['STATUS'] == status_label) & 
                        (project_status_data[str(year)] > 0)
                    ][str(year)].sum()
                    status_percentage = (status_count / total_simulations * 100) if total_simulations > 0 else 0
                    status_info += f"<strong>{status_label}:</strong> {status_percentage:.2f}%<br>"
                    
                    if status_percentage > max_percentage:
                        max_percentage = status_percentage
                        max_status = status_label
                
                marker_color = STATUS_COLORS.get(max_status, 'gray')
                size = int(5 + (row['NORMALIZED_RESOURCE'] * 15))
                
                popup = HTML(f"""
                <h4>{row['NAME']}</h4>
                <br>
                <strong>Input files:</strong><br>
                <br>
                <strong>Project ID:</strong> {row['P_ID_NUMBER']}<br>
                <strong>Region:</strong> {row['REGION']}<br>
                <strong>Deposit type:</strong> {row['DEPOSIT_TYPE']}<br>
                <strong>Commodity:</strong> {row['COMMODITY']}<br>
                <strong>Initial resource:</strong> {row['REMAINING_RESOURCE']}<br>
                <strong>Grade:</strong> {row['GRADE']}<br>
                <strong>Contained resource:</strong> {row['CONTAINED_RESOURCE']:.2f}<br>
                <strong>Initial status:</strong> {row['STATUS']}<br>
                <br>
                <strong>Status percentages for {year}:</strong><br>
                <br>
                {status_info}
                """)
                
                circle = CircleMarker(
                    location=(row["LATITUDE"], row["LONGITUDE"]),
                    radius=size,
                    color=marker_color,
                    fill_color=marker_color,
                    fill_opacity=0.7
                )
                circle.popup = popup
                map.marker_layer.add_layer(circle)
            
            map.base_map.add_layer(map.marker_layer)
            return map.base_map
        
        except Exception as e:
            print(f"Error creating map: {str(e)}")
            return Map(center=(0, 0), zoom=2, layout={'height': '900px'})

# ==================== Server Startup ====================

app = App(app_ui, server)

if __name__ == "__main__":
    app.run(host="localhost", port=8000, launch_browser = True)