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
    import_postprocessing()
    import_historic()
    import_statistics_flat()
    import_statistics_flat_filter()

    TODO: 1. Add copyright statement
    TODO: 2. Add cross-references to the journal article
    TODO: 3. Update this docstring after all other todos removed
"""

# Import standard packages
import csv
from shutil import copyfile
from collections import defaultdict

# Import custom modules
import modules.deposit as deposit
from modules.file_export import export_log


#Import Data Functions

def import_static_files(path, copy_path_folder=None, log_file=None):
    """
    import_static_files()
    Imports the input files that don't need
    to be reimported through the model run.
    Includes:
        input_parameters.csv
        input_exploration_production_factors.csv
        input_exploration_production_factors_timeseries.csv
        input_demand.csv
        input_graphs.csv
    Files will be copied to copy_path_folder if specified.
    Returns file structures within a tuple.
    TODO: Update docstrings to include full input / output descriptions
    """
    
    parameters = import_parameters(path, copy_path=copy_path_folder, log_path=log_file)
    imported_factors = import_exploration_production_factors(path, copy_path=copy_path_folder, log_path=log_file)
    timeseries_project_updates, timeseries_exploration_production_factors_updates = import_exploration_production_factors_timeseries(path, copy_path=copy_path_folder, log_path=log_file)
    imported_demand = import_demand(path, copy_path=copy_path_folder, log_path=log_file)
    imported_graphs = import_graphs(path, copy_path=copy_path_folder, log_path=log_file)
    imported_postprocessing = import_postprocessing(path, copy_path=copy_path_folder, log_path=log_file)
    imported_historic = import_historic(path, copy_path=copy_path_folder, log_path=log_file)

    return (parameters,
            imported_factors,
            timeseries_project_updates,
            timeseries_exploration_production_factors_updates,
            imported_demand,
            imported_graphs,
            imported_postprocessing,
            imported_historic)

def import_parameters(path, copy_path=None, log_path=None):
    """
    import_parameters()
    Imports parameters from input_parameters.csv located in the path directory.
    Output is a dictionary, imported_parameters['key'][i], where i is each scenario run.
    Copies input_parameters if copy_path directory specified.

    TODO: Add input argument description to docstrings
    TODO: Describe input file format, see import_postprocessing
    """
    imported_parameters = {'scenario_name': [], 'year_start': [], 'year_end': [], 'iterations': [],
                           'brownfield_exploration_on': [], 'greenfield_exploration_on': [],
                           'greenfield_background': [], 'priority_active': [], 'random_seed': [],
                           'generate_all_coproducts': [], 'update_values': []}

    with open(path + r'\\input_parameters.csv', mode='r') as parameters_file:
        csv_reader = csv.DictReader(parameters_file)
        #Import scenarios
        for row in csv_reader:
            imported_parameters['scenario_name'].append(str(row['SCENARIO_NAME']))
            imported_parameters['year_start'].append(int(row['YEAR_START']))
            imported_parameters['year_end'].append(int(row['YEAR_END']))
            imported_parameters['iterations'].append(int(row["ITERATIONS"]))
            imported_parameters['brownfield_exploration_on'].append(int(row['BROWNFIELD_EXPLORATION_ON']))
            imported_parameters['greenfield_exploration_on'].append(int(row['GREENFIELD_EXPLORATION_ON']))
            imported_parameters['greenfield_background'].append(int(row['GREENFIELD_BACKGROUND']))
            imported_parameters['priority_active'].append(int(row['PRIORITY_ACTIVE']))
            imported_parameters['random_seed'].append(float(row['RANDOM_SEED']))
            imported_parameters['generate_all_coproducts'].append(int(row['GENERATE_ALL_COPRODUCTS']))
            imported_parameters['update_values'].append(int(row['UPDATE_VALUES']))
    if copy_path is not None:
        copyfile(path + r'\\input_parameters.csv', copy_path + r'\\input_parameters.csv')
    if log_path is not None:
        export_log('Imported input_parameters.csv', log_path, 1)
    return imported_parameters



def import_projects(f, path, copy_path=None, log_path=None):
    """
    import_projects()
    Imports projects from input_projects.csv in the working directory.
    Output is a list of Mine() objects
    Missing variables are infilled using a variety of approaches,
    based upon parameters defined in input_exploration_production_factors.csv.
    P_ID_NUMBER should start sequentially from zero to avoid P_ID collisions when generating greenfield deposits.
    TODO: Add random region generation (incl. check for deposit type)
    TODO: Add random deposit type generation (incl. check for region)
    TODO: Update log text
    TODO: Describe input file format, see import_postprocessing
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
    no_discovery_year = 0
    no_start_year = 0
    no_brownfield_grade_factor = 0
    no_brownfield_tonnage_factor = 0
    # Open and generate projects from input_projects.csv
    imported_projects = []
    brownfield = {}

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
            if row['REGION'] == "":
                no_region += 1
                region = 'UNSPECIFIED'
                # FIXME: Add random region generation, plus checks for Dep. Type.
            else:
                region = str(row['REGION'])
            if row['DEPOSIT_TYPE'] == "":
                no_deposit_type += 1
                deposit_type = 'UNSPECIFIED'
                export_log('Deposit type not entered for P_ID_NUMBER: '+str(id_number)+', NAME: '+str(name)+
                           '\nDeposit type randomly set to '+str(deposit_type)+
                           '\nNOTE: It is recommended to manually input deposit types and regions for all projects.')
                # FIXME: Add random deposit type generation, plus checks for Region.
            else:
                deposit_type = str(row['DEPOSIT_TYPE'])

            index = f['lookup_table'][region][deposit_type]

            if row['COMMODITY'] == "":
                no_commodity += 1
                commodity = f['commodity_primary'][index]
            else:
                commodity = row['COMMODITY']
            if row['GRADE'] == "":
                no_grade += 1
                grade = deposit.grade_generate(f['grade'][index], {'a': f['grade_a'][index],
                                                                   'b': f['grade_b'][index],
                                                                   'c': f['grade_c'][index],
                                                                   'd': f['grade_d'][index]})
            else:
                grade = float(row['GRADE'])
            if row['REMAINING_RESOURCE'] == "":
                no_remaining_resource += 1
                remaining_resource = deposit.tonnage_generate(f['size_model'][index],
                                                              {'a': f['tonnage_a'][index],
                                                               'b': f['tonnage_b'][index],
                                                               'c': f['tonnage_c'][index],
                                                               'd': f['tonnage_d'][index]},
                                                              grade)
            else:
                remaining_resource = float(row['REMAINING_RESOURCE'])
            if row['RECOVERY'] == "":
                no_recovery += 1
                recovery = float(f['default_recovery'][index])
            else:
                recovery = float(row['RECOVERY'])
            if row['PRODUCTION_CAPACITY'] == "":
                no_production_capacity += 1
                production_capacity = deposit.capacity_generate(remaining_resource,
                                                                f['taylor_a'][index],
                                                                f['taylor_b'][index],
                                                                f['taylor_min'][index],
                                                                f['taylor_max'][index])
            else:
                production_capacity = float(row['PRODUCTION_CAPACITY'])
            if row['STATUS'] == "":
                no_status += 1
                status = 0
            else:
                status = int(row['STATUS'])
            if row['VALUE'] == "":
                no_value += 1
                value_factors = {'MINE': {'cost': {'model': f['mine_cost_model'][index],
                                                        'a': f['mine_cost_a'][index],
                                                        'b': f['mine_cost_b'][index],
                                                        'c': f['mine_cost_c'][index],
                                                        'd': f['mine_cost_d'][index]}},
                                 commodity: {'revenue': {'model': f['revenue_model'][index],
                                                         'a': f['revenue_a'][index],
                                                         'b': f['revenue_b'][index],
                                                         'c': f['revenue_c'][index],
                                                         'd': f['revenue_d'][index]},
                                             'cost': {'model': f['cost_model'][index],
                                                      'a': f['cost_a'][index],
                                                      'b': f['cost_b'][index],
                                                      'c': f['cost_c'][index],
                                                      'd': f['cost_d'][index]}}}
                value = deposit.value_model(value_factors, remaining_resource, grade, recovery)

            else:
                # TODO: check logic of including value_factors here. Want to be able to maintain project by project value factors
                value = {'ALL': float(row['VALUE']), commodity: float(row['VALUE'])}
                value_factors = {'MINE': {'cost': {'model': f['mine_cost_model'][index],
                                                        'a': f['mine_cost_a'][index],
                                                        'b': f['mine_cost_b'][index],
                                                        'c': f['mine_cost_c'][index],
                                                        'd': f['mine_cost_d'][index]}},
                                 commodity: {'revenue': {'model': f['revenue_model'][index],
                                                         'a': f['revenue_a'][index],
                                                         'b': f['revenue_b'][index],
                                                         'c': f['revenue_c'][index],
                                                         'd': f['revenue_d'][index]},
                                             'cost': {'model': f['cost_model'][index],
                                                      'a': f['cost_a'][index],
                                                      'b': f['cost_b'][index],
                                                      'c': f['cost_c'][index],
                                                      'd': f['cost_d'][index]}}}
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
                             start_year, brownfield_tonnage, brownfield_grade, value_factors, aggregation))

    if copy_path is not None:
        copyfile(path + r'\\input_projects.csv', copy_path + r'\\input_projects.csv')

    if log_path is not None:
        export_log('Imported input_projects.csv', output_path=log_path, print_on=1)
        
        export_log('Imported ' + str(len(imported_projects)) + ' projects. \n\nCount of project blank entries:', output_path=log_path)
        export_log(str(no_id_number) + ' : id_number. Missing values generated by system.', output_path=log_path)
        export_log(str(no_name) + ' : name. Missing names set as UNSPECIFIED.', output_path=log_path)
        export_log(str(no_region) + ' : region. Missing regions set as UNSPECIFIED.', output_path=log_path)
        export_log(str(no_deposit_type) + ' : deposit_type. Missing deposit types selected from selected randomly from weighted options.', output_path=log_path)
        export_log(str(no_commodity) + ' : commodity. Missing commodity lists assigned corresponding to deposit type.', output_path=log_path)
        export_log(str(no_remaining_resource) + ' : remaining_resource. Remaining resource generated using estimation method....', output_path=log_path)
        # FIXME: Add remaining resource estimation method outputting to log.
        export_log(str(no_grade) + ' : grade. Missing grades generated using estimation method...', output_path=log_path)
        # FIXME: Add grade estimation method outputting to log.
        export_log(str(no_recovery) + ' : recovery. Missing recovery factors assigned to default value.', output_path=log_path)
        export_log(str(no_production_capacity) + " : production capacity. Missing production capacity generated using taylor's law functions.", output_path=log_path)
        export_log(str(no_status) + ' : status. Missing status assigned to 0', output_path=log_path)
        export_log(str(no_value) + ' : value. Missing values assigned using the value model specified for the region and deposit type.', output_path=log_path)
        # FIXME: Add grade estimation method outputting to log.
        export_log(str(no_discovery_year) + ' : discovery_year. Missing discovery year set to -9999', output_path=log_path)
        export_log(str(no_start_year) + ' : start_year. Missing start year left blank for inactive mines or set to -9999 for active mines', output_path=log_path)
        export_log(str(no_brownfield_grade_factor) + ' : brownfield_grade_factor. Missing values assigned from input_exploration_production_factors.csv', output_path=log_path)
        export_log(str(no_brownfield_tonnage_factor) + ' : brownfield_grade_factor. Missing values assigned from input_exploration_production_factors.csv', output_path=log_path)

    return imported_projects


def import_project_coproducts(f, path, projects, generate_all, copy_path=None, log_path=None):
    """
    import_project_coproducts(path):
    Imports and adds coproduct parameters to projects from input_project_coproducts.csv located in the working directory.
    f = exploration_production_factors
    generate_all | If 1, update projects only listed in input_project_coproducts.csv. If 0, also update all other projects with data from exploration_production_factors.csv.
    TODO: Update docstrings
    TODO: Describe input file format, see import_postprocessing
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
                        export_log('Error: Must specify COPRODUCT_COMMODITY for all projects in inputs_projects_coproducts.csv. Rows with missing coproduct commodity names skipped.')
                    else:
                        entries += 1
                        c = row['COPRODUCT_COMMODITY']
                        for x in range(0, len(f['coproduct_commodity'][index])):
                            if len(f['coproduct_commodity'][index]) != 0:
                                if f['coproduct_commodity'][index][x] == row['COPRODUCT_COMMODITY']:
                                    if row['COPRODUCT_GRADE'] == '':
                                        # Generate grade from the region and deposit type grade model
                                        g = deposit.coproduct_grade_generate(p, f, index, x)
                                        generated_grades += 1
                                    else:
                                        # Use inputted coproduct grade
                                        g = float(row['COPRODUCT_GRADE'])
                                    if row['COPRODUCT_RECOVERY'] == '':
                                        # Use default coproduct recovery for the region and deposit type
                                        r = float(f['coproduct_default_recovery'][index][x])
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
                                    # TODO: check indentation level
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
                                    p.add_commodity(c, g, r, st, bgf, vf)
                elif generate_all == 1:
                    # Generate project coproduct parameters using the region and production factors given in input_exploration_production_factors.csv
                    for x in range(0, len(f['coproduct_commodity'][index])):
                        if len(f['coproduct_commodity'][index]) != 0:
                            c = f['coproduct_commodity'][index][x]
                            if c != '':
                                g = deposit.coproduct_grade_generate(p, f, index, x)
                                r = float(f['coproduct_default_recovery'][index][x])
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

                                p.add_commodity(c, g, r, st, bgf, vf)
                                generated_grades += 1
                                generated_recovery += 1
                                generated_supply_trigger += 1
                                generated_brownfield_grade_factor += 1
    if copy_path is not None:
        copyfile(path + r'\\input_project_coproducts.csv', copy_path + r'\\input_project_coproducts.csv')

    if log_path is not None:
        export_log('Imported input_projects_coproducts.csv', output_path=log_path, print_on=1)
        export_log('Added ' + str(entries)+' new coproduct entries. '+str(skipped)+' skipped (check log file for details). '+str(generated_grades)+' grade, '+str(generated_recovery)+' recovery, '+str(generated_supply_trigger)+' supply trigger, and '+str(generated_brownfield_grade_factor)+' brownfield grade factors generated from factors in input_exploration_production.csv.', output_path=log_path, print_on=0)
    return projects


def import_exploration_production_factors(path, copy_path=None, log_path=None):
    """
    import_exploration_production_factors()
    Imports parameters from input_exploration_production_factors.csv located in the working directory.
    Output is a dictionary, imported_factors['key'][i], where 'key' is the deposit type [i].
    TODO: Update docstrings
    TODO: Return variables described incorrectly.
    TODO: Describe input file format, see import_postprocessing
    """
    imported_factors = {'index': [], 'weighting': [], 'region': [], 'deposit_type': [], 'commodity_primary': [],
                        'grade_model': [], 'grade_a': [], 'grade_b': [], 'grade_c': [], 'grade_d': [],
                        'tonnage_model': [], 'tonnage_a': [], 'tonnage_b': [], 'tonnage_c': [], 'tonnage_d': [],
                        'brownfield_tonnage_factor': [], 'brownfield_grade_factor': [],
                        'taylor_a': [], 'taylor_b': [], 'taylor_min': [], 'taylor_max': [],
                        'default_recovery': [],
                        'revenue_model': [], 'revenue_a': [], 'revenue_b': [], 'revenue_c': [], 'revenue_d': [],
                        'cost_model': [], 'cost_a': [], 'cost_b': [], 'cost_c': [], 'cost_d': [],
                        'mine_cost_model': [], 'mine_cost_a': [], 'mine_cost_b': [], 'mine_cost_c': [], 'mine_cost_d': [],
                        'development_period': [], 'coproduct_commodity': [],
                        'coproduct_grade_model': [], 'coproduct_a': [], 'coproduct_b': [], 'coproduct_c': [], 'coproduct_d': [],
                        'coproduct_default_recovery': [], 'coproduct_supply_trigger': [], 'coproduct_brownfield_grade_factor': [],
                        'coproduct_revenue_model': [], 'coproduct_revenue_a': [], 'coproduct_revenue_b': [], 'coproduct_revenue_c': [], 'coproduct_revenue_d': [],
                        'coproduct_cost_model': [], 'coproduct_cost_a': [], 'coproduct_cost_b': [], 'coproduct_cost_c': [], 'coproduct_cost_d': [],
                        'lookup_table': {}}

    with open(path+r'\\input_exploration_production_factors.csv', mode='r') as parameters_file:
        csv_reader = csv.DictReader(parameters_file)
        #Import scenarios
        for row in csv_reader:
            imported_factors['index'].append(int(row['INDEX']))
            imported_factors['weighting'].append(float(row['WEIGHTING']))
            imported_factors['region'].append(row['REGION'])
            imported_factors['deposit_type'].append(row['DEPOSIT_TYPE'])
            imported_factors['commodity_primary'].append(row['COMMODITY_PRIMARY'])
            imported_factors['grade_model'].append(row['GRADE_MODEL'])
            imported_factors['grade_a'].append(float(row['GRADE_A']))
            imported_factors['grade_b'].append(float(row['GRADE_B']))
            imported_factors['grade_c'].append(float(row['GRADE_C']))
            imported_factors['grade_d'].append(float(row['GRADE_D']))
            imported_factors['tonnage_model'].append(row['TONNAGE_MODEL'])
            imported_factors['tonnage_a'].append(float(row['TONNAGE_A']))
            imported_factors['tonnage_b'].append(float(row['TONNAGE_B']))
            imported_factors['tonnage_c'].append(float(row['TONNAGE_C']))
            imported_factors['tonnage_d'].append(float(row['TONNAGE_D']))
            imported_factors['brownfield_tonnage_factor'].append(float(row['BROWNFIELD_TONNAGE_FACTOR']))
            imported_factors['brownfield_grade_factor'].append(float(row['BROWNFIELD_GRADE_FACTOR']))
            imported_factors['taylor_a'].append(float(row['TAYLOR_A']))
            imported_factors['taylor_b'].append(float(row['TAYLOR_B']))
            imported_factors['taylor_min'].append(float(row['TAYLOR_MIN']))
            imported_factors['taylor_max'].append(float(row['TAYLOR_MAX']))
            imported_factors['default_recovery'].append(float(row['DEFAULT_RECOVERY']))
            imported_factors['revenue_model'].append(row['REVENUE_MODEL'])
            imported_factors['revenue_a'].append(float(row['REVENUE_A']))
            imported_factors['revenue_b'].append(float(row['REVENUE_B']))
            imported_factors['revenue_c'].append(float(row['REVENUE_C']))
            imported_factors['revenue_d'].append(float(row['REVENUE_D']))
            imported_factors['cost_model'].append(row['COST_MODEL'])
            imported_factors['cost_a'].append(float(row['COST_A']))
            imported_factors['cost_b'].append(float(row['COST_B']))
            imported_factors['cost_c'].append(float(row['COST_C']))
            imported_factors['cost_d'].append(float(row['COST_D']))
            imported_factors['mine_cost_model'].append(row['MINE_COST_MODEL'])
            imported_factors['mine_cost_a'].append(float(row['MINE_COST_A']))
            imported_factors['mine_cost_b'].append(float(row['MINE_COST_B']))
            imported_factors['mine_cost_c'].append(float(row['MINE_COST_C']))
            imported_factors['mine_cost_d'].append(float(row['MINE_COST_D']))
            imported_factors['development_period'].append(int(row['DEVELOPMENT_PERIOD']))
            imported_factors['coproduct_commodity'].extend([row['COPRODUCT_COMMODITY'].split(';')])
            imported_factors['coproduct_grade_model'].extend([row['COPRODUCT_GRADE_MODEL'].split(';')])
            imported_factors['coproduct_a'].extend([row['COPRODUCT_A'].split(';')])
            imported_factors['coproduct_b'].extend([row['COPRODUCT_B'].split(';')])
            imported_factors['coproduct_c'].extend([row['COPRODUCT_C'].split(';')])
            imported_factors['coproduct_d'].extend([row['COPRODUCT_D'].split(';')])
            imported_factors['coproduct_default_recovery'].extend([row['COPRODUCT_DEFAULT_RECOVERY'].split(';')])
            imported_factors['coproduct_supply_trigger'].extend([row['COPRODUCT_SUPPLY_TRIGGER'].split(';')])
            imported_factors['coproduct_brownfield_grade_factor'].extend([row['COPRODUCT_BROWNFIELD_GRADE_FACTOR'].split(';')])
            imported_factors['coproduct_revenue_model'].extend([row['COPRODUCT_REVENUE_MODEL'].split(';')])
            imported_factors['coproduct_revenue_a'].extend([row['COPRODUCT_REVENUE_A'].split(';')])
            imported_factors['coproduct_revenue_b'].extend([row['COPRODUCT_REVENUE_B'].split(';')])
            imported_factors['coproduct_revenue_c'].extend([row['COPRODUCT_REVENUE_C'].split(';')])
            imported_factors['coproduct_revenue_d'].extend([row['COPRODUCT_REVENUE_D'].split(';')])
            imported_factors['coproduct_cost_model'].extend([row['COPRODUCT_COST_MODEL'].split(';')])
            imported_factors['coproduct_cost_a'].extend([row['COPRODUCT_COST_A'].split(';')])
            imported_factors['coproduct_cost_b'].extend([row['COPRODUCT_COST_B'].split(';')])
            imported_factors['coproduct_cost_c'].extend([row['COPRODUCT_COST_C'].split(';')])
            imported_factors['coproduct_cost_d'].extend([row['COPRODUCT_COST_D'].split(';')])
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
    Output is two dictionaries (project updates, exploration_production_factors updates)
        of structure {year: {'region': {'deposit_type': {'variable': {'commodity': value}}}}}
    TODO: Update docstrings
    TODO: add input argument file structure description
    TODO: DDescribe input file format, see import_postprocessing
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
    TODO: Describe use case -- currently used by file_import.import_exploration_production_factors.timeseries()
    TODO: Update docstrings
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
    Imports parameters from input_demand.csv located in the working directory.
    Outputs is a dictionary, imported_demand{scenario_name: {commodity: {'balance_supply': 1 or 0,'intermediate_recovery': 0 to 1, 'demand_threshold': 0 to 1, 'demand_carry': float(), year: commodity demand}}}
    TODO: Update docstrings to include functionality, inputs and correct path description
    TODO: Describe input file format, see import_postprocessing
    """
    print('Importing input_demand.csv')
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
    Typical path is \WORKING DIRECTORY\input_files\
    Ouputs is a list of dictionaries, imported_graphs[{}, {}...]
    
        KEYS            |   ACCEPTABLE INPUT VALUES
        file_prefix     |   No hard restrictions (keep short though)
        plot_algorithm  |   statistics_cs_plots_i_subplots, statistics_ij_plots_c_subplots
        subplot_type    |   line, scatter, stacked
        i_keys          |   -1 (will generate all keys) or key0;key1;key2;key3;etc.
        j_keys          |   -1 (will generate all keys) or key0;key1;key2;key3;etc.
        a_keys          |
        r_keys          |   -1 (will generate all keys) or key0;key1;key2;key3;etc.
        d_keys          |   -1 (will generate all keys) or key0;key1;key2;key3;etc.
        c_keys          |   -1 (will generate all keys) or key0;key1;key2;key3;etc.
        s_keys          |   -1 (will generate all keys) or key0;key1;key2;key3;etc.
        t_keys          |   -1 (will generate all keys) or key0;key1;key2;key3;etc.
        labels_on       |   x;x;x;x;x;x   where x = 0 (off) and x = 1 (on)
        include_all     |   x;x;x;x;x;x   where x = 0 (off) and x = 1 (on)
        share_scale     |   True or False (can be 1 or 0 and will automatically convert to boolean True or False)
        y_axis_label    |   -1 (will generate all keys) or a string
    TODO: Add docstring description of copy_path and log_path
    TODO: Add a_keys description to docstring
    TODO: Check labels format
    TODO: Describe input file format, see import_postprocessing
    """
    print('Importing input_graphs.csv')
    imported_graphs = []

    with open(path+r'\\input_graphs.csv', mode='r') as input_file:
        csv_reader = csv.DictReader(input_file)

        # Iterate through each row / graph
        for row in csv_reader:
            imported_graphs.append({})
            imported_graphs[-1].update({'file_prefix': row['FILE_PREFIX'],
                                        'plot_algorithm': row['PLOT_ALGORITHM'],
                                        'subplot_type': row['SUBPLOT_TYPE'],
                                        'i_keys': row['I_KEYS'].split(';'),
                                        'j_keys': row['J_KEYS'].split(';'),
                                        'a_keys': row['A_KEYS'].split(';'),
                                        'r_keys': row['R_KEYS'].split(';'),
                                        'd_keys': row['D_KEYS'].split(';'),
                                        'c_keys': row['C_KEYS'].split(';'),
                                        's_keys': row['S_KEYS'].split(';'),
                                        't_keys': row['T_KEYS'].split(';'),
                                        'labels_on': row['LABELS_ON'].split(';'),
                                        'include_all': row['INCLUDE_ALL'].split(';'),
                                        'share_scale': row['SHARE_SCALE'],
                                        'y_axis_label': row['Y_AXIS_LABEL'],
                                        })

            # Convert values to integers

            #FIXME: converting from "-1" to -1
            for k in ['i_keys', 'j_keys', 'a_keys', 'r_keys', 'd_keys', 'c_keys', 's_keys', 't_keys']:
                if imported_graphs[-1][k][0] == "-1":
                    imported_graphs[-1][k] = -1
                    # FIXME: Also consider altering to True, False and lists for argument alignment with the new x_y_labels_generate_flat function

            for value in imported_graphs[-1]['labels_on']:
                value = int(value)
            for index in range(len(imported_graphs[-1]['include_all'])):
                imported_graphs[-1]['include_all'][index] = int(imported_graphs[-1]['include_all'][index])
            if imported_graphs[-1]['share_scale'] == "false" or imported_graphs[-1]['share_scale'] == "0" or imported_graphs[-1]['share_scale'] == "FALSE":
                imported_graphs[-1]['share_scale'] = False
            elif imported_graphs[-1]['share_scale'] == "true" or imported_graphs[-1]['share_scale'] == "1" or imported_graphs[-1]['share_scale'] == "TRUE":
                imported_graphs[-1]['share_scale'] = True
            if imported_graphs[-1]['y_axis_label'] == "-1":
                imported_graphs[-1]['y_axis_label'] = -1
    if copy_path is not None:
        copyfile(path + r'\\input_graphs.csv', copy_path + r'\\input_graphs.csv')
        
    if log_path is not None:
        export_log('Imported input_graphs.csv', output_path=log_path, print_on=1)

    return imported_graphs

def import_postprocessing(path, copy_path=None, log_path=None):
    """
    import_postprocessing()
    Imports postprocessing parameters from a csv located at 'path'.
    Typical path is \WORKING_DIRECTORY\input_files\input_postprocessing.csv
    Output is a dictionaries {statistic: {header, value}] for statistics where 'POSTPROCESS' == 1
                              
    Copies input_parameters if copy_path directory specified.
                              
    Expected input csv format:
         HEADER ROW  | ACCEPTABLE INPUT ROW VALUES
         STATISTIC   | 
         POSTPROCESS | 1 (will filter statistic and build a merged csv the from _statistics.csv files) or 0 (will exclude from postprocessing)
         MEAN        | 1 (generate the mean of a scenario's iteration values for each time period) or 0 (will exclude)
         MEDIAN      | 1 (generate the median of a scenario's iteration values for each time period) or 0 (will exclude)
         STDEV       | 1 (generate the standard deviation of a scenario's iteration values for each time period') or 0 (will exclude)
         MIN         | 1 (generate the minimum of a scenario's iteration values for each time period') or 0 (will exclude)
         MAX         | 1 (generate the maximum of a scenario's iteration values for each time period') or 0 (will exclude)
         CUMULATIVE  | 1 (generate a cumulative time series of each iteration time series' values) or 0 (will exclude)
         
    Header row should be capitalised in input file. Output dictionary has lowercase keys.

    TODO: Docstrings, describe STATISTIC input and matching to statistics data structure.
    """
    imported_postprocessing = {}

    with open(path + r'\\input_postprocessing.csv', mode='r') as parameters_file:
        csv_reader = csv.DictReader(parameters_file)
        #Import scenarios
        for row in csv_reader:
            if row['POSTPROCESS'] == '1':
                imported_postprocessing.update({row["STATISTIC"]: {'postprocess': row['POSTPROCESS'],
                                                                   'mean': row['MEAN'],
                                                                   'median': row['MEDIAN'],
                                                                   'stdev': row['STDEV'],
                                                                   'min': row['MIN'],
                                                                   'max': row['MAX'],
                                                                   'cumulative': row['CUMULATIVE']}})

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

    TODO: Describe input file format, see import_postprocessing
    """
    imported_historic = import_statistics_flat(path + r'\\input_historic.csv', custom_keys=['AGGREGATION', 'REGION', 'DEPOSIT_TYPE', 'COMMODITY', 'STATISTIC'])
    
    if copy_path is not None:
        copyfile(path + r'\\input_historic.csv', copy_path + r'\\input_historic.csv')
    if log_path is not None:
        export_log('Imported input_historic.csv', log_path, 1)
    
    return imported_historic
    
    

def import_statistics_flat(path, log_path=None, custom_keys=False):
    """
    import_statistics_flat()
    Imports csv file with a flat statistics data structure.
    custom_keys | Default is (i,j,a,r,d,c,s).
                | For input_historic.csv use:
                | custom_keys=['AGGREGATION', 'REGION', 'DEPOSIT_TYPE', 'COMMODITY', 'STATISTIC']
    Returns a shallow nested dictionary {(i,j,a,r,d,c,s): {time: values}}
    TODO: Describe input file format, see import_postprocessing
    TODO: Refactor to import_statistics_flat
    """
    print('Importing statistics.csv')
        
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
                time_keys = row['TIME']
            else:
                tuple_key = tuple([row[k] for k in keys])

                imported_statistics.update({tuple_key: dict(zip(time_keys, row['TIME']))})
                
                
    if log_path is not None:
        export_log('Imported a flat statistics csv.', output_path=log_path, print_on=1)

    return imported_statistics

def import_statistics_flat_filter(path, stats_included, log_path=None):
    """
    import_statistics_flat_filter()
    Imports a _statistics.csv file with a flatter data structure for post-processing.
    stats_included is a list of statistics to include
    Returns a nested dictionary {s:{(i,j,a,r,d,c,s): {time: values}}} and the time keys.
    ## top level {s} is a default dictionary
    TODO: Describe input file format, see import_postprocessing
    TODO: Refactor to import_statistics_filter()
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
                
            # Filter statistics
            if row['STATISTIC'] in stats_included:
                time_dict = dict(zip(time_keys,row['TIME']))
                imported_statistics[row['STATISTIC']].update({(row['SCENARIO_INDEX'],
                                                              row['ITERATION'],
                                                              row['AGGREGATION'],
                                                              row['REGION'],
                                                              row['DEPOSIT_TYPE'],
                                                              row['COMMODITY'],
                                                              row['STATISTIC']): time_dict})                
    if log_path is not None:
        export_log('Imported_statistics.csv', output_path=log_path, print_on=1)
    return imported_statistics, time_keys
