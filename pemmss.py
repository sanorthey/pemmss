"""
Primary Exploration, Mining and Metal Supply Scenario (PEMMSS) model

Developed by Stephen A. Northey
in collaboration with S. Pauliuk, S. Klose, M. Yellishetty and D. Giurco
For further information email:
    stephen.northey@uts.edu.au

This scenario model evaluates the rates of mine development, mineral exploration
and co-product recovery required to meet primary demand over-time.

--- Journal article cross-references ---
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

---File Structure---
CITATION.cff
LICENSE.md
pemmss.py
README.md
input_files/
    input_demand.csv
    input_input_exploration_production_factors.csv
    input_input_exploration_production_factors_timeseries.csv
    input_graphs.csv
    input_graphs_formatting.csv
    input_historic.csv
    input_parameters.csv
    input_postprocessing.csv
    input_project_coproducts.csv
    input_projects.csv
    input_files/shapefile/shapefile.shp
modules/
    deposit.py
    file_export.py
    file_import.py
    post_processing.py
    results.py
output_files/
    placeholder.txt

Copyright and license information available in LICENSE.md
Attribution and citation information available in CITATION.cff
"""

# Import standard packages
import datetime
import random
import cProfile
from time import time
from copy import deepcopy
from multiprocessing import Pool, cpu_count
from collections import defaultdict
from pathlib import Path
import geopandas as gpd

# Import custom modules
import modules.file_import as file_import
import modules.file_export as file_export
import modules.deposit as deposit
import modules.results as results
import modules.post_processing as post_processing
import modules.spatial as spatial


def initialise():
    """
    Generates the model run output directories, creates the log file and imports and copies non-stochastic input files.
    Returns a dictionary containing input data for passing to scenario().

    Files read:
    input_files/input_demand.csv
    input_files/input_exploration_production_factors.csv
    input_files/input_exploration_production_factors_timeseries.csv
    input_files/input_graphs.csv
    input_files/input_historic.csv
    input_files/input_parameters.csv
    input_files/input_postprocessing.csv

    Files & directories written:
    output_files/[RUN_TIME]/
    output_files/[RUN_TIME]/_input_files/
    output_files/[RUN_TIME]/_input_files/input_demand.csv
    output_files/[RUN_TIME]/_input_files/input_exploration_production_factors.csv
    output_files/[RUN_TIME]/_input_files/input_exploration_production_factors_timeseries.csv
    output_files/[RUN_TIME]/_input_files/input_graphs.csv
    output_files/[RUN_TIME]/_input_files/input_historic.csv
    output_files/[RUN_TIME]/_input_files/input_parameters.csv
    output_files/[RUN_TIME]/_input_files/input_postprocessing.csv
    output_files/[RUN_TIME]/_statistics/
    output_files/[RUN_TIME]/_graphs/
    output_files/[RUN_TIME]/log.txt

    --- Journal article cross-references ---
    P1, R1

    """
    constants = {}

    # Initialise and Import Data
    constants['run_time'] = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

    # Set-up file management constants
    constants['cwd'] = Path.cwd()
    constants['input_folder'] = constants['cwd'] / 'input_files'
    constants['output_folder'] = constants['cwd'] / 'output_files' / constants['run_time']
    constants['output_folder_input_copy'] = constants['output_folder'] / '_input_files'
    constants['output_folder_statistics'] = constants['output_folder'] / '_statistics'
    constants['output_folder_graphs'] = constants['output_folder'] / '_graphs'
    constants['log'] = constants['output_folder'] / 'log.txt'

    # Make directories to store model outputs
    constants['output_folder'].mkdir(parents=True, exist_ok=True)
    constants['output_folder_input_copy'].mkdir(parents=True, exist_ok=True)
    constants['output_folder_statistics'].mkdir(parents=True, exist_ok=True)
    constants['output_folder_graphs'].mkdir(parents=True, exist_ok=True)

    # Model version details for log and file writing
    constants['version_number'] = '1.3.1'
    constants['version_date'] = '2024-07-10'

    file_export.export_log("Primary Exploration, Mining and Metal Supply Scenario (PEMMSS) model\n" +
                           "Version " + constants['version_number'] + ", " + constants['version_date'] + " \n" +
                           "Developed led by Stephen A. Northey " +
                           'in collaboration with S. Pauliuk, S. Klose, M. Yellishetty, D. Giurco, B. Mendonca Severiano and J. Hyman. \n \n' +
                           "For further information contact stephen.northey@uts.edu.au.\n" +
                           "- - - - - - - - - - - - - - - \n", output_path=constants['log'], print_on=1)
    file_export.export_log('Model executed at ' + constants['run_time'] + '\n', output_path=constants['log'], print_on=1)

    # Import user input files and assign variables
    constants.update(file_import.import_static_files(constants['input_folder'], copy_path_folder=constants['output_folder_input_copy'], log_file=constants['log']))

    # [BM] Loading the shapefile
    shapefile_path = constants['input_folder'] / 'shapefile/shapefile.shp'
    constants['shapefile_gdf'] = spatial.import_shapefile(shapefile_path)

    return constants


def scenario(i, constants):
    """
    Executes multiple iterations of the scenario run, creates scenario specific output folders and files,
    imports project specific data and then loops through all time periods where it generates background greenfield
    discoveries, sorts the production schedule of deposits, balances commodity supply and demand, generates demanded
    greenfield discoveries, adjusts subsequent years demand by a factor of over/undersupply and generates brownfield
    expansion of deposits. Then final scenario, iteration, project data and results are exported to .csv files.
    Returns the path to the scenario specific output folder.

    Files read:
    input_files/input_projects.csv
    input_files/input_project_coproducts.csv
    input_files/shapefile/shapefile.shp

    Files & directories written:
    output_files/[RUN_TIME]/_input_files/input_projects.csv
    output_files/[RUN_TIME]/_input_files/input_project_coproducts.csv
    output_files/[RUN_TIME]/log.txt
    output_files/[RUN_TIME]input_files/exploration_production
    output_files/[RUN_TIME]/[scenario_name]/_statistics.csv
    output_files/[RUN_TIME]/[scenario_name]/[iteration]-Projects.csv
    output_files/[RUN_TIME]/[scenario_name]/[iteration]-Production_Ore.csv
    output_files/[RUN_TIME]/[scenario_name]/[iteration]-Expansion.csv
    output_files/[RUN_TIME]/[scenario_name]/[iteration]-Demand.csv
    output_files/[RUN_TIME]/[scenario_name]/[iteration]-Production_Intermediate_[commodity].csv

    --- Journal article cross-references ---
    P3, P4, P5, P6, P7, P8, P9, P10, P11, P12, P13, P14, R2, W1
    """
    parameters = constants['parameters'][i]
    imported_factors = constants['imported_factors']
    timeseries_project_updates = constants['timeseries_project_updates']
    timeseries_exploration_production_factors_updates = constants['timeseries_exploration_production_factors_updates']
    imported_demand = constants['imported_demand']
    input_folder = constants['input_folder']
    output_folder = constants['output_folder']
    output_folder_input_copy = constants['output_folder_input_copy']
    imported_historic = constants['imported_historic']
    log = constants['log']
    shapefile_gdf = constants['shapefile_gdf']

    # --- Scenario Specific Data

    year_start = parameters['year_start']
    year_end = parameters['year_end']

    # As import_projects can have stochastic elements, need to use the scenario specific seed.
    random.seed(parameters['random_seed'])
    output_folder_scenario = output_folder / str(i)
    output_path_stats = output_folder_scenario / '_statistics.csv'
    output_folder_scenario.mkdir(parents=True, exist_ok=True)

    # --- Iteration Loop
    # P3
    for j in range(0, parameters['iterations']):
        # Execution timing
        log_message = []
        jt0 = (time())
        factors = deepcopy(imported_factors)
        demand = deepcopy(imported_demand[parameters['scenario_name']])
        commodities = list(demand.keys())
        # Projects imported here instead of initialise() so that each iteration has unique random data infilling.
        projects = file_import.import_projects(factors, input_folder / 'input_projects.csv', copy_path=output_folder_input_copy, log_path=log)
        projects = file_import.import_project_coproducts(factors, input_folder / 'input_project_coproducts.csv', projects, parameters['generate_all_coproducts'], copy_path=output_folder_input_copy, log_path=log)
        log_message.append('\nScenario ' + str(parameters['scenario_name']) + ' Iteration ' + str(j) + '\nImported input_projects.csv\nImported input_project_coproducts.csv')

        # Time Loop - Iterates model through each time period
        # P4
        for year_current in range(year_start, year_end + 1):

            # Update project variables and exploration_production_factors for timeseries overrides in input_exploration_production_factors_timeseries.csv
            # Update project value if enabled
            # P5
            if year_current in timeseries_exploration_production_factors_updates:
                factors = deposit.update_exploration_production_factors(factors, timeseries_exploration_production_factors_updates[year_current])
            if year_current in timeseries_project_updates:
                if parameters['update_values'] == 1:
                    for p in projects:
                        p.update_by_region_deposit_type(timeseries_project_updates[year_current], log_file=log)
                        p.value_update(log_file=log)
                else:
                    for p in projects:
                        p.update_by_region_deposit_type(timeseries_project_updates[year_current], log_file=log)

            # Background greenfield discovery
            # P6
            if parameters['greenfield_background'] > 0:
                for gb in range(parameters['greenfield_background']):
                    print("TRIED P6")
                    projects.append(deposit.resource_discovery(factors, year_current, True, len(projects), shapefile_gdf, 'REGION_1'))

            # Priority Ranking Algorithm
            # P7
            if parameters['priority_marginal'] == 1:  # Sort by current ore tranche value
                projects.sort(key=lambda x: x.value[x.current_tranche]['ALL'], reverse=True)
            else:
                projects.sort(key=lambda x: x.value['ALL']['ALL'], reverse=True)  # Sort by total net value
            if parameters['priority_active'] == 1:  # Prioritise existing mines
                projects.sort(key=lambda x: x.status, reverse=True)

            # Commodity Supply-Demand Balance Algorithm
            # P8

            random.shuffle(commodities)
            for c in commodities:
                if demand[c]['balance_supply'] == 1:

                    # Project Loop
                    # P9
                    for project in projects:
                        # break loop if residual demand less than the commodities demand threshold
                        if demand[c][year_current] <= demand[c]['demand_threshold']:
                            break

                        # Determine intermediate supply for all the project's commodities. Note project will not supply for certain project.status values.
                        supplied = project.supply(demand[c][year_current]/demand[c]['intermediate_recovery'], year_current, c, marginal_recovery=parameters['marginal_recovery'])
                        # Subtract supply from demand for all commodities produced by the project.
                        if supplied == 1:
                            for p_commodity in project.commodity:
                                if p_commodity not in demand:
                                    log_message.append('Project '+str(project.name)+' attempted to supply commodity '+str(p_commodity)+ ' that has no corresponding demand list. Supply of this commodity has not been recorded. To address this ensure in input_demand.csv all commodities have a corresponding demand entry for scenario '+parameters['scenario_name']+' (this can be blank).')
                                else:
                                    demand[p_commodity][year_current] -= project.production_intermediate[p_commodity][year_current] * demand[p_commodity]['intermediate_recovery']

                    # Greenfield Discovery (Demanded). If supply insufficient, generate new deposits
                    # P10
                    if parameters['greenfield_exploration_on'] == 1:
                        while demand[c][year_current] > demand[c]['demand_threshold']:
                            print("TRIED P10")
                            projects.append(deposit.resource_discovery(factors, year_current, False, len(projects)+1, shapefile_gdf, 'REGION_1'))
                            # Subtract supply from demand for all commodities produced by the project. Note that this means oversupply of a commodity can happen when there are multiple demand commodities being balanced.
                            supplied = projects[-1].supply(demand[c][year_current]/demand[c]['intermediate_recovery'], year_current, c, marginal_recovery=parameters['marginal_recovery'])
                            if supplied == 1:
                                for p_commodity in projects[-1].commodity.keys():
                                    demand[p_commodity][year_current] -= projects[-1].production_intermediate[p_commodity][year_current] * demand[p_commodity]['intermediate_recovery']

            # Adjust next year's commodity demand by a ratio of any under or over commodity supply.
            # P11
            for c in demand:
                if year_current + 1 in demand[c].keys():
                    if demand[c]['demand_carry'] != 0:
                        demand[c][year_current + 1] += demand[c][year_current] * demand[c]['demand_carry']
                else:
                    log_message.append('\nFinal unmet '+str(c)+' demand at end of '+str(year_current)+' = '+str(demand[c][year_current]))

            # Reset project status. Note this must be done before the ranking algorithm, but after the supply and greenfield algorithms.
            # P12
            for project in projects:
                # Record status at end of timestep
                project.status_timeseries.update({year_current: project.status})
                # Active mine status reset
                if project.status == 2:  # Produced
                    project.status = 1  # Developed
                # Mine end year reset
                if project.status == 3:  # Produced and depleted
                    project.status = -1  # Depleted
                # Deposits failing development probability test reset
                if project.status == -3:  # Development probability test failed
                    project.status = 0  # Undeveloped

            # Brownfield Resource Expansion Algorithm
            # P13
            if parameters['brownfield_exploration_on'] == 1:
                for project in projects:
                    if project.status == 1:
                        project.resource_expansion(year_current)

        jt1 = (time())
        log_message.append('\nIteration execution duration ' + str((jt1 - jt0)) + ' seconds.')

        # -------------------------------------
        # --- Results Processing

        stats = defaultdict(dict)
        key_projects_dict = {}

        # Iterate through projects
        for p in projects:
            # Append p to all relevant keys
            # Create new key where required
            # key_projects_dict = {(i,j,a,r,d,c):[p, p2, p3, ...]}
            key_projects_dict = p.update_key_dict(key_projects_dict, parameters['scenario_name'], j)

        for key, project_list in key_projects_dict.items():
            # Generate stats {(i,j,a,r,d,s): {time: value}}
            stats.update(results.generate_statistics(key, project_list, range(year_start, year_end + 1), demand))

        year_set = set(range(year_start, year_end + 1))

        # Update stats to include any historic values present in input_historic.csv
        # P14
        for a_r_d_c_s_key, time_dict in imported_historic.items():
            stats[(parameters['scenario_name'], j,) + (a_r_d_c_s_key)].update(time_dict)
            year_set.update(time_dict.keys())

        jt2 = (time())
        log_message.append('\nIteration statistics generation duration ' + str((jt2 - jt1)) + ' seconds.')

        # ----- Results Export
        # P15
        # W1
        # Define file export paths
        output_path_projects = output_folder_scenario / f'{j}-Projects.csv'
        output_path_production_ore = output_folder_scenario / f'{j}-Production_Ore.csv'
        output_path_expansion = output_folder_scenario / f'{j}-Expansion.csv'
        output_path_demand = output_folder_scenario / f'{j}-Demand.csv'
        output_path_status = output_folder_scenario / f'{j}-Status.csv'

        # Export projects data
        projects.sort(key=lambda x: int(x.id_number))
        file_export.export_projects(output_path_projects, projects)
        file_export.export_project_dictionary(output_path_production_ore, projects, 'production_ore', header='None', id_key='id_number', commodity='None', log_path=log)
        file_export.export_project_dictionary(output_path_expansion, projects, 'expansion', header='None', id_key='id_number', commodity='None', log_path=log)
        file_export.export_project_dictionary(output_path_status, projects, 'status_timeseries', header='None', id_key='id_number', commodity='None', log_path=log)

        for c in demand:
            # Define commodity specific project export paths
            output_path_production_intermediate = output_folder_scenario / f'{j}-Production_Intermediate_{c}.csv'
            output_path_expansion_contained = output_folder_scenario / f'{j}-Expansion_Contained_{c}.csv'
            output_path_grade_timeseries = output_folder_scenario / f'{j}-Grade_Timeseries_{c}.csv'

            # Export commodity specific project data
            file_export.export_project_dictionary(output_path_production_intermediate, projects,'production_intermediate', header='None', id_key='id_number', commodity=c, log_path=log)
            file_export.export_project_dictionary(output_path_expansion_contained, projects, 'expansion_contained', header='None', id_key='id_number', commodity=c, log_path=log)
            file_export.export_project_dictionary(output_path_grade_timeseries, projects, 'grade_timeseries', header='None', id_key='id_number', commodity=c, log_path=log)

        # Export unmet demand timeseries
        file_export.export_demand(output_path_demand, demand)

        # Export statistics
        time_range = list(year_set)
        time_range.sort(key=lambda x: int(x))
        file_export.export_statistics(output_path_stats, stats, time_range)

        jt3 = (time())
        log_message.append('\nIteration export duration ' + str((jt3 - jt2)))
        log_message.append('\nExported to ' + str(output_folder_scenario))
        file_export.export_log(''.join(log_message), output_path=log, print_on=1)

    return output_folder_scenario


def post_process(scenario_folders, output_stats_folder, output_graphs_folder, imported_postprocessing, imported_graphs, imported_graphs_formatting, log_path):
    """
    Merges and filters scenario data, generate and export graphs and final results files.

    Files read:
    output_files/[RUN_TIME]/[scenario]/_statistics.csv

    Files & directories written:
    output_files/[RUN_TIME]/_statistics/
    output_files/[RUN_TIME]/_statistics/_[statistic].csv
    output_files/[RUN_TIME]/_graphs/
    for file_prefix, plot_key in input_files/input_graphs.csv
        output_files/[RUN_TIME]/_graphs/_[file_prefix] [plot_key].png
        output_files/[RUN_TIME]/_graphs/_[file_prefix] [plot_key].csv

    --- Journal article cross-references ---
    P16, P17, R3, R4, W2, W3
    """
    pt0 = (time())

    # P16, R3, W2 - Filter and merge scenario and iteration statistics
    file_export.export_log('Merging scenario data', output_path=log_path, print_on=1)
    statistics_files = post_processing.merge_scenarios(imported_postprocessing, scenario_folders, output_stats_folder)
    project_statistics_files = post_processing.project_iteration_statistics(scenario_folders)
    pt1 = (time())
    file_export.export_log('Merge duration ' + str((pt1 - pt0)) + ' seconds.', output_path=log_path, print_on=1)
    file_export.export_log('Merged data exported to ' + str(output_stats_folder), output_path=log_path, print_on=1)

    # P17, R4, W3 - Generate figures
    file_export.export_log('\nGenerating Figures:', output_path=log_path, print_on=1)
    figure_paths_objects = []
    figure_paths = []
    with Pool(cpu_count() - 1) as pool:
        for graph in imported_graphs:
            figure_paths_objects.append(pool.apply_async(post_processing.generate_figure, (statistics_files, graph, imported_graphs_formatting, output_graphs_folder)))
        pool.close()
        pool.join()

    # Get returned values from AsyncResult objects.
    # .get() will also raise any pooled process errors and exceptions.
    for o in figure_paths_objects:
        figure_paths.append(o.get())

    pt2 = (time())
    file_export.export_log('Figure generation duration '+str((pt2-pt1))+' seconds.', output_path=log_path, print_on=1)
    file_export.export_log('Exported to '+str(output_graphs_folder), output_path=log_path, print_on=1)


def main():
    """
    Execute scenario modelling across parallel processes

    --- Journal article cross-references ---
    P1 - Import input files
    P2 - Execute scenario modelling concurrently amongst pooled cpu processes
    P16 - Post-processing of scenario output files to produce summary graphs
    P17 - Post-processing of scenario output files to generate graphs
    """
    t0 = (time())

    # P1 - Import input files
    CONSTANTS = initialise()
    scenario_folder_objects = []
    scenario_folders = []

    # P2 - Execute scenario modelling concurrently amongst pooled cpu processes
    with Pool(cpu_count() - 1) as pool:
        for scenario_name in CONSTANTS['parameters']:
            i = scenario_name
            scenario_folder_objects.append(pool.apply_async(scenario, (i,), dict(constants=CONSTANTS)))  # R2, W1 and P3 to P14
            print('Scenario ' + scenario_name + ' initialised.')
        print('\nScenarios being modelled.')
        pool.close()
        pool.join()

    # Check for pooled process errors and exceptions
    for o in scenario_folder_objects:
        # Get returned values from AsyncResult objects.
        # .get() will also raise any pooled process errors and exceptions.
        scenario_folders.append(o.get())

    t1 = (time())
    file_export.export_log('\nScenario modelling duration ' + str(t1 - t0) + ' seconds.\n--- Scenario Modelling Complete ---\n\nPost-processing of scenario outputs.\n',
                           output_path=CONSTANTS['log'], print_on=1)

    # P16 - Filter and Merge Results
    # P17 - Generate Graphs
    post_process(scenario_folders=scenario_folders,
                 output_stats_folder=CONSTANTS['output_folder_statistics'],
                 output_graphs_folder=CONSTANTS['output_folder_graphs'],
                 imported_postprocessing=CONSTANTS['imported_postprocessing'],
                 imported_graphs=CONSTANTS['imported_graphs'],
                 imported_graphs_formatting=CONSTANTS['imported_graphs_formatting'],
                 log_path=CONSTANTS['log'])

    t2 = (time())
    log_message = ('\nPost-processing duration ' + str(t2 - t1) +
                   '\n--- Post-Processing Complete---\n\nResults available in:\n' + str(CONSTANTS['output_folder']) +
                   '\nExecution time (s): ' + str(t2 - t0))
    file_export.export_log(log_message, output_path=CONSTANTS['log'], print_on=1)

    # Scenario generation complete. Congratulations !!


def post_process_only():
    # P1 - Import input files
    CONSTANTS = initialise()
    scenario_folders = []

    with cProfile.Profile() as pr:
        post_process(scenario_folders=scenario_folders,
                     output_stats_folder=CONSTANTS['output_folder_statistics'],
                     output_graphs_folder=CONSTANTS['output_folder_graphs'],
                     imported_postprocessing=CONSTANTS['imported_postprocessing'],
                     imported_graphs=CONSTANTS['imported_graphs'],
                     imported_graphs_formatting=CONSTANTS['imported_graphs_formatting'],
                     log_path=CONSTANTS['log'])

        pr.print_stats()
    # TODO: test


if __name__ == '__main__':
    main()
