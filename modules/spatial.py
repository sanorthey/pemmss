"""
Module with functions for handling spatial data
"""
import geopandas as gpd
import pandas as pd
from shapely.geometry import Point
from shapely.ops import nearest_points
import random


def import_geopackage(path):
    """
    Reads a geopackage (.shp) at 'shapefile_path' and returns a geopandas dataframe
    """
    try:
        # Load the shapefile
        gdf = gpd.read_file(path)
        return gdf
    except Exception as e:
        print(f"Failed to load shapefile: {e}")
        return None

def generate_region_coordinate(geodataframe, region_label, region_value, method='random', log_path='None'):
    """
    Selects a region from a shapefile and generates latitude and longitude coordinates as decimal degrees.

    Parameters:
    - geodataframe (geopandas dataframe): The GeoDataFrame containing the geopackage data.
    - region_label (str): The attribute used to identify the region (e.g., a column name such as REGION).
    - region_value (str): The value of the region_label to filter the desired region (e.g. 'Region 1', or 'Chile', or 'Asia').
    - method (str): 'midpoint' to return the spatial midpoint, 'random' to return a random coordinate within the region.

    Returns:
    - (float, float): Latitude and longitude coordinates as decimal degrees. Returns (None, None) if region_label or region_value not in geodataframe.

    Example use:
    lat, lon = generate_region_coordinate(shapefile_gdf, region_label, region_value, method)
    """

    if region_label not in geodataframe:
        return None, None

    # Select the region based on the provided label and value
    region = geodataframe[geodataframe[region_label] == region_value]

    if region.empty:
        return None, None

    # Ensure the region is in a single geometry
    if len(region) > 1:
        region = region.unary_union
    else:
        region = region.geometry.iloc[0]

    if method == 'midpoint':
        # Calculate the centroid (midpoint)
        centroid = region.centroid
        return centroid.y, centroid.x
    elif method == 'random':
        # Generate a random point strictly within the polygon
        minx, miny, maxx, maxy = region.bounds
        while True:
            random_point = Point(random.uniform(minx, maxx), random.uniform(miny, maxy))
            if region.contains(random_point):
                return random_point.y, random_point.x
    elif method == 'centroid_within':
        # Calculate the centroid
        centroid = region.centroid
        if region.contains(centroid):
            return centroid.y, centroid.x
        else:
            # Find the nearest point within the polygon
            nearest_point = nearest_points(region, centroid)[0]
            return nearest_point.y, nearest_point.x
    else:
        raise ValueError("Method must be 'midpoint', 'random', or 'centroid_within'")


# [BM] The following function was written to remove the save_project_as_shapefile from the iteration loop, and out to the post-processing loop
# It reads from the scenarios/iterations and generates 1 shapefile per Scenario (e.g. Decoupling). This shapefile will have j layers, where j is the number of iterations.
# Each layer (j) will have a cloud of points respective to the Projects (i)

def deduplicate_columns(columns):
    """
    Deduplicate column names by appending a suffix when a duplicate is found.
    Ensures column names are unique within the DataFrame.
    """
    seen = {}
    for i, col in enumerate(columns):
        if col in seen:
            seen[col] += 1
            columns[i] = f"{col[:9]}_{seen[col]}"  # Keep names within 10 characters
        else:
            seen[col] = 0
    return columns

def save_scenario_geopackage(shapefile_gdf, scenario_folders):
    """
    Creates and saves an OGC geopackage for each scenario with data from all iterations combined.

    Files written: [scenario_folder]/_geopackage.gpkg

    Parameters:
    - shapefile_gdf (GeoDataFrame or None): The original GeoDataFrame from the shapefile. Can be None.
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
            if shapefile_gdf is not None:
                projects_gdf.set_crs(shapefile_gdf.crs, inplace=True)
            else:
                projects_gdf.set_crs("EPSG:4326", inplace=True)  # Default CRS (WGS 84)

            # Add an iteration column to distinguish between different iterations
            projects_gdf['iteration'] = i

            # Add this GeoDataFrame to the list
            all_points_gdfs.append(projects_gdf)

        # Combine all the points from different iterations into a single GeoDataFrame
        combined_gdf = gpd.GeoDataFrame(pd.concat(all_points_gdfs, ignore_index=True))

        # Deduplicate column names to ensure uniqueness and keep them within 10 characters
        combined_gdf.columns = deduplicate_columns(combined_gdf.columns.to_list())

        # Define the output path for the OGC GeoPackage
        output_geopackage_path = scenario_folder / f'_geopackage.gpkg'

        # Save the shapefile
        try:
            combined_gdf.to_file(output_geopackage_path)
            output_paths.append(output_geopackage_path)
        except Exception as e:
            print(f"Failed to save geopackage for scenario {j}: {e}")

    return output_paths