# -*- coding: utf-8 -*-
"""
Module with routines for post_processing of results data.
    generate_figures()
    generate_plot_keys()
    statistics_ij_plots_c_subplots()
    statistics_cs_plots_i_subplots()
    plot_subplot_generator()
    post_processing_old()
    merge_scenarios()

TODO: 1. Add copywrite statement
TODO: 2. Finish writing and testing module functionality
TODO: 3. Add cross-refernces to the journal article
TODO: 4. Check docstrings after functionality finalised
"""

# Import standard packages
from math import ceil
from collections import defaultdict
from random import choice

# Import external packages
# TODO check if general matplotlib import is still needed
import matplotlib
import matplotlib.pyplot as plt
from numpy import nan

# Import custom modules

from modules.results import key_all_expand, key_generate_filter, x_y_labels_generate_flat, key_include_filter
from modules.file_export import export_statistics
from modules.file_import import import_statistics_filter, import_statistics

def generate_figure(statistics_files, graph, graph_formatting, output_folder):
    """

    post_processing.generate_figure(statistics_files, graph, output_graphs_folder)
    graph = {'file_prefix', 'plot_algorithm', 'subplot_type', 'i_keys, 'j_keys', 'a_keys', 'r_keys', 'd_keys', 'c_keys',
                s_keys', 't_keys': -1, 'labels_on', 'include_all', 'share_scale', 'y_axis_label'}
    graph_formatting = {label: {'color': value, 'linewidth': value, 'linestyle':value}}
    returns a path to the output figure
    TODO: Write docstrings
    TODO: Add figure types
    """
    g_statistics = {}

    output_path = str()

    # Import required .csv files
    for s, s_dict in statistics_files.items():
        if s in graph['s_keys']:
            g_statistics.update(import_statistics(s_dict['path'], convert_values=True))

    # Filter statistics
    filtered_data, filtered_key_dict_set = filter_statistics(g_statistics, graph)

    if graph['plot_algorithm'] == 'plot_subplot_default':
        output_path = plot_subplot(filtered_data, output_folder, graph, graph_formatting)

    return output_path


def filter_statistics(statistics, g):
    """
    TODO: considered removing filtered_key_dict if not used.
    TODO: consider filtering for t_keys.
    """
    i_keys, j_keys, a_keys, r_keys, d_keys, c_keys, s_keys, t_keys =\
        g['i_keys'], g['j_keys'], g['a_keys'], g['r_keys'], g['d_keys'], g['c_keys'], g['s_keys'], g['t_keys']
    filtered_statistics = {}
    filtered_key_dict_set = {'i': set(),
                         'j': set(),
                         'a': set(),
                         'r': set(),
                         'd': set(),
                         'c': set(),
                         's': set()}


    for key in statistics:
        if filter_key_tuple(key, i_keys, j_keys, a_keys, r_keys, d_keys, c_keys, s_keys):
            filtered_key_dict_set['i'].add(key[0])
            filtered_key_dict_set['j'].add(key[1])
            filtered_key_dict_set['a'].add(key[2])
            filtered_key_dict_set['r'].add(key[3])
            filtered_key_dict_set['d'].add(key[4])
            filtered_key_dict_set['c'].add(key[5])
            filtered_key_dict_set['s'].add(key[6])
            filtered_statistics.update({key: statistics[key]})

    return filtered_statistics, filtered_key_dict_set


def filter_key_tuple(key, i_keys, j_keys, a_keys, r_keys, d_keys, c_keys, s_keys):
    """
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
    """

    file_prefix, plot_keys, subplot_keys, labels_on, subplot_type, share_scale, y_axis_label = (
        g['file_prefix'], g['plot_keys'], g['subplot_keys'], g['labels_on'], g['subplot_type'], g['share_scale'], g['y_axis_label'])

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
        if y_axis_label == -1:
            y_label = str(plot)
            y_label = y_label[0].upper() + y_label[1:]
        else:
            y_label = y_axis_label

        # Generate file path
        output_filepath = path + r'\_' + file_prefix + '-' + str(plot) + '.png'

        path_outputs.append(plot_subplot_generator(output_filepath, str(title), plot_subplot_label_xy_data[plot], h_panels, v_panels, subplot_type, share_scale, y_label, g_formatting))
        path_outputs.append(plot_subplot_data_export(output_filepath + '.csv', plot))

    return path_outputs


def plot_subplot_generator(output_filename, title, plot, h_panels, v_panels, plot_type, share_scale, y_axis_label, g_formatting):
    """
    Returns a plot with an arbitrary number of subplots.
    plot_type can equal 'stacked', 'scatter', 'line'
    iterator must be ordered to generate horizontal then vertical.
    TODO: Update docstrings

    x | for stacked plots x[0] should equal any x[any]
    """
    matplotlib.use('Agg') # Using this backend to avoid a memory leak when using fig.savefig for subplots without a show()

    # Create an iterator for the subplots (e.g. commodity keys)
    subplot = iter(sorted(plot))

    # Generating plot with subplots
    if share_scale == True:
        # Subplots have common scale
        fig, ax = plt.subplots(h_panels, v_panels, figsize=(h_panels * 7, v_panels * 7), sharey=True, sharex=True,
                                   squeeze=False)
    elif share_scale == False:
        # Subplots have independent scales
        fig, ax = plt.subplots(h_panels, v_panels, figsize=(h_panels * 7, v_panels * 7), sharey=False, sharex=False)

    fig.suptitle(title)
    for h in range(h_panels):
        for v in range(v_panels):
            # Generate next panel key and check if it exists.
            sp = next(subplot, False)
            if sp is not False:
                # Unpack plot[sp] = {label: {x: [[x0, x0], [x1, x1], ...], y: [[y0, y0], [y1, y1], ...]}}
                # Sort to ensure labels are alphabetical in legend. Does this based on label, not legend_text.
                for label, data in sorted(plot[sp].items()):
                    legend_text, legend_suppress, color, linewidth, linestyle = label_format(label, g_formatting)

                    if plot_type == 'stacked':
                        # Rebuild y for stacked plot. [[y series 0],[y series 1], ...]
                        y = []
                        for y_list in data['y']:
                            y_list_with_none_as_zero = [0 if v is None else v for v in y_list]
                            y.append(y_list_with_none_as_zero)
                        ax[h, v].stackplot(data['x'][0], y, color=color) # Assumes all x series are the same.
                        if legend_suppress is False:
                            ax[h, v].stackplot([], [], labels=[legend_text], color=color)

                    elif plot_type == 'scatter':
                        # Generate scatter plots for all series in this label
                        for n, x in enumerate(data['x']):
                            ax[h, v].scatter(x, data['y'][n], marker=',', s=1.5, color=color)
                        if legend_suppress is False:
                            ax[h, v].scatter([], [], label=legend_text, marker=',', s=1.5, color=color)

                    elif plot_type == 'line':
                        # Generate line plots for all series in this label
                        for n, x in enumerate(data['x']):
                            ax[h, v].plot(x, data['y'][n], color=color, linewidth=linewidth, linestyle=linestyle)
                        if legend_suppress is False:
                            ax[h, v].plot([], [], label=legend_text, color=color)

                    elif plot_type == 'fill':
                        min_y = []
                        max_y = []
                        modified_x = []
                        for i in range(len(data['y'][0])):
                            # Extract series y values and filter out None. Replace these with numpy nan to allow plotting breaks in series.
                            y_list_for_x = [y_list[i] for y_list in data['y'] if y_list[i] is not None]
                            if len(y_list_for_x) == 0:
                                modified_x.append(nan)
                                min_y.append(nan)
                                max_y.append(nan)
                            else:
                                modified_x.append(data['x'][0][i])
                                min_y.append(min(y_list_for_x))
                                max_y.append(max(y_list_for_x))
                        ax[h, v].fill_between(modified_x, min_y, max_y, color=color)
                        if legend_suppress is False:
                            ax[h, v].fill([], [], label=legend_text, color=color)

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

    return output_filename


def label_format(label, g_formatting):
    if label in g_formatting:
        legend_text = str(g_formatting[label]['legend_text'])
        legend_suppress = g_formatting[label]['legend_suppress']
        color = g_formatting[label]['color']
        linewidth = g_formatting[label]['linewidth']
        linestyle = g_formatting[label]['linestyle']
    else:
        legend_text = str(label)
        color = choice(['b', 'g', 'r', 'c', 'm', 'y', 'k'])
        linewidth = 0.5
        linestyle = 'solid'
        legend_suppress = False
        g_formatting.update({label: {'legend_text': legend_text, 'color': color, 'linewidth': linewidth, 'linestyle': linestyle, 'legend_suppress': legend_suppress}})
    return legend_text, legend_suppress, color, linewidth, linestyle

def build_plot_subplot_label_xy_data(statistics, plot_keys, subplot_keys, labels_on):
    """
    Build x, y, labels and subtitles of format
    Returns nested dictionary of key structure: [plot][subplot][label]['x' or 'y'] = [[series_1 values], [series_2 values], etc.]
    TODO: update docstrings with all input arguments described.
    """
    plot_subplot_label_xy_data = defaultdict(dict)  #[(plot_keys)][subplot_keys][label][[x_lists],[y_lists], FORMAT_KWARGS]
    key_map = {'i': 0, 'j': 1, 'a': 2, 'r': 3, 'd': 4, 'c': 5, 's': 6}

    for k, v in statistics.items():
        # k = (i,j,a,r,d,c,s)
        # v = {t0: val0, t1: val1, t2: val2, etc}
        plot_key = build_plot_key(k, key_map, plot_keys)
        subplot_key = build_plot_key(k, key_map, subplot_keys)
        label = build_plot_key(k, key_map, labels_on)

        if plot_key not in plot_subplot_label_xy_data:
            plot_subplot_label_xy_data[plot_key] = {subplot_key: {label: {'x': [list(v),],
                                                                          'y': [list(v.values()),]
                                                                          }}}
        elif subplot_key not in plot_subplot_label_xy_data[plot_key]:
            plot_subplot_label_xy_data[plot_key].update({subplot_key: {label: {'x': [list(v),],
                                                                               'y': [list(v.values()),]
                                                                               }}})
        elif label not in plot_subplot_label_xy_data[plot_key][subplot_key]:
            plot_subplot_label_xy_data[plot_key][subplot_key].update({label: {'x': [list(v),],
                                                                              'y': [list(v.values()),]
                                                                              }})
        else:
            plot_subplot_label_xy_data[plot_key][subplot_key][label]['x'].append(list(v),)
            plot_subplot_label_xy_data[plot_key][subplot_key][label]['y'].append(list(v.values()),)

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




def plot_subplot_data_export(output_filename, plot):
    """
    Exports data to subplot series data to a .csv file.
    """
    path = 'dummy.csv'
    return output_filename


def merge_scenarios(imported_postprocessing, scenario_folders, output_stats_folder):
    """
    merge_scenarios()
    # Merges statistics from scenario statistics.csv and outputs as individuals CSVs in a new folder
    imported_postprocessing =
    scenario_folders =
    output_stats_folder =

    TODO: Update docstrings
    #TODO: optimise. Possibly can use import_statistics rather than import_statistics_filter. Then change 'for s in stats_list'
    """

    updated_postprocessing = imported_postprocessing

    # Iterate scenario CSVs and rewrite to files for each statistic.
    for folder in scenario_folders:
        stats_list, time_keys = import_statistics_filter((folder + r'\_statistics.csv'), updated_postprocessing.keys())
        ## stats_list is {s: {(i,j,a,r,d,s): {t: value}}}
        ## time_keys is [t1, t2, etc.]

        for s in stats_list:
            updated_postprocessing[s].update({'path': (output_stats_folder + r'\_' + str(s) + '.csv')})
            export_statistics(updated_postprocessing[s]['path'], stats_list[s], time_keys)
            
    return updated_postprocessing

