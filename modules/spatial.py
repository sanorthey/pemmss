"""
Module with functions for handling spatial data
"""
# Import standard packages

# Import non-standard packages
import geopandas as gpd
import pandas as pd
import charset_normalizer
import warnings
from concurrent.futures import ThreadPoolExecutor, as_completed

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
            columns_missing.add(column)

        if gdf.empty:
            regions_missing.add(r)
            gdf_dict = {'gdf': gdf,
                        'geoseries': None,
                        'empty': True}
        else:
            # Combine geodataframe indices if multiple
            if len(gdf) > 1:
                region = gdf.union_all()
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


# [BM] The following function was written to remove the geopackage generation from the iteration loop and out to the post-processing loop
# It reads from the scenarios/iterations and generates 1 geopackage per Scenario (e.g. Decoupling). This geopackage will have j layers, where j is the number of iterations.
# Each layer (j) will have a cloud of points respective to the Projects (i)

def detect_encoding(filepath):
    with open(filepath, 'rb') as f:
        raw = f.read()
        result = charset_normalizer.detect(raw)
        encoding = result['encoding']
        return encoding

def deduplicate_columns(columns):
    """
    Return a new list of column names with duplicates suffixed (e.g., 'col', 'col_1', 'col_2', ...).
    """
    seen = {}
    deduped = []

    for col in columns:
        count = seen.get(col, 0)
        if count:
            new_col = f"{col}_{count}"
        else:
            new_col = col
        deduped.append(new_col)
        seen[col] = count + 1

    return deduped


def process_scenario_folder(j, scenario_folder, geodataframe):
    """
    Processes project CSV files in a scenario folder into a combined GeoDataFrame.

    Reads all '*-Projects.csv' files, converts coordinate data to geometries, and combines them.
    Saves the result as a GeoPackage in the scenario folder.

    Args:
        j (int): Index of the scenario (unused but passed in).
        scenario_folder (Path): Path to the scenario directory containing CSV files.
        geodataframe (GeoDataFrame): Reference GeoDataFrame for CRS alignment.

    Returns:
        Path or None: Path to the saved GeoPackage file, or None if processing fails.
    """

    all_points = []
    project_files = list(scenario_folder.glob('*-Projects.csv'))

    for i, csv_path in enumerate(project_files):
        try:
            encoding = detect_encoding(csv_path)
            df = pd.read_csv(csv_path, encoding=encoding, low_memory=False)

            # Drop rows missing coordinates
            df = df.dropna(subset=['LONGITUDE', 'LATITUDE'])

            if df.empty:
                continue

            geometry = gpd.points_from_xy(df['LONGITUDE'], df['LATITUDE'], crs="EPSG:4326")
            gdf = gpd.GeoDataFrame(df, geometry=geometry)

            if geodataframe is not None:
                gdf = gdf.set_crs(geodataframe.crs, allow_override=True)

            gdf['iteration'] = i
            all_points.append(gdf)

        except Exception as e:
            print(f"[WARN] Error processing {csv_path.name}: {e}")

    if not all_points:
        return None

    combined = pd.concat(all_points, ignore_index=True)
    combined.columns = deduplicate_columns(combined.columns.tolist())
    combined_gdf = gpd.GeoDataFrame(combined, geometry='geometry')

    out_path = scenario_folder / '_geopackage.gpkg'
    try:
        combined_gdf.to_file(out_path)
        return out_path
    except Exception as e:
        print(f"[ERROR] Failed to save {out_path.name}: {e}")
        return None


def save_scenario_geopackage(geodataframe, scenario_folders, max_workers=4):
    """
    Processes multiple scenario folders in parallel and saves their GeoPackages.

    Uses a thread pool to run `process_scenario_folder` for each scenario folder concurrently.

    Args:
        geodataframe (GeoDataFrame): Reference GeoDataFrame for CRS alignment.
        scenario_folders (List[Path]): List of scenario folder paths to process.
        max_workers (int, optional): Maximum number of parallel threads. Defaults to 4.

    Returns:
        List[Path]: List of paths to successfully saved GeoPackage files.
    """

    warnings.filterwarnings('ignore', 'GeoSeries.notna', UserWarning)
    output_paths = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(process_scenario_folder, j, folder, geodataframe): folder
            for j, folder in enumerate(scenario_folders)
        }
        for future in as_completed(futures):
            result = future.result()
            if result:
                output_paths.append(result)
    return output_paths
