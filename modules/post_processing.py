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

"""

# Import standard packages
from math import ceil

# Import external packages
import matplotlib.pyplot as plt

# Import custom modules

from modules.results import key_all_expand, key_generate_filter, x_y_labels_generate_flat, key_include_filter
from modules.file_export import export_log, export_statistics_flat
from modules.file_import import import_statistics_flat_filter, import_statistics_flat

def generate_figures(statistics, graphs, output_folder):
    figs = 0
    g_statistics = {}
    for g in graphs:
        figs += 1
        if g['plot_algorithm'] == 'statistics_cs_plots_i_subplots':
            g_statistics = import_statistics_flat()
            statistics_cs_plots_i_subplots(statistics, output_folder, g)
        elif g['plot_algorithm'] == 'statistics_ij_plots_c_subplots':
            statistics_ij_plots_c_subplots(statistics, output_folder, g)

    export_log(str(figs) + ' figures generated.', print_on=0)


def generate_plot_keys(statistics, keys_0, keys_1, index_0, index_1):
    """
    generate_plot_keys()
    
    statistics | 
    keys_0     | True, False or list []
    keys_1     |
    index_0    | (i,j,a,r,d,c,s)
    index_1    | (i,j,a,r,d,c,s)
    """
    
    
    if isinstance(keys_0, list):
        if isinstance(keys_1, list):
            new_keys_0 = keys_0
            new_keys_1 = keys_1
        else:
            new_keys_0 = keys_0
            new_keys_1 = set()
            for s in statistics:
                if key_include_filter(s,index_1,_include=j_keys):
                    new_keys_1.update(s[index_1])     
    else:
        if isinstance(keys_1, list):
            new_keys_0 = set()
            new_keys_1 = keys_1
            for s in statistic:
                if key_include_filter(s,index_0,_include=keys_0):
                    new_keys_0.update(s[index_0])
        else:
            new_keys_0 = set()
            new_keys_1 = set()
            for s in statistic:
                if key_include_filter(s,index_0,_include=keys_0):
                    new_keys_0.update(s[index_0])
                if key_include_filter(s,index_1,_include=keys_1):
                    new_keys_1.update(s[index_1])
                
                
                
                
            
        ## FIXME: elif
        if type(keys_1) != list:
            new_keys_1 = set()
            for s in statistic:
                if key_include_filter(s,index_0,_include=keys_0):
                    new_keys_0.update(s[index_0])
                if key_include_filter(s,index_1,_include=keys_1):
                    # TODO: update this 
                    print("######## Update post_processing.generate_plot_keys")
                    
                    
                    
                elif key_include_filter(s,index_0,_include=keys_0):
                    new_keys_0.append(s[index_0])
                elif key_include_filter(s,index_1,_include=j_keys):
                    new_keys_1.append(s[index_1])     
                    
        else:
            new_keys_1 = keys_1
            for s in statistic:
                if key_include_filter(s,0,_include=keys_0):
                    new_keys_0.append(s[0])

    

    return new_keys_0, new_keys_1
    

def statistics_ij_plots_c_subplots(statistics, path, g):
    """
    Generates plots for each inputted scenario and iteration, with subplots for each inputted commodity.
    Refer to def statistics_x_y labels for definitions of: i_keys, j_keys, r_keys, d_keys, c_keys, s_keys, t_keys, labels_on, include_all

    ----- WARNING: c_keys must be a list and cannot be -1 -----

    i_keys = -1 ## Either -1 or a list [scenario_name_1,scenario_name_1, etc.]
    j_keys = -1 ## Either -1 or a list ## FIXME: True, False or a list. 
    a_keys = -1 ## Either -1 or a list
    r_keys = -1 ## Either -1 or ['ALL'] or a list
    d_keys = ['ALL'] ## Either -1 or ['ALL'] or a list
    c_keys = ['A','B','C','D'] # WARNING: For entry into ij_plots_c_subplots cannot be -1.
    s_keys = ['mines_producing_count']
    t_keys = -1
    labels_on = [0,0,1,0,0,0] # [i,j,r,d,c,s]
    include_all = [0,0,0,0,0,0]
    plot_type = 'scatter' ## 'stacked', 'scatter', 'line'
    share_scale = True
    y_axis_label = 0 ## Can set to 0 for auto-generation.
    statistics_ij_plots_c_subplots(statistics,output_folder,i_keys,j_keys,r_keys,d_keys,c_keys,s_keys,t_keys,labels_on,include_all,plot_type,share_scale,y_axis_label)
    """

    file_prefix, i_keys, j_keys, a_keys, r_keys, d_keys, c_keys, s_keys, t_keys, labels_on, include_all, subplot_type, share_scale, y_axis_label = (
        g['file_prefix'], g['i_keys'], g['j_keys'], g['a_keys'], g['r_keys'], g['d_keys'], g['c_keys'], g['s_keys'], g['t_keys'],
        g['labels_on'], g['include_all'], g['subplot_type'], g['share_scale'], g['y_axis_label'])

    ## Autogenerate i_keys and j_keys where required.
    #i_keys = key_generate_filter(statistics, i_keys, 1, 'ALL')
    #if j_keys == -1:
    #    j_keys = []
    #    for i in i_keys:
    #        for j in statistics[i].keys():
    #            if j not in j_keys:
    #                j_keys.append(j)
    
    
    # Autogenerate i_keys and j_keys where required.
    if type(i_keys) != list:
        new_i_keys = []
        if j_keys != list:
            new_j_keys = []
            for s in statistic:
                if key_include_filter(s,0,_include=i_keys):
                    new_i_keys.append(s[0])
                if key_include_filter(s,1,_include=j_keys):
                    new_j_keys.append(s[1])     
        else:
            new_j_keys = j_keys
            for s in statistic:
                if key_include_filter(s,0,_include=i_keys):
                    new_i_keys.append(s[0])
    else:
        new_i_keys = i_keys
        if j_keys != list:
            new_j_keys = []
            for s in statistics:
                if key_include_filter(s,1,_include=j_keys):
                    new_j_keys.append(s[1])  
        else:
            new_j_keys = j_keys
    i_keys = new_i_keys
    j_keys = new_j_keys   

    # Autogenerate y_axis_label if required.
    if y_axis_label == -1:
        y_label = str(s_keys[0]).replace('_', ' ')
        y_label = y_label[0].upper() + y_label[1:]
    else:
        y_label = y_axis_label

    for i in i_keys:
        for j in j_keys:
            if j in statistics[i]:
                x, y, l, subtitles = {}, {}, {}, {}
                for c in c_keys:
                    x[c], y[c], l[c] = statistics_x_y_labels(statistics, [i], [j], a_keys, r_keys, d_keys, [c], s_keys, t_keys,
                                                             labels_on, include_all, force_keys=False,
                                                             suppress_log=True)
                    x[c], y[c], l[c] = x_y_labels_generate_flat(statistics,
                                                                i_include=i_key,
                                                                j_include=j_keys,
                                                                a_include=a_keys,
                                                                r_include=r_keys,
                                                                d_include=d_keys,
                                                                c_include=c_keys,
                                                                s_include=c_keys,
                                                                filter_t=t_keys)
                    subtitles[c] = str(c)

                # Generate plot for every i and j, with subplots for every c.
                title = 'Scenario ' + str(i) + ', Iteration ' + str(j)
                h_panels = ceil(len(c_keys) / 2)
                v_panels = ceil(len(c_keys) / h_panels)
                output_filename = path + r'\_' + file_prefix + '-' + str(i) + '_' + str(j) + '.png'
                plot_subplot_generator(output_filename, title, x, y, l, subtitles, c_keys, h_panels, v_panels,
                                       subplot_type, share_scale, y_label)
                plot_subplot_data_export(output_filename+'.csv',x,y,l)

            else:
                export_log('No iteration ' + str(j) + ' exists for scenario ' + str(i) + '. Figure generation skipped.',
                           print_on=0)


def statistics_cs_plots_i_subplots(statistics, path, g):
    """
    Generates plots for each inputted commodity and statistic, with subplots for each inputted scenario.
    Refer to def statistics_x_y labels for definitions of: i_keys, j_keys, a_keys, r_keys, d_keys, c_keys, s_keys, t_keys, labels_on, include_all
    ----- WARNING: c_keys must be a list and cannot be -1 -----

    i_keys = -1
    j_keys = -1
    a_keys = ['ALL']
    r_keys = -1
    d_keys = ['ALL']
    c_keys = ['ALL'] # WARNING: For entry into ij_plots_c_subplots cannot be -1.
    s_keys = ['cumulative_deposits_discovered_count']
    t_keys = -1
    labels_on = [0,0,0,1,0,0,0] # [i,j,a,r,d,c,s]
    include_all = [0,0,0,0,0,0,0]
    plot_type = 'line'  ## 'stacked', 'scatter', 'line'
    share_scale = True
    y_axis_label = -1 # Can set to a string (e.g.'label') or 0 for auto-generation.
    statistics_cs_plots_i_subplots(statistics,output_folder,i_keys,j_keys,a_keys,r_keys,d_keys,c_keys,s_keys,t_keys,labels_on,include_all,plot_type,share_scale,y_axis_label)
    """
    file_prefix, i_keys, j_keys, a_keys, r_keys, d_keys, c_keys, s_keys, t_keys, labels_on, include_all, subplot_type, share_scale, y_axis_label = (
        g['file_prefix'], g['i_keys'], g['j_keys'], g['a_keys'], g['r_keys'], g['d_keys'], g['c_keys'], g['s_keys'], g['t_keys'],
        g['labels_on'], g['include_all'], g['subplot_type'], g['share_scale'], g['y_axis_label'])
    
    # Autogenerate i_keys, apply 'ALL' filter
    i_keys = key_generate_filter(statistics, i_keys, include_all[0], filtered_value='ALL')

    for c in c_keys:
        for s in s_keys:
            # Autogenerate y_axis_label if required.
            if y_axis_label == -1:
                y_label = str(s).replace('_', ' ')
                y_label = y_label[0].upper() + y_label[1:]
            else:
                y_label = y_axis_label

            x, y, l, subtitles = {}, {}, {}, {}
            for i in i_keys:
                x[i], y[i], l[i] = statistics_x_y_labels(statistics, [i], j_keys, a_keys, r_keys, d_keys, [c], [s], t_keys,
                                                         labels_on, include_all, force_keys=False, suppress_log=True)
                subtitles[i] = str(i)
            # Generate plot for every c and s, with subplots for every i, with subplots for every c.
            title = 'Commodity ' + str(c) + ', Statistic ' + str(s)
            h_panels = ceil(len(i_keys) / 2)
            v_panels = ceil(len(i_keys) / h_panels)
            output_filename = path + r'\_' + file_prefix + '-' + str(c) + '_' + str(s) + '.png'
            plot_subplot_generator(output_filename, title, x, y, l, subtitles, i_keys, h_panels, v_panels, subplot_type,
                                   share_scale, y_label)
            plot_subplot_data_export(output_filename+'.csv',x,y,l)


def plot_subplot_generator(output_filename, title, x, y, l, subtitles, iterator, h_panels, v_panels, plot_type,
                           share_scale, y_axis_label):
    """
    Returns a plot with an arbitrary number of subplots.
    plot_type can equal 'stacked', 'scatter', 'line'
    iterator must be ordered to generate horizontal then vertical. ## CHECK THIS.
    """
    # Create an iterator for the subplots (e.g. commodity keys)
    subplot = iter(iterator)
    # Generating plot with subplots
    if share_scale == True:
        # Subplots have common scale
        g_stack, ax = plt.subplots(h_panels, v_panels, figsize=(h_panels * 7, v_panels * 7), sharey=True, sharex=True,
                                   squeeze=False)
    elif share_scale == False:
        # Subplots have independent scales
        g_stack, ax = plt.subplots(h_panels, v_panels, figsize=(h_panels * 7, v_panels * 7), sharey=False, sharex=False)

    g_stack.suptitle(title)
    for h in range(0, h_panels):
        for v in range(0, v_panels):
            # Generate next panel key and check if it exists.
            sp = next(subplot)
            if sp != StopIteration:
                if plot_type == 'stacked':
                    # Generate stacked plot for this subplot
                    ax[h, v].stackplot(x[sp], y[sp], labels=l[sp])
                elif plot_type == 'scatter':
                    # Iterates through y series
                    for ind in range(0, len(y[sp])):
                        # Generate scatter plot series for this subplot
                        ax[h, v].scatter(x[sp], y[sp][ind], marker=',', s=2, label=l[sp][ind])
                elif plot_type == 'line':
                    for ind in range(0, len(y[sp])):
                        # Generate line plot series for this subplot
                        ax[h, v].plot(x[sp], y[sp][ind], label=l[sp][ind])
                # Subplot formatting
                ax[h, v].legend(loc='upper left')
                ax[h, v].set_title(str(subtitles[sp]), pad=-15)
                ax[h, v].set_ylabel(y_axis_label)
                ax[h, v].tick_params(labelbottom=1, labelleft=1)

    # Export file
    g_stack.savefig(fname=output_filename, dpi=300)
    # plt.show()
    plt.close(g_stack)

def post_processing_old(imported_postprocessing, scenario_folders, output_stats_folder):
    """
    # Create a list of statistics to be postprocessed
    imported_postprocessing = 
    scenario_folders = 
    output_stats_folder = 
    ## FIXME: finish documentation    
    """

    stats_list = []
    for row in imported_postprocessing:
        if row['postprocess'] == '1':
            stats_list.append(row['statistic'])

    # Iterate scenario CSVs and rewrite to files for each statistic.
    for folder in scenario_folders:
        stats_list, time_keys = import_statistics_flat_filter((folder+r'\_statistics.csv'),stats_list)
        
        for row in imported_postprocessing:
            if row['postprocess'] == '1':
                export_statistics_flat(output_stats_folder+r'\_'+str(row)+'.csv', stats_list[row], time_keys)


def merge_scenarios(imported_postprocessing, scenario_folders, output_stats_folder):
    """
    merge_scenarios()
    # Merges statistics from scenario statistics.csv and outputs as individuals CSVs in a new folder
    imported_postprocessing =
    scenario_folders =
    output_stats_folder =
    ## FIXME: finish documentation
    """

    updated_postprocessing = imported_postprocessing

    # Iterate scenario CSVs and rewrite to files for each statistic.
    for folder in scenario_folders:
        stats_list, time_keys = import_statistics_flat_filter((folder + r'\_statistics.csv'), updated_postprocessing.keys())
        ## stats_list is {s: {(i,j,a,r,d,s): {t: value}}}
        ## time_keys is [t1, t2, etc.]

        for s in stats_list:
            updated_postprocessing[s].update({'path': (output_stats_folder + r'\_' + str(s) + '.csv')})
            export_statistics_flat(updated_postprocessing[s]['path'], stats_list[s], time_keys)
            
    return updated_postprocessing

