# -*- coding: utf-8 -*-
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

# Import external packages
import matplotlib
import matplotlib.pyplot as plt
from numpy import nan

# Import custom modules

from modules.file_export import export_statistics, export_plot_subplot_data
from modules.file_import import import_statistics_keyed, import_statistics


def merge_scenarios(imported_postprocessing, scenario_folders, output_stats_folder):
    """
    merge_scenarios()
    # Merges scenario statistics.csv files and outputs as individual statistic csv files in a new folder
    imported_postprocessing | {s: statistic:}
    scenario_folders =
    output_stats_folder =

    """

    updated_postprocessing = imported_postprocessing

    # Iterate scenario CSVs and rewrite to files for each statistic.
    for folder in scenario_folders:
        stats_list, time_keys = import_statistics_keyed((folder + r'\_statistics.csv'), base_key='STATISTIC')
        ## stats_list is {s: {(i,j,a,r,d,s): {t: value}}}
        ## time_keys is [t1, t2, etc.]

        for s in stats_list:
            updated_postprocessing[s].update({'path': (output_stats_folder + r'\_' + str(s) + '.csv')})
            export_statistics(updated_postprocessing[s]['path'], stats_list[s], time_keys)

    return updated_postprocessing


def generate_figure(statistics_files, graph, graph_formatting, output_folder):
    """
    post_processing.generate_figure(statistics_files, graph, output_graphs_folder)
    graph = {'file_prefix', 'plot_algorithm', 'subplot_type', 'i_keys, 'j_keys', 'a_keys', 'r_keys', 'd_keys', 'c_keys',
                s_keys', 't_keys': -1, 'labels_on', 'include_all', 'share_scale', 'y_axis_label', 'cumulative'}
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
    i_keys, j_keys, a_keys, r_keys, d_keys, c_keys, s_keys, t_keys =\
        g['i_keys'], g['j_keys'], g['a_keys'], g['r_keys'], g['d_keys'], g['c_keys'], g['s_keys'], g['t_keys']
    filtered_statistics = {}
    for key in statistics:
        if filter_key_tuple(key, i_keys, j_keys, a_keys, r_keys, d_keys, c_keys, s_keys):
            filtered_statistics.update({key: statistics[key]})

    return filtered_statistics


def filter_key_tuple(key, i_keys, j_keys, a_keys, r_keys, d_keys, c_keys, s_keys):
    """
    Checks if key (i,j,a,r,d,c) included in keys.
    Returns True if key included or False if key excluded
    """
    i, j, a, r, d, c, s = key

    if _include_key(i, i_keys):
        if _include_key(j, j_keys):
            if _include_key(a, a_keys):
                if _include_key(r, r_keys):
                    if _include_key(d, d_keys):
                        if _include_key(c, c_keys):
                            if _include_key(s, s_keys):
                                return True
    return False


def _include_key(key, include_keys):
    """
    Returns True if key included or False if key excluded

    include_key | True = include any key except 'ALL'
                | False = only include key if 'ALL'
                | [k1, k2] =  return any

    Returns | True, include key
            | False, exclude key
    """
    if include_keys is True:
        if key != 'ALL':
            return True
        else:
            return False
    if include_keys is False:
        if key == "ALL":
            return True
        else:
            return False
    if key in include_keys:
        return True
    else:
        return False


def plot_subplot(statistics, path, g, g_formatting):
    """
    Generates multiple plots with subplots based on figure data defined in input_graphs.csv and input_graphs_formatting.csv

    Returns list of figure and figure data file paths.
    """

    file_prefix, plot_keys, subplot_keys, labels_on, subplot_type, share_scale, y_axis_label, cumulative = (
        g['file_prefix'], g['plot_keys'], g['subplot_keys'], g['labels_on'], g['subplot_type'], g['share_scale'], g['y_axis_label'], g['cumulative'])

    # Build x, y and labels of format
    plot_subplot_label_xy_data = build_plot_subplot_label_xy_data(statistics, plot_keys, subplot_keys, labels_on)

    # Generate plot path holder
    path_outputs = []

    # Generate plots
    for plot in plot_subplot_label_xy_data:
        # Generate plot title
        title = ' '.join(plot)

        # Generate subplot panels
        num_subplots = len(plot_subplot_label_xy_data[plot])
        h_panels = ceil(num_subplots / 2)
        v_panels = ceil(num_subplots / h_panels)

        # Generate y labels
        if y_axis_label == False:
            y_label = str(plot)
            y_label = y_label[0].upper() + y_label[1:]
        else:
            y_label = y_axis_label

        # Generate file path
        output_filepath = path + r'\_' + file_prefix + '-' + str(plot) + '.png'
        output_filepath_data = output_filepath + '.csv'

        fig_path, fig_data = plot_subplot_generator(output_filepath, str(title), plot_subplot_label_xy_data[plot], h_panels, v_panels, subplot_type, share_scale, y_label, cumulative, g_formatting)
        path_outputs.append(fig_path)
        path_outputs.append(export_plot_subplot_data(output_filepath_data, fig_data))

    return path_outputs


def plot_subplot_generator(output_filename, title, plot, h_panels, v_panels, plot_type, share_scale, y_axis_label, cumulative, g_formatting):
    """
    Returns a plot with an arbitrary number of subplots.
    plot_type can equal 'stacked', 'scatter', 'line', 'fill', 'fill_line'

    x | for stacked plots x[0] should equal any x[any]
    """
    matplotlib.use('Agg') # Using this backend to avoid a memory leak when using fig.savefig for subplots without a show()

    # Create an iterator for the subplots (e.g. commodity keys)
    subplot = iter(sorted(plot))

    # Generating plot with subplots
    if share_scale == True:
        # Subplots have common scale
        fig, ax = plt.subplots(h_panels, v_panels, figsize=(h_panels * 7, v_panels * 7), subplot_kw={'xmargin': 0, 'ymargin': 0}, sharey=True, sharex=True, squeeze=False)
    elif share_scale == False:
        # Subplots have independent scales
        fig, ax = plt.subplots(h_panels, v_panels, figsize=(h_panels * 7, v_panels * 7), subplot_kw={'xmargin': 0, 'ymargin': 0}, sharey=False, sharex=False)

    fig.suptitle(title)
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
                        data['y'] = series_modify(data['y'], cumulative) # add replace_none=float(0) if reverting to generate_stackplot()
                        stacked_y, data_height = series_stack(data['y'], data_height)
                        generate_fill(ax[h, v], data['x'], stacked_y, l_format)

                # Subplot formatting
                ax[h, v].legend(loc='upper left')
                ax[h, v].set_title(sp, pad=-15)
                ax[h, v].set_ylabel(y_axis_label)
                ax[h, v].tick_params(labelbottom=1, labelleft=1)

            else:
                fig.delaxes(ax[h, v])
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
        l['color'] = choice(['b', 'g', 'r', 'c', 'm', 'y', 'k'])
        l['alpha'] = 1
        l['fill_alpha'] = 1
        l['linewidth'] = 0.5
        l['linestyle'] = 'solid'
        l['legend_suppress'] = False
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





