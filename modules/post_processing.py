"""
Module with routines for post_processing of results data.
    merge_scenarios()
    generate_figure()
    filter_statistics()
    filter_key_tuple()
    _include_key()
    plot_subplot()
    plot_subplot_generator()
    generate_stackplot()
    generate_scatter()
    generate_line()
    generate_fill()
    series_modify()
    label_format()
    build_plot_subplot_label_xy_data()
    build_plot_key()
"""

# Import standard packages
from math import ceil
from collections import defaultdict, Counter
from random import choice
from itertools import islice
from pathlib import Path

# Import external packages
import matplotlib
import matplotlib.pyplot as plt
from numpy import nan
import numpy as np
import imageio
import pandas as pd
import polars as pl

# Import custom modules

from modules.file_export import export_plot_subplot_data
from modules.file_import import import_statistics


def merge_scenarios(imported_postprocessing, scenario_folders, output_stats_folder):
    """
    merge_scenarios()
    # Merges scenario statistics.csv files and outputs as individual statistic csv files in a new folder
    imported_postprocessing | {s: statistic:}
    scenario_folders =
    output_stats_folder =

    """
    updated_postprocessing = imported_postprocessing

    filter_columns = ["STATISTIC" for s in updated_postprocessing]
    filter_keys = [[s] for s in updated_postprocessing]
    key_output_filepath_dict = combine_csv_files(scenario_folders, output_stats_folder, filter_columns, filter_keys, filenameend="_statistics.csv")
    for s, path in key_output_filepath_dict.items():
        updated_postprocessing[s[0]].update({'path': path})  #s [0] because s is a tuple (s,) with an extra, empty element. Should really fix this up.

    return updated_postprocessing


def combine_csv_files(input_dirs, output_dir, filter_columns, filter_keys, filenameend="statistics.csv", chunksize=100000):
    """
    Combines CSV files from multiple directories based on filter keys and saves the filtered data into separate CSV files.

    Args:
        input_dirs (list): List of input directories containing CSV files.
        output_dir (str): Output directory to save the generated CSV files.
        filter_columns (list): List of column names to filter on.
        filter_keys (list): List of filter key combinations.
        filenameend (str, optional): Ending of the input CSV filenames. Defaults to "statistics.csv".
        chunksize (int, optional): Number of csv lines read and processed at once. Defaults to 100,000.

    Returns:
        dict: {key, filepath} Dictionary containing the filter keys and corresponding paths of the generated CSV files.
    """
    key_path_dict = {}

    for input_dir in input_dirs:
        for entry in Path(input_dir).iterdir():
            if entry.name.endswith(filenameend) and entry.is_file():
                file_path = entry

                df_chunks = pd.read_csv(file_path, chunksize=chunksize)
                for chunk in df_chunks:
                    for keys in filter_keys:
                        filters = [chunk[column] == key for column, key in zip(filter_columns, keys)]
                        filtered_chunk = chunk[np.logical_and.reduce(filters)]

                        if tuple(keys) not in key_path_dict:
                            output_file = "_".join(keys) + ".csv"
                            output_path = Path(output_dir) / output_file

                            filtered_chunk.to_csv(output_path, index=False)
                            key_path_dict[tuple(keys)] = output_path
                        else:
                            output_path = key_path_dict[tuple(keys)]
                            filtered_chunk.to_csv(output_path, mode='a', header=False, index=False)

    return key_path_dict


def project_iteration_statistics(directories):
    """
    Generates and outputs project iteration statistics for each demand scenario directory.

    returns {demand scenario directory: {'status': filepath}}
    """
    filepath_nested_dict = {}

    int_labels = {
        -3: 'Development Probability Test Failed',
        -2: 'Not Valuable Enough to Mine',
        -1: 'Depleted',
        0: 'Undeveloped',
        1: 'Care and Maintenance',
        2: 'Producing',
        3: 'Produced and Depleted'
    }
    nan_label = 'Undiscovered'

    for d in directories:
        status_filepath = count_iteration_frequencies(
            d,
            int_labels=int_labels,
            nan_label=nan_label
        )
        filepath_nested_dict[d] = {'status': status_filepath}

    return filepath_nested_dict


def count_iteration_frequencies(directory, file_pattern="*-Status.csv", output_file="_status.csv",
                               id_vars='P_ID_NUMBER', label='STATUS', int_labels={}, nan_label='Missing'):
    """
    Count the frequency of each integer for each ID at each point in time across all files matching the pattern in the directory.

    Args:
        directory (str or Path): Directory path containing CSV files.
        file_pattern (str): Pattern to match input CSV files.
        output_file (str): Filename for output CSV.
        id_vars (str): ID column name.
        label (str): Status/label column name.
        int_labels (dict): Mapping of int values to descriptive labels.
        nan_label (str): Label for missing/NaN values.

    Returns:
        Path: Path to the output CSV file.
    """
    directory = Path(directory)
    output_filepath = directory / output_file

    # Collect melted DataFrames for all matching files
    dfs = []
    for filepath in directory.glob(file_pattern):
        df = pl.read_csv(filepath)
        time_cols = [col for col in df.columns if col != id_vars]
        melted = df.melt(id_vars=id_vars, value_vars=time_cols, variable_name="Time", value_name=label)
        dfs.append(melted)

    if not dfs:
        # No matching files, return path anyway
        return output_filepath

    full_df = pl.concat(dfs)

    # Count frequency of each value per ID and Time
    freq_df = (
        full_df
        .group_by([id_vars, "Time", label])
        .agg(pl.count().alias("Count"))
    )

    # Ensure label column is Int64 for mapping
    freq_df = freq_df.with_columns([
        pl.col(label).cast(pl.Int64).alias(label)
    ])

    # Map integer labels and handle missing with chained when-then-otherwise
    freq_df = freq_df.with_columns(
        pl.when(pl.col(label).is_null()).then(pl.lit(nan_label))
        .when(pl.col(label) == -3).then(pl.lit(int_labels.get(-3)))
        .when(pl.col(label) == -2).then(pl.lit(int_labels.get(-2)))
        .when(pl.col(label) == -1).then(pl.lit(int_labels.get(-1)))
        .when(pl.col(label) == 0).then(pl.lit(int_labels.get(0)))
        .when(pl.col(label) == 1).then(pl.lit(int_labels.get(1)))
        .when(pl.col(label) == 2).then(pl.lit(int_labels.get(2)))
        .when(pl.col(label) == 3).then(pl.lit(int_labels.get(3)))
        .otherwise(pl.col(label).cast(pl.Utf8))
        .alias(label)
    )

    # Pivot to wide format: each Time is a column
    pivot_df = freq_df.pivot(
        values="Count",
        index=[id_vars, label],
        columns="Time"
    )

    # Write to CSV
    pivot_df.write_csv(output_filepath)

    return output_filepath


def generate_figure(statistics_files, graph, graph_formatting, output_folder):
    """
    post_processing.generate_figure(statistics_files, graph, output_graphs_folder)
    graph = {'file_prefix', 'plot_algorithm', 'subplot_type', 'i_keys, 'j_keys', 'a_keys', 'r_keys', 'd_keys', 'c_keys',
                s_keys', 't_keys': -1, 'labels_on', 'include_all', 'share_scale', 'y_axis_label', 'cumulative', 'columns'}
    graph_formatting = {label: {'legend_text': val, 'legend_suppress': val, 'color':val, 'alpha': val, 'fill_alpha': val:, 'marker':, 'size':, 'linewidth': value, 'linestyle':value, '}}
    returns a path to the output figure
    """
    g_statistics = {}

    output_path = str()

    # Import required .csv files
    for s, s_dict in statistics_files.items():
        if s in graph['s_keys']:
            g_statistics.update(import_statistics(s_dict['path'], convert_values=True))

    # Filter statistics
    filtered_data = filter_statistics(g_statistics, graph)

    # Execute plot algorithm
    if graph['plot_algorithm'] == 'plot_subplot_default':
        output_path = plot_subplot(filtered_data, output_folder, graph, graph_formatting)

    return output_path


def filter_statistics(statistics, g):
    """
    Will filter and include any statistics matching the key lists defined in g.
    g keys            | 'i_keys', 'j_keys', 'a_keys', 'r_keys', 'd_keys', 'c_keys', 's_keys', 't_keys'
    g possible values | True = include any key except 'ALL'
                      | False = only include key if 'ALL'
                      | [k1, k2, k3, etc.] = return any statistic matching listed keys
    Returns {(i, j, a, r, d, c, s): {t: val}}
    """
    i_keys, j_keys, a_keys, r_keys, d_keys, c_keys, s_keys, t_keys = \
        (g['i_keys'], g['j_keys'], g['a_keys'], g['r_keys'], g['d_keys'], g['c_keys'], g['s_keys'], g['t_keys'])

    filtered_statistics = {
        key: statistics[key]
        for key in statistics
        if filter_key_tuple(key, i_keys, j_keys, a_keys, r_keys, d_keys, c_keys, s_keys)
    }

    return filtered_statistics


def filter_key_tuple(key, i_keys, j_keys, a_keys, r_keys, d_keys, c_keys, s_keys):
    """
    Checks if key (i,j,a,r,d,c) included in keys.
    Returns True if key included or False if key excluded
    """
    i, j, a, r, d, c, s = key

    return all(_include_key(value, keys) for value, keys in [(i, i_keys),
                                                             (j, j_keys),
                                                             (a, a_keys),
                                                             (r, r_keys),
                                                             (d, d_keys),
                                                             (c, c_keys),
                                                             (s, s_keys)])


def _include_key(key, include_keys):
    """
    Returns True if key included or False if key excluded

    include_keys | True = include any key except 'ALL'
                | False = only include key if 'ALL'
                | [k1, k2] =  return any

    Returns | True, include key
            | False, exclude key
    """
    if include_keys is True:
        return key != 'ALL'
    elif include_keys is False:
        return key == 'ALL'
    else:
        return key in include_keys


def plot_subplot(statistics, path, g, g_formatting):
    """
    Generates multiple plots with subplots based on figure data defined in input_graphs.csv and input_graphs_formatting.csv

    Returns list of figure and figure data file paths.
    """

    file_prefix = g['file_prefix']
    plot_keys = g['plot_keys']
    subplot_keys = g['subplot_keys']
    labels_on = g['labels_on']
    subplot_type = g['subplot_type']
    share_scale = g['share_scale']
    y_axis_label = g['y_axis_label']
    y_scale_set = g['y_scale_set']
    cumulative = g['cumulative']
    columns = g['columns']
    gif = g['gif']
    fps = g['gif_fps']
    delete_frames = g['gif_delete_frames']

    # Build x, y and labels of format
    plot_subplot_label_xy_data = build_plot_subplot_label_xy_data(statistics, plot_keys, subplot_keys, labels_on)

    # Generate plot path holder
    plot_paths = []
    plot_data_paths = []

    # Assign plot directory or create a directory for holding gif frames
    plot_folder_path = path
    if gif:
        plot_folder_path = path / ('_' + file_prefix)
        plot_folder_path.mkdir()

    # Generate plots
    for plot, subplots in plot_subplot_label_xy_data.items():
        # Generate plot title
        title = ''.join(plot)

        # Generate subplot panels
        num_subplots = len(subplots)
        h_panels = ceil(num_subplots / columns)
        v_panels = ceil(num_subplots / h_panels)

        # Generate y labels
        y_label = y_axis_label if y_axis_label else str(plot).capitalize()

        # Generate file paths
        output_filepath = plot_folder_path / f'_{file_prefix}-{plot}.png'
        output_filepath_data = plot_folder_path / f'_{file_prefix}-{plot}.png.csv'

        fig_path, fig_data = plot_subplot_generator(output_filepath, str(title), subplots, h_panels, v_panels, subplot_type, share_scale, y_label, y_scale_set, cumulative, g_formatting)
        plot_paths.append(fig_path)
        export_plot_subplot_data(output_filepath_data, fig_data)
        plot_data_paths.append(output_filepath_data)

    # Generate GIF
    if gif:
        gif_filepath = path / f'_{file_prefix}.gif'
        plot_paths = generate_gif(plot_paths, gif_filepath, fps=fps, delete_frames=delete_frames)

    # Generate final returned output paths list
    output_paths = plot_paths + plot_data_paths

    return output_paths


def plot_subplot_generator(output_filename, title, plot, h_panels, v_panels, plot_type, share_scale, y_axis_label, y_scale_set, cumulative, g_formatting):
    """
    Returns a plot with an arbitrary number of subplots.
    plot_type can equal 'stacked', 'scatter', 'line', 'fill', 'fill_line'

    x | for stacked plots x[0] should equal any x[any]
    """
    matplotlib.use('Agg')  # Using this backend to avoid a memory leak when using fig.savefig for subplots without a show()

    # Plot text formatting
    TEXT_SIZE_DEFAULT = 7
    TEXT_SIZE_PLOT_TITLE = 10
    TEXT_SIZE_SUBPLOT_TITLE = 7
    TEXT_SIZE_LEGEND = 7
    TEXT_SIZE_X_Y = 7

    plt.rc('font', size=7)  # controls default text sizes
    plt.rc('axes', titlesize=TEXT_SIZE_SUBPLOT_TITLE)  # fontsize of the axes title
    plt.rc('axes', labelsize=TEXT_SIZE_X_Y)  # fontsize of the x and y labels
    plt.rc('xtick', labelsize=TEXT_SIZE_X_Y)  # fontsize of the tick labels
    plt.rc('ytick', labelsize=TEXT_SIZE_X_Y)  # fontsize of the tick labels
    plt.rc('legend', fontsize=TEXT_SIZE_LEGEND)  # legend fontsize
    plt.rc('figure', titlesize=TEXT_SIZE_PLOT_TITLE)  # fontsize of the figure title

    # Generating plot with subplots
    if share_scale == True:
        # Subplots have common scale
        fig, ax = plt.subplots(h_panels, v_panels, figsize=(v_panels * 9/2.54, h_panels * 9/2.54), subplot_kw={'xmargin': 0, 'ymargin': 0}, sharey=True, sharex=True, squeeze=False)
    else:  # share_scale == False
        # Subplots have independent scales
        fig, ax = plt.subplots(h_panels, v_panels, figsize=(v_panels * 9/2.54, h_panels * 9/2.54), subplot_kw={'xmargin': 0, 'ymargin': 0}, sharey=False, sharex=False)

    # Create an iterator for the subplots (e.g. commodity keys)
    subplots = iter(sorted(plot))

    # Create a dictionary to store subplot coordinates
    subplot_coords = {(h, v): next(subplots, None) for h, v in
                      islice(((h, v) for h in range(h_panels) for v in range(v_panels)), h_panels * v_panels)}

    for (h, v), sp in subplot_coords.items():
        if sp is not None:
            data_height = []  # for use with stackplots
            for label, data in sorted(plot[sp].items()):
                l_format = label_format(label, g_formatting)
                data.update(l_format)
                data.update({'cumulative': cumulative})
                if plot_type == 'scatter':
                    data['y'] = series_modify(data['y'], cumulative)
                    generate_scatter(ax[h, v], data['x'], data['y'], l_format)
                elif plot_type == 'line':
                    data['y'] = series_modify(data['y'], cumulative)
                    generate_line(ax[h, v], data['x'], data['y'], l_format)
                elif plot_type == 'fill':
                    data['y'] = series_modify(data['y'], cumulative)
                    generate_fill(ax[h, v], data['x'], data['y'], l_format)
                elif plot_type == 'fill_line':
                    data['y'] = series_modify(data['y'], cumulative)
                    generate_fill(ax[h, v], data['x'], data['y'], l_format)
                    generate_line(ax[h, v], data['x'], data['y'], l_format, force_legend_suppress=True)
                elif plot_type == 'stacked':
                    data['y'] = series_modify(data['y'], cumulative, replace_none=float(0))
                    stacked_y, data_height = series_stack(data['y'], data_height)
                    generate_fill(ax[h, v], data['x'], stacked_y, l_format)
                # Format y axis scale, if set
                if y_scale_set != False:
                    ax[h, v].set_ylim([0, float(y_scale_set)])

            # Subplot formatting
            ax[h, v].legend(loc='upper left')
            title_text = g_formatting.get(sp, {}).get('title_text', sp)
            legend_suppress = g_formatting.get(sp, {}).get('legend_suppress', False)
            ax[h, v].set_title(title_text, pad=None) if not legend_suppress else None
            ax[h, v].set_ylabel(y_axis_label)
            ax[h, v].tick_params(labelbottom=1, labelleft=1)

        else:
            fig.delaxes(ax[h, v])

    # Final figure format
    if title in g_formatting:
        if g_formatting[title]['title_suppress'] is False:
            fig.suptitle(g_formatting[title]['title_text'])
    else:
        fig.suptitle(title)
    plt.tight_layout(rect=[0, 0, 1, 0.98])
    # Export file
    fig.savefig(fname=output_filename, dpi=300)
    plt.close('all')

    return output_filename, plot


def generate_stackplot(axis, x, y, l_format, force_legend_suppress=False):
    # Must rebuild y for stacked plot. [[y series 0],[y series 1]+[y series 0], etc.]
    # Note this needs debugging. Currently using generate_fill() instead.
    axis.stackplot(x[0], y, color=l_format['color'], alpha=l_format['fill_alpha'])  # Assumes all x series are the same.
    if l_format['legend_suppress'] is False and force_legend_suppress is False:
        axis.stackplot([], [], labels=[l_format['legend_text']], color=l_format['color'], alpha=l_format['fill_alpha'])


def generate_scatter(axis, x, y, l_format, force_legend_suppress=False):
    # Generate scatter plots for all series in this label
    for n, x_series in enumerate(x):
        axis.scatter(x_series, y[n], marker=l_format['marker'], s=l_format['size'], color=l_format['color'])
    if l_format['legend_suppress'] is False and force_legend_suppress is False:
        axis.scatter([], [], label=l_format['legend_text'], marker=l_format['marker'], s=l_format['size'], color=l_format['color'], alpha=l_format['alpha'])


def generate_line(axis, x, y, l_format, force_legend_suppress=False):
    # Generate line plots for all series in this label
    for n, x_series in enumerate(x):
        axis.plot(x_series, y[n], color=l_format['color'], linewidth=l_format['linewidth'],
                  linestyle=l_format['linestyle'], alpha=l_format['alpha'])
    if l_format['legend_suppress'] is False and force_legend_suppress is False:
        axis.plot([], [], label=l_format['legend_text'], color=l_format['color'])


def generate_fill(axis, x, y, l_format, force_legend_suppress=False):
    min_y = []
    max_y = []
    modified_x = []

    for i in range(len(y[0])):
        # Extract series y values and filter out None. Replace these with numpy nan to allow plotting breaks in series.
        y_list_for_x = [y_list[i] for y_list in y if y_list[i] is not None]

        if len(y_list_for_x) == 0:
            modified_x.append(nan)
            min_y.append(nan)
            max_y.append(nan)
        else:
            modified_x.append(x[0][i])
            min_y.append(min(y_list_for_x))
            max_y.append(max(y_list_for_x))

    axis.fill_between(modified_x, min_y, max_y, color=l_format['color'], alpha=l_format['fill_alpha'])
    if l_format['legend_suppress'] is False and force_legend_suppress is False:
        axis.fill([], [], label=l_format['legend_text'], color=l_format['color'], alpha=l_format['fill_alpha'])


def series_modify(data_series, cumulative=False, replace_none=False):
    modified_series = []
    for series_list in data_series:
        if cumulative:
            series_list = [0 if v is None else v for v in series_list]
            filtered_list = np.nan_to_num(series_list, nan=0.0) # Change None values to 0. Change nan values to 0.
            modified_series.append(np.cumsum(filtered_list).tolist())
        elif replace_none is not False:
            modified_series.append(np.where(np.array(series_list) == None, replace_none, series_list).tolist())
        else:
            modified_series.append(series_list)
    return modified_series


def series_stack(data_series, data_height):
    # Convert data_series and data_height to NumPy arrays
    data_series = np.array(data_series)
    data_height = np.array(data_height)

    # Create new zeroed height array if not same length as data_series.
    if data_series.shape[1] != data_height.shape[0]:
        data_height = np.zeros(data_series.shape[1], dtype=data_series.dtype)

    # Build stacked_data_series starting at the height.
    stacked_data_series = []
    stacked_data_series.append(data_height)
    # Use NumPy's cumulative sum along axis 0 to calculate the stacked data series
    stacked_data_series.extend(np.cumsum(data_series, axis=0) + data_height)

    # Set new height
    new_height = stacked_data_series[-1]

    return stacked_data_series, new_height


def label_format(label, g_formatting):
    l = {}
    if label in g_formatting:
        l.update(g_formatting[label])
    else:
        l['legend_text'] = str(label)
        l['legend_suppress'] = False
        l['title_text'] = str(label)
        l['title_suppress'] = False
        l['color'] = choice(['b', 'g', 'r', 'c', 'm', 'y', 'k'])
        l['alpha'] = 1
        l['fill_alpha'] = 1
        l['linewidth'] = 0.5
        l['linestyle'] = 'solid'
        l['marker'] = '.'
        l['size'] = 1
        g_formatting.update({label: l})
    return l


def build_plot_subplot_label_xy_data(statistics, plot_keys, subplot_keys, labels_on):
    """
    Build x, y, labels and subtitles of format
    Returns nested dictionary of key structure: [plot][subplot][label]['x' or 'y'] = [[series_1 values], [series_2 values], etc.]
    """
    plot_subplot_label_xy_data = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: {'x': [], 'y': []})))
    key_map = {'i': 0, 'j': 1, 'a': 2, 'r': 3, 'd': 4, 'c': 5, 's': 6}

    for k, v in statistics.items():
        plot_key = build_plot_key(k, key_map, plot_keys)
        subplot_key = build_plot_key(k, key_map, subplot_keys)
        label = build_plot_key(k, key_map, labels_on)
        x = np.array(list(v))
        y = np.array(list(v.values()))

        plot_subplot_label_xy_data[plot_key][subplot_key][label]['x'].append(x)
        plot_subplot_label_xy_data[plot_key][subplot_key][label]['y'].append(y)

    return plot_subplot_label_xy_data


def build_plot_key(k, key_map, plot_keys):
    """
    Builds a label
    k = (scenario, iteration, aggregation, region, deposit_type, statistic)
    key_map = ('i': 0, 'j': 1, 'a': 2, 'r': 3, 'd':4 , 's': 5)
    labels_on = list of k items to be included, e.g. ['a', 'c', 's']
    """
    return_key = ' '.join([k[key_map[plt_key]] for plt_key in plot_keys])
    return return_key


def generate_gif(frame_path_list, gif_path, fps=5, delete_frames=True):
    """
    Builds a .gif from image files included in frame_path_list.
    frame_path_list | List of filepaths for each frame [image0, image1, image2, image3, etc.]
    gif_path | Path where gif will be saved
    fps | Frames per second
    delete_frames | True (will delete original frame files) or False (will preserve frame files)
    Returns list of path of the .gif file and any preserved frame files.
    """
    return_paths = [gif_path]
    frames = []
    duration = 1000 / fps  # New imageio version uses duration in milliseconds instead of fps.
    for index, frame_path in enumerate(frame_path_list):
            frame = imageio.v2.imread(frame_path)
            frames.append(frame)
            if delete_frames and index != len(frame_path_list):
                frame_path.unlink()

    with imageio.get_writer(gif_path, mode='I', duration=duration, subrectangles=True) as writer:
        for frame in frames:
            writer.append_data(frame)

    if not delete_frames:
        return_paths.extend(frame_path_list)

    return return_paths





