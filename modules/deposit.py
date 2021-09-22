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
    Used to initialise and track the current state of each mining project overtime.
    Mine(id_number, name, region, deposit_type, commodity, remaining_resource, grade,
    recovery, production_capacity, status, value, discovery_year, start_year,
    brownfield, value_threshold, aggregation)

    **** Variables ****
    Mine.id_number | Unique deposit identifying number
    Mine.name | Name of the deposit
    Mine.region | Region containing the deposit
    Mine.deposit_type | Primary deposit type
    Mine.commodity | Dictionary of commodities in the project {commodity: balanced}
                   | Where balanced = 1 indicates demand for this commodity can trigger mine supply
                   | Where balanced = 0 indicates demand for this commodity cannot trigger mine supply
    Mine.remaining_resource | Size of the remaining mineral resource, ore basis
    Mine.grade | Dictionary of commodity ore grades. Ratio of total ore mass. {commodity: grade}
    Mine.recovery | Dictionary of commodity recoveries. Ratio of total ore content. {commodity: recovery}
    Mine.production_capacity | Maximum extraction rate per period, ore basis.
    Mine.status | Already Produced in Time Period = 2
                  Developed = 1
                  Undeveloped = 0
                  Depleted = -1
                  Not valuable enough to mine = -2
    Mine.value | Dictionary of net recovery value for each  Used to sequence mine supply.
    Mine.discovery_year | Year of deposit generation
    Mine.start_year | Year of first mine production
    Mine.production_ore | Dictionary of ore production from start_year {t: ore production}
    Mine.production_intermediate | Nested dictionary of intermediate commodity production from start_year {commodity: {t: value}}
    Mine.expansion | Dictionary of brownfield ore expansion from start_year {t: ore expansion}
    Mine.expansion_contained | Nested dictionary of commodity contained in brownfield ore expansion {commodity: {t: value}}
    Mine.brownfield_tonnage | Brownfield tonnage expansion factor
    Mine.brownfield_grade | Dictionary of brownfield grade dilution factors {commodity: factor}
    Mine.end_year   | Year of resource depletion
    Mine.value_factors | Nested dictionary of value model factors {commodity: {type: {'model':,'a':,'b':,'c':,'d':}}
                       | 'ALL' commodity represents value model factors for the mines fixed value (or costs if negative).
                       | 'Type' should be either 'revenue' or 'cost'
    Mine.aggregation | Descriptor of deposit initialisation conditions
                         'user_input_active'
                         'user_input_active_delayed_start'
                         'user_input_inactive'
                         'user_input_inactive_delayed_start'
                         'generated_background'
                         'generated_demanded'
    Mine.key_set | Set of tuple key combinations with 'ALL' wildcard for fast filtering
                 | {(aggregation, region, deposit_type, commodity)}

    **** Functions ****
    Mine.add_commodity(add_commodity,add_grade,add_recovery,is_balanced)
    Mine.get(variable,get_commodity)
    Mine.update_key_dict(key_dict,i,j)
    Mine.update_by_region_deposit_type(update_factors)
    Mine.supply(ext_demand,year,ext_demand_commodity)
    Mine.resource_expansion(year)
    """
    __slots__ = ('id_number', 'name', 'region', 'deposit_type', 'commodity',
                 'remaining_resource', 'initial_resource', 'grade', 'initial_grade', 'recovery',
                 'production_capacity', 'production_intermediate', 'production_ore', 'expansion',
                 'expansion_contained', 'status', 'initial_status', 'value', 'discovery_year',
                 'start_year', 'production_ore', 'brownfield_tonnage', 'brownfield_grade',
                 'end_year', 'value_factors', 'aggregation', 'key_set')

    # Initialise mine variables
    def __init__(self, id_number, name, region, deposit_type, commodity,
                 remaining_resource, grade, recovery, production_capacity,
                 status, value, discovery_year, start_year, brownfield_tonnage, brownfield_grade,
                 value_factors, aggregation):
        self.id_number = id_number
        self.name = name
        self.region = region
        self.deposit_type = deposit_type
        self.commodity = {commodity: 1} # All Mine objects should have at least one balanced commodity.
        self.remaining_resource = remaining_resource
        self.initial_resource = remaining_resource
        self.grade = {commodity: grade}
        self.initial_grade = {commodity: grade}
        self.recovery = {commodity: recovery}
        self.production_capacity = production_capacity
        self.status = status
        self.initial_status = status
        self.value = value # {'ALL': value, commodity: value}
        self.discovery_year = discovery_year
        self.start_year = start_year
        self.production_ore = {}
        self.production_intermediate = {commodity: {}}
        self.expansion = {}
        self.expansion_contained = {commodity: {}}
        self.brownfield_tonnage = brownfield_tonnage
        self.brownfield_grade = {commodity: brownfield_grade}
        self.end_year = -1
        self.value_factors = value_factors
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

    def add_commodity(self, add_commodity, add_grade, add_recovery, is_balanced, add_brownfield_grade, add_value_factors, update_value=True):
        """
        Mine.add_commodity(add_commodity, add_grade, add_recovery, is_balanced, add_brownfield_grade)
        Adds a commodity to a Mine objects commodity, grade, recovery, production_intermediate and key_set variables
        Can also be used to update variables for a Mine's existing commodity

        is_balanced = 1 then mine supply will be triggered by this commodity's demand
        is_balanced = 0 then mine supply won't be triggered by this commodity's demand

        update_value = True then Mine.value['ALL'] and Mine.value[c for c in Mine.commodity] will be updated.
        """
        self.commodity.update({add_commodity: int(is_balanced)})
        self.grade.update({add_commodity: float(add_grade)})
        self.recovery.update({add_commodity: float(add_recovery)})
        self.brownfield_grade.update({add_commodity: float(add_brownfield_grade)})
        self.value_factors.update({add_commodity: add_value_factors})
        if update_value == True:
            self.value_update()
        self.production_intermediate.update({add_commodity: {}})
        self.expansion_contained.update({add_commodity: {}})
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
        Returns a Mine object variable corresponding to an input string

        get_commodity can be used to return commodity specific dictionary values
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
        elif variable == 'remaining_resource':
            return self.remaining_resource
        elif variable == 'initial_resource':
            return self.initial_resource
        elif variable == 'grade':
            if get_commodity is None:
                return self.grade
            elif get_commodity in self.commodity:
                return self.grade[get_commodity]
        elif variable == 'initial_grade':
            if get_commodity is None:
                return self.initial_grade
            elif get_commodity in self.commodity:
                return self.initial_grade[get_commodity]
        elif variable == 'recovery':
            if get_commodity is None:
                return self.recovery
            elif get_commodity in self.commodity:
                return self.recovery[get_commodity]
        elif variable == 'production_capacity':
            return self.production_capacity
        elif variable == 'status':
            return self.status
        elif variable == 'initial_status':
            return self.initial_status
        elif variable == 'value':
            if get_commodity is None:
                return self.value
            elif get_commodity in self.commodity:
                return self.value[get_commodity]
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
        elif variable == 'expansion_contained':
            if get_commodity is None:
                return self.expansion_contained
            elif get_commodity in self.commodity:
                return self.expansion_contained[get_commodity]
            else:
                return {}
        elif variable == 'brownfield_tonnage':
            return self.brownfield_tonnage
        elif variable == 'brownfield_grade':
            if get_commodity is None:
                return self.brownfield_grade
            elif get_commodity in self.commodity:
                return self.brownfield_grade[get_commodity]
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
                  'that does not exist from Mine class object.')



    def update_key_dict(self, key_dict, i, j):
        """
        Mine.update_key_dict(key_dict, i, j)
        Appends self to a (i,j,a,r,d,c) keyed dictionary.
        Returns updated key_dict = {(i,j,a,r,d,c): [self, mine1, mine2, ...]}
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
        TODO: Consider removing after updating graph functionality. Doesn't seem to be used within anything.
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
        Updates a mine variable if it matches the deposit type and region.
        update_factors = {region: {deposit_type: {variable: value OR {commodity: value}}}}

        Variables that can be updated:
        Mine.production_capacity
        Mine.status
        Mine.value
        Mine.discovery_year
        Mine.start_year
        Mine.grade
        Mine.recovery
        Mine.end_year
        Mine.aggregation

        Note: Cannot be used to add a new commodity. Use Mine.add_commodity() for this
        or insert '0' values for a commodity in the input files, then update later on.
        TODO: Consider adding functionality for updating Mine.value_factors
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
                    # Unpack commodity structure
                    for c in variable:
                        if c in self.value:
                            self.value[c] = float(variable[c])
                        else:
                            export_log('Attempted to update a project value for a non-existent project commodity. Variable update skipped.', print_on=0)
                    self.value = float(variable[''])
                elif variable == 'discovery_year':
                    self.discovery_year = int(variable[''])
                elif variable == 'start_year':
                    self.start_year = int(variable[''])
                elif variable == 'grade':
                    # Unpack commodity structure
                    for c in variable:
                        if c in self.grade:
                            self.grade[c] = float(variable[c])
                        else:
                            export_log('Attempted to update a project grade for a non-existent project commodity. Variable update skipped.', print_on=0)
                elif variable == 'recovery':
                    for c in variable:
                        if c in self.recovery:
                            self.recovery[c] = float(variable[c])
                        else:
                            export_log('Attempted to update a project recovery for a non-existent project commodity. Variable update skipped.', print_on=0)
                elif variable == 'end_year':
                    self.end_year = int(variable[''])
                elif variable == 'aggregation':
                    self.aggregation = variable['']


    def supply(self, ext_demand, year, ext_demand_commodity):
        """
        Mine.supply(ext_demand, year, ext_demand_commodity)
        Checks mine's ability to supply and determines ore production based upon resource and supply capacity constraints.
        Converts external commodity demand into ore demand based upon Mine.grade and Mine.recovery.
        If supply is triggered, all Mine commodities will be supplied.

        ext_demand | mass of commodity demand
        year | time period for the production
        ext_demanded_commodity | demanded commodity

        *** Supply Criteria ***
        Does the mine's value exceed the value threshold?
        Does the mine produce the demanded commodity?
        Does demand for this commodity trigger this mine's supply?
        Does the mine have a start year and has this been passed?
        Has the mine already produced during this time period?

        *** Updates ***
        Mine.end_year
        Mine.production_ore[year]
        Mine.production_intermediate[c][t]
        Mine.remaining_resource
        Mine.start_year
        Mine.status

        Returns | 0 if mine did not supply
                | 1 if mine did supply

        """
        if self.value['ALL'] < 0:
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
                if self.value[c] >= 0:
                    # Recovery of c generates positive or neutral value
                    self.production_intermediate[c][year] = self.production_ore[year]*self.recovery[c]*self.grade[c]
                else:
                    # Recovery of c generates a neutral value. c not supplied.
                    self.production_intermediate[c][year] = 0

            # Return Mine as having supplied
            return 1


    def resource_expansion(self, year):
        """
        Mine.resource_expansion(year)
        Increases a deposit's remaining resource and recalculates deposit grades based on the brownfield tonnage and
        brownfield grade factors.
        Added ore = remaining resource * brownfield tonnage factor
        Grade of added ore = grade[commodity] * brownfield grade factor[commodity]
        """
        # Determine the amount of added ore
        self.expansion[year] = self.remaining_resource * self.brownfield_tonnage

        expansion_grade = {}
        for c in self.commodity:
            # Determine the grade of added ore
            expansion_grade[c] = self.grade[c] * self.brownfield_grade[c]

            # Record the amount of commodity contained in added ore
            self.expansion_contained[c][year] = expansion_grade[c] * self.expansion[year]

            # Adjust grade of the remaining resource
            self.grade[c] = (self.grade[c] * self.remaining_resource + self.expansion_contained[c][year])/(self.remaining_resource + self.expansion[year])

        # Adjust size of the remaining resource
        self.remaining_resource += self.expansion[year]

    def value_update(self):
        """
        Mine.value_update()
        Updates Mine.value based upon the current Mine object variables and value model.
        """
        self.value = value_generate(self.value_factors, self.remaining_resource, self.grade, self.recovery)


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

    Returns a new Mine object
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
    brownfield_tonnage_factor = f['brownfield_tonnage_factor'][index]
    brownfield_grade_factor = f['brownfield_grade_factor'][index]
    value_factors = {"MINE": {"cost": {"model": f['mine_cost_model'][index],
                                       "a": f['mine_cost_a'][index],
                                       "b": f['mine_cost_b'][index],
                                       "c": f['mine_cost_c'][index],
                                       "d": f['mine_cost_d'][index]}},
                     commodity: {"cost": {"model": f['cost_model'][index],
                                          "a": f['cost_a'][index],
                                          "b": f['cost_b'][index],
                                          "c": f['cost_c'][index],
                                          "d": f['cost_d'][index]},
                                 "revenue": {"model": f['revenue_model'][index],
                                             "a": f['revenue_a'][index],
                                             "b": f['revenue_b'][index],
                                             "c": f['revenue_c'][index],
                                             "d": f['revenue_d'][index]}}}

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
    generated_value = value_generate(value_factors, tonnage, {commodity: grade}, {commodity: recovery})

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
                       generated_value, discovery_time, start_time, brownfield_tonnage_factor, brownfield_grade_factor, value_factors, aggregation)

    # Generate project coproduct parameters using the region and production factors given in input_exploration_production_factors.csv
    for x in range(0, len(f['coproduct_commodity'][index])):
        if len(f['coproduct_commodity'][index]) != 0:
            c = f['coproduct_commodity'][index][x]
            if c != '':
                g = coproduct_grade_generate(new_project, f, index, x)
                r = f['coproduct_default_recovery'][index][x]
                st = f['coproduct_supply_trigger'][index][x]
                bgf = f['coproduct_brownfield_grade_factor'][index][x]
                vf = {'revenue': {'model': f['coproduct_revenue_model'][index][x],
                                  'a': f['coproduct_revenue_a'][index][x],
                                  'b': f['coproduct_revenue_b'][index][x],
                                  'c': f['coproduct_revenue_c'][index][x],
                                  'd': f['coproduct_revenue_d'][index][x]},
                      'cost': {'model': f['coproduct_cost_model'][index][x],
                               'a': f['coproduct_cost_a'][index][x],
                               'b': f['coproduct_cost_a'][index][x],
                               'c': f['coproduct_cost_a'][index][x],
                               'd': f['coproduct_cost_a'][index][x]}}
                new_project.add_commodity(c, g, r, st, bgf, vf)
    return new_project


def grade_generate(grade_model, factors, grade_dictionary={}):
    """
    grade_generate()
    Returns a mass ratio of commodity mass to total mass of the ore deposit, generated in accordance with defined grade
    distributions.
    'factors' input must be a dictionary with 'grade_model', 'a', 'b', 'c' and 'd' defined.
    grade_model = 1: Fixed grade distribution
        a = grade
    grade_model = 2: Lognormal grade distribution
        a = mu, mean
        b = sigma, standard deviation
        c = multiplier
        d = max grade
    grade_model = 3: Placeholder for user-defined grade distribution

    TODO: Check lognormal distribution function and grade-dependent tonnage
    TODO: Ensure parameter definition consistent with coproduct_grade_generate
    TODO: Add grade model for multiple of an input variable
    TODO: Refactor grade_model to strings e.g. "fixed", "lognormal", etc.
    """
    a = factors['a']
    b = factors['b']
    c = factors['c']
    d = factors['d']

    if grade_model == "fixed":
        # Fixed grade | 'a' = grade
        grade = float(a)
    elif grade_model == "multiple":
        # Multiple of main commodity grade | 'a' = commodity name, 'b' = grade multiplier, grade_dictionary = {commodity: value}
        grade = grade_dictionary[a] * float(b)
    elif grade_model == "lognormal":
        # Lognormal grade distribution
        # Distribution | 'a' = mean mu, 'b' = standard deviation sigma, 'c' = max value
        grade = abs(random.lognormvariate(float(a),float(b)))
        if grade > float(c):
            grade = float(c)

        # FIXME: 'tonnage' not passed to function
        # FIXME: check Gerst / paper the correct log-normal grade equation
        # tonnage = abs(random.gauss(factors['a'],factors['b']) * factors['c'])
        # Generate grade and ensure it is positive
        # grade = abs(tonnage / random.gauss(factors['a'],factors['b']) ** factors['c'])
        # Check if generated grade is higher than the maximum grade given in factor 'd'
        # FIXME: check for an alternative approach using random.lognormvariate(mu, sigma) function. Need to determine whether grade dependent.
        # FIXME: ensure parameter definition consistency with coproduct_grade_generate
        #grade = abs(random.lognormvariate(factors['a'], factors['b'])) * factors['c']
        #if grade > float(factors['d']):
        #    grade = float(factors['d'])
    elif grade_model == "user":
        # User-defined grade distribution
        # grade = "ENTER USER DEFINED DISTRIBUTION HERE"
        grade = "ENTER USER DEFINED GRADE DISTRIBUTION HERE"

    else:
        print("!!! VALID GRADE_MODEL NOT SELECTED !!!")
    return grade

def coproduct_grade_generate(project, factors, factor_index, commodity_index):
    """
    coproduct_grade_generate(
    factors['coproduct_a'][factor_index][commodity_index]
    factors['coproduct_b'][factor_index][commodity_index]
    factors['coproduct_c'][factor_index][commodity_index]
    factors['coproduct_d'][factor_index][commodity_index]
    )
    TODO: Fix docstrings
    TODO: consider returning dictionary so that can return and update() empty dictionary.
    """
    try:
        grade_model = factors['coproduct_grade_model'][factor_index][commodity_index]
    except:
        return 0

    factors['a'] = factors['coproduct_a'][factor_index][commodity_index]
    factors['b'] = factors['coproduct_b'][factor_index][commodity_index]
    factors['c'] = factors['coproduct_c'][factor_index][commodity_index]
    factors['d'] = factors['coproduct_d'][factor_index][commodity_index]
    grade = grade_generate(grade_model, factors, project.grade)
    return grade
    # Means that the coproduct doesn't exist.


def tonnage_generate(size_model, factors, grade):
    """
    Returns a resource tonnage, generated in accordance with defined distributions.
    'factors' input must be a dictionary with 'a', 'b', 'c' and 'd' defined.
    tonnage_model : 1. Fixed tonnage distribution, 2. Lognormal tonnage distribution, 3. Lognormal-grade dependent
    tonnage distribution, 4. User-defined tonnage distribution
    TODO: Check lognormal-grade dependent tonnage distribution
    TODO: Define variable inputs for each model in comments.
    TODO: change size_model inputs to strings, e.g. "fixed", "lognormal", etc.
    TODO: Refactor tonnage models to strings
    """
    # Generate primary resource tonnage based upon a distribution relationship.
    if size_model == "fixed":
        # Fixed tonnage distribution
        tonnage = factors['a']
    elif size_model == "lognormal":
        # Lognormal tonnage distribution
        tonnage = abs(random.lognormvariate(factors['a'], factors['b']) * factors['c'])
    elif size_model == "lognormal_grade_dependent":
        # Lognormal-grade dependent tonnage distribution
        # FIXME: define the log-normal grade dependent tonnage distribution.
        tonnage = grade * random.lognormvariate(factors['a'],factors['b']) ** factors['c']
        # grade = tonnage / random.lognormvariate(factors['a'],factors['b']) ** factors['c']
        # FIXME: ensure that size generated are greater than zero. Use abs()
    elif size_model == "user":
        # User-defined size model
        tonnage = "ENTER USER DEFINED DISTRIBUTION HERE"
    else:
        print("!!! VALID SIZE_MODEL NOT SELECTED !!!")
    return tonnage


def value_generate(value_factors, ore, ore_grade, recovery):
    """
    value_generate()
    Generates net value based upon the current Mine object variables and value model.
    value_factors = {'MINE': {'cost': {'model': string, 'a': value, 'b', value: 'c': value, 'd': value},
                     commodity: {'revenue': {'model': string, 'a': value, 'b', value: 'c': value, 'd': value},
                                {'cost': {'model': string, 'a': value, 'b', value: 'c': value, 'd': value}}
    """
    # Establish net value under 'ALL' commodity
    return_value = {'ALL': float(0)}

    # Loop through commodities
    for c in value_factors:
        return_value[c] = 0

        # Check for 'MINE' costs to avoid passing c to ore_grade and recovery.
        if c == 'MINE':
            grade = ore_grade
            rec = recovery
        else:
            grade = ore_grade[c]
            rec = recovery[c]

        # Loop through revenue and cost models
        for k in value_factors[c]:

            value = (value_model(value_factors[c][k], ore, grade, rec))
            if k == "revenue":
                return_value[c] += value
                return_value['ALL'] += value
            elif k == "cost":
                return_value[c] -= value
                return_value['ALL'] -= value
    return return_value

def value_model(value_factors, ore, ore_grade, recovery):
    """
    value_generate(value_factors, ore, ore_grade, recovery)
    Generates value based upon the value model selected in the input_parameters.csv

    User defined models can be defined below and use input parameters value_factors['a'], value_factors['b'],
    value_factors['c'] and value_factors['d'] for individual regions and deposit types from the
    input_exploration_production_factors.csv input file.
    """

    model = value_factors['model']
    a = float(value_factors['a'])
    b = float(value_factors['b'])
    c = float(value_factors['c'])
    d = float(value_factors['d'])

    if model == "fixed":
        return a
    if model == "size":
        return ore
    if model == "grade":
        return ore_grade
    if model == "grade_recoverable":
        return ore_grade * recovery
    if model == "contained":
        return ore * ore_grade
    if model == "contained_recoverable":
        return ore * ore_grade * recovery
    if model == "size_value":
        return ore * a
    if model == "grade_value":
        return ore_grade * a
    if model == "grade_recoverable_value":
        return ore_grade * recovery * a
    if model == "contained_value":
        return ore * ore_grade * a
    if model == "contained_recoverable_value":
        return ore * ore_grade * recovery * a


def capacity_generate(resource_tonnage, a, b, minimum, maximum):
    """
    Returns a production capacity based upon the taylor rule factors in input_exploration_production_factors.csv
    production_capacity = a * resource_tonnage ** b, constrained to between min and max
    """
    production_capacity = a * resource_tonnage ** b
    if production_capacity < minimum:
        production_capacity = minimum
    elif production_capacity > maximum:
        production_capacity = maximum

    return production_capacity


def update_exploration_production_factors(factors, updates):
    """
    Updates the exploration_production_factors data structure
    factors | a dictionary containing lists of exploration_production_factor variables
    updates | a nested dictionary of structure {region: {deposit_type: {variable: {commodity: value}}}}

    returns updated factors

    Note: Ignores any production variables. # Can't remember the purpose of this comment, but keeping just in case.
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
