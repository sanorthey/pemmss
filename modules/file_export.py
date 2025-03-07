"""
Module with routines for exporting PEMMSS model results and data files.

  export_log()
  export_projects()
  export_list_of_dictionary()
  export_project_dictionary()
  export_demand()
  export_statistics()

"""

# Import standard packages
import csv
import os

# Import custom modules

def export_log(entry, output_path='log.txt', print_on=0):
    """
    Exports a custom log message ('entry') to the file designated by 'output_path' 
    If the file exists than the entry will be appended, otherwise a new file will be created.
    If 'print_on' == 1 then the entry will also be printed in the console.
    """
    with open(output_path, mode='a') as output_file:
        e = str(entry)+'\n'
        output_file.write(e)
        if print_on == 1:
            print(str(entry))


def export_projects(output_path, project_list):
    """
    Exports project data to a csv file.
    Output csv has similar headers to the input.csv, with a few modifications.
    Parameter dictionaries will be outputted in some cases.
    Does not output timeseries data (e.g. production_ore, production_intermediate, brownfield).

    output_path  | file path of export .csv
    project_list | list of Mine objects
    """
    with open(output_path, 'w+', newline='') as output_file:
        w = csv.writer(output_file, delimiter=',')
        w.writerow(("P_ID_NUMBER", "PROJECT_NAME", 'REGION', 'LATITUDE', 'LONGITUDE','DEPOSIT_TYPE',
                    'COMMODITY', 'RESOURCE_INITIAL', 'REMAINING_RESOURCE',
                    "GRADE", 'INITIAL_GRADE', 'RECOVERY', 'PRODUCTION_CAPACITY', 'STATUS',
                    'INITIAL_STATUS', 'DISCOVERY_YEAR',
                    'START_YEAR', 'END_YEAR', 'DEVELOPMENT_PROBABILITY', 'BROWNFIELD_TONNAGE_FACTOR',
                    'BROWNFIELD_GRADE_FACTOR', 'AGGREGATION', 'VALUE', 'VALUE_FACTORS'))
        for p in project_list:
            w.writerow([p.id_number, p.name, p.region, p.latitude, p.longitude, p.deposit_type,
                        p.commodity, p.initial_resource, p.remaining_resource,
                        p.grade, p.initial_grade, p.recovery, p.production_capacity, p.status,
                        p.initial_status, p.discovery_year,
                        p.start_year, p.end_year, p.development_probability, p.brownfield_tonnage,
                        p.brownfield_grade, p.aggregation, p.value, p.value_factors])
    output_file.close()


def export_list_of_dictionary(path, list_of_dictionary, header='None', id_key='None'):
    """
    Exports a csv file with a header row of keys, with subsequent rows for each dictionary contained in a list of dictionaries.

    Writes keys as a header row.
    path               | file path of export .csv
    list_of_dictionary | [{k:v, k:v},{k:v, k:v}, etc.]
    header             | 'None' = generate header row from dictionary keys
                       | [h0, h1, h2, etc]
    id_key             | 'None'
                       | key = key added to start of header list, only if header is not 'None'
    """

    if header == 'None':
        keys = {}
        for dic in list_of_dictionary:
            for k in dic:
                keys.update({k: ''})
        export_header = list(keys)
    else:
        export_header = header
        if id_key != 'None':
            export_header.insert(0, id_key)

    if os.path.isfile(path) is False:
        existing = False
    else:
        existing = True

    with open(path, 'a', newline='') as output_file:
        w = csv.DictWriter(output_file, export_header)
        if existing is False:
            w.writeheader()
        for dic in list_of_dictionary:
            w.writerow(dic)
    output_file.close()


def export_project_dictionary(path, project_list, variable, header='None', id_key='id_number', commodity='None', log_path='None'):
    """
    Generates a list of project dictionaries
    path                 | file path of export .csv
    project_list         | list of Mine objects to be exported.
    variable             | String of mine object dictionary name to be exported (e.g. 'production_intermediate')
    header [optional]    | A list of dictionary keys to export (e.g. [2010,2011,2012])
                           If left as default 'None' will return all
    id_key [optional]    | Use to specify a custom project key variable for the export file
                           (e.g. Mine.name, Mine.deposit_type, Mine.region).
                           Useful for exporting data for quick aggregation (e.g. by deposit_type).
    commodity [optional] | Use to specify a commodity sub-dictionary
                           (e.g. for Mine.production_intermediate[commodity], Mine.grade[commodity])
    """
    list_of_dictionary = []
    for p in project_list:
        if id_key == 'id_number':
            # Append 'p_' to ensure consistency with input files.
            key = 'P_ID_NUMBER'
        else:
            key = str(id_key).upper()

        list_of_dictionary.append({key: p.get(id_key, commodity)})
        p_dictionary = p.get(variable, commodity)
        if type(p_dictionary) == dict:
            list_of_dictionary[-1].update(p_dictionary)
        elif log_path is not None:
            export_log('Unable to export Mine.'+str(variable)+' as the type is not dict.', output_path=log_path, print_on=1)
    export_list_of_dictionary(path, list_of_dictionary, header, key)


def export_demand(output_path, demand):
    """
    Exports a .csv with a timeseries of residual commodity demand data
    output_path | file path of export .csv
    imported_demand{scenario_name: {commodity: {'balance_supply': 1 or 0,
                                                'intermediate_recovery': 0 to 1,
                                                'demand_threshold': 0 to 1,
                                                'demand_carry': float(),
                                                year: commodity demand}}}
    """
    header = ['commodity']
    for c in demand:
        for k in demand[c].keys():
            if k not in header:
                header.append(k)
    with open(output_path, 'w+', newline='') as output_file:
        w = csv.DictWriter(output_file, header, delimiter=',')
        w.writeheader()
        for c in demand:
            dict_to_write = demand[c]
            dict_to_write.update({'commodity': c})
            w.writerow(dict_to_write)
    output_file.close()


def export_statistics(path, stats_flat_dict, time_range):
    """
    Exports values to a csv from the stats data structure
    exp_stats = {(i,j,a,r,d,c,s):{t:}}
    header = ([i,j,a,r,d,c,s], [t1,t2,t3,etc.])
    i.e. header[0] = key     |    header[1] = time keys
    """
    if os.path.isfile(path) == 0:
        existing = 0
    else:
        existing = 1
    
    header = ['SCENARIO_INDEX', 'ITERATION', 'AGGREGATION', 'REGION', 'DEPOSIT_TYPE', 'COMMODITY', 'STATISTIC']
    header.extend(time_range)

    with open(path, 'a', newline='', encoding='UTF-8') as output_file:
        w = csv.DictWriter(output_file, header)
        if existing == 0:
            w.writeheader()

        # Unpack stats_flat_dict
        for k, time_dict in stats_flat_dict.items():
            dict_to_write = {'SCENARIO_INDEX': k[0], 'ITERATION': k[1], 'AGGREGATION': k[2], 'REGION': k[3], 'DEPOSIT_TYPE': k[4], 'COMMODITY': k[5], 'STATISTIC': k[6]}

            for t in time_dict:
                if t in time_range:
                    # This check required because some stats can be generated outside of scenario time range.
                    dict_to_write.update({t: time_dict[t]})
            w.writerow(dict_to_write)


def export_plot_subplot_data(path, plot_data):
    """
    Exports plot and subplot series to a .csv file.
    path |  file path of export .csv
    data = {plot: {subplot: {label: {x: [values],
                                     y: [values]}}}
    """
    with open(path, 'w+', newline='') as output_file:
        w = csv.writer(output_file, delimiter=',')
        w.writerow(['SUBPLOT', 'LABEL', 'LEGEND_TEXT', 'CUMULATIVE', 'SERIES', 'AXIS', 'VALUES'])
        for subplot in plot_data:
            for label in plot_data[subplot]:
                for n, x_series in enumerate(plot_data[subplot][label]['x']):
                    x_row = [str(subplot), str(label), plot_data[subplot][label]['legend_text'], plot_data[subplot][label]['cumulative'], n, 'x']
                    y_row = [str(subplot), str(label), plot_data[subplot][label]['legend_text'], plot_data[subplot][label]['cumulative'], n, 'y']
                    x_row.extend(x_series)
                    y_row.extend(plot_data[subplot][label]['y'][n])
                    w.writerow(x_row)
                    w.writerow(y_row)
    output_file.close()

