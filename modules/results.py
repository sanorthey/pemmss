"""
Module with routines for handling results data.
    generate_statistics()

"""

# Import standard packages
from statistics import median
from collections import defaultdict


def generate_statistics(key, project_list, time_range, demand_factors):
    """
    Returns a dictionary of statistics for a given key tuple and list of project id's

    key = (i,j,a,r,d,c) # tuple
    time_range = {t0,t1,t2, etc.} # set

    returns = {(i,j,a,r,d,c,s): {t: []}

    """
    # return_stats = {(i,j,a,r,d,c,s): {t: value}}, where
    #### {t: value} is defaultdict(int) for counting statistics
    #### {t: value} is defaultdict(float) for summing statistics

    # Useful variables
    commodity = (key[5])

    grade_dict_list = defaultdict(list)
    discovery_grade_dict_list = defaultdict(list)

    return_stats = {key+('mines_started_count',): defaultdict(int),
                    key+('mines_ended_count',): defaultdict(int),
                    key+('mines_producing_count',): defaultdict(int),
                    key+('mines_care_maintenance_count',): defaultdict(int),
                    key+('deposits_discovered_count',): defaultdict(int),
                    key + ('production_ore_mass',): defaultdict(float),
                    key+('deposits_discovered_ore_mass',): defaultdict(float),
                    key+('brownfield_expansion_ore_mass',): defaultdict(float),
                    }

    if commodity != 'ALL':
        intermediate_recovery = (demand_factors[commodity]['intermediate_recovery'])
        return_stats.update({key+('production_commodity',): defaultdict(float),
                             key+('production_intermediate',): defaultdict(float),
                             key+('production_ore_content',): defaultdict(float),
                             key+('losses_intermediate',): defaultdict(float),
                             key+('losses_mine',): defaultdict(float),
                             key+('losses_commodity',): defaultdict(float),
                             key+('mined_grade_weighted_average',): defaultdict(float),
                             key+('mined_grade_median',): defaultdict(float),
                             key+('deposits_discovered_ore_content',): defaultdict(float),
                             key+('deposits_discovered_grade_weighted_average',): defaultdict(float),
                             key+('deposits_discovered_grade_median',): defaultdict(float),
                             key+('brownfield_expansion_ore_content',): defaultdict(float),
                             key+('unmet_demand',): defaultdict(float),
                             })


    for p in project_list:
        # Not commodity or time dependent
        # Note with background greenfield exploration, start years can occur after model end. Consider adding a check for this.
        return_stats[key+('mines_started_count',)][p.start_year] += 1
        if p.end_year is not None:
            return_stats[key+('mines_ended_count',)][p.end_year] += 1
        return_stats[key+('deposits_discovered_count',)][p.discovery_year] += 1
        discovered_ore_mass = sum(p.initial_resource)
        return_stats[key+('deposits_discovered_ore_mass',)][p.discovery_year] += discovered_ore_mass

        if commodity != 'ALL':
            # Commodity dependent. Not time dependent.
            discovered_ore_content = sum([x*y for x, y in zip(p.initial_resource, p.initial_grade[commodity])])
            return_stats[key+('deposits_discovered_ore_content',)][p.discovery_year] += discovered_ore_content
            if discovered_ore_mass != 0:
                discovery_grade_dict_list[p.discovery_year].append(discovered_ore_content/discovered_ore_mass)

        for t, ore in p.production_ore.items():
            # Time dependent. Not commodity dependent.
            return_stats[key + ('mines_producing_count',)][t] += 1
            return_stats[key+('production_ore_mass',)][t] += ore

            if t in p.expansion:
                # In the year a mine depletes, p.production_ore[t] exists, but not p.expansion[t]
                # Also somehow p.expansion[t] might not exist in initial year, despite p.production_ore[t] existing.
                # Using try-except may be faster than an if statement.
                return_stats[key+('brownfield_expansion_ore_mass',)][t] += p.expansion[t]

                if commodity != 'ALL':
                    # Time and commodity dependent
                    # In the year a mine depletes, p.production_ore[t] exists, but not p.expansion[t]
                    # Also somehow p.expansion[t] might not exist in initial year, despite p.production_ore[t] existing.
                    # Using try-except here would be slightly faster than if statement.
                    return_stats[key + ('brownfield_expansion_ore_content',)][t] += p.expansion_contained[commodity][t]

            if commodity != 'ALL':
                # Time and commodity dependent.
                ## Note a try except here may possibly be faster, but less readable
                grade_dict_list[t].append(p.grade_timeseries[commodity][t])
                return_stats[key+('production_ore_content',)][t] += ore * grade_dict_list[t][-1]
                return_stats[key+('production_intermediate',)][t] += p.production_intermediate[commodity][t]
                return_stats[key+('production_commodity',)][t] += p.production_intermediate[commodity][t] * intermediate_recovery
                return_stats[key+('losses_mine',)][t] += ore * grade_dict_list[t][-1] - p.production_intermediate[commodity][t]
                return_stats[key+('losses_intermediate',)][t] += p.production_intermediate[commodity][t] * (1 - intermediate_recovery)
                return_stats[key+('losses_commodity',)][t] += ore * grade_dict_list[t][-1] - p.production_intermediate[commodity][t] + p.production_intermediate[commodity][t] * (1 - intermediate_recovery)



    if commodity != 'ALL':
        # Median grade processing
        for time_key, grade_list in grade_dict_list.items():
            return_stats[key + ('mined_grade_median',)][time_key] = median(grade_list)
        for time_key, grade_list in discovery_grade_dict_list.items():
            return_stats[key + ('deposits_discovered_grade_median',)][time_key] = median(grade_list)

        for time_key in time_range:
            # Weighted average grades
            if return_stats[key+('production_ore_mass',)][time_key] != 0:
                return_stats[key+('mined_grade_weighted_average',)][time_key] = return_stats[key+('production_ore_content',)][time_key] / return_stats[key+('production_ore_mass',)][time_key]

            if return_stats[key+('deposits_discovered_ore_mass',)][time_key] != 0:
                return_stats[key + ('deposits_discovered_grade_weighted_average',)][time_key] = return_stats[key+('deposits_discovered_ore_content',)][time_key] / return_stats[key+('deposits_discovered_ore_mass',)][time_key]
            # Unmet demand
            if key[2] == 'ALL' and key[3] == 'ALL' and key[4] == 'ALL':
                return_stats[key+('unmet_demand',)][time_key] = demand_factors[commodity][time_key]
    for time_key in time_range:
        for p in project_list:
            if p.start_year is not None:
                if p.start_year <= time_key:
                    if p.end_year is None:
                        if time_key not in p.production_ore:
                            return_stats[key + ('mines_care_maintenance_count',)][time_key] += 1
                    elif time_key < p.end_year and time_key not in p.production_ore:
                        return_stats[key + ('mines_care_maintenance_count',)][time_key] += 1

    return return_stats

# TODO: def generate_inventory_statistics()

# TODO: def generate_indicator_statistics()

