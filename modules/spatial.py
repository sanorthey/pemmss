"""
Module with functions for handling spatial data
"""
import geopandas as gpd
import pandas as pd
from shapely.geometry import Point
from shapely.strtree import STRtree  # Spatial index for faster querying
from shapely.prepared import prep
import random


def import_geopackage(path):
    """
    Reads a geopackage (.shp) at 'path' and returns a geopandas dataframe
    """
    try:
        # Load the geopackage
        gdf = gpd.read_file(path)
        return gdf
    except Exception as e:
        print(f"Failed to load geopackage: {e}")
        return None

def gdf_region_preprocess(geodataframe, simplify=False):

    if geodataframe is None:
        gdf_dict = {'gdf': None,
                    'gdf_simplified': None,
                    'spatial_index': None,
                    'minx': None,
                    'miny': None,
                    'maxx': None,
                    'maxy': None,
                    'empty': True}
    elif geodataframe.empty:
        gdf_dict = {'gdf': geodataframe,
                    'gdf_simplified': geodataframe,
                    'spatial_index': None,
                    'minx': None,
                    'miny': None,
                    'maxx': None,
                    'maxy': None,
                    'empty': True}
    else:
        if len(geodataframe) > 1:
            region = geodataframe.unary_union
        else:
            region = geodataframe.geometry.iloc[0]

        if simplify:
            # Simplify the geometry to speed up point containment check (optional)
            # Defaulting to False as prepared_region conversion seems to be sufficient with test datasets
            simplified_region = region.simplify(tolerance=0.001, preserve_topology=True)
        else:
            simplified_region = region

        # Build a spatial index to reduce the number of containment checks
        spatial_index = STRtree([simplified_region])

        # Generate region bounds
        minx, miny, maxx, maxy = region.bounds

        gdf_dict = {'gdf': geodataframe,
                    'gdf_simplified': simplified_region,
                    'spatial_index': spatial_index,
                    'minx': minx,
                    'miny': miny,
                    'maxx': maxx,
                    'maxy': maxy,
                    'empty': False}

    return gdf_dict

def prepare_gdf(gdf_dict):
    # For use in pemmss.scenario() as prepared regions can't be pickled, so don't work with multiprocessing or deepcopy
    # Prepare the region to enable faster, cached containment checks
    return_list = []
    for i in gdf_dict:
        prepared_region = prep(i['gdf_simplified'])
        return_list.append(prepared_region)

    return return_list

def generate_region_coordinate(gdf_dict, gdf_prepared):
    """
    Generates a region coordinate within polygons of a geodataframe and generates latitude and longitude coordinates as decimal degrees. This will typically be filtered prior to this function call.

    Parameters:
    - gdf_dict containing a geodatabase and preprocessed spatial_index (STRtree), bounds

    Returns:
    - (float, float): Latitude and longitude coordinates as decimal degrees. Returns (None, None) if region_label or region_value not in geodataframe.

    Example use:
    lat, lon = generate_region_coordinate(geodataframe, region_label, region_value, method)
    """
    if gdf_dict['empty']:
        return None, None
    else:
        prepared_region = gdf_prepared
        spatial_index = gdf_dict['spatial_index']
        minx = gdf_dict['minx']
        miny = gdf_dict['miny']
        maxx = gdf_dict['maxx']
        maxy = gdf_dict['maxy']

        # Try generating a random point within the bounds
        # for _ in range(100):  # Reduce the number of attempts if needed
        while True:
            random_point = Point(random.uniform(minx, maxx), random.uniform(miny, maxy))

            # Only check if the point is within the polygon using the spatial index
            if any(prepared_region.contains(random_point) for r in spatial_index.query(random_point)):
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
