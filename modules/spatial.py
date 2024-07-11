"""
Module with functions for handling spatial data
"""
import geopandas as gpd
from shapely.geometry import Point
import random

def import_shapefile(shapefile_path):
    """
    Reads a shapefile (.shp) at 'shapefile_path' and returns a geopandas dataframe
    """

    # Load the shapefile
    gdf = gpd.read_file(shapefile_path)
    return gdf

def generate_region_coordinate(shapefile_gdf, region_label, region_value, method='midpoint'):
    """
    Selects a region from a shapefile and generates latitude and longitude coordinates as decimal degrees.

    Parameters:
    - shapefile_gdf (geopandas dataframe)
    - region_label (str): The attribute used to identify the region (e.g., a column name).
    - region_value (str): The value of the region_label to filter the desired region.
    - method (str): 'midpoint' to return the spatial midpoint, 'random' to return a random coordinate within the region.

    Returns:
    - (float, float): Latitude and longitude coordinates as decimal degrees.

    Example use:
    lat, lon = get_region_coordinate(shapefile_path, region_label, region_value, method)
    """

    # Select the region based on the provided label and value
    region = shapefile_gdf[shapefile_gdf[region_label] == region_value]

    if region.empty:
        raise ValueError(f"No region found with {region_label} = {region_value}")

    # Ensure the region is in a single geometry
    region = region.unary_union

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
                return random_point.y, random_point.x
    else:
        raise ValueError("Method must be 'midpoint' or 'random'")



