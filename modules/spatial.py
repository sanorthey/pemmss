"""
Module with functions for handling spatial data
"""
import geopandas as gpd
import pandas as pd
from shapely.geometry import Point
from shapely.ops import nearest_points
import random

def import_shapefile(shapefile_path):
    """
    Reads a shapefile (.shp) at 'shapefile_path' and returns a geopandas dataframe
    """

    # Load the shapefile
    gdf = gpd.read_file(shapefile_path)
    return gdf

def generate_region_coordinate(shapefile_gdf, region_label, region_value, method='random'):
    """
    Selects a region from a shapefile and generates latitude and longitude coordinates as decimal degrees.

    Parameters:
    - shapefile_gdf (geopandas dataframe): The GeoDataFrame containing the shapefile data.
    - region_label (str): The attribute used to identify the region (e.g., a column name such as REGION).
    - region_value (str): The value of the region_label to filter the desired region (e.g. 'Region 1', or 'Chile', or 'Asia').
    - method (str): 'midpoint' to return the spatial midpoint, 'random' to return a random coordinate within the region.

    Returns:
    - (float, float): Latitude and longitude coordinates as decimal degrees.

    Example use:
    lat, lon = generate_region_coordinate(shapefile_gdf, region_label, region_value, method)
    """

    # Debug print statements
    ##print(f"Columns in GeoDataFrame: {shapefile_gdf.columns}")
    ##print(f"Unique values in {region_label}: {shapefile_gdf[region_label].unique()}")
    ##print(f"Looking for region_label: {region_label}")
    ##print(f"Looking for region_value: {region_value}")

    # Select the region based on the provided label and value
    region = shapefile_gdf[shapefile_gdf[region_label] == region_value]

    if region.empty:
        raise ValueError(f"No region found with {region_label} = {region_value}")

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
        # Generate a random point within the region's bounds
        minx, miny, maxx, maxy = region.bounds
        while True:
            random_point = Point(random.uniform(minx, maxx), random.uniform(miny, maxy))
            if region.contains(random_point):
                # [BM] Was debugging with the following:
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


def add_coordinates_to_gdf(gdf, region_label,method='random'):
    """
    Adds random latitude and longitude coordinates to each polygon/multipolygon in a GeoDataFrame.

    Parameters:
    - gdf (geopandas.GeoDataFrame): The GeoDataFrame containing the polygons.
    - region_label (str): The attribute used to identify the region (e.g., a column name).

    Returns:
    - gdf (geopandas.GeoDataFrame): The GeoDataFrame with new latitude and longitude columns.
    """
    latitudes = []
    longitudes = []

    for _, row in gdf.iterrows():
        latitude, longitude = generate_region_coordinate(gdf, region_label, row[region_label], method)
        latitudes.append(latitude)
        longitudes.append(longitude)

    gdf['latitude'] = latitudes
    gdf['longitude'] = longitudes

    return gdf

def add_geometry_to_projects(projects, shapefile_gdf):
    """
    Creates a shapefile for the given iteration from a list of Mine objects.
    
    Parameters:
    - projects: List of Mine objects.
    - shapefile_gdf: GeoDataFrame containing the original shapefile with polygon data.
    - output_folder_scenario: Path to the folder where outputs will be saved.
    - iteration_index: Current iteration index (used for naming the shapefile).
    """
    # Step 1: Extract data from Mine objects into a list of dictionaries

    # [BM] Added automatic method with slots and get attributes:
    project_data = []
    for project in projects:
        project_dict = {slot: getattr(project, slot) for slot in project.__slots__}
        project_data.append(project_dict)

    # Step 2: Convert the list of dictionaries into a DataFrame
    projects_df = pd.DataFrame(project_data)

    # Step 3: Initialize a new column in projects_df to store geometry
    projects_df['geometry'] = None

    # Step 4: Loop through each row in projects_df
    for idx, project_row in projects_df.iterrows():
        region = project_row['region']  # Get the region for the current project
        
        # Step 3: Find the corresponding row in shapefile_gdf
        matching_row = shapefile_gdf[shapefile_gdf['REGION_1'] == region]
        
        if not matching_row.empty:
            # Step 4: Assign the geometry from shapefile_gdf to the corresponding row in projects_df
            projects_df.at[idx, 'geometry'] = matching_row.iloc[0]['geometry']
        else:
            print(f"Warning: No matching region found for project {project_row['name']} with region {region}")
    return projects_df

def save_projects_as_shapefile(projects_with_geometry, output_path_shapefile):
    """
    Saves the projects DataFrame with geometry as a shapefile.
    
    Parameters:
    - projects_with_geometry: DataFrame with project data and geometry.
    - output_path_shapefile: Path to save the shapefile.
    """

    # Convert the projects DataFrame to a GeoDataFrame
    projects_gdf = gpd.GeoDataFrame(projects_with_geometry, geometry='geometry', crs="EPSG:4326")

    # Save the GeoDataFrame as a shapefile
    projects_gdf.to_file(output_path_shapefile)