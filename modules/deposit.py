"""
Module with data structures and functions for handling deposit data

  class Mine:
        .__init__()
        .add_commodity()
        .get()
        .update_by_region_deposit_type()
        .supply()
        .resource_expansion()

  # Functions for discovering and defining resources
  resource_discovery()
  grade_generate()
  coproduct_grade_generate()
  tonnage_generate()
  value_generate()
  update_exploration_production_factors()

# TODO: 1. Add copyright to docstring
# TODO: 2. Modify docstring to include description of modulee use and application.
# TODO: 3. Add cross-references to journal article
# TODO: 4. Check this docstring after all other todos removed

"""

# Import standard packages
import random

# Import from custom packages
from modules.file_export import export_log


class Mine:
    """ Mine Class.
    Used to track the current state of each mining project overtime.
    (id_number, name, region, deposit_type, commodity, remaining_resource, grade,
     recovery, production_capacity, status, value,
     discovery_year, start_year, brownfield, value_threshold, aggregation)

    **** Variables ****
    Mine.id_number | Unique deposit identifying number
    Mine.name | Name of the deposit
    Mine.region | Region containing the deposit
    Mine.deposit_type | Primary deposit formation process
    Mine.commodity | Dictionary of commodities in the project
    Mine.remaining_resource | Size of the remaining mineral resource, ore basis
    Mine.grade | Grade of primary commodity.
    Mine.recovery | Recovery rate of primary commodity
    Mine.production_capacity | Max rate of extraction per period, ore basis
    Mine.status | Already Produced in Time Period = 2
                  Developed = 1
                  Undeveloped = 0
                  Depleted = -1
                  Not valuable enough to mine = -2
                  #FIXME: Check the status definitions
    Mine.value | Relative marginal value for sequencing mine extraction.
    Mine.discovery_year | Year of deposit generation
    Mine.start_year | Year of first mine production
    Mine.production_ore | Dictionary of production from start_year
    Mine.production_intermediate | Nested dictionary of intermediate commodity production from start_year {commodity: {t: value}}
    Mine.expansion | Dictionary of brownfield expansion from start_year
    Mine.brownfield | Dictionary of brownfield expansion factors. 'grade', 'tonnage'
    Mine.end_year   | Year of resource depletion
    Mine.value_threshold | Value that must be exceeded for the mine to produce
    Mine.aggregation | Descriptor of deposit initialisation conditions
                         'user_input_active'
                         'user_input_active_delayed_start'
                         'user_input_inactive'
                         'user_input_inactive_delayed_start'
                         'generated_background'
                         'generated_demanded'
    Mine.key_set

    **** Functions ****
    Mine.add_commodity(add_commodity,add_grade,add_recovery,is_primary_product)
    Mine.get(variable,get_commodity)
    Mine.update_by_region_deposit_type(update_factors)
    Mine.supply(ext_demand,year,ext_commodity)
    Mine.resource_expansion
    Mine.export()
    Mine.stats_update()

    #TODO: Mine.commodity - add description of 1 and 0 values reflecting whether demand driver or not.
    #TODO: Check description of all variables, include variable type / structure

    """
    __slots__ = ('id_number', 'name', 'region', 'deposit_type', 'commodity',
                 'remaining_resource', 'initial_resource', 'grade', 'recovery',
                 'production_capacity', 'production_intermediate', 'production_ore', 'expansion',
                 'status', 'status_initial', 'value',
                 'discovery_year', 'start_year', 'production_ore',
                 'brownfield', 'end_year', 'value_threshold', 'aggregation', 'key_set')

    # Initialise mine variables
    def __init__(self, id_number, name, region, deposit_type, commodity,
                 remaining_resource, grade, recovery, production_capacity,
                 status, value, discovery_year, start_year, brownfield,
                 value_threshold, aggregation):
        self.id_number = id_number
        self.name = name
        self.region = region
        self.deposit_type = deposit_type
        self.commodity = {}
        self.commodity = {commodity: 1}
        self.remaining_resource = remaining_resource
        self.initial_resource = remaining_resource
        self.grade = {commodity: grade}
        self.recovery = {commodity: recovery}
        self.production_capacity = production_capacity
        self.status = status
        self.status_initial = status
        self.value = value
        self.discovery_year = discovery_year
        self.start_year = start_year
        self.production_ore = {}
        self.production_intermediate = {commodity: {}}
        self.expansion = {}
        self.brownfield = brownfield
        self.end_year = -1
        self.value_threshold = value_threshold
        self.aggregation = aggregation
        self.key_set = {('ALL', 'ALL', 'ALL', 'ALL'),
                       ('ALL', 'ALL', deposit_type, 'ALL'),
                       ('ALL', region, 'ALL', 'ALL'),
                       ('ALL', region, deposit_type, 'ALL'),
                       (aggregation, 'ALL', 'ALL', 'ALL'),
                       (aggregation, 'ALL', deposit_type, 'ALL'),
                       (aggregation, region, 'ALL', 'ALL'),
                       (aggregation, region, deposit_type, 'ALL'),
                        ('ALL', 'ALL', 'ALL', commodity),
                        ('ALL', 'ALL', deposit_type, commodity),
                        ('ALL', region, 'ALL', commodity),
                        ('ALL', region, deposit_type, commodity),
                        (aggregation, 'ALL', 'ALL', commodity),
                        (aggregation, 'ALL', deposit_type, commodity),
                        (aggregation, region, 'ALL', commodity),
                        (aggregation, region, deposit_type, commodity)
                        }

    def add_commodity(self, add_commodity, add_grade, add_recovery, is_primary_product):
        """
        Mine.add_commodity(add_commodity, add_grade, add_recovery, is_primary_product)
        Adds a commodity to Mine.
        is_primary_product = 1 then mine will be triggered by commodity demand
        is_primary_product = 0 then mine won't be triggered by commodity demand

        # TODO: Update docstrings to explain input variables
        # TODO: Update docstrings to explain updated variables
        """
        self.commodity.update({add_commodity: int(is_primary_product)})
        self.grade.update({add_commodity: float(add_grade)})
        self.recovery.update({add_commodity: float(add_recovery)})
        self.production_intermediate.update({add_commodity: {}})
        self.key_set.update({('ALL', 'ALL', 'ALL', add_commodity),
                        ('ALL', 'ALL', self.deposit_type, add_commodity),
                        ('ALL', self.region, 'ALL', add_commodity),
                        ('ALL', self.region, self.deposit_type, add_commodity),
                        (self.aggregation, 'ALL', 'ALL', add_commodity),
                        (self.aggregation, 'ALL', self.deposit_type, add_commodity),
                        (self.aggregation, self.region, 'ALL', add_commodity),
                        (self.aggregation, self.region, self.deposit_type, add_commodity)})


    def get(self, variable, get_commodity=None):
        """
        Mine.get(variable, get_commodity=None)
        variable is a string
        returns the instance variable associated with the passed string

        #TODO: Descrine input arguments more fully
        #TODO: Modify docstring to include how get_commodity alters return variable
        """
        if variable == 'id_number':
            return self.id_number
        elif variable == 'name':
            return self.name
        elif variable == 'region':
            return self.region
        elif variable == 'deposit_type':
            return self.deposit_type
        elif variable == 'commodity':
            if get_commodity is None:
                return self.commodity
            elif get_commodity in self.commodity:
                return self.commodity[get_commodity]
        elif variable == 'grade':
            if get_commodity is None:
                return self.grade
            elif get_commodity in self.commodity:
                return self.grade[get_commodity]
        elif variable == 'recovery':
            if get_commodity is None:
                return self.recovery
            elif get_commodity in self.commodity:
                return self.recovery[get_commodity]
        elif variable == 'production_capacity':
            return self.production_capacity
        elif variable == 'status':
            return self.status
        elif variable == 'status_initial':
            return self.status_initial
        elif variable == 'value':
            return self.value
        elif variable == 'discovery_year':
            return self.discovery_year
        elif variable == 'start_year':
            return self.start_year
        elif variable == 'production_ore':
            return self.production_ore
        elif variable == 'production_intermediate':
            if get_commodity is None:
                return self.production_intermediate
            elif get_commodity in self.commodity:
                return self.production_intermediate[get_commodity]
            else:
                return {}
        elif variable == 'expansion':
            return self.expansion
        elif variable == 'brownfield':
            return self.brownfield
        elif variable == 'end_year':
            return self.end_year
        elif variable == 'value_threshold':
            return self.value_threshold
        elif variable == 'aggregation':
            return self.aggregation
        elif variable == 'key_set':
            return self.key_set
        else:
            print('Attempted to get variable ' + str(variable) +
                  'from Mine class object that does not exist.')



    def update_key_dict(self, key_dict, i, j):
        """
        Mine.update_key_dict(key_dict, i, j)
        Appends self to a (i,j,a,r,d,c) keyed dictionary.
        key_dict = {(i,j,a,r,d,c): [self, mine1, mine2, ...]}

        #TODO: Improve docstring to more clearly show input and return variable
        """

        # Include (i,j) in every self.key_set key (a,r,d,c)
        new_key_set = set([(i, j, k[0], k[1], k[2], k[3]) for k in self.key_set])

        for key in new_key_set:
            if key in key_dict:
                key_dict[key].append(self)
            else:
                key_dict.update({key: [self]})

        return key_dict


    def check_key_set(self, key_set, check_aggregation=True, check_region=True, check_deposit_type=True):
        """
        If key_set matches the instances key set, then return self.
        Setting check_aggregation, check_region and check_deposit_type to False
            will assign these instance keys to 'ALL'.
            So this requires 'ALL' values to be present in the key_set to work.
            # Possibly not needed anymore...
        TODO: Consider removing. Doesn't seem to be used within anything.
        """
        if check_aggregation and check_region and check_deposit_type:
            if (self.aggregation, self.region, self.deposit_type, self.commodity) in key_set:
                return self
        else:
            self_key_set = [self.aggregation, self.region, self.deposit_type]
            if not check_aggregation:
                self_key_set[0] = 'ALL'
            if not check_region:
                self_key_set[1] = 'ALL'
            if not check_deposit_type:
                self_key_set[2] = 'ALL'
            if (self_key_set[0], self_key_set[1], self_key_set[2]) in key_set:
                return self

    def update_by_region_deposit_type(self, update_factors):
        """
        Mine.update(ext_factors)
        Updates a mine's variables if it matches the deposit type and region.
        update_factors = {region: {deposit_type: {variable: {commodity: value}}}}
        # TODO: Add list to the docstring describing variables that can be altered by the algorithm.
        """
        # Check if region and deposit type pair is present in update_factors
        if self.region in update_factors.keys():
            if self.deposit_type in update_factors[self.region].keys():

                # Change the appropriate variable
                variable = update_factors[self.region][self.deposit_type]
                if variable == 'production_capacity':
                    self.production_capacity = float(variable[''])
                elif variable == 'status':
                    self.status = int(variable[''])
                elif variable == 'value':
                    self.value = float(variable[''])
                elif variable == 'discovery_year':
                    self.discovery_year = int(variable[''])
                elif variable == 'start_year':
                    self.start_year = int(variable[''])
                elif variable == 'grade':
                    # Unpack commodity structure
                    # Note does not have the capacity to add a new commodity.
                    # This could be achieved by inserting '0' grade values for
                    # a commodity in the input files, then updating later on.
                    for c in variable:
                        if c in self.grade:
                            self.grade[c] = float(variable[c])
                        else:
                            export_log('Attempted to update a project grade for a non-existant project commodity. Variable update skipped.', print_on=0)
                elif variable == 'recovery':
                    for c in variable:
                        if c in self.recovery:
                            self.recovery[c] = float(variable[c])
                        else:
                            export_log('Attempted to update a project recovery for a non-existant project commodity. Variable update skipped.', print_on=0)
                elif variable == 'end_year':
                    self.end_year = int(variable[''])
                elif variable == 'value_threshold':
                    self.value_threshold = float(variable[''])
                elif variable == 'aggregation':
                    self.aggregation = variable['']

    def supply(self, ext_demand, year, ext_demand_commodity):
        """
        Mine.supply(supply_requirement)
        Determines a mine's annual ore production rate based upon resource and supply capacity constraints.
        Converts commodity demand into ore demand based upon Mine.grade and Mine.recovery.
        Depletes the remaining resource based upon the production rate.
        Saves the mine's ore production rate to self.production_ore[year]
        Saves the mine's intermediate commodity production rates to self.production_intermediate[commodity][year]
        Returns the mine's intermediate commodity production rates, accounting for ore produced, grade and mine recovery factor.
        Updates Mine.status, Mine.start_year and Mine.end_year.
        # FIXME - check return statements and update doc strings
        # FIXME: Correct docstring to include return supply status
        # TODO: Modify docstring to include input argument descriptions
        # TODO: Modify docstring to include demanded commodity check description
        """
        if self.value < self.value_threshold:
            # Deposit is not valuable enough to mine.
            self.status = -2
            return 0

        if ext_demand_commodity not in self.commodity.keys():
            # Mine does not produce demanded commodity. Supply not triggered.
            return 0
        elif self.commodity[ext_demand_commodity] == 0:
            # Mine only produces the demanded commodity as a co-/by-product.
            # Therefore supply not triggered.
            return 0

        if self.start_year is not None and self.start_year > year:
            return 0

        if self.status == 0:
            # Record year of mine becoming active
            self.status = 1
            self.start_year = year

        if self.status == -1:
            # Mine is depleted
            return 0
        elif self.status == 2:
            # Mine already produced this time period.
            return 0
        else:
            # Convert external demand into ore demand by accounting for recovery factors
            supply_requirement = ext_demand / self.grade[ext_demand_commodity] / self.recovery[ext_demand_commodity]
            if supply_requirement <= self.remaining_resource:
                # Not resource constrained
                if supply_requirement <= self.production_capacity:
                    # Not supply capacity constrained, supply requirements fully met
                    self.remaining_resource -= supply_requirement
                    self.production_ore[year] = supply_requirement
                    self.status = 2
                else:
                    # Supply capacity constrained, supply requirements not fully met
                    self.remaining_resource -= self.production_capacity
                    self.production_ore[year] = self.production_capacity
                    self.status = 2
            else:
                # Resource constrained
                if self.remaining_resource <= self.production_capacity:
                    # Not supply capacity constrained, resource will be fully depleted, supply requirements not fully met
                    self.production_ore[year] = self.remaining_resource
                    self.remaining_resource = 0
                    self.status = -1
                    self.end_year = year
                else:
                    # Supply capacity constrained, supply at full capacity, supply requirements not fully met
                    self.remaining_resource -= self.production_capacity
                    self.production_ore[year] = self.production_capacity
                    self.status = 2

            # Return ore production
            for c in self.production_intermediate:
                self.production_intermediate[c][year] = self.production_ore[year]*self.recovery[c]*self.grade[c]

            # Return Mine as having supplied
            return 1

    def resource_expansion(self, year):
        """
        Mine.resource_expansion(year)
        Consider adding resource_dilution() model for grade dilution
        """
        # FIXME: Get brownfield factors out of the input correctly.
        # FIXME: Add resource_dilution() model
        # FIXME: Check brownfield factors from project file or from deposit type / region file.
        self.expansion[year] = self.remaining_resource * self.brownfield['tonnage']
        self.remaining_resource += self.expansion[year]

# ------------------------------------------------ #
# Functions for discovering and defining resources 
# ------------------------------------------------ #

def resource_discovery(f, current_year, is_background, id_number):
    """
    resource_discovery()
    Randomly generates a new mineral deposit, based upon the parameter table 'f' outlined in the file
        input_exploration_production_factors.csv
    f | resource_exploration_production factors data structure {key: [,,,]}
    is_background == True | Background greenfield discovery, start year forward dated
    is_background == False | Demand triggered greenfield discovery, discovery year backdated
    id_number | Unique ID for the generated Mine class instance, must be an integer

    TODO: Add returned object to docstring
    """

    # Randomly generate a new deposit type based upon weightings
    gen_index = random.choices(f['index'], f['weighting'], k=1)
    index = int(gen_index[0])
    commodity = f['commodity_primary'][index]
    generated_type = f['deposit_type'][int(index)]
    generated_region = f['region'][index]
    grade_factors = {'a': f['grade_a'][index], 'b': f['grade_b'][index],
                     'c': f['grade_c'][index], 'd': f['grade_d'][index]}
    tonnage_factors = {'a': f['tonnage_a'][index], 'b': f['tonnage_b'][index],
                       'c': f['tonnage_c'][index], 'd': f['tonnage_d'][index]}
    brownfield_factors = {'grade': f['brownfield_grade_factor'][index],
                          'tonnage': f['brownfield_tonnage_factor'][index]}
    value_factors = {'a': f['value_a'][index], 'b': f['value_b'][index],
                     'c': f['value_c'][index], 'd': f['value_d'][index],
                     'value_threshold': f['value_threshold'][index]}
    development_period = f['development_period'][index]

    # Generate an ore grade based upon the deposit type's grade distribution model.
    grade = grade_generate(f['grade_model'][index], grade_factors)

    # Generate a resource size based upon deposit type's tonnage distribution model.
    tonnage = tonnage_generate(f['tonnage_model'][index], tonnage_factors, grade)

    # Lookup default recovery factor for deposit type
    recovery = f['default_recovery'][index]

    # Estimate supply capacity, check that within min and max
    capacity = capacity_generate(tonnage, f['taylor_a'][index], f['taylor_b'][index], f['taylor_min'][index], f['taylor_max'][index])

    # Generate Value
    generated_value = value_generate(f['value_model'][index], tonnage, grade, recovery, value_factors)

    # Discovery and Start Time and Aggregation
    if is_background is True:
        discovery_time = current_year
        start_time = current_year + development_period
        aggregation = 'Greenfield - Background'
    else:
        discovery_time = current_year - development_period
        start_time = current_year
        aggregation = 'Greenfield - Demanded'

    # Generate project
    new_project = Mine(id_number, "GENERATED_"+str(id_number), generated_region, generated_type, commodity, tonnage, grade, recovery, capacity, 0,
                       generated_value, discovery_time, start_time, brownfield_factors, value_factors['value_threshold'], aggregation)

    # Generate project coproduct parameters using the region and production factors given in input_exploration_production_factors.csv
    for x in range(0, len(f['coproduct_commodity'][index])):
        if len(f['coproduct_commodity'][index]) != 0:
            c = f['coproduct_commodity'][index][x]
            if c != '':
                g = coproduct_grade_generate(new_project, f, index, x)
                r = f['coproduct_default_recovery'][index][x]
                trigger = f['coproduct_supply_trigger'][index][x]
                new_project.add_commodity(c, g, r, trigger)
    return new_project


def grade_generate(grade_model, factors):
    """
    grade_generate()
    Returns a mass ratio of commodity mass to total mass of the ore deposit, generated in accordance with defined grade
    distributions.
    'factors' input must be a dictionary with 'a', 'b', 'c' and 'd' defined.
    grade_model : 1. Fixed grade distribution, 2. Lognormal grade distribution, 3. User-defined grade distribution
    grade_model = 2:
        a = mu, mean
        b = sigma, standard deviation
        c = multiplier
        d = max grade
    TODO: Describe inputs for all grade models
    TODO: Check lognormal distribution function and grade-dependent tonnage
    TODO: Ensure parameter definition consistent with coproduct_grade_generate
    TODO: Add grade model for multiple of an input variable
    TODO: Refactor grade_model to strings e.g. "fixed", "lognormal", etc.
    """
    if grade_model == 1:
        # Fixed grade distribution
        grade = factors['a']
    elif grade_model == 2:
        # Lognormal grade distribution
        # FIXME: 'tonnage' not passed to function
        # FIXME: check Gerst / paper the correct log-normal grade equation
        # tonnage = abs(random.gauss(factors['a'],factors['b']) * factors['c'])
        # Generate grade and ensure it is positive
        # grade = abs(tonnage / random.gauss(factors['a'],factors['b']) ** factors['c'])
        # Check if generated grade is higher than the maximum grade given in factor 'd'
        # FIXME: check for an alternative approach using random.lognormvariate(mu, sigma) function. Need to determine whether grade dependent.
        # FIXME: ensure parameter definition consistency with coproduct_grade_generate
        grade = abs(random.lognormvariate(factors['a'], factors['b'])) * factors['c']
        if grade > float(factors['d']):
            grade = float(factors['d'])
    elif grade_model == 3:
        # User-defined grade distribution
        # grade = "ENTER USER DEFINED DISTRIBUTION HERE"
        grade = "ENTER USER DEFINED GRADE DISTRIBUTION HERE"

    else:
        print("!!! VALID GRADE_MODEL NOT SELECTED !!!")
    return grade

def coproduct_grade_generate(project, factors, factors_index, commodity_index):
    """
    coproduct_grade_generate(
    factors['coproduct_a'][factor_index][commodity_index]
    factors['coproduct_b'][factor_index][commodity_index]
    factors['coproduct_c'][factor_index][commodity_index]
    factors['coproduct_d'][factor_index][commodity_index]
    )
    TODO: Remove hard coding of grade models, make call to grade_generate
    TODO: Create lognormal-tonnage dependent grade distribution model.
    TODO: Fix docstrings
    """
    try:
        coproduct_grade_model = int(factors['coproduct_grade_model'][factors_index][commodity_index])
    except:
        return 0

    # Means that the coproduct doesn't exist.

    if coproduct_grade_model == 1:
        # Fixed grade | 'a' = grade
        grade = factors['coproduct_a'][factors_index][commodity_index]
    elif coproduct_grade_model == 2:
        # Multiple of main commodity grade | 'a' = commodity name, 'b' = grade multiplier
        grade = project.grade[factors['coproduct_a'][factors_index][commodity_index]] * float(factors['coproduct_b'][factors_index][commodity_index])
    elif coproduct_grade_model == 3:
        # Distribution | 'a' = mean mu, 'b' = standard deviation sigma, 'c' = max value
        grade = abs(random.lognormvariate(factors['coproduct_a'][factors_index][commodity_index], factors['coproduct_b'][factors_index][commodity_index]))
        if grade > factors['coproduct_c'][factors_index][commodity_index]:
            grade = factors['coproduct_c'][factors_index][commodity_index]
    return grade


def tonnage_generate(size_model, factors, grade):
    """
    tonnage_generate()
    Returns a resource tonnage, generated in accordance with defined distributions.
    'factors' input must be a dictionary with 'a', 'b', 'c' and 'd' defined.
    tonnage_model : 1. Fixed tonnage distribution, 2. Lognormal tonnage distribution, 3. Lognormal-grade dependent
    tonnage distribution, 4. User-defined tonnage distribution
    TODO: Check lognormal-grade dependent tonnage distribution
    TODO: Define variable inputs for each model in comments.
    TODO: change size_model inputs to strings, e.g. "fixed", "lognormal", etc.
    """
    # Generate primary resource tonnage based upon a distribution relationship.
    if size_model == 1:
        # Fixed tonnage distribution
        tonnage = factors['a']
    elif size_model == 2:
        # Lognormal tonnage distribution
        tonnage = abs(random.lognormvariate(factors['a'], factors['b']) * factors['c'])
    elif size_model == 3:
        # Lognormal-grade dependent tonnage distribution
        # FIXME: define the log-normal grade dependent tonnage distribution.
        tonnage = grade
        # grade = tonnage / random.lognormvariate(factors['a'],factors['b']) ** factors['c']
        # FIXME: ensure that size generated are greater than zero. Use abs()
    elif size_model == 4:
        # User-defined size model
        tonnage = "ENTER USER DEFINED DISTRIBUTION HERE"
    else:
        print("!!! VALID SIZE_MODEL NOT SELECTED !!!")
    return tonnage


def value_generate(model, size, ore_grade, mine_recovery, value_factor):
    """
    Generates value based upon the value model selected in the input_parameters.csv

    TODO: Create a basic commodity price / revenue model.
    TODO: Generalise grade and recovery models for multiple commodity systems
    TODO: Update docstrings
    """
    if model == 1:
        # Fixed
        return value_factor['a']
    if model == 2:
        # Contained
        return size * ore_grade
    if model == 3:
        # Grade
        return ore_grade
    if model == 4:
        # Recoverable
        return size * ore_grade * mine_recovery
    if model == 5:
        # Size
        return size
    if model == 6:
        # User_Defined
        # Placeholder for a user-defined value function.
        # Users can define value_factor['a'], value_factor['b'], value_factor['c'], value_factor['d'] and value_factor['value_threshold'] for individual
        # regions and deposit types in the input_exploration_production_factors.csv input file.
        user_defined = size + ore_grade + mine_recovery + value_factor['a'] * value_factor['b'] * value_factor['c'] * value_factor['d']
        return user_defined

def capacity_generate(resource_tonnage, a, b, min, max):
    """
    Generates production capacity based upon the taylor rule factors in input_exploration_production_factors.csv
    TODO: Update docstrings to include input argument description
    TODO: Update docstrings to include return variable description
    """
    production_capacity = a * resource_tonnage ** b
    if production_capacity < min:
        production_capacity = min
    elif production_capacity > max:
        production_capacity = max

    return production_capacity



def update_exploration_production_factors(factors, updates):
    """
    factors | a dictionary containing lists of exploration_production_factor variables
    updates | a nested dictionary of structure {region: {deposit_type: {variable: {commodity: value}}}}
    Ignores any production variables.
    TODO: Update docstrings to include description of functionality and return variables
    TODO: Decide whether to add in functionality for selective changes to a commodities values. Currently can still update all commodities at once.

    """
    for r in updates:
        for d in updates[r]:
            index = factors['lookup_table'][r][d]
            for v in updates[r][d]:
                for c in updates[r][d][v]:
                    if c == '':
                        variable_split = updates[r][d][v][c].split(';')
                        if len(variable_split) == 1:
                            # Attempt to convert to float, otherwise store as string.
                            try:
                                factors[v][index] = float(variable_split[0])
                            except:
                                factors[v][index] = variable_split[0]
                        else:
                            variable_rebuilt = []
                            # Attempt to convert values to floats
                            for x in range(0, len(variable_split)):
                                try:
                                    variable_rebuilt.append(float(variable_split[x]))
                                except:
                                    variable_rebuilt.append(variable_split[x])
                            factors[v][index] = variable_rebuilt
                    else:
                        # Replicated incase ever want to add functionality for selective changes to a commodities values. This section would need modifying to allow that.
                        variable_split = updates[r][d][v][c].split(';')
                        if len(variable_split) == 1:
                            try:
                                factors[v][index][c] = float(variable_split[0])
                            except:
                                factors[v][index][c] = variable_split[0]
                        else:
                            variable_rebuilt = []
                            for x in range(0, len(variable_split)):
                                try:
                                    variable_rebuilt.append(float(variable_split[x]))
                                except:
                                    variable_rebuilt.append(variable_split[x])
                            factors[v][index] = variable_rebuilt
    return factors
