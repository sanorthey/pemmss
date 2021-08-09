# -*- coding: utf-8 -*-
"""
Module with routines for handling results data.
    generate_statistics()
    key_generate_filter()
    key_all_expand()
    x_y_labels_generate_flat()
    key_include_filter()
    x_y_labels_generate()

TODO: 1. Add copyrwrite statement
TODO: 2. Check docstrings after refactoring x_y_labels_generate_flat()
TODO: 3. Check docstrings after deleting x_y_labels_generate()
TODO: 4. Add cross-references to the journal article
TODO: 5. Update this docstring after all other todos completed

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
    TODO: Update docstrings

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
        return_stats[key+('mines_ended_count',)][p.end_year] += 1
        return_stats[key+('deposits_discovered_count',)][p.discovery_year] += 1
        return_stats[key+('deposits_discovered_ore_mass',)][p.discovery_year] += p.initial_resource


        if commodity != 'ALL':
            # Commodity dependent. Not time dependent.
            return_stats[key+('deposits_discovered_ore_content',)][p.discovery_year] += p.initial_resource * p.grade[commodity]
            discovery_grade_dict_list[p.discovery_year].append(p.grade[commodity])

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
                # Time and commodity dependent.
                ## Note a try except here may possibly be faster, but less readable
                grade_dict_list[t].append(p.grade[commodity])
                return_stats[key+('production_ore_content',)][t] += ore * grade_dict_list[t][-1]
                return_stats[key+('production_intermediate',)][t] += p.production_intermediate[commodity][t]
                return_stats[key+('production_commodity',)][t] += p.production_intermediate[commodity][t] * intermediate_recovery
                return_stats[key+('losses_mine',)][t] += ore * grade_dict_list[t][-1] - p.production_intermediate[commodity][t]
                return_stats[key+('losses_intermediate',)][t] += p.production_intermediate[commodity][t] * (1 - intermediate_recovery)
                return_stats[key+('losses_commodity',)][t] += ore * grade_dict_list[t][-1] - p.production_intermediate[commodity][t] + p.production_intermediate[commodity][t] * (1 - intermediate_recovery)

                if t in p.expansion:
                    # In the year a mine depletes, p.production_ore[t] exists, but not p.expansion[t]
                    # Also somehow p.expansion[t] might not exist in initial year, despite p.production_ore[t] existing.
                    # Using try-except here would be slightly faster than if statement.
                    return_stats[key + ('brownfield_expansion_ore_content',)][t] += p.expansion[t] * grade_dict_list[t][-1]

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
                return_stats[key + ('deposits_discovered_ore_mass',)][time_key] = return_stats[key+('deposits_discovered_ore_content',)][time_key] / return_stats[key+('deposits_discovered_ore_mass',)][time_key]
            # Unmet demand
            if key[3] == 'ALL' and key[4] == 'ALL' and key[5] == 'ALL':
                return_stats[key+('unmet_demand',)][time_key] = demand_factors[commodity][time_key]

    # FIXME: Think about adding 'ALL' time_key to return_stats[(key)][time_key]. May be necessary for compatability with original export, import and graphing functions.
    # Potential implementation.. May just add to processing time though.
    # for stat, time_dict in return_stats.items():
    #     return_stats[stat]['ALL'] = sum(time_dict.keys())
    # Manual override for incompatible stats.
     # FIXME: return_stats[key+('mines_care_maintenance_count',)][t]

    return return_stats


def key_generate_filter(dictionary, keys_list, filter_off, filtered_value):
    """
    Autogenerates and can filter a value from dictionary keys
    keys = key_generate_filter(dictionary, keys_list, filter_on, filtered_value)
    dictionary | Dictionary corresponding to the keys
    keys_list  | If equals -1 then autogenerate keys, else will pass the existing list
    filter_off  | 1 equals off, 0 equals on. Only filters autogenerated keys.
    filtered_value | key to be filtered.
    TODO: Describe returned variable
    TODO: Delete if not used, check whether key_all_expand is used.
    """

    # Copy keys_list
    keys = keys_list

    # Generates keys_list new dictionary when keys_list is -1
    if keys_list == -1:
        keys = list(dictionary.keys())
        if filter_off == 0:
            if filtered_value in keys:
                keys.remove(filtered_value)
    return keys


def key_all_expand(dictionary, key):
    """
    TODO: Write docstrings
    TODO: Delete if not used
    """

    keys_list = []
    if key == 'ALL':
        key_includes_all = True
        keys_list = key_generate_filter(dictionary, -1, 0, 'ALL')
    else:
        key_includes_all = False
        keys_list = [key]
        
    return keys_list, key_includes_all


def x_y_labels_generate_flat(flat_stats, i_include=False, j_include=False, a_include=False, r_include=False, d_include=False, c_include=False, s_include=False, filter_t=False):
    """
    x_y_labels_generate_flat()
    flat_stats = {(i,j,a,r,d,c,s): {t: value}}
    
    If _include arguments are:
        False - Will only return when key is 'ALL'
        True - Will return any key except 'ALL'
        list[k1, k2, k3] - Will return listed keys
        ## See key_include_filter()

    filter_t | False, then all time periods will be included.
             | list[t1,t2,t3], then only listed time periods will be included.

    Returns tuple (x, y, labels):
        x = [[Series 1 x's], [Series 2 x's], etc.]
        y = [[Series 1 y's], [Series 2 y's], etc.]
        labels = [Series 1 label, Series 2 label, etc.]
    TODO: Refactor to x_y_labels_generate()
    TODO: Docstring, update with a description of the functionality
    TODO: Test with true and false statements to check functionality

    """
    
    x = []
    y = []
    labels = []
    
    for key, time_dict in flat_stats.items():
        
        include_test = []
        include_test.append(key_include_filter(key,0,i_include))
        include_test.append(key_include_filter(key,1,j_include))
        include_test.append(key_include_filter(key,2,a_include))
        include_test.append(key_include_filter(key,3,r_include))
        include_test.append(key_include_filter(key,4,d_include))
        include_test.append(key_include_filter(key,5,c_include))
        include_test.append(key_include_filter(key,6,s_include))
            
        if False not in include_test:
            x.append([])
            y.append([])
            
            labels.append(key)
            
            for t, v in time_dict.items():
                if filter_t == False or t in filter_t:
                    x[-1].append(t)
                    y[-1].append(v)
            
            # If blank, remove the added entries.
            if y[-1] == []:
                x.pop()
                y.pop()
                labels.pop()
    return (x, y, labels)
                
            
def key_include_filter(key,index,_include=False):
    """
    Can pass to the _include arguments:
        False - Will only return when key is 'ALL'
        True - Will return any key except 'ALL'
        list[k1, k2, k3] - Will return listed keys
        
    Returns | True, key should be included
            | False, key should be excluded
    TODO: Update docstrings to include functionality and use case description
    """

    if _include == False:
        if key[index] == 'ALL':
             return True
        else:
            return False
        
    elif _include == True:
        if key[index] != 'ALL':
            return True
        else:
            return False
      
    elif _include.type() == list:
        if key[index] in _include:
            return True
        else:
            return False
    else:
        raise Exception('Argument _include passed to key_include_filter() was not a list or boolean.\n_include Type: '+str(type(_include())+'\nValue: '+str(_include)))
        
    
def x_y_labels_generate(stats, i, j, a, r, d, c, s, t_keys, labels_on=[0, 0, 0, 0, 0, 0, 0], y=None, labels=None, filter_value=False, filter_pop=True):
    """
    Generates a x, y and label series from a statistics data structure.
    stats = {i: {j: {a: {r: {d: {c: {s: {t: value}}}}}}}}
    labels_on = [i,j,a,r,d,c,s]. Set to 1 (include) or 0 (exclude).
    filter_value | If specified will filter out that value from y.
    filter_pop | Default True will pop filtered y and corresponding x
               | If specified will replace y value with filter_pop
    If y and labels are specified, will append to existing list.
    Returns x, y[[val1, val2, etc.], [val1, val2, etc.]], labels [[]]
    Note - may return empty y and labels, i.e. []

    TODO: Ensure functionality is properly replicated by x_y_labels_generate_flat() then delete.
    """

    # Checking whether to create new y and labels, or append to passed lists.
    if y is None:
        y = []
    if labels is None:
        labels = []

    # Generate new series
    x = []
    y.append([])
    labels.append([])
    for t in t_keys:
        x.append(t)
        y[-1].append(stats[i][j][a][r][d][c][s][t])

        # Value filtering
        if filter_value is not False:
            if y[-1][-1] == filter_value:
                if filter_pop is True:
                    x[-1].pop()
                    y[-1].pop()
                else:
                    y[-1][-1] = filter_pop

    # If timeseries blank, remove added y and label entries.
    if y[-1] == []:
        y.pop()
        labels.pop()
    else:
        # Generate series label
        l_current = ''
        if labels_on[0] == 1:
            l_current += str(i) + ' '
        if labels_on[1] == 1:
            l_current += str(j) + ' '
        if labels_on[2] == 1:
            l_current += str(a) + ' '
        if labels_on[3] == 1:
            l_current += str(r) + ' '
        if labels_on[4] == 1:
            l_current += str(d) + ' '
        if labels_on[5] == 1:
            l_current += str(c) + ' '
        if labels_on[6] == 1:
            l_current += str(s)
        labels[-1] = l_current

    return x, y, 

