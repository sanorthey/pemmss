"""
============================================================================================
Web Application for the Primary Exploration, Mining and Metal Supply Scenario (PEMMSS) Model
============================================================================================

This script implements a prototype Shiny for Python web application for the PEMMSS model.

It provides an interactive user interface for input management, simulation execution, output visualisation (including regional mapping).

This app.py file should exist in the same directory as the pemmss.py file.

To run the app, in the terminal run the command 'shiny run app.py', or 'python app.py'.

Author: Jayden Hyman
Date: 2025-05-26
Version: 0.2.0
Compatability: PEMMSS Version 1.3.1
License: BSD 3-Clause License
Dependencies: shiny, pandas, matplotlib, ipyleaflet, ipywidgets, shinywidgets, plotly, anywidget, localtileserver, rioxarray, geopandas
"""

# ==================== Imports and Setup ====================

import sys
import os
import subprocess
import asyncio
import shutil
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
import plotly.graph_objects as go
import geopandas as gpd
from shiny import App, render, ui, reactive
from pathlib import Path
from threading import Thread
from shapely.geometry import Point
from modules.post_processing import generate_figure
from modules.file_import import import_graphs, import_graphs_formatting, import_static_files
from ipyleaflet import Map, CircleMarker, TileLayer, LayersControl, LayerGroup, WidgetControl
from ipywidgets import HTML
from shinywidgets import output_widget, render_widget
from localtileserver import TileClient, get_leaflet_tile_layer

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

# ==================== Shared Functions ====================

def calculate_contained_resource(resource_str, grade_str):
    """Calculate contained resource from resource and grade strings."""
    resources = [float(r) for r in str(resource_str).split(';')]
    grades = [float(g) for g in str(grade_str).split(';')]
    return sum(r * g for r, g in zip(resources, grades))

def parse_status_string(status_str):
    """Parse status string and return status label with max probability."""
    if not isinstance(status_str, str) or status_str == "Unknown":
        return "Unknown"
    
    statuses = status_str.split(';')
    max_prob = -1
    max_status_code = None
    
    for s in statuses:
        try:
            code, prob_str = s.split(':')
            prob = float(prob_str)
            if prob > max_prob:
                max_prob = prob
                max_status_code = int(code)
        except (ValueError, IndexError):
            continue
            
    return STATUS_LABELS.get(max_status_code, "Unknown")

def create_hover_text_probs(row, year):
    """Create hover text showing status probabilities."""
    status_prob_str = row[str(year)]
    status_text_parts = []
    if isinstance(status_prob_str, str) and status_prob_str != "Unknown":
        for s in status_prob_str.split(';'):
            try:
                code, prob_str = s.split(':')
                label = STATUS_LABELS.get(int(code), '?')
                status_text_parts.append(f"{label}: {float(prob_str):.2f}")
            except (ValueError, IndexError):
                continue
        status_text = "<br>".join(status_text_parts)
    else:
        status_text = "No simulation data"

    return (f"<b>{row['NAME']}</b><br>"
            f"<b>Project ID:</b> {row['P_ID_NUMBER']}<br>"
            f"<b>Region:</b> {row['REGION']}<br>"
            f"<b>Deposit type:</b> {row['DEPOSIT_TYPE']}<br>"
            f"<b>Commodity:</b> {row['COMMODITY']}<br>"
            f"<b>Initial resource:</b> {row['REMAINING_RESOURCE']}<br>"
            f"<b>Grade:</b> {row['GRADE']}<br>"
            f"<b>Recovery:</b> {row['RECOVERY']}<br>"
            f"<b>Contained commodity:</b> {row['CONTAINED_RESOURCE']:.0f}<br>"
            f"<b>Initial status:</b> {row['STATUS']}<br>"
            f"<b>Development probability:</b> {row['DEVELOPMENT_PROBABILITY']}<br>"
            f"<b>Start year:</b> {row['START_YEAR']}<br>"
            f"<b>Status probabilities for {year}:</b><br>"
            f"{status_text}")

def get_project_status_counts(project_id, status_df, year):
    """Get status counts for a project at a given year - no calculations, just read from CSV."""
    year_str = str(year)
    if year_str not in status_df.columns:
        return {}, ""
    
    project_data = status_df[status_df['P_ID_NUMBER'] == project_id]
    if project_data.empty:
        return {}, ""
    
    status_counts = {}
    max_count = 0
    max_status = ""
    
    for _, row in project_data.iterrows():
        status = row['STATUS']
        # Handle NaN values
        try:
            count = row[year_str]
            if pd.isna(count):
                count = 0
            else:
                count = int(count)
        except (ValueError, TypeError):
            count = 0
            
        if count > 0:
            status_counts[status] = count
            if count > max_count:
                max_count = count
                max_status = status
    
    return status_counts, max_status

def prepare_all_project_data(projects_df, status_df):
    """Prepare project data for all years at once for caching."""
    required_columns = ['LATITUDE', 'LONGITUDE', 'NAME', 'P_ID_NUMBER', 'REGION', 
                       'DEPOSIT_TYPE', 'COMMODITY', 'REMAINING_RESOURCE', 'GRADE', 'STATUS', 'DEVELOPMENT_PROBABILITY','START_YEAR', 'DISCOVERY_YEAR']
    missing_columns = [col for col in required_columns if col not in projects_df.columns]
    if missing_columns:
        return None
    
    # Get year columns
    year_columns = [col for col in status_df.columns if col.isdigit()]
    if not year_columns:
        return None
    
    # Filter valid projects once
    valid_projects = projects_df.copy()
    valid_projects = valid_projects.dropna(subset=['LATITUDE', 'LONGITUDE', 'REMAINING_RESOURCE', 'GRADE'])
    valid_projects = valid_projects[
        (valid_projects['LATITUDE'].between(-90, 90)) & 
        (valid_projects['LONGITUDE'].between(-180, 180))
    ]
    
    if valid_projects.empty:
        return None
    
    # Calculate static attributes once
    valid_projects['CONTAINED_RESOURCE'] = valid_projects.apply(
        lambda row: calculate_contained_resource(row['REMAINING_RESOURCE'], row['GRADE']), 
        axis=1
    )
    
    valid_projects['FIRST_RESOURCE'] = valid_projects['REMAINING_RESOURCE'].apply(
        lambda x: float(str(x).split(';')[0])
    )
    valid_projects['FIRST_GRADE'] = valid_projects['GRADE'].apply(
        lambda x: float(str(x).split(';')[0])
    )
    
    min_resource = valid_projects['CONTAINED_RESOURCE'].min()
    max_resource = valid_projects['CONTAINED_RESOURCE'].max()
    if max_resource > min_resource:
        valid_projects['NORMALIZED_RESOURCE'] = (valid_projects['CONTAINED_RESOURCE'] - min_resource) / (max_resource - min_resource)
    else:
        valid_projects['NORMALIZED_RESOURCE'] = 0.5
    
    # Pre-calculate status data for all years
    year_data = {}
    for year in year_columns:
        year_int = int(year)
        year_project_data = []
        
        for _, row in valid_projects.iterrows():
            status_counts, max_status = get_project_status_counts(row['P_ID_NUMBER'], status_df, year_int)
            year_project_data.append({
                'status_counts': status_counts,
                'max_status': max_status,
                'marker_color': STATUS_COLORS.get(max_status, 'gray')
            })
        
        year_data[year_int] = pd.DataFrame(year_project_data)
    
    return valid_projects, year_data, [int(y) for y in year_columns]

def create_hover_text_counts(row, status_counts, year):
    """Create hover text showing status counts instead of percentages."""
    if status_counts:
        status_text = "<br>".join([f"{label}: {count}" for label, count in status_counts.items()])
    else:
        status_text = "No simulation data"
    
    return (f"<b>{row['NAME']}</b><br>"
            f"<b>Project ID:</b> {row['P_ID_NUMBER']}<br>"
            f"<b>Region:</b> {row['REGION']}<br>"
            f"<b>Deposit type:</b> {row['DEPOSIT_TYPE']}<br>"
            f"<b>Commodity:</b> {row['COMMODITY']}<br>"
            f"<b>Initial resource:</b> {row['REMAINING_RESOURCE']}<br>"
            f"<b>Grade:</b> {row['GRADE']}<br>"
            f"<b>Recovery:</b> {row['RECOVERY']}<br>"
            f"<b>Contained commodity:</b> {row['CONTAINED_RESOURCE']:.0f}<br>"
            f"<b>Initial status:</b> {row['STATUS']}<br>"
            f"<b>Development probability:</b> {row['DEVELOPMENT_PROBABILITY']}<br>"
            f"<b>Start year:</b> {row['START_YEAR']}<br>"
            f"<b>Status counts for {year}:</b><br>"
            f"{status_text}")

def load_raster_layers(map_instance):
    """Load raster layers from CSV and add them to the map."""
    raster_csv_path = input_files_path / "input_spatial.csv"
    if not raster_csv_path.exists():
        return {}

    raster_df = pd.read_csv(raster_csv_path)
    raster_clients = {}
    for _, row in raster_df.iterrows():
        try:
            client = TileClient(Path(row['file_path']))
            raster_clients[row['layer_name']] = client

            colormap = row['palette'] if pd.notna(row['palette']) and row['palette'].strip() else 'viridis'

            tile_layer = get_leaflet_tile_layer(
                client,
                indexes=1,
                colormap=colormap,
                vmin=float(row['min_val']),
                vmax=float(row['max_val']),
                nodata=float(row['nodata']),
                name=row['layer_name'],
                attribution=row['attribution']
            )
            
            map_instance.add_layer(tile_layer)
        except Exception as e:
            print(f"Error loading raster layer {row['layer_name']}: {e}")
    
    return raster_clients

def generate_geopackage_from_scenario(scenario_path, input_projects_path):
    """
    Process status data for a scenario, merge with project data, and create a geopackage.
    """
    status_path = scenario_path / "_status.csv"
    output_path = scenario_path / "projects.gpkg"

    if not status_path.exists():
        print(f"Cannot generate GeoPackage: _status.csv not found in {scenario_path}")
        return None
    if not input_projects_path.exists():
        print(f"Cannot generate GeoPackage: input_projects.csv not found in {input_projects_path.parent}")
        return None
        
    status_df = pd.read_csv(status_path)
    year_columns = [col for col in status_df.columns if col.isdigit()]
    
    STATUS_CODES = {v: k for k, v in STATUS_LABELS.items()}
    result_data = []
    
    for project_id in status_df['P_ID_NUMBER'].unique():
        project_data = status_df[status_df['P_ID_NUMBER'] == project_id]
        row_data = {'P_ID_NUMBER': project_id}
        
        for year in year_columns:
            total_simulations = project_data[year].sum()
            
            if total_simulations == 0:
                row_data[year] = "Unknown"
                continue
                
            status_counts = project_data.groupby('STATUS')[year].sum()
            if status_counts.empty:
                row_data[year] = "Unknown"
                continue
            
            status_probs = status_counts / total_simulations
            sorted_statuses = status_probs.sort_values(ascending=False)
            status_strings = []
            for status, prob in sorted_statuses.items():
                status_code = STATUS_CODES.get(status, "?")
                status_strings.append(f"{status_code}:{prob:.2f}")
            
            row_data[year] = ";".join(status_strings)
        
        result_data.append(row_data)
    
    result_df = pd.DataFrame(result_data)
    projects_df = pd.read_csv(input_projects_path)
    projects_with_status = projects_df.merge(result_df, on='P_ID_NUMBER', how='left')
    
    projects_with_status['LATITUDE'] = pd.to_numeric(projects_with_status['LATITUDE'], errors='coerce')
    projects_with_status['LONGITUDE'] = pd.to_numeric(projects_with_status['LONGITUDE'], errors='coerce')
    
    valid_projects = projects_with_status.dropna(subset=['LATITUDE', 'LONGITUDE'])
    valid_projects = valid_projects[
        valid_projects['LATITUDE'].between(-90, 90) &
        valid_projects['LONGITUDE'].between(-180, 180)
    ].copy()

    if valid_projects.empty:
        print("Warning: No valid project coordinates found during GeoPackage generation.")
        return None

    geometries = [Point(row['LONGITUDE'], row['LATITUDE']) for _, row in valid_projects.iterrows()]
    projects_gdf = gpd.GeoDataFrame(valid_projects, geometry=geometries, crs="EPSG:4326")
    
    try:
        projects_gdf.to_file(output_path, driver='GPKG')
        ui.notification_show(f"Map data created for {scenario_path.name}.", type="success")
        return output_path
    except Exception as e:
        print(f"Error saving GeoPackage: {e}")
        return None

# ==================== User Interface ====================

app_ui = ui.page_fluid(ui.tags.style(
    """ 
    .leaflet-container {height: 900px !important;}
    .plotly-container {height: 900px !important;}
    """),
    ui.navset_tab(
        ui.nav_panel("Inputs",
            ui.layout_sidebar(
                ui.panel_sidebar(
                    ui.output_ui("scenario_selector_ui"),
                    ui.input_action_button("load_scenario_btn", "Load scenario inputs", class_="btn-warning"),
                    ui.hr(),
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
                    ui.input_action_button("delete_folder_btn", "Delete folder", class_="btn-danger"),
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
        ui.nav_panel("Projects",
            ui.layout_sidebar(
                ui.panel_sidebar(
                    ui.output_ui("map_folder_ui"),
                    ui.input_slider("map_width_slider", "Map-Plot Width:", min=1, max=11, value=7),
                    width=2
                ),
                ui.panel_main(
                    ui.row(
                        ui.output_ui("map_column_ui"),
                        ui.output_ui("scatter_column_ui")
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
    current_year = reactive.Value(None)
    input_source = reactive.Value("default")  # Track whether using default or scenario inputs
    
    # New reactive value for caching the GeoDataFrame
    cached_geodata_val = reactive.Value(None)
    is_playing = reactive.Value(False)

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
            return sorted([f for f in os.listdir(graphs_folder) if f.endswith(('.png', '.gif'))]) if graphs_folder.exists() else []
        return []

    @reactive.Calc
    def get_inp_arc_files():
        folder = input.folder()
        if folder:
            input_files_folder = output_files_path / folder / "_input_files"
            return sorted([f for f in os.listdir(input_files_folder) if f.endswith('.csv')]) if input_files_folder.exists() else []
        return []

    @reactive.Calc
    def get_stats_files():
        folder = input.folder()
        if folder:
            stats_files_folder = output_files_path / folder / "_statistics"
            return sorted([f for f in os.listdir(stats_files_folder) if f.endswith('.csv')]) if stats_files_folder.exists() else []
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
    
    @reactive.Effect
    @reactive.event(input.delete_folder_btn)
    def delete_folder():
        current_folder = input.folder()
        if current_folder:
            ui.modal_show(ui.modal(
                ui.p(f"Are you sure you want to delete the folder '{current_folder}'?"),
                ui.p("This action cannot be undone and will permanently delete all files in this folder.", style="color: red;"),
                ui.input_action_button("confirm_delete", "Yes, delete folder", class_="btn-danger"),
                ui.input_action_button("cancel_delete", "Cancel", class_="btn-secondary"),
                title="Confirm Folder Deletion",
                easy_close=True
            ))
        else:
            ui.notification_show("No folder selected.", type="warning", duration=3)

    @reactive.Effect
    @reactive.event(input.confirm_delete)
    def confirm_delete():
        current_folder = input.folder()
        if current_folder:
            folder_path = output_files_path / current_folder
            if folder_path.exists():
                try:
                    # Delete the folder and all its contents
                    shutil.rmtree(folder_path)
                    ui.notification_show(f"Folder '{current_folder}' deleted successfully.", type="success", duration=3)
                    
                    # Update the folder list and select the first available folder
                    new_folders = get_folders()
                    if new_folders:
                        ui.update_select("folder", choices=new_folders, selected=new_folders[0])
                    else:
                        ui.update_select("folder", choices=[], selected=None)
                except Exception as e:
                    ui.notification_show(f"Error deleting folder: {str(e)}", type="error", duration=5)
            else:
                ui.notification_show("Folder not found.", type="error", duration=3)
        ui.modal_remove()

    @reactive.Effect
    @reactive.event(input.cancel_delete)
    def cancel_delete():
        """Cancel the delete operation."""
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

    # ==================== Scenario Selector for Inputs Tab ====================

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
        """Update the input source when scenario selector changes."""
        if input.scenario_selector() == "Current input files":
            input_source.set("default")
        else:
            input_source.set(input.scenario_selector())
        # Force refresh of CSV inputs
        ui.update_select("csv_input", choices=get_current_csv_files())

    # ==================== CSV Input Handling ====================

    @reactive.Calc
    def get_current_csv_files():
        """Get CSV files based on current input source."""
        if input_source.get() == "default":
            # Use main input_files directory
            try:
                return sorted([f for f in os.listdir(input_files_path) if f.endswith('.csv')])
            except FileNotFoundError:
                return []
        else:
            # Use scenario's _input_files directory
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
                # Add indicator showing source
                return ui.tags.div(
                    ui.tags.small(f"Viewing from: {input_source.get()}", class_="text-warning"),
                    select_input
                )
            return ui.tags.div(select_input)
        else:
            return ui.div(f"No CSV files found")

    @reactive.Calc
    def load_csv():
        """Load CSV from the appropriate directory based on input source."""
        if input_source.get() == "default":
            csv_path = input_files_path / input.csv_input()
        else:
            csv_path = output_files_path / input_source.get() / "_input_files" / input.csv_input()
        
        if csv_path.exists():
            return pd.read_csv(csv_path, dtype=str) 
        else:
            print(f"CSV file not found: {csv_path}")
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
                    subprocess.run(["open" if sys.platform == "darwin" else "xdg-open" if sys.platform != "win32" else "start", str(selected_file_path)])

    @output
    @render.data_frame
    def editable_df():
        df = load_csv()
        # Make it read-only if viewing from a scenario
        editable = (input_source.get() == "default")
        return render.DataGrid(
            data=df,
            editable=editable,
            height="900px",
        )

    @editable_df.set_patch_fn
    def _(*, patch: render.CellPatch) -> render.CellValue:
        # Only allow edits if using default input files
        if input_source.get() != "default":
            ui.notification_show("Cannot edit files from scenario folders. Load them first.", type="warning", duration=3)
            return patch["value"]
        
        csv_path = input_files_path / input.csv_input()
        df = pd.read_csv(csv_path) 
        df = df.astype('object')
        column_name = df.columns[patch["column_index"]]
        df.at[patch["row_index"], column_name] = patch["value"]
        df.to_csv(csv_path, index=False)
        return patch["value"]

    # ==================== Load Scenario Functionality ====================

    @reactive.Effect
    @reactive.event(input.load_scenario_btn)
    def load_scenario_inputs():
        """Load input files from selected scenario to main input_files directory."""
        if input.scenario_selector() == "Current input files":
            ui.notification_show("Already using current input files.", type="info", duration=3)
            return
        
        scenario_folder = input.scenario_selector()
        scenario_input_path = output_files_path / scenario_folder / "_input_files"
        
        if not scenario_input_path.exists():
            ui.notification_show(f"No input files found for scenario: {scenario_folder}", type="error", duration=5)
            return
        
        # Show confirmation modal
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
        """Actually perform the file loading after confirmation."""
        scenario_folder = input.scenario_selector()
        scenario_input_path = output_files_path / scenario_folder / "_input_files"
        
        try:
            # Get list of CSV files to copy
            csv_files = sorted([f for f in os.listdir(scenario_input_path) if f.endswith('.csv')])
            
            if not csv_files:
                ui.notification_show("No CSV files found in scenario folder.", type="warning", duration=5)
                ui.modal_remove()
                return
            
            # Copy each file
            for csv_file in csv_files:
                src = scenario_input_path / csv_file
                dst = input_files_path / csv_file
                shutil.copy2(src, dst)
            
            # Switch back to default input source
            ui.update_select("scenario_selector", selected="Current input files")
            input_source.set("default")
            
            # Force refresh of file list
            ui.update_select("csv_input", choices=get_current_csv_files())
            
            ui.notification_show(f"Successfully loaded {len(csv_files)} files from '{scenario_folder}'", type="success", duration=5)
            
        except Exception as e:
            ui.notification_show(f"Error loading files: {str(e)}", type="error", duration=5)
        
        ui.modal_remove()

    @reactive.Effect
    @reactive.event(input.cancel_load)
    def cancel_load():
        """Cancel the load operation."""
        ui.modal_remove()

    # ==================== Simulation and Processing ====================

    @reactive.Effect
    @reactive.event(input.btn)
    async def run_pemmss():
        # Ensure we're using default input files for simulation
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
        
        if output_graphs_directory.exists():
            shutil.rmtree(output_graphs_directory)
        output_graphs_directory.mkdir(exist_ok=True)
        
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
            _, years = cached_geodata()
            if years:
                min_year, max_year = min(years), max(years)
                selected_year = current_year.get()
                if selected_year is None or selected_year not in years:
                    selected_year = min_year
                    current_year.set(selected_year)
                
                return ui.div(
                    ui.input_slider("year", "Select Year:", 
                                  min=min_year, 
                                  max=max_year, 
                                  value=selected_year, 
                                  step=1),
                    ui.div(
                        ui.input_action_button("play_btn", "Play", 
                                             class_="btn-success btn-sm"),
                        ui.input_action_button("stop_btn", "Stop", 
                                             class_="btn-danger btn-sm"),
                        style="margin-top: 10px;"
                    )
                )
        return ui.div()

    @reactive.Effect
    @reactive.event(input.year)
    def update_current_year():
        """Update current year when slider changes."""
        year = input.year()
        if year is not None:
            current_year.set(year)

    @reactive.Calc
    def cached_geodata():
        """Load and cache GeoPackage data for the selected scenario."""
        folder = input.map_folder()
        subfolder = input.subfolder()
        
        if not folder or not subfolder:
            cached_geodata_val.set(None)
            return None, []
            
        gpkg_path = output_files_path / folder / subfolder / "projects.gpkg"
        
        if not gpkg_path.exists():
            ui.notification_show(f"Map data not found. Generating for {subfolder}...", duration=None)
            scenario_path = output_files_path / folder / subfolder
            input_projects_path = output_files_path / folder / "_input_files" / "input_projects.csv"
            
            generated_path = generate_geopackage_from_scenario(scenario_path, input_projects_path)
            if not generated_path:
                ui.notification_show(f"Failed to generate map data for {subfolder}. Check logs.", type="error", duration=10)
                cached_geodata_val.set(None)
                return None, []
        
        cached_data = cached_geodata_val.get()
        if cached_data and cached_data.get('path') == gpkg_path:
            return cached_data['gdf'], cached_data['years']

        if not gpkg_path.exists():
            cached_geodata_val.set(None)
            return None, []
            
        try:
            gdf = gpd.read_file(gpkg_path)
            
            # Add data validation to ensure map stability
            gdf['LATITUDE'] = pd.to_numeric(gdf['LATITUDE'], errors='coerce')
            gdf['LONGITUDE'] = pd.to_numeric(gdf['LONGITUDE'], errors='coerce')
            gdf = gdf.dropna(subset=['LATITUDE', 'LONGITUDE'])
            gdf = gdf[
                gdf['LATITUDE'].between(-90, 90) &
                gdf['LONGITUDE'].between(-180, 180)
            ].copy()

            if gdf.empty:
                print("Warning: GeoPackage contains no valid project coordinates after cleaning.")
                cached_geodata_val.set(None)
                return None, []

            # Calculate static attributes once
            gdf['CONTAINED_RESOURCE'] = gdf.apply(
                lambda row: calculate_contained_resource(row['REMAINING_RESOURCE'], row['GRADE']), 
                axis=1
            )
            
            min_resource = gdf['CONTAINED_RESOURCE'].min()
            max_resource = gdf['CONTAINED_RESOURCE'].max()
            if max_resource > min_resource:
                gdf['NORMALIZED_RESOURCE'] = (gdf['CONTAINED_RESOURCE'] - min_resource) / (max_resource - min_resource)
            else:
                gdf['NORMALIZED_RESOURCE'] = 0.5

            gdf['FIRST_RESOURCE'] = gdf['REMAINING_RESOURCE'].apply(
                lambda x: float(str(x).split(';')[0]) if pd.notna(x) else np.nan
            )
            gdf['FIRST_GRADE'] = gdf['GRADE'].apply(
                lambda x: float(str(x).split(';')[0]) if pd.notna(x) else np.nan
            )

            year_columns = sorted([col for col in gdf.columns if col.isdigit()])
            years = [int(y) for y in year_columns]

            cached_geodata_val.set({'gdf': gdf, 'years': years, 'path': gpkg_path})
            
            return gdf, years
            
        except Exception as e:
            print(f"Error loading GeoPackage data: {str(e)}")
            cached_geodata_val.set(None)
            return None, []

    @reactive.Calc
    def projects_for_year():
        """Get processed project data for the current year from cached GeoDataFrame."""
        gdf, _ = cached_geodata()
        year = input.year()
        
        if gdf is None or gdf.empty or year is None or str(year) not in gdf.columns:
            return None
        
        df = gdf.copy()
        
        year_str = str(year)
        df['MAX_STATUS'] = df[year_str].apply(parse_status_string)
        df['MARKER_COLOR'] = df['MAX_STATUS'].apply(lambda x: STATUS_COLORS.get(x, 'gray'))
        
        return df

    @reactive.Calc
    def animation_timer():
        if is_playing.get():
            reactive.invalidate_later(1)
            return True
        return False

    @reactive.Effect
    @reactive.event(animation_timer)
    def advance_year_animation():
        """Advance year when animation is playing."""
        if is_playing.get():
            years = cached_geodata()[1]
            if years:
                current = input.year()
                max_year = max(years)
                min_year = min(years)
                
                # Find next year in the list
                if current < max_year:
                    # Get next year that exists in the data
                    next_years = [y for y in years if y > current]
                    if next_years:
                        next_year = min(next_years)
                        ui.update_slider("year", value=next_year)
                else:
                    # Loop back to beginning
                    ui.update_slider("year", value=min_year)

    @reactive.Effect
    @reactive.event(input.play_btn)
    def start_animation():
        """Start the year animation."""
        is_playing.set(True)

    @reactive.Effect
    @reactive.event(input.stop_btn)
    def stop_animation():
        """Stop the year animation."""
        is_playing.set(False)

    @reactive.Effect
    @reactive.event(input.map_folder, input.subfolder)
    def reset_on_folder_change():
        """Reset animation state and clear cache when folder changes."""
        is_playing.set(False)
        cached_geodata_val.set(None)
        current_year.set(None)
        
        if hasattr(map, 'current_folder_key'):
            map.current_folder_key = None
        if hasattr(scatter_plot, 'current_folder_key'):
            scatter_plot.current_folder_key = None

    @render_widget
    def map():
        valid_projects = projects_for_year()
        year = input.year()
        
        if valid_projects is None or valid_projects.empty:
            return Map(center=(0, 0), zoom=2, layout={'height': '900px'})
        
        center_lat = valid_projects["LATITUDE"].mean()
        center_lon = valid_projects["LONGITUDE"].mean()
        
        if not hasattr(map, 'base_map') or not hasattr(map, 'current_folder_key'):
            map.current_folder_key = None
        
        folder_key = f"{input.map_folder()}_{input.subfolder()}"
        
        if map.current_folder_key != folder_key:
            map.base_map = Map(center=(center_lat, center_lon), zoom=2, 
                             scroll_wheel_zoom=True, layout={'height': '900px'})
            
            # Add base layers (Google, etc.)
            google_hybrid = TileLayer(
                url='https://mt1.google.com/vt/lyrs=y&x={x}&y={y}&z={z}',
                attribution='Google',
                name='Google Hybrid',
                base=True
            )
            google_sat = TileLayer(
                url='https://mt1.google.com/vt/lyrs=s,h&x={x}&y={y}&z={z}',
                attribution='Google',
                name='Google Satellite',
                base=True
            )
            google_roads = TileLayer(
                url='https://mt1.google.com/vt/lyrs=m&x={x}&y={y}&z={z}',
                attribution='Google',
                name='Google Roads',
                base=True
            )
            map.base_map.add_layer(google_roads)
            map.base_map.add_layer(google_sat)
            map.base_map.add_layer(google_hybrid)
            
            # Load raster layers and keep track of their clients
            map.raster_clients = load_raster_layers(map.base_map)

            layer_control = LayersControl(position='topright')
            map.base_map.add_layer(layer_control)

            # Create and add the info box for raster values
            map.info_widget = HTML(value="Click on the map for raster values")
            info_control = WidgetControl(widget=map.info_widget, position='bottomright')
            map.base_map.add(info_control)

            # Define and register the click handler
            def handle_map_click(**event):
                if event['type'] == 'click':
                    lat, lon = event['coordinates']
                    
                    html_info = f"<b>Coordinates:</b> {lat:.4f}, {lon:.4f}<br/>"
                    
                    # Query each raster client for the value at the clicked point
                    for name, client in map.raster_clients.items():
                        try:
                            value = client.point(lon=lon, lat=lat)
                            # The value is a PointData object with a `data` attribute (numpy array)
                            html_info += f"<b>{name}:</b> {value.data[0]:.2f}<br/>"
                        except Exception as e:
                            print(f"Could not get value for {name}: {e}")
                    
                    map.info_widget.value = html_info

            map.base_map.on_interaction(handle_map_click)
            
            map.marker_layer = LayerGroup(name='Projects')
            map.base_map.add_layer(map.marker_layer)
            
            map.markers = {}
            
            for _, row in valid_projects.iterrows():
                size = int(5 + (row['NORMALIZED_RESOURCE'] * 15))
                
                popup_html = create_hover_text_probs(row, year)
                popup = HTML(popup_html)
                
                circle = CircleMarker(
                    location=(row["LATITUDE"], row["LONGITUDE"]),
                    radius=size,
                    color=row['MARKER_COLOR'],
                    fill_color=row['MARKER_COLOR'],
                    fill_opacity=0.9,
                    weight=0
                )
                circle.popup = popup
                map.marker_layer.add_layer(circle)
                
                map.markers[row['P_ID_NUMBER']] = circle
            
            map.current_folder_key = folder_key
        
        else:
            for _, row in valid_projects.iterrows():
                if row['P_ID_NUMBER'] in map.markers:
                    marker = map.markers[row['P_ID_NUMBER']]
                    
                    marker.color = row['MARKER_COLOR']
                    marker.fill_color = row['MARKER_COLOR']
                    
                    popup_html = create_hover_text_probs(row, year)
                    marker.popup = HTML(popup_html)
        
        return map.base_map

    @render_widget
    def scatter_plot():
        valid_projects = projects_for_year()
        year = input.year()
        
        if valid_projects is None or valid_projects.empty:
            fig = go.Figure()
            fig.update_layout(
                title="No data available",
                height=900,
                template="plotly_white",
            )
            return fig
        
        if not hasattr(scatter_plot, 'current_folder_key'):
            scatter_plot.current_folder_key = None
            
        folder_key = f"{input.map_folder()}_{input.subfolder()}"
        
        if scatter_plot.current_folder_key != folder_key:
            fig = go.Figure()
            
            scatter_plot.trace_indices = {}
            trace_idx = 0
            
            for status in STATUS_LABELS.values():
                status_projects = valid_projects[valid_projects['MAX_STATUS'] == status]
                
                hover_texts = []
                x_data = []
                y_data = []
                sizes = []
                
                if not status_projects.empty:
                    for _, row in status_projects.iterrows():
                        hover_texts.append(create_hover_text_probs(row, year))
                    x_data = status_projects['FIRST_RESOURCE']
                    y_data = status_projects['FIRST_GRADE']
                    sizes = 5 + (status_projects['NORMALIZED_RESOURCE'] * 34)
                
                fig.add_trace(go.Scatter(
                    x=x_data,
                    y=y_data,
                    mode='markers',
                    name=status,
                    marker=dict(
                        size=sizes,
                        color=STATUS_COLORS[status],
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
                
                scatter_plot.trace_indices[status] = trace_idx
                trace_idx += 1
            
            fig.update_layout(
                xaxis=dict(
                    title="Remaining Resource (log scale)",
                    type="log",
                    gridcolor='rgba(128,128,128,0.2)',
                    showgrid=True,
                    showline=True,
                    linewidth=1,
                    linecolor='rgba(128,128,128,0.2)',
                    mirror=True
                ),
                yaxis=dict(
                    title="Grade",
                    gridcolor='rgba(128,128,128,0.2)',
                    showgrid=True,
                    showline=True,
                    linewidth=1,
                    linecolor='rgba(128,128,128,0.2)',
                    mirror=True
                ),
                height=900,
                template="plotly_white",
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
            
            scatter_plot.fig = fig
            scatter_plot.current_folder_key = folder_key
        
        else:
            fig = scatter_plot.fig
            
            for status in STATUS_LABELS.values():
                if status in scatter_plot.trace_indices:
                    status_projects = valid_projects[valid_projects['MAX_STATUS'] == status]
                    trace_idx = scatter_plot.trace_indices[status]
                    
                    if not status_projects.empty:
                        hover_texts = []
                        for _, row in status_projects.iterrows():
                            hover_texts.append(create_hover_text_probs(row, year))
                        
                        sizes = 5 + (status_projects['NORMALIZED_RESOURCE'] * 34)
                        
                        fig.data[trace_idx].x = status_projects['FIRST_RESOURCE']
                        fig.data[trace_idx].y = status_projects['FIRST_GRADE']
                        fig.data[trace_idx].hovertext = hover_texts
                        fig.data[trace_idx].marker.size = sizes
                    else:
                        fig.data[trace_idx].x = []
                        fig.data[trace_idx].y = []
                        fig.data[trace_idx].hovertext = []
                        fig.data[trace_idx].marker.size = []
        
        return scatter_plot.fig

    @render.ui
    def map_column_ui():
        return ui.column(
            input.map_width_slider(),
            ui.h4("Geographic distribution"),
            ui.div(
                output_widget("map"),
                class_="map-container"
            )
        )

    @render.ui
    def scatter_column_ui():
        scatter_width = 12 - input.map_width_slider()
        return ui.column(
            scatter_width,
            ui.h4("Resource and grade"),
            ui.div(
                output_widget("scatter_plot"),
                class_="plotly-container"
            )
        )

# ==================== Server Startup ====================

app = App(app_ui, server)

if __name__ == "__main__":
    app.run(host="localhost", port=8000, launch_browser = True)