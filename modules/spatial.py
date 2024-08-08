"""
Module with functions for handling spatial data
"""
import geopandas as gpd
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
                print(f"Got random coordinates for {region_value}: {random_point.y}, {random_point.x}")
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

## TBD -> [BM] Add function to generate shapefile from outputs