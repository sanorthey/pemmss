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
from collections import defaultdict
from random import choice
from itertools import accumulate
from itertools import islice
import os

# Import external packages
import matplotlib
import matplotlib.pyplot as plt
from numpy import nan
import numpy as np
import imageio
import pandas as pd

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
    key_output_filepath_dict = combine_csv_files(scenario_folders, output_stats_folder,filter_columns,filter_keys, filenameend="statistics.csv")
    for s, path in key_output_filepath_dict.items():
        updated_postprocessing[s[0]].update({'path': path})  #s [0] because s is a tuple (s,) with an extra, empty element. Should really fix this up.

    return updated_postprocessing


def combine_csv_files(input_dirs, output_dir, filter_columns, filter_keys, filenameend="statistics.csv"):
    """
    Combines CSV files from multiple directories based on filter keys and saves the filtered data into separate CSV files.

    Args:
        input_dirs (list): List of input directories containing CSV files.
        output_dir (str): Output directory to save the generated CSV files.
        filter_columns (list): List of column names to filter on.
        filter_keys (list): List of filter key combinations.
        filenameend (str, optional): Ending of the input CSV filenames. Defaults to "statistics.csv".

    Returns:
        dict: {key, filepath} Dictionary containing the filter keys and corresponding paths of the generated CSV files.
    """
    key_path_dict = {}  # Create an empty dictionary to store the key and paths of generated CSV files

    for input_dir in input_dirs:
        for filename in os.listdir(input_dir):
            if filename.endswith(filenameend):
                file_path = os.path.join(input_dir, filename)
                df = pd.read_csv(file_path)  # Read the CSV file into a DataFrame

                for keys in filter_keys:
                    filtered_df = df.copy()
                    for column, key in zip(filter_columns, keys):
                        filtered_df = filtered_df[filtered_df[column] == key]

                    if tuple(keys) not in key_path_dict:
                        output_file = "_".join(keys) + ".csv"
                        output_path = os.path.join(output_dir, output_file)

                        filtered_df.to_csv(output_path, index=False)
                        key_path_dict[tuple(keys)] = output_path

                    else:
                        output_path = key_path_dict[tuple(keys)]
                        filtered_df.to_csv(output_path, mode='a', header=False, index=False)

    return key_path_dict


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

    file_prefix, plot_keys, subplot_keys, labels_on, subplot_type, share_scale, y_axis_label, cumulative, columns, gif, fps, delete_frames = (
        g['file_prefix'], g['plot_keys'], g['subplot_keys'], g['labels_on'], g['subplot_type'], g['share_scale'], g['y_axis_label'], g['cumulative'], g['columns'], g['gif'], g['gif_fps'], g['gif_delete_frames'])

    # Build x, y and labels of format
    plot_subplot_label_xy_data = build_plot_subplot_label_xy_data(statistics, plot_keys, subplot_keys, labels_on)

    # Generate plot path holder
    plot_paths = []
    plot_data_paths = []

    # Assign plot directory or create a directory for holding gif frames
    plot_folder_path = path
    if g['gif'] is True:
        plot_folder_path = path + r'\_' + file_prefix
        os.mkdir(plot_folder_path)

    # Generate plots
    for plot in plot_subplot_label_xy_data:
        # Generate plot title
        title = ''.join(plot)

        # Generate subplot panels
        num_subplots = len(plot_subplot_label_xy_data[plot])
        h_panels = ceil(num_subplots / columns)
        v_panels = ceil(num_subplots / h_panels)

        # Generate y labels
        if y_axis_label == False:
            y_label = str(plot)
            y_label = y_label[0].upper() + y_label[1:]
        else:
            y_label = y_axis_label

        # Generate file path
        output_filepath = plot_folder_path + r'\_' + file_prefix + '-' + str(plot) + '.png'
        output_filepath_data = output_filepath + '.csv'

        fig_path, fig_data = plot_subplot_generator(output_filepath, str(title), plot_subplot_label_xy_data[plot], h_panels, v_panels, subplot_type, share_scale, y_label, cumulative, g_formatting)
        plot_paths.append(fig_path)
        export_plot_subplot_data(output_filepath_data, fig_data)
        plot_data_paths.append(output_filepath_data)

    # Generate GIF
    if g['gif'] is True:
        gif_filepath = path + r'\_' + file_prefix + '.gif'
        plot_paths = generate_gif(plot_paths, gif_filepath, fps=fps, delete_frames=delete_frames)

    # Generate final returned output paths list
    output_paths = plot_paths + plot_data_paths

    return output_paths


def plot_subplot_generator(output_filename, title, plot, h_panels, v_panels, plot_type, share_scale, y_axis_label, cumulative, g_formatting):
    """
    Returns a plot with an arbitrary number of subplots.
    plot_type can equal 'stacked', 'scatter', 'line', 'fill', 'fill_line'

    x | for stacked plots x[0] should equal any x[any]
    """
    matplotlib.use('Agg') # Using this backend to avoid a memory leak when using fig.savefig for subplots without a show()

    # Create an iterator for the subplots (e.g. commodity keys)
    subplot = iter(sorted(plot))

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
    elif share_scale == False:
        # Subplots have independent scales
        fig, ax = plt.subplots(h_panels, v_panels, figsize=(v_panels * 9/2.54, h_panels * 9/2.54), subplot_kw={'xmargin': 0, 'ymargin': 0}, sharey=False, sharex=False)

    for h in range(h_panels):
        for v in range(v_panels):
            # Generate next panel key and check if it exists.
            sp = next(subplot, False)
            if sp is not False:
                data_height = [] # for use with stackplots
                # Unpack plot[sp] = {label: {x: [[x0, x0], [x1, x1], ...], y: [[y0, y0], [y1, y1], ...]}}
                # Sort to ensure labels are alphabetical in legend. Does this based on label, not legend_text.
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
                        # Using generate_fill() here now because generate_stackplot() is buggy
                        data['y'] = series_modify(data['y'], cumulative, replace_none=float(0)) # add replace_none=float(0) if reverting to generate_stackplot()
                        stacked_y, data_height = series_stack(data['y'], data_height)
                        generate_fill(ax[h, v], data['x'], stacked_y, l_format)

                # Subplot formatting
                ax[h, v].legend(loc='upper left')
                if sp in g_formatting:
                    if g_formatting[sp]['legend_suppress'] is False:
                        ax[h, v].set_title(g_formatting[sp]['title_text'], pad=None)
                else:
                    ax[h, v].set_title(sp, pad=None)
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
            filtered_list = [0 if v is None else v for v in series_list]
            modified_series.append(list(accumulate(filtered_list)))
        elif replace_none is not False:
            modified_series.append([replace_none if v is None else v for v in series_list])
        else:
            modified_series.append(series_list)
    return modified_series

def series_stack(data_series, data_height):
    # For use with stack plots
    # data_height = [h0, h1, h2]
    # data_series = [[y0,y1,y2], [y0,y1,y2], etc.]

    stacked_data_series = []
    height = data_height

    # Create new zeroed height list if not same length as stacked_data_series.
    if len(data_series[0]) is not len(data_height):
        height = [0 for _ in data_series[0]]

    # Build stacked_data_series starting at the height.
    stacked_data_series.append(height)
    for data_list in data_series:
        height = [x + y for x, y in zip(data_list, height)]
        stacked_data_series.append(height)

    return stacked_data_series, height

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
    plot_subplot_label_xy_data = defaultdict(dict)  #[(plot_keys)][subplot_keys][label][[x_lists],[y_lists], FORMAT_KWARGS]
    key_map = {'i': 0, 'j': 1, 'a': 2, 'r': 3, 'd': 4, 'c': 5, 's': 6}

    for k, v in statistics.items():
        # k = (i,j,a,r,d,c,s)
        # v = {t0: val0, t1: val1, t2: val2, etc}
        plot_key = build_plot_key(k, key_map, plot_keys)
        subplot_key = build_plot_key(k, key_map, subplot_keys)
        label = build_plot_key(k, key_map, labels_on)
        x = list(v)
        y = list(v.values())

        if plot_key not in plot_subplot_label_xy_data:
            plot_subplot_label_xy_data[plot_key] = {subplot_key: {label: {'x': [x,], 'y': [y,]}}}
        elif subplot_key not in plot_subplot_label_xy_data[plot_key]:
            plot_subplot_label_xy_data[plot_key].update({subplot_key: {label: {'x': [x,], 'y': [y,]}}})
        elif label not in plot_subplot_label_xy_data[plot_key][subplot_key]:
            plot_subplot_label_xy_data[plot_key][subplot_key].update({label: {'x': [x,],'y': [y,]}})
        else:
            plot_subplot_label_xy_data[plot_key][subplot_key][label]['x'].append(x,)
            plot_subplot_label_xy_data[plot_key][subplot_key][label]['y'].append(y,)

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
    with imageio.v2.get_writer(gif_path, mode='I', fps=fps, subrectangles=True) as writer:
        for frame_path in frame_path_list:
            frame = imageio.v2.imread(frame_path)
            writer.append_data(frame)
            if delete_frames is True:
                os.remove(frame_path)
            else:
                return_paths.append(frame_path)
    return return_paths





