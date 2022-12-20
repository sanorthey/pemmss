# -*- coding: utf-8 -*-
"""
Module with routines for importing PEMMSS model parameters and data files.
    import_static_files()
    import_parameters()
    import_projects()
    import_project_coproducts()
    import_exploration_production_factors()
    import_exploration_production_factors_timeseries()
    timeseries_dictionary_merge_row()
    import_demand()
    import_graphs()
    import_graphs_formatting()
    import_postprocessing()
    import_historic()
    import_statistics()
    import_statistics_keyed()
"""

# Import standard packages
import csv
from shutil import copyfile
from collections import defaultdict
from random import choices
from distutils.util import strtobool

# Import custom modules
import modules.deposit as deposit
from modules.file_export import export_log


#Import Data Functions

def import_static_files(path, copy_path_folder=None, log_file=None):
    """
    import_static_files()
    Imports the input files that don't need to be reimported through the model run.
    Imports:
        input_parameters.csv
        input_exploration_production_factors.csv
        input_exploration_production_factors_timeseries.csv
        input_demand.csv
        input_graphs.csv
        input_postprocessing.csv
        input_historic.csv
    Files will be copied to copy_path_folder if specified.
    Returns file structures within a tuple
    """
    static_files = {}
    static_files['parameters'] = import_parameters(path, copy_path=copy_path_folder, log_path=log_file)
    static_files['imported_factors'] = import_exploration_production_factors(path, copy_path=copy_path_folder, log_path=log_file)
    static_files['timeseries_project_updates'], static_files['timeseries_exploration_production_factors_updates'] = import_exploration_production_factors_timeseries(path, copy_path=copy_path_folder, log_path=log_file)
    static_files['imported_demand'] = import_demand(path, copy_path=copy_path_folder, log_path=log_file)
    static_files['imported_graphs'] = import_graphs(path, copy_path=copy_path_folder, log_path=log_file)
    static_files['imported_graphs_formatting'] = import_graphs_formatting(path, copy_path=copy_path_folder, log_path=log_file)
    static_files['imported_postprocessing'] = import_postprocessing(path, copy_path=copy_path_folder, log_path=log_file)
    static_files['imported_historic'] = import_historic(path, copy_path=copy_path_folder, log_path=log_file)

    return static_files


def import_parameters(path, copy_path=None, log_path=None):
    """
    import_parameters()
    Imports parameters from input_parameters.csv located at 'path'.
    Typical path is \WORKING DIRECTORY\input_files\input_parameters.csv

    Returns a nested dictionary [i]['key'], where i is each scenario run.

    Copies input_parameters if copy_path directory specified.

    # Each scenario_name must be unique in input files.

    Returns a list of dictionaries [{row0_keys: row0_values}, {row1_keys: row1_values}, etc.

    Files will be copied to copy_path_folder if specified.

    Expected input csv format:
        KEYS              |   ACCEPTABLE INPUT VALUES    |   Definition
        SCENARIO_NAME     |   string, must match scenario name in input_demand.csv
        YEAR_START        |   integer, must correspond to initial time period in input_demand.csv
        YEAR_END          |   integer, must correspond to last time period in input_demand.csv
        ITERATIONS        |   integer              |   Number of times each scenario is repeated
        BROWNFIELD_EXPLORATION_ON    |   1 or 0    |   Turns brownfield exploration on or off
        GREENFIELD_EXPLORATION_ON    |   1 or 0    |   Turns demand-triggered greenfield deposit discovery on or off
        GREENFIELD_BACKGROUND        |   integer   |   Number of background greenfield deposit discoveries per time period
        PRIORITY_ACTIVE   |   1 or 0               |   Whether active mines can be prioritised ahead of undeveloped mines/deposits
        PRIORITY_MARGINAL |   1 or 0               |   Determines whether mines/deposits are prioritised based on the marginal net value of the current_tranche or their overall net value
        MARGINAL_RECOVERY |   1 or 0               |   Determines whether commodity recovery only occurs when there is a positive marginal recovery value of the current_tranche or by the overall recovery value
        RANDOM_SEED       |   float or integer     |   Seeds random functions for reproduceability of results
        GENERATE_ALL_COPRODUCTS      |   1 or 0    |   Whether to only add coproducts to those in input_projects_coproducts.csv or instead generate for all projects. See import_project_coproducts()
        UPDATE_VALUES     |   1 or 0               |   Whether to update mine/deposit values at each timestep

    """
    imported_parameters = {}

    with open(path + r'\\input_parameters.csv', mode='r') as parameters_file:
        csv_reader = csv.DictReader(parameters_file)
        #Import scenarios
        for row in csv_reader:
            imported_parameters.update({row['SCENARIO_NAME']: {'scenario_name': str(row['SCENARIO_NAME']),
                                                               'year_start': int(row['YEAR_START']),
                                                               'year_end': int(row['YEAR_END']),
                                                               'iterations': int(row["ITERATIONS"]),
                                                               'brownfield_exploration_on': int(row['BROWNFIELD_EXPLORATION_ON']),
                                                               'greenfield_exploration_on': int(row['GREENFIELD_EXPLORATION_ON']),
                                                               'greenfield_background': int(row['GREENFIELD_BACKGROUND']),
                                                               'priority_active': int(row['PRIORITY_ACTIVE']),
                                                               'priority_marginal': int(row['PRIORITY_MARGINAL']),
                                                               'marginal_recovery': int(row['MARGINAL_RECOVERY']),
                                                               'random_seed': float(row['RANDOM_SEED']),
                                                               'generate_all_coproducts': int(row['GENERATE_ALL_COPRODUCTS']),
                                                               'update_values': int(row['UPDATE_VALUES'])}})
    if copy_path is not None:
        copyfile(path + r'\\input_parameters.csv', copy_path + r'\\input_parameters.csv')
    if log_path is not None:
        export_log('Imported input_parameters.csv', output_path=log_path, print_on=1)
    return imported_parameters


def import_projects(f, path, copy_path=None, log_path=None):
    """
    import_projects()
    Imports projects from input_projects.csv in the working directory.
    Output is a list of Mine() objects
    Missing variables are infilled using a variety of approaches,
    based upon parameters defined in input_exploration_production_factors.csv.
    P_ID_NUMBER should start sequentially from zero to avoid P_ID collisions when generating greenfield deposits.

    File will be copied to copy_path if specified.

    Expected csv format:
        KEYS                 | ACCEPTABLE INPUT VALUES
        P_ID_NUMBER          | integer or string, optional
        NAME                 | string, optional
        REGION               | string, optional
        DEPOSIT_TYPE         | string, optional
        COMMODITY            | string, optional
        REMAINING_RESOURCE   | float, tranches separated by ";", optional
        PRODUCTION_CAPACITY  | float, optional
        STATUS               | integer, 1 or 0
        DISCOVERY_YEAR       | integer, optional
        START_YEAR           | integer, optional
        DEVELOPMENT_PROBABILITY    | float, optional
        GRADE                | float, tranches separated by ";", optional
        RECOVERY             | float, optional
        BROWNFIELD_TONNAGE_FACTOR  | float, optional
        BROWNFIELD_GRADE_FACTOR    | float, optional
        VALUE_NET            | float, tranches separated by ";", optional, Note: will autogenerate if VALUE_RECOVERY_NET is not specified
        VALUE_RECOVERY_NET   | float, tranches separated by ";", optional, Note: will autogenerate if VALUE_NET is not specified
        MINE_COST_MODEL      | string corresponding to models in deposit.value_model(), optional
        MINE_COST_A          | value corresponding to parameter in deposit.value_model(), optional
        MINE_COST_B          | value corresponding to parameter in deposit.value_model(), optional
        MINE_COST_C          | value corresponding to parameter in deposit.value_model(), optional
        MINE_COST_D          | value corresponding to parameter in deposit.value_model(), optional
        REVENUE_MODEL        | string corresponding to models in deposit.value_model(), optional
        REVENUE_A            | value corresponding to parameter in deposit.value_model(), optional
        REVENUE_B            | value corresponding to parameter in deposit.value_model(), optional
        REVENUE_C            | value corresponding to parameter in deposit.value_model(), optional
        REVENUE_D            | value corresponding to parameter in deposit.value_model(), optional
        COST_MODEL           | string corresponding to models in deposit.value_model(), optional
        COST_A               | value corresponding to parameter in deposit.value_model(), optional
        COST_B               | value corresponding to parameter in deposit.value_model(), optional
        COST_C               | value corresponding to parameter in deposit.value_model(), optional
        COST_D               | value corresponding to parameter in deposit.value_model(), optional

    Any optional missing values will be autogenerated from input_exploration_production_factors.csv
    """
    # Tracking of missing values in input_projects.csv debugging purposes
    # and to track automated input generation processes.
    no_id_number = 0
    no_name = 0
    no_region = 0
    no_deposit_type = 0
    no_commodity = 0
    no_remaining_resource = 0
    no_grade = 0
    no_recovery = 0
    no_production_capacity = 0
    no_status = 0
    no_value = 0
    no_mine_cost_model = 0
    no_revenue_model = 0
    no_cost_model = 0
    no_discovery_year = 0
    no_start_year = 0
    no_development_probability = 0
    no_brownfield_grade_factor = 0
    no_brownfield_tonnage_factor = 0
    # Open and generate projects from input_projects.csv
    imported_projects = []


    with open(path + r'\\input_projects.csv', mode='r') as input_file:

        # Iterate through each row
        csv_reader = csv.DictReader(input_file)

        for row in csv_reader:

            if row['P_ID_NUMBER'] == "":
                no_id_number += 1
                id_number = "GEN_" + str(no_id_number)
            else:
                id_number = row['P_ID_NUMBER']
            if row['NAME'] == "":
                no_name += 1
                name = 'UNSPECIFIED'
            else:
                name = str(row['NAME'])

            if row['REGION'] != "" and row['DEPOSIT_TYPE'] != "":  # Use passed values
                region = str(row['REGION'])
                deposit_type = str(row['DEPOSIT_TYPE'])
                index = f['lookup_table'][region][deposit_type]
            elif row['REGION'] == "" and row['DEPOSIT_TYPE'] == "":  # Randomly generate region and deposit_type
                no_region += 1
                no_deposit_type += 1
                index = choices(f['index'], weights=f['weighting'])[0]
                region = str(f['region'][index])
                deposit_type = str(f['deposit_type'][index])
            elif row['REGION'] == "":  # Randomly generate region only
                no_region += 1
                deposit_type = str(row['DEPOSIT_TYPE'])
                possible_indices = [i for i in f['index'] if f['deposit_type'][i] == deposit_type]
                weightings = [f['weighting'][i] for i in possible_indices]
                index = choices(possible_indices, weights=weightings)[0]
                region = str(f['region'][index])
            else:  # Randomly generate deposit_type only
                no_deposit_type += 1
                region = str(row['REGION'])
                possible_indices = [i for i in f['index'] if f['region'][i] == region]
                weightings = [f['weighting'][i] for i in possible_indices]
                index = choices(possible_indices, weights=weightings)[0]
                deposit_type = str(f['deposit_type'][index])

            if row['COMMODITY'] == "":
                no_commodity += 1
                commodity = f['commodity_primary'][index]
            else:
                commodity = row['COMMODITY']
            if row['GRADE'] == "":
                no_grade += 1
                grade = [deposit.grade_generate(f['grade_model'][index], {'a': f['grade_a'][index],
                                                                   'b': f['grade_b'][index],
                                                                   'c': f['grade_c'][index],
                                                                   'd': f['grade_d'][index]},
                                                log_file=log_path)]
            else:
                grade = [float(x) for x in row['GRADE'].split(';')]
            if row['REMAINING_RESOURCE'] == "":
                no_remaining_resource += 1
                remaining_resource = [deposit.tonnage_generate(f['tonnage_model'][index],
                                                              {'a': f['tonnage_a'][index],
                                                               'b': f['tonnage_b'][index],
                                                               'c': f['tonnage_c'][index],
                                                               'd': f['tonnage_d'][index]},
                                                               grade, log_file=log_path)]
            else:
                remaining_resource = [float(x) for x in row['REMAINING_RESOURCE'].split(';')]
            if row['RECOVERY'] == "":
                no_recovery += 1
                recovery = float(f['recovery'][index])
            else:
                recovery = float(row['RECOVERY'])
            if row['PRODUCTION_CAPACITY'] == "":
                no_production_capacity += 1
                production_capacity = deposit.capacity_generate(remaining_resource,
                                                                f['capacity_a'][index],
                                                                f['capacity_b'][index],
                                                                f['capacity_sigma'][index],
                                                                f['life_min'][index],
                                                                f['life_max'][index])
            else:
                production_capacity = float(row['PRODUCTION_CAPACITY'])
            if row['STATUS'] == "":
                no_status += 1
                status = 0
            else:
                status = int(row['STATUS'])

            value_factors = {'MINE': {}, commodity: {}}

            if row['MINE_COST_MODEL'] == '':
                no_mine_cost_model += 1
                value_factors['MINE'].update({'cost': {'model': f['mine_cost_model'][index],
                                                       'a': f['mine_cost_a'][index],
                                                       'b': f['mine_cost_b'][index],
                                                       'c': f['mine_cost_c'][index],
                                                       'd': f['mine_cost_d'][index]}})
            else:
                value_factors['MINE'].update({'cost': {'model': row['MINE_COST_MODEL'],
                                                       'a': row['MINE_COST_A'],
                                                       'b': row['MINE_COST_B'],
                                                       'c': row['MINE_COST_C'],
                                                       'd': row['MINE_COST_D']}})
            if row['REVENUE_MODEL'] == '':
                no_revenue_model += 1
                value_factors[commodity].update({'revenue': {'model': f['revenue_model'][index],
                                                             'a': f['revenue_a'][index],
                                                             'b': f['revenue_b'][index],
                                                             'c': f['revenue_c'][index],
                                                             'd': f['revenue_d'][index]}})
            else:
                value_factors[commodity].update({'revenue': {'model': row['REVENUE_MODEL'],
                                                             'a': row['REVENUE_A'],
                                                             'b': row['REVENUE_B'],
                                                             'c': row['REVENUE_C'],
                                                             'd': row['REVENUE_D']}})
            if row['COST_MODEL'] == '':
                no_cost_model += 1
                value_factors[commodity].update({'cost': {'model': f['cost_model'][index],
                                                          'a': f['cost_a'][index],
                                                          'b': f['cost_b'][index],
                                                          'c': f['cost_c'][index],
                                                          'd': f['cost_d'][index]}})
            else:
                value_factors[commodity].update({'cost': {'model': row['COST_MODEL'],
                                                          'a': row['COST_A'],
                                                          'b': row['COST_B'],
                                                          'c': row['COST_C'],
                                                          'd': row['COST_D']}})
            if row['VALUE_NET'] == "" or row['VALUE_RECOVERY_NET']:
                no_value += 1
                value = {'ALL': {}, commodity: {}}
                v_update = True
            else:
                value = {'ALL': {'ALL': float(0), commodity: float(0)}}
                net_values = [float(x) for x in row['VALUE_NET'].split(';')]
                commodity_recovery_values = [float(x) for x in row['VALUE_NET'].split(';')]
                for tranche, values in enumerate(zip(net_values, commodity_recovery_values)):
                    value.update({tranche: {'ALL': values[0], commodity: values[1]}})
                    value['ALL']['ALL'] += values[0]
                    value['ALL'][commodity] += values[1]
                v_update = False

            if row['DISCOVERY_YEAR'] == "":
                no_discovery_year += 1
                discovery_year = -9999
            else:
                discovery_year = int(row['DISCOVERY_YEAR'])
            if row['START_YEAR'] == "":
                no_start_year += 1
                if row['STATUS'] == 1:
                    start_year = -9999
                else:
                    start_year = None
            else:
                start_year = int(row['START_YEAR'])
            if row['DEVELOPMENT_PROBABILITY'] == "":
                no_development_probability += 1
            else:
                development_probability = float(row['DEVELOPMENT_PROBABILITY'])
            if row['BROWNFIELD_TONNAGE_FACTOR'] == "":
                no_brownfield_tonnage_factor += 1
                brownfield_tonnage = f['brownfield_tonnage_factor'][index]
            else:
                brownfield_tonnage = float(row['BROWNFIELD_TONNAGE_FACTOR'])
            if row['BROWNFIELD_GRADE_FACTOR'] == "":
                no_brownfield_grade_factor += 1
                brownfield_grade = f['brownfield_grade_factor'][index]
            else:
                brownfield_grade = float(row['BROWNFIELD_GRADE_FACTOR'])

            # Project aggregation descriptor
            if int(row['STATUS']) == 1:
                if row['START_YEAR'] == "":
                    aggregation = 'Existing Mines'
                else:
                    aggregation = 'Existing Mines with defined start year'
            else:
                if row['START_YEAR'] == "":
                    aggregation = 'Identified Resources'
                else:
                    aggregation = 'Identified Resources with defined start year'
            imported_projects.append(
                deposit.Mine(id_number, name, region, deposit_type, commodity, remaining_resource,
                             grade, recovery, production_capacity, status, value, discovery_year,
                             start_year, development_probability, brownfield_tonnage, brownfield_grade, value_factors, aggregation, value_update=v_update))

    if copy_path is not None:
        copyfile(path + r'\\input_projects.csv', copy_path + r'\\input_projects.csv')

    if log_path is not None:
        export_log('Imported input_projects.csv', output_path=log_path, print_on=0)
        export_log('Imported ' + str(len(imported_projects)) + ' projects. \n\nCount of project blank entries:', output_path=log_path)
        export_log(str(no_id_number) + ' : id_number. Missing values generated by system.', output_path=log_path)
        export_log(str(no_name) + ' : name. Missing names set as UNSPECIFIED.', output_path=log_path)
        export_log(str(no_region) + ' : region. Missing regions selected randomly from weighted options.', output_path=log_path)
        export_log(str(no_deposit_type) + ' : deposit_type. Missing deposit types selected randomly from weighted options.', output_path=log_path)
        export_log(str(no_commodity) + ' : commodity. Missing commodity lists assigned corresponding to deposit type.', output_path=log_path)
        export_log(str(no_remaining_resource) + ' : remaining_resource. Remaining resource generated using region-deposit type specific size models.', output_path=log_path)
        export_log(str(no_grade) + ' : grade. Missing grades generated using region-deposit type specific grade models.', output_path=log_path)
        export_log(str(no_recovery) + ' : recovery. Missing recovery factors assigned to default value.', output_path=log_path)
        export_log(str(no_production_capacity) + " : production capacity. Missing production capacity generated using taylor's law functions.", output_path=log_path)
        export_log(str(no_status) + ' : status. Missing status assigned to 0', output_path=log_path)
        export_log(str(no_value) + ' : value. Missing values assigned using the value, revenue and cost models for the specific region and deposit type.', output_path=log_path)
        export_log(str(no_discovery_year) + ' : discovery_year. Missing discovery year set to -9999', output_path=log_path)
        export_log(str(no_start_year) + ' : start_year. Missing start year left blank for inactive mines or set to -9999 for active mines', output_path=log_path)
        export_log(str(no_development_probability) + ' : development_probability. Missing values from input_exploration_production_factors.csv', output_path=log_path)
        export_log(str(no_brownfield_grade_factor) + ' : brownfield_grade_factor. Missing values assigned from input_exploration_production_factors.csv', output_path=log_path)
        export_log(str(no_brownfield_tonnage_factor) + ' : brownfield_grade_factor. Missing values assigned from input_exploration_production_factors.csv', output_path=log_path)

    return imported_projects


def import_project_coproducts(f, path, projects, generate_all, copy_path=None, log_path=None):
    """
    import_project_coproducts(path):
    Imports and adds coproduct parameters to projects from input_project_coproducts.csv located in the working directory.
    f = exploration_production_factors
    generate_all | If 1, update projects only listed in input_project_coproducts.csv. If 0, also update all other projects with data from exploration_production_factors.csv.

    File will be copied to copy_path if specified.

    Expected csv format:
        KEYS                |   ACCEPTABLE INPUT VALUES
        P_ID_NUMBER         |   ID number of project to be updated, can be blank if generate_all == True
        NAME                |   string, isn't used currently. Just for readability of csv.
        REGION              |   string, must specify
        DEPOSIT_TYPE        |   string, must specify
        COPRODUCT_COMMODITY |   string, must specify
        COPRODUCT_GRADE     |   float, tranches separated by ";", or will autogenerate if blank.
        COPRODUCT_RECOVERY  |   float, or will autogenerate if blank.
        SUPPLY_TRIGGER      |   1 or 0, or will autogenerate if blank.
        COPRODUCT_BROWNFIELD_GRADE_FACTOR       |   float, or will autogenerate if blank.

    Currently autogenerates value models from data in input_exploration_production_factors.csv
    """

    with open(path+r'\\input_project_coproducts.csv', mode='r') as input_file:

        csv_reader = csv.DictReader(input_file)

        entries = 0
        skipped = 0
        generated_grades = 0
        generated_recovery = 0
        generated_supply_trigger = 0
        generated_brownfield_grade_factor = 0
        for row in csv_reader:
            for p in projects:
                index = f['lookup_table'][p.region][p.deposit_type]
                if p.id_number == row['P_ID_NUMBER']:
                    # Manual inputs for the project are listed in input_project_coproducts.csv
                    if row['COPRODUCT_COMMODITY'] == '':
                        skipped += 1
                        export_log('Error: Must specify COPRODUCT_COMMODITY for all projects in inputs_projects_coproducts.csv. Rows with missing coproduct commodity names skipped.', out_path=log_path)
                    else:
                        entries += 1
                        c = row['COPRODUCT_COMMODITY']
                        for x in range(0, len(f['coproduct_commodity'][index])):
                            if len(f['coproduct_commodity'][index]) != 0:
                                if f['coproduct_commodity'][index][x] == row['COPRODUCT_COMMODITY']:
                                    if row['COPRODUCT_GRADE'] == '':
                                        # Generate grade from the region and deposit type grade model
                                        g = [deposit.coproduct_grade_generate(p, f, index, x, log_file=log_path)]
                                        generated_grades += 1
                                    else:
                                        # Use inputted coproduct grade
                                        g = [float(x) for x in row['COPRODUCT_GRADE'].split(";")]
                                    if row['COPRODUCT_RECOVERY'] == '':
                                        # Use default coproduct recovery for the region and deposit type
                                        r = float(f['coproduct_recovery'][index][x])
                                        generated_recovery += 1
                                    else:
                                        # Use inputted coproduct recovery
                                        r = float(row['COPRODUCT_RECOVERY'])
                                    if row['SUPPLY_TRIGGER']:
                                        # Use default coproduct supply trigger for the region and deposit type
                                        st = float(f['coproduct_supply_trigger'][index][x])
                                        generated_supply_trigger += 1
                                    else:
                                        # Use inputted supply trigger
                                        st = float(row['SUPPLY_TRIGGER'])
                                    if row['COPRODUCT_BROWNFIELD_GRADE_FACTOR']:
                                        # Use default coproduct brownfield grade factor for the region and deposit type
                                        bgf = float(f['coproduct_brownfield_grade_factor'][index][x])
                                        generated_brownfield_grade_factor += 1
                                    else:
                                        # Use inputted brownfield grade factor
                                        bgf = float(row['COPRODUCT_BROWNFIELD_GRADE_FACTOR'])
                                    vf = {'revenue': {'model': f['coproduct_revenue_model'][index][x],
                                                      'a': float(f['coproduct_revenue_a'][index][x]),
                                                      'b': float(f['coproduct_revenue_b'][index][x]),
                                                      'c': float(f['coproduct_revenue_c'][index][x]),
                                                      'd': float(f['coproduct_revenue_d'][index][x])},
                                          'cost': {'model': f['coproduct_cost_model'][index][x],
                                                   'a': float(f['coproduct_cost_a'][index][x]),
                                                   'b': float(f['coproduct_cost_b'][index][x]),
                                                   'c': float(f['coproduct_cost_c'][index][x]),
                                                   'd': float(f['coproduct_cost_d'][index][x])}}
                                    p.add_commodity(c, g, r, st, bgf, vf, log_file=log_path)
                elif generate_all == 1:
                    # Generate project coproduct parameters using the region and production factors given in input_exploration_production_factors.csv
                    for x in range(0, len(f['coproduct_commodity'][index])):
                        if len(f['coproduct_commodity'][index]) != 0:
                            c = f['coproduct_commodity'][index][x]
                            if c != '':
                                g = [deposit.coproduct_grade_generate(p, f, index, x, log_file=log_path)]
                                r = float(f['coproduct_recovery'][index][x])
                                st = float(f['coproduct_supply_trigger'][index][x])
                                bgf = float(f['coproduct_brownfield_grade_factor'][index][x])
                                vf = {'revenue': {'model': f['coproduct_revenue_model'][index][x],
                                                  'a': float(f['coproduct_revenue_a'][index][x]),
                                                  'b': float(f['coproduct_revenue_b'][index][x]),
                                                  'c': float(f['coproduct_revenue_c'][index][x]),
                                                  'd': float(f['coproduct_revenue_d'][index][x])},
                                      'cost': {'model': f['coproduct_cost_model'][index][x],
                                               'a': float(f['coproduct_cost_a'][index][x]),
                                               'b': float(f['coproduct_cost_b'][index][x]),
                                               'c': float(f['coproduct_cost_c'][index][x]),
                                               'd': float(f['coproduct_cost_d'][index][x])}}

                                p.add_commodity(c, g, r, st, bgf, vf, log_file=log_path)
                                generated_grades += 1
                                generated_recovery += 1
                                generated_supply_trigger += 1
                                generated_brownfield_grade_factor += 1
    if copy_path is not None:
        copyfile(path + r'\\input_project_coproducts.csv', copy_path + r'\\input_project_coproducts.csv')

    if log_path is not None:
        export_log('Imported input_projects_coproducts.csv', output_path=log_path, print_on=0)
        export_log('Added ' + str(entries)+' new coproduct entries. '+str(skipped)+' skipped (check log file for details). '+str(generated_grades)+' grade, '+str(generated_recovery)+' recovery, '+str(generated_supply_trigger)+' supply trigger, and '+str(generated_brownfield_grade_factor)+' brownfield grade factors generated from factors in input_exploration_production.csv.', output_path=log_path, print_on=0)
    return projects


def import_exploration_production_factors(path, copy_path=None, log_path=None):
    """
    import_exploration_production_factors()
    Imports parameters from input_exploration_production_factors.csv located in the working directory.
    Returns a dictionary, imported_factors[variable][index]

    Files will be copied to copy_path_folder if specified.

    Expected csv format: header is imported_factors.keys.upper(), excluding 'lookup_table' key.
    For column description see in-line comments.
    """
    imported_factors = {'index': [], 'weighting': [], 'region': [], 'deposit_type': [], 'commodity_primary': [],
                        'grade_model': [], 'grade_a': [], 'grade_b': [], 'grade_c': [], 'grade_d': [],
                        'tonnage_model': [], 'tonnage_a': [], 'tonnage_b': [], 'tonnage_c': [], 'tonnage_d': [],
                        'brownfield_tonnage_factor': [], 'brownfield_grade_factor': [],
                        'capacity_a': [], 'capacity_b': [], 'capacity_sigma': [], 'life_min': [], 'life_max': [],
                        'recovery': [],
                        'revenue_model': [], 'revenue_a': [], 'revenue_b': [], 'revenue_c': [], 'revenue_d': [],
                        'cost_model': [], 'cost_a': [], 'cost_b': [], 'cost_c': [], 'cost_d': [],
                        'mine_cost_model': [], 'mine_cost_a': [], 'mine_cost_b': [], 'mine_cost_c': [], 'mine_cost_d': [],
                        'development_period': [], 'development_probability': [], 'coproduct_commodity': [],
                        'coproduct_grade_model': [], 'coproduct_a': [], 'coproduct_b': [], 'coproduct_c': [], 'coproduct_d': [],
                        'coproduct_recovery': [], 'coproduct_supply_trigger': [], 'coproduct_brownfield_grade_factor': [],
                        'coproduct_revenue_model': [], 'coproduct_revenue_a': [], 'coproduct_revenue_b': [], 'coproduct_revenue_c': [], 'coproduct_revenue_d': [],
                        'coproduct_cost_model': [], 'coproduct_cost_a': [], 'coproduct_cost_b': [], 'coproduct_cost_c': [], 'coproduct_cost_d': [],
                        'lookup_table': {}}

    with open(path+r'\\input_exploration_production_factors.csv', mode='r') as parameters_file:
        csv_reader = csv.DictReader(parameters_file)
        #Import scenarios
        for row in csv_reader:
            imported_factors['index'].append(int(row['INDEX']))  # Sequential integers starting at 0
            imported_factors['weighting'].append(float(row['WEIGHTING']))  # Probability of greenfield discovery, float
            imported_factors['region'].append(row['REGION'])  # string
            imported_factors['deposit_type'].append(row['DEPOSIT_TYPE'])  # string
            imported_factors['commodity_primary'].append(row['COMMODITY_PRIMARY'])  # string, corresponding commodities in input_demand.csv
            imported_factors['grade_model'].append(row['GRADE_MODEL'])  # string, corresponding to models in deposit.grade_generate()
            imported_factors['grade_a'].append(float(row['GRADE_A']))  # value, see model parameter in deposit.grade_generate()
            imported_factors['grade_b'].append(float(row['GRADE_B']))  # value, see model parameter in deposit.grade_generate()
            imported_factors['grade_c'].append(float(row['GRADE_C']))  # value, see model parameter in deposit.grade_generate()
            imported_factors['grade_d'].append(float(row['GRADE_D']))  # value, see model parameter in deposit.grade_generate()
            imported_factors['tonnage_model'].append(row['TONNAGE_MODEL'])  # string, corresponding to models in deposit.tonnage_generate()
            imported_factors['tonnage_a'].append(float(row['TONNAGE_A']))  # value, see model parameter in deposit.tonnage_generate()
            imported_factors['tonnage_b'].append(float(row['TONNAGE_B']))  # value, see model parameter in deposit.tonnage_generate()
            imported_factors['tonnage_c'].append(float(row['TONNAGE_C']))  # value, see model parameter in deposit.tonnage_generate()
            imported_factors['tonnage_d'].append(float(row['TONNAGE_D']))  # value, see model parameter in deposit.tonnage_generate()
            imported_factors['brownfield_tonnage_factor'].append(float(row['BROWNFIELD_TONNAGE_FACTOR']))  # Ratio of remaining resource added each time period, float, see deposit.Mine.resource_expansion()
            imported_factors['brownfield_grade_factor'].append(float(row['BROWNFIELD_GRADE_FACTOR']))  # Ratio, grade adjuster for added ore, float, see deposit.Mine.resource_expansion()
            imported_factors['capacity_a'].append(float(row['CAPACITY_A']))  # float, y = a*tonnage^b, see deposit.capacity_generate()
            imported_factors['capacity_b'].append(float(row['CAPACITY_B']))  # float, y = a*tonnage^b, see deposit.capacity_generate()
            imported_factors['capacity_sigma'].append(float(row['CAPACITY_SIGMA']))  # float, standard deviation, see deposit.capacity_generate()
            imported_factors['life_min'].append(float(row['LIFE_MIN']))  # float, minimum mine life, see deposit.capacity_generate()
            imported_factors['life_max'].append(float(row['LIFE_MAX']))  # float, maximum mine life, see deposit.capacity_generate()
            imported_factors['recovery'].append(float(row['RECOVERY']))  # Ratio, mine recovery for commodity_primary
            imported_factors['revenue_model'].append(row['REVENUE_MODEL'])  # string, corresponding to models in deposit.value_model()
            imported_factors['revenue_a'].append(float(row['REVENUE_A']))  # value, see model parameter in deposit.value_model()
            imported_factors['revenue_b'].append(float(row['REVENUE_B']))  # value, see model parameter in deposit.value_model()
            imported_factors['revenue_c'].append(float(row['REVENUE_C']))  # value, see model parameter in deposit.value_model()
            imported_factors['revenue_d'].append(float(row['REVENUE_D']))  # value, see model parameter in deposit.value_model()
            imported_factors['cost_model'].append(row['COST_MODEL'])  # string, corresponding to models in deposit.value_model()
            imported_factors['cost_a'].append(float(row['COST_A']))  # value, see model parameter in deposit.value_model()
            imported_factors['cost_b'].append(float(row['COST_B']))  # value, see model parameter in deposit.value_model()
            imported_factors['cost_c'].append(float(row['COST_C']))  # value, see model parameter in deposit.value_model()
            imported_factors['cost_d'].append(float(row['COST_D']))  # value, see model parameter in deposit.value_model()
            imported_factors['mine_cost_model'].append(row['MINE_COST_MODEL'])  # string, corresponding to models in deposit.value_model()
            imported_factors['mine_cost_a'].append(float(row['MINE_COST_A']))  # value, see model parameter in deposit.value_model()
            imported_factors['mine_cost_b'].append(float(row['MINE_COST_B']))  # value, see model parameter in deposit.value_model()
            imported_factors['mine_cost_c'].append(float(row['MINE_COST_C']))  # value, see model parameter in deposit.value_model()
            imported_factors['mine_cost_d'].append(float(row['MINE_COST_D']))  # value, see model parameter in deposit.value_model()
            imported_factors['development_period'].append(int(row['DEVELOPMENT_PERIOD']))  # integer, minimum time period between discovery and production
            imported_factors['development_probability'].append(float(row['DEVELOPMENT_PROBABILITY'])) # value (ratio), probability of deposit development when supply triggered in a given time period
            imported_factors['coproduct_commodity'].extend([row['COPRODUCT_COMMODITY'].split(';')])  # string separated by semicolons for each commodity, don't include whitespace
            imported_factors['coproduct_grade_model'].extend([row['COPRODUCT_GRADE_MODEL'].split(';')])  # strings separated by semicolons for each commodity, don't include whitespace, corresponding to models in deposit.grade_generate()
            imported_factors['coproduct_a'].extend([row['COPRODUCT_A'].split(';')])  # values separated by semicolons for each commodity, don't include whitespace, see model parameter in deposit.grade_generate()
            imported_factors['coproduct_b'].extend([row['COPRODUCT_B'].split(';')])  # values separated by semicolons for each commodity, don't include whitespace, see model parameter in deposit.grade_generate()
            imported_factors['coproduct_c'].extend([row['COPRODUCT_C'].split(';')])  # values separated by semicolons for each commodity, don't include whitespace, see model parameter in deposit.grade_generate()
            imported_factors['coproduct_d'].extend([row['COPRODUCT_D'].split(';')])  # values separated by semicolons for each commodity, don't include whitespace, see model parameter in deposit.grade_generate()
            imported_factors['coproduct_recovery'].extend([row['COPRODUCT_RECOVERY'].split(';')])  # mine recovery as a ratio, floats separated by semicolons for each commodity, don't include whitespace
            imported_factors['coproduct_supply_trigger'].extend([row['COPRODUCT_SUPPLY_TRIGGER'].split(';')])  # 1 or 0 separated by semicolons for each commodity
            imported_factors['coproduct_brownfield_grade_factor'].extend([row['COPRODUCT_BROWNFIELD_GRADE_FACTOR'].split(';')])  # values separated by semicolons for each commodity
            imported_factors['coproduct_revenue_model'].extend([row['COPRODUCT_REVENUE_MODEL'].split(';')])  # strings separated by semicolons for each commodity, don't include whitespace, corresponding to models in deposit.value_model()
            imported_factors['coproduct_revenue_a'].extend([row['COPRODUCT_REVENUE_A'].split(';')])  # values separated by semicolons for each commodity, don't include whitespace, see model parameter in deposit.value_model()
            imported_factors['coproduct_revenue_b'].extend([row['COPRODUCT_REVENUE_B'].split(';')])  # values separated by semicolons for each commodity, don't include whitespace, see model parameter in deposit.value_model()
            imported_factors['coproduct_revenue_c'].extend([row['COPRODUCT_REVENUE_C'].split(';')])  # values separated by semicolons for each commodity, don't include whitespace, see model parameter in deposit.value_model()
            imported_factors['coproduct_revenue_d'].extend([row['COPRODUCT_REVENUE_D'].split(';')])  # values separated by semicolons for each commodity, don't include whitespace, see model parameter in deposit.value_model()
            imported_factors['coproduct_cost_model'].extend([row['COPRODUCT_COST_MODEL'].split(';')])  # strings separated by semicolons for each commodity, don't include whitespace, corresponding to models in deposit.value_model()
            imported_factors['coproduct_cost_a'].extend([row['COPRODUCT_COST_A'].split(';')])  # values separated by semicolons for each commodity, don't include whitespace, see model parameter in deposit.value_model()
            imported_factors['coproduct_cost_b'].extend([row['COPRODUCT_COST_B'].split(';')])  # values separated by semicolons for each commodity, don't include whitespace, see model parameter in deposit.value_model()
            imported_factors['coproduct_cost_c'].extend([row['COPRODUCT_COST_C'].split(';')])  # values separated by semicolons for each commodity, don't include whitespace, see model parameter in deposit.value_model()
            imported_factors['coproduct_cost_d'].extend([row['COPRODUCT_COST_D'].split(';')])  # values separated by semicolons for each commodity, don't include whitespace, see model parameter in deposit.value_model()
            region_key = imported_factors['region'][-1]
            deposit_type_key = imported_factors['deposit_type'][-1]
            if region_key in imported_factors['lookup_table']:
                imported_factors['lookup_table'][region_key].update({deposit_type_key: imported_factors['index'][-1]})
            else:
                imported_factors['lookup_table'].update({region_key: {deposit_type_key: imported_factors['index'][-1]}})
    if copy_path is not None:
        copyfile(path + r'\\input_exploration_production_factors.csv', copy_path + r'\\input_exploration_production_factors.csv')
        
    if log_path is not None:
        export_log('Imported input_exploration_production_factors.csv', output_path=log_path, print_on=1)

    return imported_factors

def import_exploration_production_factors_timeseries(path, copy_path=None, log_path=None):
    """
    Import parameter overrides for each point in time from input_exploration_production_factors_timeseries.csv
    Returns two dictionaries (project updates, exploration_production_factors updates)
        of structure {year: {'region': {'deposit_type': {'variable': {'commodity': value}}}}}

    Files will be copied to copy_path_folder if specified.

    Expected csv format:
        KEYS                 | ACCEPTABLE INPUT VALUES
        UPDATE_PROJECTS      | 1 or 0. Indicates whether Mine objects with matching REGION and DEPOSIT_TYPE will be updated each time period.
        UPDATE_EXPLORATION_PRODUCTION_FACTORS  | 1 or 0. Indicates whether exploration_production_factors data structure will be updated each time period.
        REGION               | string or "ALL"
        DEPOSIT_TYPE         | string or "ALL"
        VARIABLE             | string, variable to be updated
        COMMODITY            | string
        t0, t1, t2, ..., tn  | value to update to in year t
    """
    project_updates = {}
    exploration_production_factors_updates = {}

    with open(path+r'\\input_exploration_production_factors_timeseries.csv', mode='r') as input_file:
        csv_reader = csv.DictReader(input_file)
        # Iterate through each row to populate time series of variable overrides.
        for row in csv_reader:
            #index = factors['lookup_table'][row['REGION']][row['DEPOSIT_TYPE']]
            if int(row['UPDATE_PROJECTS']) == 1:
                project_updates = timeseries_dictionary_merge_row(project_updates, row)
            if int(row['UPDATE_EXPLORATION_PRODUCTION_FACTORS']) == 1:
                exploration_production_factors_updates = timeseries_dictionary_merge_row(exploration_production_factors_updates, row)
    if copy_path is not None:
        copyfile(path + r'\\input_exploration_production_factors_timeseries.csv', copy_path + r'\\input_exploration_production_factors_timeseries.csv')
    
    if log_path is not None:
        export_log('Imported input_exploration_production_factors_timeseries.csv', output_path=log_path, print_on=1)

    return (project_updates, exploration_production_factors_updates)

def timeseries_dictionary_merge_row(dictionary, row):
    """
    Merges a new row into an existing timeseries factor update dictionary.
    Currently used by file_import.import_exploration_production_factors_timeseries()
    """
    for key in row.keys():
        if key not in ('UPDATE_PROJECTS', 'UPDATE_EXPLORATION_PRODUCTION_FACTORS', 'REGION',
                       'DEPOSIT_TYPE', 'VARIABLE', 'COMMODITY', ''):
            if int(key) in dictionary.keys():
                if row['REGION'] in dictionary[int(key)].keys():
                    if row['DEPOSIT_TYPE'] in dictionary[int(key)][row['REGION']].keys():
                        if row['VARIABLE'] in dictionary[int(key)][row['REGION']][row['DEPOSIT_TYPE']].keys():
                            dictionary[int(key)][row['REGION']][row['DEPOSIT_TYPE']][row['VARIABLE']].update({row['COMMODITY']: row[key]})
                        else:
                            dictionary[int(key)][row['REGION']][row['DEPOSIT_TYPE']].update({row['VARIABLE']: {row['COMMODITY']: row[key]}})
                    else:
                        dictionary[int(key)][row['REGION']].update({row['DEPOSIT_TYPE']: {row['VARIABLE']: {row['COMMODITY']: row[key]}}})
                else:
                    dictionary[int(key)].update({row['REGION']: {row['DEPOSIT_TYPE']: {row['VARIABLE']: {row['COMMODITY']: row[key]}}}})
            else:
                dictionary.update({int(key): {row['REGION']: {row['DEPOSIT_TYPE']: {row['VARIABLE']: {row['COMMODITY']: row[key]}}}}})
    return dictionary

def import_demand(path, copy_path=None, log_path=None):
    """
    import_demand()
    Imports parameters from input_demand.csv located at 'path'.
    Typical path is \WORKING_DIRECTORY\input_files\input_demand.csv

    Returns a dictionary, imported_demand{scenario_name: {commodity: {'balance_supply': 1 or 0,'intermediate_recovery': 0 to 1, 'demand_threshold': 0 to 1, 'demand_carry': float(), year: commodity demand}}}

    Files will be copied to copy_path_folder if specified.

    Expected csv format:
        KEYS                    | ACCEPTABLE INPUT VALUES
        SCENARIO_NAME           | string. Must correspond to values in input_parameters.csv
        COMMODITY               | string
        BALANCE_SUPPLY          | 1 or 0. Indicates whether supply-demand balancing will be attempted for that commodity
        INTERMEDIATE_RECOVERY   | Ratio between 0 and 1. Recovery between mine outputs and final demand commodity (e.g. at smelter).
        DEMAND_THRESHOLD        | Absolute unmet demand required to end commodity supply-demand balance loop.
        DEMAND_CARRY            | Ratio of unmet demand that will be carried to the next year. Can be negative to model supply-demand elasticity.
        t0, t1, t2, ..., tn     | Commodity demand in year t

    """
    imported_demand = {}

    with open(path+r'\\input_demand.csv', mode='r') as input_file:
        csv_reader = csv.DictReader(input_file)

        # Iterate through each row for a new series of commodity demand
        for row in csv_reader:
            if row['SCENARIO_NAME'] not in imported_demand.keys():
                imported_demand.update({row['SCENARIO_NAME']: {row['COMMODITY']: {'balance_supply': int(row['BALANCE_SUPPLY']),
                                                                                  'intermediate_recovery': float(row['INTERMEDIATE_RECOVERY']),
                                                                                  'demand_threshold': float(row['DEMAND_THRESHOLD']),
                                                                                  'demand_carry': float(row['DEMAND_CARRY'])}}})
            elif row['COMMODITY'] not in imported_demand[row['SCENARIO_NAME']].keys():
                imported_demand[row['SCENARIO_NAME']].update({row['COMMODITY']: {'balance_supply': int(row['BALANCE_SUPPLY']),
                                                                                 'intermediate_recovery': float(row['INTERMEDIATE_RECOVERY']),
                                                                                 'demand_threshold': float(row['DEMAND_THRESHOLD']),
                                                                                 'demand_carry': float(row['DEMAND_CARRY'])}})
            for key in row.keys():
                if key not in ('COMMODITY', 'SCENARIO_NAME', 'BALANCE_SUPPLY',
                               'INTERMEDIATE_RECOVERY', 'DEMAND_THRESHOLD', 'DEMAND_CARRY'):
                    imported_demand[row['SCENARIO_NAME']][row['COMMODITY']].update({int(key): float(row[key])})
    if copy_path is not None:
        copyfile(path + r'\\input_demand.csv', copy_path + r'\\input_demand.csv')
        
    if log_path is not None:
        export_log('Imported input_demand.csv', output_path=log_path, print_on=1)
        
    return imported_demand

def import_graphs(path, copy_path=None, log_path=None):
    """
    import_graphs(()
    Imports graph generation parameters from input_graphs.csv located at 'path'.
    Typical path is \WORKING DIRECTORY\input_files\input_graphs.csv

    Returns a list of dictionaries [{row0_keys: row0_values}, {row1_keys: row1_values}, etc.

    Files will be copied to copy_path_folder if specified.

    Expected csv format:
        KEYS            |   ACCEPTABLE INPUT VALUES
        file_prefix     |   No hard restrictions (best practice would be to keep short though)
        plot_algorithm  |   plot_subplot_default
        subplot_type    |   line, scatter, stacked, fill, fill_line
        plot_keys       |   one of i,j,a,r,d,c,s or multiple separated by ';' (e.g. i;c;s)
        subplot_keys    |   one of i,j,a,r,d,c,s or multiple separated by ';' (e.g. i;c;s)
        i_keys          |   True (will generate all keys excl. 'ALL'), False (will generate only 'ALL') or key0;key1;key2;key3;etc. (note must have no spaces)
        j_keys          |   True (will generate all keys excl. 'ALL'), False (will generate only 'ALL') or key0;key1;key2;key3;etc. (note must have no spaces)
        a_keys          |   True (will generate all keys excl. 'ALL'), False (will generate only 'ALL') or key0;key1;key2;key3;etc. (note must have no spaces)
        r_keys          |   True (will generate all keys excl. 'ALL'), False (will generate only 'ALL') or key0;key1;key2;key3;etc. (note must have no spaces)
        d_keys          |   True (will generate all keys excl. 'ALL'), False (will generate only 'ALL') or key0;key1;key2;key3;etc. (note must have no spaces)
        c_keys          |   True (will generate all keys excl. 'ALL'), False (will generate only 'ALL') or key0;key1;key2;key3;etc. (note must have no spaces)
        s_keys          |   True (will generate all keys excl. 'ALL'), False (will generate only 'ALL') or key0;key1;key2;key3;etc. (note must have no spaces)
        t_keys          |   True (will generate all keys excl. 'ALL'), False (will generate only 'ALL') or key0;key1;key2;key3;etc. (note must have no spaces)
        share_scale     |   True or False (can be 1 or 0 and will automatically convert to boolean True or False)
        y_axis_label    |   False (will autogenerate y_axis_label based on plot_keys) or a string
        cumulative      |   True or False
        labels_on       |   one of i,j,a,r,d,c,s or multiple separated by ';' (e.g. i;c;s). This acts as a grouping to share series and legend formatting.
        columns         |   False (will default to 2 subplot columns) or number
        gif             |   True (will combine plots into a GIF) or False
        gif_fps         |   Frames per second in generate gif. Default = 10.
        gif_delete_frames|  True (will delete plots after generating GIF) or False (will preserve plot and GIF files)
    """
    imported_graphs = []

    with open(path+r'\\input_graphs.csv', mode='r') as input_file:
        csv_reader = csv.DictReader(input_file)

        # Iterate through each row / graph
        for row in csv_reader:
            imported_graphs.append({})
            imported_graphs[-1].update({'file_prefix': row['FILE_PREFIX'],
                                        'plot_algorithm': row['PLOT_ALGORITHM'],
                                        'subplot_type': row['SUBPLOT_TYPE'],
                                        'plot_keys': row['PLOT_KEYS'].split(';'),
                                        'subplot_keys': row['SUBPLOT_KEYS'].split(';'),
                                        'i_keys': row['I_KEYS'].split(';'),
                                        'j_keys': row['J_KEYS'].split(';'),
                                        'a_keys': row['A_KEYS'].split(';'),
                                        'r_keys': row['R_KEYS'].split(';'),
                                        'd_keys': row['D_KEYS'].split(';'),
                                        'c_keys': row['C_KEYS'].split(';'),
                                        's_keys': row['S_KEYS'].split(';'),
                                        't_keys': row['T_KEYS'].split(';'),
                                        'share_scale': row['SHARE_SCALE'],
                                        'y_axis_label': row['Y_AXIS_LABEL'],
                                        'labels_on': row['LABELS_ON'].split(';'),
                                        'cumulative': row['CUMULATIVE'],
                                        'columns': row['COLUMNS'],
                                        'gif': row['GIF'],
                                        'gif_fps': int(row['GIF_FPS']),
                                        'gif_delete_frames': row['GIF_DELETE_FRAMES']
                                        })

            # Convert 'true' and 'false' inputs to booleans.
            for k in ['i_keys', 'j_keys', 'a_keys', 'r_keys', 'd_keys', 'c_keys', 's_keys', 't_keys']:
                if imported_graphs[-1][k][0].lower() == 'false':
                    imported_graphs[-1][k] = False
                elif imported_graphs[-1][k][0].lower() == 'true':
                    imported_graphs[-1][k] = True
            if imported_graphs[-1]['share_scale'].lower() == "false":
                imported_graphs[-1]['share_scale'] = False
            elif imported_graphs[-1]['share_scale'].lower() == "true":
                imported_graphs[-1]['share_scale'] = True
            if imported_graphs[-1]['y_axis_label'].lower() == "false":
                imported_graphs[-1]['y_axis_label'] = False
            if imported_graphs[-1]['cumulative'].lower() == "false":
                imported_graphs[-1]['cumulative'] = False
            elif imported_graphs[-1]['cumulative'].lower() == "true":
                imported_graphs[-1]['cumulative'] = True
            if imported_graphs[-1]['columns'].lower() == "false":
                imported_graphs[-1]['columns'] = 2
            else:
                imported_graphs[-1]['columns'] = int(imported_graphs[-1]['columns'])
            if imported_graphs[-1]['gif'].lower() == 'false':
                imported_graphs[-1]['gif'] = False
            elif imported_graphs[-1]['gif'].lower() == "true":
                imported_graphs[-1]['gif'] = True
            if imported_graphs[-1]['gif_delete_frames'].lower() == 'false':
                imported_graphs[-1]['gif_delete_frames'] = False
            elif imported_graphs[-1]['gif_delete_frames'].lower() == "true":
                imported_graphs[-1]['gif_delete_frames'] = True


    if copy_path is not None:
        copyfile(path + r'\\input_graphs.csv', copy_path + r'\\input_graphs.csv')
        
    if log_path is not None:
        export_log('Imported input_graphs.csv', output_path=log_path, print_on=1)

    return imported_graphs


def import_graphs_formatting(path, copy_path=None, log_path=None):
    """
    import_graphs_formatting()
    Imports postprocessing parameters from a csv located at 'path'.
    Typical path is \WORKING_DIRECTORY\input_files\input_graphs_formatting.csv
    Output is a dictionary {label: {color: value, line: value, linestyle: value, etc.}}

    Copies file if copy_path directory specified.

    Expected input csv format:
         HEADER ROW           | ACCEPTABLE INPUT ROW VALUES
         LABEL                | grouping label corresponding to import_graphs / input_graphs.csv [labels_on] column
         LEGEND_TEXT          | string for use in figure legends
         LEGEND_SUPPRESS      | Boolean (True, False, 1, 0), prevents inclusion in legend - useful for grouping labels
         TITLE_TEXT           | string for use in figure and subplot titles
         TITLE_SUPPRESS       | Boolean (True, False, 1, 0), prevents title being generated
         COLOR                | Matplotlib colors
         ALPHA                | 0 to 1
         FILL_ALPHA           | 0 to 1
         LINEWIDTH            | decimal / float, linewidth in pt
         LINESTYLE            | Matplotlib linestyles
         MARKER               | Matplotlib markers
         SIZE                 | decimal / float, marker size in pt

    Header row should be capitalised in input file. Output dictionary has lowercase keys.

    NOTE: Any change to the output dictionary structure requires change to post_processing.label_format()
    """
    imported_graphs_formatting = {}

    with open(path + r'\\input_graphs_formatting.csv', mode='r') as input_file:
        csv_reader = csv.DictReader(input_file)
        # Import labels
        for row in csv_reader:
            imported_graphs_formatting.update({str(row["LABEL"]): {'legend_text': str(row['LEGEND_TEXT']),
                                                                   'legend_suppress': bool(strtobool(str(row['LEGEND_SUPPRESS']))),
                                                                   'title_text': str(row['TITLE_TEXT']),
                                                                   'title_suppress': bool(strtobool(str(row['TITLE_SUPPRESS']))),
                                                                   'color': row['COLOR'],
                                                                   'alpha': float(row['ALPHA']),
                                                                   'fill_alpha': float(row['FILL_ALPHA']),
                                                                   'linestyle': row['LINESTYLE'],
                                                                   'linewidth': float(row['LINEWIDTH']),
                                                                   'marker': row['MARKER'],
                                                                   'size': float(row['SIZE'])}})

    if copy_path is not None:
        copyfile(path + r'\\input_graphs_formatting.csv', copy_path + r'\\input_graphs_formatting.csv')
    if log_path is not None:
        export_log('Imported input_graphs_formatting.csv', log_path, 1)
    return imported_graphs_formatting

def import_postprocessing(path, copy_path=None, log_path=None):
    """
    import_postprocessing()
    Imports postprocessing parameters from a csv located at 'path'.
    Typical path is \WORKING_DIRECTORY\input_files\input_postprocessing.csv
    Output is a dictionaries {statistic: {'postprocess': True}] for statistics where 'POSTPROCESS' csv column == True
                              
    Copies input_parameters if copy_path directory specified.
                              
    Expected input csv format:
         HEADER ROW  | ACCEPTABLE INPUT ROW VALUES
         STATISTIC   | Primarily results.generate_statistics() return dictionary keys.
         POSTPROCESS | TRUE (will filter statistic and build a merged csv the from _statistics.csv files) or 0 (will exclude from postprocessing)

    Header row should be capitalised in input file. Output dictionary has lowercase keys.

    """
    imported_postprocessing = {}

    with open(path + r'\\input_postprocessing.csv', mode='r') as parameters_file:
        csv_reader = csv.DictReader(parameters_file)
        #Import scenarios
        for row in csv_reader:
            if row['POSTPROCESS'].lower() == 'true':
                imported_postprocessing.update({row["STATISTIC"]: {'postprocess': True}})

    if copy_path is not None:
        copyfile(path + r'\\input_postprocessing.csv', copy_path + r'\\input_postprocessing.csv')
    if log_path is not None:
        export_log('Imported input_postprocessing.csv', log_path, 1)
    return imported_postprocessing  

def import_historic(path, copy_path=None, log_path=None):
    """
    import_historic()
    Imports from input_historic located in the path directory.
    Returns a shallow nested dictionary {(a,r,d,c,s): {time: values}}
    Copies input_historic.csv if copy_path directory specified.

    Expected input csv format:
         HEADER ROW    | ACCEPTABLE INPUT ROW VALUES
         AGGREGATION   |
         DEPOSIT_TYPE  |
         REGION        |
         COMMODITY     |
         STATISTIC     |
         t0, t1, ..., tn  | values
    """
    imported_historic = import_statistics(path + r'\\input_historic.csv', custom_keys=['AGGREGATION', 'REGION', 'DEPOSIT_TYPE', 'COMMODITY', 'STATISTIC'])
    
    if copy_path is not None:
        copyfile(path + r'\\input_historic.csv', copy_path + r'\\input_historic.csv')
    if log_path is not None:
        export_log('Imported input_historic.csv', log_path, 1)
    
    return imported_historic
    
    

def import_statistics(path, log_path=None, custom_keys=False, convert_values=False):
    """
    import_statistics()
    Imports csv file with a flat statistics data structure.
    custom_keys | Default (False) will generate (i,j,a,r,d,c,s).
                | For input_historic.csv use:
                | custom_keys=['AGGREGATION', 'REGION', 'DEPOSIT_TYPE', 'COMMODITY', 'STATISTIC']
    convert_values | True will convert values in the time dictionaries to float and missing values to None
    Returns a shallow nested dictionary {(i,j,a,r,d,c,s): {time: values}}
    ## Usage Note. For historic.csv import convert_values should be False.

    Expected input csv format if custom_keys is False:
         HEADER ROW       | ACCEPTABLE INPUT ROW VALUES
         SCENARIO_INDEX   |
         ITERATION        |
         AGGREGATION      |
         REGION           |
         DEPOSIT_TYPE     |
         COMMODITY        |
         STATISTIC        |
         t0, t1, ..., tn  | values

    """
    imported_statistics = {}
    
    with open(path, mode='r') as input_file:
        
        if not custom_keys:
            keys = ['SCENARIO_INDEX', 'ITERATION', 'AGGREGATION', 'REGION', 'DEPOSIT_TYPE', 'COMMODITY', 'STATISTIC']
        else:
            keys = custom_keys

        csv_reader = csv.DictReader(input_file, fieldnames=keys, restkey='TIME')
        
        # Iterate through each row
        for row in csv_reader:
            if row[keys[0]] == keys[0]:
                imported_statistics = {}
                if convert_values:
                    time_keys = [int(t) for t in row['TIME']]
                else:
                    time_keys = row['TIME']
            else:
                tuple_key = tuple([row[k] for k in keys])
                if convert_values:
                    time_values = [float(v) if v != '' else None for v in row['TIME']]
                else:
                    time_values = row['TIME']
                imported_statistics.update({tuple_key: dict(zip(time_keys, time_values))})

    if log_path is not None:
        export_log('Imported a flat statistics csv.', output_path=log_path, print_on=1)

    return imported_statistics

def import_statistics_keyed(path, base_key='STATISTIC', log_path=None):
    """
    import_statistics_keyed()
    Imports a _statistics.csv file, current use is when merging scenario data.

    Returns a nested dictionary {base_key:{(i,j,a,r,d,c,s): {time: values}}} and the time keys.

    ARGUMENT | EXPECTED VALUES
    base_key | 'SCENARIO_INDEX', 'ITERATION', 'AGGREGATION', 'REGION', 'DEPOSIT_TYPE', 'COMMODITY', 'STATISTIC' (default)
    ## top level {base_key} is a defaultdict

    Expected input csv format:
         HEADER ROW       | ACCEPTABLE INPUT ROW VALUES
         SCENARIO_INDEX   |
         ITERATION        |
         AGGREGATION      |
         REGION           |
         DEPOSIT_TYPE     |
         COMMODITY        |
         STATISTIC        |
         t0, t1, ..., tn  | values
    """
    
    imported_statistics = defaultdict(dict)
    time_keys = []
    
    with open(path, mode='r') as input_file:
        
        keys = ['SCENARIO_INDEX', 'ITERATION', 'AGGREGATION', 'REGION', 'DEPOSIT_TYPE', 'COMMODITY', 'STATISTIC']
        csv_reader = csv.DictReader(input_file, fieldnames=keys, restkey='TIME', restval='VALUES')
        
        for i, row in enumerate(csv_reader):
            # Generate header
            if i == 0:
                time_keys = row['TIME']
                
            # Add row to nested stats
            else:
                time_dict = dict(zip(time_keys,row['TIME']))
                imported_statistics[row[base_key]].update({(row['SCENARIO_INDEX'],
                                                              row['ITERATION'],
                                                              row['AGGREGATION'],
                                                              row['REGION'],
                                                              row['DEPOSIT_TYPE'],
                                                              row['COMMODITY'],
                                                              row['STATISTIC']): time_dict})
    if log_path is not None:
        export_log('Imported_statistics.csv', output_path=log_path, print_on=1)
    return imported_statistics, time_keys
