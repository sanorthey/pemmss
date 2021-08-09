"""
Module with routines for exporting PEMMSS model results and data files.

  export_log()
  export_projects()
  export_list_of_dictionary()
  export_project_dictionary()
  export_demand()
  export_statistics()
  export_statistics_flat()

  TODO: 1. Add copyright to docstring
  TODO: 2. Add cross-references to journal article
  TODO: 3. Check this docstring after all other todos removed

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

    TODO: Improve docstrings
    """
    with open(output_path, 'w+', newline='') as output_file:
        w = csv.writer(output_file, delimiter=',')
        w.writerow(("P_ID_NUMBER", "PROJECT_NAME", 'REGION', 'DEPOSIT_TYPE',
                    'COMMODITY', 'INITIAL_RESOURCE', 'REMAINING_RESOURCE',
                    "GRADE", 'RECOVERY', 'PRODUCTION_CAPACITY', 'STATUS',
                    'STATUS_INITIAL', 'VALUE', 'DISCOVERY_YEAR',
                    'START_YEAR', 'END_YEAR', 'BROWNFIELD_TONNAGE_FACTOR',
                    'BROWNFIELD_GRADE_FACTOR', 'AGGREGATION'))
        for p in project_list:
            w.writerow([p.id_number, p.name, p.region, p.deposit_type,
                        p.commodity, p.initial_resource, p.remaining_resource,
                        p.grade, p.recovery, p.production_capacity, p.status,
                        p.status_initial, p.value, p.discovery_year,
                        p.start_year, p.end_year, p.brownfield['tonnage'],
                        p.brownfield['grade'], p.aggregation])
    output_file.close()


def export_list_of_dictionary(path, list_of_dictionary, header='None', id_key='None'):
    """
    Exports a csv file with a header row,
    with subsequent rows for each dictionary contained in a list of dictionaries.

    # TODO: improve docstrings
    # TODO: describe id_key functionality
    """
    # Exports values to a csv from a dictionary for a defined list of keys.
    # Writes keys as a header row.
    # If header == 'None', generate header row from dictionary keys.
    # If key != 'None', add the key to the header row.
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

    if os.path.isfile(path) == 0:
        existing = 0
    else:
        existing = 1

    with open(path, 'a', newline='') as output_file:
        w = csv.DictWriter(output_file, export_header)
        if existing == 0:
            w.writeheader()
        # Test
        for dic in list_of_dictionary:
            w.writerow(dic)
    output_file.close()


def export_project_dictionary(path, project_list, variable, header='None', id_key='id_number', commodity='None'):
    """
    Generates a list of project dictionaries
    path
    project_list         |
    variable             |
    header [optional]    | A list of dictionary keys to export (e.g. [2010,2011,2012])
                           If left as default 'None' will return all
    id_key [optional]    | Use to specify a custom project key variable for the export file
                           (e.g. Mine.name, Mine.deposit_type, Mine.region).
                           Useful for exporting data for quick aggregation (e.g. by deposit_type).
    commodity [optional] | Use to specify a commodity sub-dictionary
                           (e.g. for Mine.production_intermediate[commodity], Mine.grade[commodity])

    TODO: Update docstrings
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
        else:
            print('Unable to export Mine.'+str(variable)+' as the type is not dict.')
    export_list_of_dictionary(path, list_of_dictionary, header, key)


def export_demand(output_path, demand):
    """
    Exports a .csv with demand data
    imported_demand{scenario_name: {commodity: {'balance_supply': 1 or 0,
                                                'intermediate_recovery': 0 to 1,
                                                'demand_threshold': 0 to 1,
                                                'demand_carry': float(),
                                                year: commodity demand}}}
    TODO: Update docstrings
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

def export_statistics_flat(path, stats_flat_dict, time_range):
    """
    Exports values to a csv from a flat stats data structure
    exp_stats = {(i,j,a,r,d,c,s):{t:}}
    header = ([i,j,a,r,d,c,s], [t1,t2,t3,etc.])
    i.e. header[0] = key     |    header[1] = time keys
    TODO: update docstrings to describe variable naming
    TODO: refactor to file_export.export_statistics()
    """
    if os.path.isfile(path) == 0:
        existing = 0
    else:
        existing = 1
    
    header = ['SCENARIO_INDEX', 'ITERATION', 'AGGREGATION', 'REGION', 'DEPOSIT_TYPE', 'COMMODITY', 'STATISTIC']
    header.extend(time_range)

    with open(path, 'a', newline='') as output_file:
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

