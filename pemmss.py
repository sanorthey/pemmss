"""
Primary Exploration, Mining and Metal Supply Scenario (PEMMSS) model

Developed by Stephen A. Northey
in collaboration with S. Pauliuk, S. Klose, M. Yellishetty and D. Giurco
For further information email:
    stephen.northey@uts.edu.au or stephen.northey@gmail.com

This scenario model evaluates the rates of mine development, mineral exploration
and co-product recovery required to meet primary demand over-time.

--- Cross-references to Journal Article ---
# P1 - Initialisation, Import scenario description and calibration data
# P2 - Scenario Loop
# P3 - Iteration Loop
# P4 - Time Loop
# P5 - Time Dependent Parameter Update Algorithm
# P6 - Greenfield Discovery (Background) Algorithm
# P7 - Value Prioritisation Algorithm
# P8 - Commodity Supply Loop
# P9 - Project Supply Algorithm
# P10 - Greenfield Discovery (Demanded) Algorithm
# P11 - Active Project Status Reset
# P12 - Brownfield Exploration Algorithm
# P13 - Add Historic Series
# P14 - Export Iteration Results
# P15 - Filter and Merge Results
# P16 - Generate Graphs
# R1 - Read static input files
# R2 - Read project files
# R3 - Read scenario & iteration output files
# W1 - Write iteration output files
# W2 - Write consolidated output files


---Functions---
initialise()
scenario()
_main_()

# TODO: 1. Add copywrite statement
# TODO: 2. Add file structure
# TODO: 3. Change argument passing to via dictionary
# TODO: 4. Update this docstring after all module todos are completed.
"""

# Import standard packages
import datetime
import random
from os import mkdir, getcwd
from time import time
from copy import deepcopy
from multiprocessing import Pool, cpu_count
from collections import defaultdict


# Import custom modules
import modules.file_import as file_import
import modules.file_export as file_export
import modules.deposit as deposit
import modules.results as results
import modules.post_processing as post_processing


def initialise():
    """
    # P1

    TODO: Change to returning a dictionary
    TODO: Add simple docstring
    """
    # Initialise and Import Data
    RUN_TIME = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

    # Set-up file management constants
    CWD = getcwd()
    INPUT_FOLDER = (CWD + r'\input_files')
    OUTPUT_FOLDER = (CWD + r'\output_files\\' + RUN_TIME)
    OUTPUT_FOLDER_INPUT_COPY = (OUTPUT_FOLDER + r'\_input_files')
    OUTPUT_FOLDER_STATISTICS = (OUTPUT_FOLDER + r'\_statistics')
    OUTPUT_FOLDER_GRAPHS = (OUTPUT_FOLDER + r'\_graphs')
    LOG = (OUTPUT_FOLDER + r'\\log.txt')

    # Make directories to store model outputs
    mkdir(OUTPUT_FOLDER)
    mkdir(OUTPUT_FOLDER_INPUT_COPY)
    mkdir(OUTPUT_FOLDER_STATISTICS)
    mkdir(OUTPUT_FOLDER_GRAPHS)

    # Model version details for log and file writing
    VERSION_NUMBER = (str(0.996))
    VERSION_DATE = '2021-04-21'

    file_export.export_log("Primary Exploration, Mining and Metal Supply Scenario (PEMMSS)\n" +
                   "Version " + VERSION_NUMBER + ", " + VERSION_DATE + " \n" +
                   "Developed by Stephen A. Northey " +
                   'in collaboration with S. Pauliuk, S. Klose, M. Yellishetty and D. Giurco \n \n' +
                   "For further information contact stephen.northey@uts.edu.au or stephen.northey@gmail.com.\n" +
                   "- - - - - - - - - - - - - - - \n", output_path=LOG, print_on=1)
    file_export.export_log('Model executed at '+RUN_TIME+'\n', output_path=LOG, print_on=1)

    # Import user input files and assign variables
    PARAMETERS, IMPORTED_FACTORS, TIMESERIES_PROJECT_UPDATES, TIMESERIES_EXPLORATION_PRODUCTION_FACTORS_UPDATES, IMPORTED_DEMAND, IMPORTED_GRAPHS, IMPORTED_POSTPROCESSING, IMPORTED_HISTORIC = file_import.import_static_files(INPUT_FOLDER, copy_path_folder=OUTPUT_FOLDER_INPUT_COPY)
    return (PARAMETERS, IMPORTED_FACTORS, TIMESERIES_PROJECT_UPDATES,
            TIMESERIES_EXPLORATION_PRODUCTION_FACTORS_UPDATES, IMPORTED_DEMAND,
            IMPORTED_GRAPHS, IMPORTED_POSTPROCESSING,
            INPUT_FOLDER, OUTPUT_FOLDER, OUTPUT_FOLDER_INPUT_COPY, OUTPUT_FOLDER_STATISTICS, OUTPUT_FOLDER_GRAPHS, IMPORTED_HISTORIC, LOG)


def scenario(parameters, imported_factors, timeseries_project_updates, timeseries_exploration_production_factors_updates, imported_demand, imported_graphs, imported_postprocessing, input_folder, output_folder, output_folder_input_copy, output_folder_statistics, output_folder_graphs, imported_historic, log, i):
    """
    Generate a scenario based upon the 
    # P2

    TODO: Update docstring
    TODO: Change to inputting a dictionary
    TODO: Check and test P6 - background greenfield discovery loop
    """

    ### Scenario Specific Data

    year_start = parameters['year_start'][i]
    year_end = parameters['year_end'][i]

    # As import_projects can have stochastic elements, need to use the scenario specific seed.
    random.seed(parameters['random_seed'][i])
    output_folder_scenario = output_folder + '\\' + str(parameters['scenario_name'][i])
    output_path_stats = (output_folder_scenario + r'\_statistics.csv')
    mkdir(output_folder_scenario)
    
    ### Iteration Loop
    # P3
    for j in range(0, parameters['iterations'][i]):
        # Execution timing
        log_message = []
        jt0 = (time())
        factors = deepcopy(imported_factors)
        demand = deepcopy(imported_demand[parameters['scenario_name'][i]])
        projects = file_import.import_projects(factors, input_folder, copy_path=output_folder_input_copy)
        projects = file_import.import_project_coproducts(factors, input_folder, projects, parameters['generate_all_coproducts'][i], copy_path=output_folder_input_copy)
        log_message.append('\nScenario '+str(parameters['scenario_name'][i])+' Iteration '+str(j))
        
        
        # Time Loop - Iterates model through each time period
        # P4
        for year_current in range(year_start, year_end+1):

            # Update project variables and exploration_production_factors for timeseries overrides in input_exploration_production_factors_timeseries.csv
            # P5
            for p in projects:
                p.update_by_region_deposit_type(timeseries_project_updates[year_current])
            factors = deposit.update_exploration_production_factors(factors, timeseries_exploration_production_factors_updates[year_current])

            # Background greenfield discovery
            # P6
            if parameters['greenfield_background'][i] > 0:
                # FIXME: check this for loop
                for gb in range(parameters['greenfield_background'][i]):
                    projects.append(deposit.resource_discovery(factors, year_current, True, len(projects)+1))

            # Priority Ranking Algorithm
            # P7
            if parameters['priority_active'][i] == 1:
                # Sort then prioritise existing mines
                projects.sort(key=lambda x: x.value)
                projects.sort(key=lambda x: x.status, reverse=True)
            else:
                projects.sort(key=lambda x: x.value)

            # Commodity Supply-Demand Balance Algorithm
            # P8
            for c in demand:
                if demand[c]['balance_supply'] == 1:

                    # Project Loop
                    # P9
                    for project in projects:
                        # break loop if residual demand less than the commodities demand threshold
                        if demand[c][year_current] <= demand[c]['demand_threshold']:
                            break

                        # Determine intermediate supply for all the project's commodities. Note project will not supply for certain project.status values.
                        supplied = project.supply(demand[c][year_current]/demand[c]['intermediate_recovery'], year_current, c)
                        # Subtract supply from demand for all commodities produced by the project.
                        if supplied == 1:
                            for p_commodity in project.commodity:
                                if p_commodity not in demand:
                                    log_message.append('Project '+str(project.name)+' attempted to supply commodity '+str(p_commodity)+ ' that has no corresponding demand list. Supply of this commodity has not been recorded. To address this ensure in input_demand.csv all commodities have a corresponding demand entry for scenario '+parameters['scenario_name'][i]+' (this can be blank).')
                                else:
                                   demand[p_commodity][year_current] -= project.production_intermediate[p_commodity][year_current] * demand[p_commodity]['intermediate_recovery']

                    # Greenfield Discovery (Demanded). If supply insufficient, generate new deposits
                    # P10
                    if parameters['greenfield_exploration_on'][i] == 1:
                        while demand[c][year_current] > demand[c]['demand_threshold']:
                            projects.append(deposit.resource_discovery(factors, year_current, False, len(projects)+1))
                            # Subtract supply from demand for all commodities produced by the project. Note that this means oversupply of a commodity can happen when there are multiple demand commodities being balanced.
                            supplied = projects[-1].supply(demand[c][year_current]/demand[c]['intermediate_recovery'], year_current, c)
                            if supplied == 1:
                                for p_commodity in projects[-1].commodity.keys():
                                    demand[p_commodity][year_current] -= projects[-1].production_intermediate[p_commodity][year_current] * demand[p_commodity]['intermediate_recovery']

            # Adjust next years commodity demand by a ratio of any under or over commodity supply.
            # P10
            for c in demand:
                if year_current + 1 in demand[c].keys():
                    if demand[c]['demand_carry'] != 0:
                        demand[c][year_current + 1] += demand[c][year_current] * demand[c]['demand_carry']
                else:
                    log_message.append('\nFinal unmet '+str(c)+' demand at end of '+str(year_current)+' = '+str(demand[c][year_current]))

            # Reset project status for active mines. Note this must be done before the ranking algorithm, but after the supply and greenfield algorithms.
            # P11
            for project in projects:
                if project.status == 2:
                    project.status = 1
            
            # Brownfield Resource Expansion Algorithm
            # P12
            if parameters['brownfield_exploration_on'][i] == 1:
                for project in projects:
                    if project.status == 1:
                        project.resource_expansion(year_current)


        jt1 = (time())
        log_message.append('\nIteration execution duration '+str((jt1-jt0))+' seconds.')
        
        #################################################
        ### Results Processing
        
        stats = defaultdict(dict)
        key_projects_dict = {}
        
        # Iterate through projects
        for p in projects:
            # Append p to all relevant keys
            # Create new key where required
            # key_projects_dict = {(i,j,a,r,d,c):[p, p2, p3, ...]}
            key_projects_dict = p.update_key_dict(key_projects_dict, parameters['scenario_name'][i], j)

        for key, project_list in key_projects_dict.items():
            # Generate stats {(i,j,a,r,d,s): {time: value}}
            stats.update(results.generate_statistics(key, project_list, range(year_start, year_end+1), demand))
            
        year_set = set(range(year_start, year_end+1))
        
        for a_r_d_c_s_key, time_dict in imported_historic.items():
            # Update stats to include any historic values present in input_historic.csv
            # P13
            stats[(parameters['scenario_name'][i],j,)+(a_r_d_c_s_key)].update(time_dict)
            year_set.update(time_dict.keys())
        

        jt2 = (time())
        log_message.append('\nIteration statistics generation duration '+str((jt2-jt1))+' seconds.')

        ### Results Export
        # P14
        # W1
        # Define file export paths
        output_path_projects = output_folder_scenario + '\\' + str(j) + '-Projects.csv'
        output_path_production_ore = output_folder_scenario + '\\' + str(j) + '-Production_Ore.csv'
        output_path_expansion = output_folder_scenario + '\\' + str(j) + '-Expansion.csv'
        output_path_demand = output_folder_scenario + '\\' + str(j) + '-Demand.csv'

        # Export projects data
        projects.sort(key=lambda x: int(x.id_number))
        file_export.export_projects(output_path_projects, projects)
        file_export.export_project_dictionary(output_path_production_ore, projects, 'production_ore', header='None', id_key='id_number', commodity='None')
        file_export.export_project_dictionary(output_path_expansion, projects, 'expansion', header='None', id_key='id_number', commodity='None')
        for c in demand:
            output_path_production_intermediate = output_folder_scenario + '\\' + ''+str(j) + '-Production_Intermediate_'+str(c)+'.csv'
            file_export.export_project_dictionary(output_path_production_intermediate, projects, 'production_intermediate', header='None', id_key='id_number', commodity=c)

        # Export original demand
        file_export.export_demand(output_path_demand, demand)

        # Export statistics
        time_range = list(year_set)
        time_range.sort(key=lambda x: int(x))
        file_export.export_statistics_flat(output_path_stats, stats, time_range)

        jt3 = (time())
        log_message.append('\nIteration export duration '+str((jt3-jt2)))
        log_message.append('\nExported to '+output_folder_scenario)
        file_export.export_log(''.join(log_message), output_path=log, print_on=1)


    return output_folder_scenario

def post_process(scenario_folders, output_stats_folder, output_graphs_folder, imported_postprocessing, imported_graphs):
    """
    # P15
    # P16

    FIXME: Write docstrings
    FIXME: Fix figure generation loop
    """

    # Filter and merge scenario and iteration statistics
    # P15
    statistics_files = post_processing.merge_scenarios(imported_postprocessing, scenario_folders, output_stats_folder)
    # Generate figures
    # P16
    # FIXME: generate_figures based upon filtered statistics

    #for s in statistics_files:
    #    post_processing.generate_figures(statistics_files[s]['path'], imported_graphs, output_graphs_folder)


if __name__ == '__main__':
    """
    Execute scenario modelling across parallel processes
    
    --- Journal article cross-references ---
    P1 - Import input files
    P2 - Execute scenario modelling concurrently amongst pooled cpu processes
    P13 - Check for pooled process errors and exceptions
    P14 - Post-processing of scenario output files to produce summary graphs
    
    # FIXME: Refactor CONSTANTS variable to a dictionary
    """
    t0 = (time())
    
    # P1 - Import input files
    CONSTANTS = initialise()
    scenario_folder_objects = []
    scenario_folders = []

    # P2 - Execute scenario modelling concurrently amongst pooled cpu processes
    with Pool(cpu_count()-1) as pool:
        for i, scenario_name in enumerate(CONSTANTS[0]['scenario_name']):
            scenario_folder_objects.append(pool.apply_async(scenario, CONSTANTS + (i,)))  # Contains P3 to P12
            print('Scenario '+scenario_name+' initialised.')
        print('\nScenarios being modelled.')
        pool.close()
        pool.join()

    # P13 - Check for pooled process errors and exceptions
    for o in scenario_folder_objects:
        # Get returned values from AsyncResult objects.
        # .get() will also raise any pooled process errors and exceptions. 
        scenario_folders.append(o.get())


    print('\n--- Scenario Modelling Complete ---',
          '\nPost-processing of scenario outputs.')

    t1 = (time())
    # P15 - Post-processing of scenario output files to produce summary files
    # P16 - Post-processing of output files to generate graphs
    post_process(scenario_folders=scenario_folders, output_stats_folder=CONSTANTS[10],
                 output_graphs_folder=CONSTANTS[11], imported_postprocessing=CONSTANTS[6],
                 imported_graphs=CONSTANTS[5])
    
    t2 = (time())
    print('Post-processing duration '+str(t2-t1))
    print('\n--- Post-Processing Complete---\n\nResults available in:\n'+str(CONSTANTS[8]))


    file_export.export_log('\nExecution time (s): '+str(t2-t0), output_path=CONSTANTS[-1], print_on=1)
    # Scenario generation complete. Congratulations !!

