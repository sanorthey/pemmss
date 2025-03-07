"""
Module with functions for handling spatial data
"""
# Import standard packages
import random

# Import non-standard packages
import geopandas as gpd
import pandas as pd
from shapely.geometry import Point

# Import custom modules
from modules.file_export import export_log

def import_geopackage(path, log_path=None):
    """
    Reads a geopackage (.gpkg) at 'path' and returns a geopandas dataframe. If fails, returns a blank geodataframe
    """
    try:
        # Load the geopackage
        gdf = gpd.read_file(path)
        return gdf
    except:
        gdf = gpd.GeoDataFrame(geometry=gpd.GeoSeries(), crs='EPSG:4326')  # Blank geodataframe
        if log_path is not None:
            export_log('+++ Failed to import input_geopackage.gpkg.'
                       '--- Unable to generate coordinates for greenfield discoveries.'
                       '--- Unable to generate missing coordinates in input_projects.csv', output_path=log_path, print_on=True)
        return gdf


def create_geodataframe_dict_list(factors, geodataframe, simplify=True, log_path=None):
    """
    Separate and process geopackage components for regions specified in input_exploration_production_factors.csv
    Arguments:
         factors | {k: [v0, v1, vn], k: [v0, v1, vn]}
    Returns {'gdf': geodataframe, 'geoseries': geoseries, 'empty': boolean}
    """
    gdf_list = []
    columns_missing_log = False
    regions_missing_log = False
    columns_missing = set()
    regions_missing = set()

    for n, r in enumerate(factors['region']):
        # Extract region's geodataframe or assign a blank geodataframe
        column = factors['geopackage_region_column'][n]
        if column in geodataframe.columns:
            gdf = geodataframe[geodataframe[column].isin([r])]
            if gdf.empty:
                regions_missing_log = True
        else:
            gdf = gpd.GeoDataFrame(geometry=gpd.GeoSeries(), crs=geodataframe.crs)  # Blank geodataframe
            columns_missing_log = True
            columns_missing.update(column)

        if gdf.empty:
            regions_missing.update(r)
            gdf_dict = {'gdf': gdf,
                        'geoseries': None,
                        'empty': True}
        else:
            # Combine geodataframe indices if multiple
            if len(gdf) > 1:
                region = gdf.unary_all()
            else:
                region = gdf.geometry.iloc[0]
            if simplify:
                # Simplify the geometry to speed up point containment check
                region = region.simplify(tolerance=0.01, preserve_topology=True)

            region_geoseries = gpd.GeoSeries([region])

            gdf_dict = {'gdf': gdf,
                        'geoseries': region_geoseries,
                        'empty': False}
        gdf_list.append(gdf_dict)

    if log_path is not None:
        if columns_missing_log:
            export_log('+++ Failed to map GEOPACKAGE_REGION_COLUMN value(s) in input_exploration_production_factors.csv to column headers in input_geopackage.gpkg\n'
                       '---See log file for list of missing column headers\n', output_path=log_path, print_on=True)
            export_log(f'Column(s) Missing: {columns_missing}', output_path=log_path, print_on=False)
        if regions_missing_log:
            export_log('+++ Failed to map region(s) in input_exploration_production_factors.csv to input_geopackage.gpkg\n'
                       '---See log file for list of regions\n', output_path=log_path, print_on=True)
            export_log(f'Region(s) Missing: {regions_missing}', output_path=log_path, print_on=False)
        if columns_missing_log and regions_missing_log:
            export_log("Note that some (but not necessarily all) missing regions may be caused by the missing columns.", output_path=log_path, print_on=True)
        if columns_missing_log or regions_missing_log:
            export_log('+++Coordinates for greenfield discoveries in associated regions will not be assigned.\n'
                       '+++Coordinates missing in input_projects.csv in associated regions will not be assigned.', output_path=log_path, print_on=True)

    return gdf_list


def generate_region_coordinate(gdf_dict):
    """
    Generates a region coordinate within polygons of a geoseries and returns latitude and longitude coordinates
    as decimal degrees.

    Parameters:
    - gdf_dict: A dictionary containing {'empty': bool, 'geoseries': gpd.Geoseries}

    Returns:
    - (float, float): Latitude and longitude coordinates as decimal degrees.
      Returns (None, None) if the region is empty or invalid.
    """
    if gdf_dict['empty']:
        return None, None

    # Generate a random point within the polygon using sample_points()
    random_point = gdf_dict['geoseries'].sample_points(1).iloc[0]

    # Return latitude and longitude as decimal degrees
    return random_point.y, random_point.x

def deduplicate_columns(columns):
    """
    Deduplicate column names by appending a suffix when a duplicate is found.
    Ensures column names are unique within the DataFrame.
    """
    seen = {}
    for i, col in enumerate(columns):
        if col in seen:
            seen[col] += 1
            columns[i] = f"{col}_{seen[col]}"
        else:
            seen[col] = 0
    return columns

# [BM] The following function was written to remove the geopackage generation from the iteration loop and out to the post-processing loop
# It reads from the scenarios/iterations and generates 1 geopackage per Scenario (e.g. Decoupling). This geopackage will have j layers, where j is the number of iterations.
# Each layer (j) will have a cloud of points respective to the Projects (i)

def save_scenario_geopackage(geodataframe, scenario_folders):
    """
    Creates and saves an OGC geopackage for each scenario (i) with data from all iterations (j) combined.

    Files written: [scenario_folder]/_geopackage.gpkg

    Parameters:
    - geodataframe (GeoDataFrame or None): The original GeoDataFrame from the input_geopackage.gpkg. Can be None.
    - scenario_folders (list): List of paths to scenario folders.
    """
    import warnings
    warnings.filterwarnings('ignore', 'GeoSeries.notna', UserWarning)

    output_paths = []

    for j, scenario_folder in enumerate(scenario_folders):
        all_points_gdfs = []

        # Convert the generator to a list to iterate over and get the length if needed
        project_files = list(scenario_folder.glob('*-Projects.csv'))

        for i, projects_csv_path in enumerate(project_files):
            # Load the i-Projects.csv for this iteration
            projects_df = pd.read_csv(projects_csv_path)

            # Create GeoDataFrame from the CSV data
            geometry = [Point(xy) for xy in zip(projects_df['LONGITUDE'], projects_df['LATITUDE'])]
            projects_gdf = gpd.GeoDataFrame(projects_df, geometry=geometry)

            # Set CRS to match the input shapefile if provided
            if geodataframe is not None:
                projects_gdf.set_crs(geodataframe.crs, inplace=True)
            else:
                projects_gdf.set_crs("EPSG:4326", inplace=True)  # Default CRS (WGS 84)

            # Add an iteration column to distinguish between different iterations
            projects_gdf['iteration'] = i

            # Add this GeoDataFrame to the list
            all_points_gdfs.append(projects_gdf)

        # Combine all the points from different iterations into a single GeoDataFrame
        combined_gdf = gpd.GeoDataFrame(pd.concat(all_points_gdfs, ignore_index=True))

        # Deduplicate column names to ensure uniqueness
        combined_gdf.columns = deduplicate_columns(combined_gdf.columns.to_list())

        # Define the output path for the OGC GeoPackage
        output_geopackage_path = scenario_folder / f'_geopackage.gpkg'

        # Save the geopackage
        try:
            combined_gdf.to_file(output_geopackage_path)
            output_paths.append(output_geopackage_path)
        except Exception as e:
            print(f"Failed to save geopackage for scenario {j}: {e}")

    return output_paths
