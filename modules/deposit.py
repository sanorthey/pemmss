"""
Module with data structures and functions for handling deposit data

  class Mine:
        .__init__()
        .add_commodity()
        .get()
        .update_key_dict()
        .check_key_set()
        .update_by_region_deposit_type()
        .supply()
        .resource_expansion()
        .value_update()

  # Functions for discovering and defining resources
  resource_discovery()
  grade_generate()
  coproduct_grade_generate()
  tonnage_generate()
  value_generate()
  value_model()
  capacity_generate()
  update_exploration_production_factors()

"""

# Import standard packages
import random
import copy
from collections import defaultdict
from math import log
from statistics import mean, stdev

# Import from custom packages
from modules.file_export import export_log


class Mine:
    """ Mine Class.
    Used to initialise and track the current state of each mining project overtime.
    Mine(id_number, name, region, deposit_type, commodity, remaining_resource, grade,
    recovery, production_capacity, status, value, discovery_year, start_year,
    brownfield_tonnage, brownfield_grade, value_factors, aggregation)

    **** Variables ****
    Mine.id_number | Unique deposit identifying number
    Mine.name | Name of the deposit
    Mine.region | Region containing the deposit
    Mine.deposit_type | Primary deposit type
    Mine.commodity | Dictionary of commodities in the project {commodity: balanced}
                   | Where balanced = 1 indicates demand for this commodity can trigger mine supply
                   | Where balanced = 0 indicates demand for this commodity cannot trigger mine supply
    Mine.remaining_resource | List of tranches of remaining mineral resource, ore basis [R tranche 0,R tranche 1,]
    Mine.grade | Dictionary of lists of current resource ore grade tranches for each commodity. Ratio of total ore mass. {commodity: [G tranche 0,G tranche 1,]}
    Mine.current_tranche | Tranche of resource / grade that is currently being considered for resource exploitation
    Mine.initial_resource | # Size of the initial mineral resource, ore basis
    Mine.initial_grade | Dictionary of lists of initial resource ore grade tranches for each commodity. Ratio of total ore mass. {commodity: [G tranche 0,G tranche 1,]}
    Mine.grade_timeseries | Dictionary of grade of produced ore per year. Ratio of total ore mass. {commodity: {t: grade}}
    Mine.recovery | Dictionary of commodity recoveries. Ratio of total ore content. {commodity: recovery}
    Mine.production_capacity | Maximum extraction rate per period, ore basis.
    Mine.status | Already Produced in Time Period = 2
                  Developed = 1
                  Undeveloped = 0
                  Depleted = -1
                  Not valuable enough to mine = -2
                  Development probability test failed = -3
    Mine.value | Dictionary of value dictionaries of net recovery value for each commodity. Used to sequence mine supply.
                 {'ALL': {'ALL': net value, c: net_recovery_value}, tranche: {'ALL': net value, c: net_recovery_value}}
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
                 'remaining_resource', 'initial_resource', 'grade', 'initial_grade', 'grade_timeseries',
                 'current_tranche',
                 'recovery', 'production_capacity', 'production_intermediate', 'production_ore', 'expansion',
                 'expansion_contained', 'status', 'initial_status', 'value', 'discovery_year',
                 'start_year', 'development_probability', 'brownfield_tonnage', 'brownfield_grade',
                 'end_year', 'value_factors', 'aggregation', 'key_set')

    # Initialise mine variables
    def __init__(self, id_number, name, region, deposit_type, commodity,
                 remaining_resource, grade, recovery, production_capacity,
                 status, value, discovery_year, start_year, development_probability, brownfield_tonnage, brownfield_grade,
                 value_factors, aggregation, value_update=False):
        self.id_number = id_number
        self.name = name
        self.region = region
        self.deposit_type = deposit_type
        self.commodity = {commodity: 1}  # All Mine objects should have at least one balanced commodity.
        self.remaining_resource = remaining_resource  # List of ore tranches {c: [tranche 0, tranche 1, etc.]}
        self.grade = {commodity: grade}  # List of grades for each ore tranche {c: [tranche 0, tranche 1, etc.]}
        self.initial_resource = copy.deepcopy(self.remaining_resource)
        self.initial_grade = copy.deepcopy(self.grade)
        self.grade_timeseries = {commodity: {}}
        self.current_tranche = 0
        self.recovery = {commodity: recovery}
        self.production_capacity = production_capacity
        self.status = status
        self.initial_status = copy.deepcopy(self.status)
        self.discovery_year = discovery_year
        self.start_year = start_year
        self.development_probability = development_probability
        self.production_ore = {}
        self.production_intermediate = {commodity: {}}
        self.expansion = {}
        self.expansion_contained = {commodity: {}}
        self.brownfield_tonnage = brownfield_tonnage
        self.brownfield_grade = {commodity: brownfield_grade}
        self.end_year = None
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
        self.value = {}
        if value_update is False:
            self.value = value  # {'ALL': {'ALL': net value, c: net_recovery_value}, tranche: {'ALL': net value, c: net_recovery_value}}
        else:
            self.value_update()  # To simplify value generation during project import in cases where there's multiple tranches

    def add_commodity(self, add_commodity, add_grade, add_recovery, is_balanced, add_brownfield_grade, add_value_factors, update_value=True, log_file=None, tranche=0):
        """
        Mine.add_commodity(add_commodity, add_grade, add_recovery, is_balanced, add_brownfield_grade)
        Adds a commodity to a Mine objects commodity, grade, recovery, production_intermediate and key_set variables
        Can also be used to update variables for a Mine's existing commodity

        is_balanced == 1 then mine supply will be triggered by this commodity's demand
        is_balanced == 0 then mine supply won't be triggered by this commodity's demand

        update_value == True then Mine.value['ALL'] and Mine.value[c for c in Mine.commodity] will be updated.
        add_grade | should be list of tranche ore grades [tranche 0, tranche 1, etc.]
        tranche   | optional, can be used to modify tranche used to assign current grade
        # Note assumes all commodities would initially be added in the first year
        """
        self.commodity.update({add_commodity: int(is_balanced)})
        self.grade.update({add_commodity: add_grade})
        self.initial_grade.update(copy.deepcopy({add_commodity: add_grade}))
        self.grade_timeseries.update({add_commodity: {}})
        self.recovery.update({add_commodity: float(add_recovery)})
        self.brownfield_grade.update({add_commodity: float(add_brownfield_grade)})
        self.value_factors.update({add_commodity: add_value_factors})
        if update_value == True:
            self.value_update(log_file=log_file)
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
        elif variable == "grade_timeseries":
            if get_commodity is None:
                return self.grade_timeseries
            elif get_commodity in self.commodity:
                return self.grade_timeseries[get_commodity]
            else:
                return {}
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
        elif variable == 'development_probability':
            return self.development_probability
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
        elif variable == 'value_factors':
            return self.value_factors
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


    def update_by_region_deposit_type(self, update_factors, log_file=None):
        """
        Mine.update_by_region_deposit_type(ext_factors)
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
        Mine.development_probability

        Important Notes:
        - Cannot be used to add a new commodity. Use Mine.add_commodity() for this or insert '0' values for a commodity
              in the input files, then update later on.
        - If global parameter 'update_values' is true than any direct updates to Mine.value will be immediately
              overridden in the time loop by the models defined in Mine.value_factors.
        - If wanting to update grades in both Mine objects and exploration_production_factors then best to have separate
              inputs in input_exploration_production_factors_timeseries.csv
        - Update override / priority when using "ALL" wildcard
                            1. [self.region][self.deposit_type] - Won't be overriden
                            2. [self.region]["ALL"]
                            3. ["ALL"][self.deposit_type]
                            4. ["ALL"]["ALL"] - Will be overriden
        """
        variables = {}
        # Check if region and deposit_type pair is present in update_factors. "ALL" can be used as a wildcard also.
        # Generate set of update variables
        if "ALL" in update_factors.keys():
            if "ALL" in update_factors["ALL"].keys():
                variables.update(update_factors["ALL"]["ALL"])
            if self.deposit_type in update_factors["ALL"].keys():
                variables.update(update_factors["ALL"][self.deposit_type])
        if self.region in update_factors.keys():
            if "ALL" in update_factors[self.region].keys():
                variables.update(update_factors[self.region]["ALL"])
            if self.deposit_type in update_factors[self.region].keys():
                variables.update(update_factors[self.region][self.deposit_type])

        self.update_variables(variables, log_file=log_file)


    def update_variables(self, variables, log_file=None):
        """
        Mine.update_variables(variables)
        Updates a Mine object variables based upon a passed dictionary.
        variables = {variable: value OR {commodity: value}}

        Variables that can be updated:
            Mine.production_capacity
            Mine.status
            Mine.value
            Mine.discovery_year
            Mine.start_year
            Mine.grade
            Mine.recovery
            Mine.end_year
            Mine.development_probability
        """
        if 'production_capacity' in variables:
            self.production_capacity = float(variables['production_capacity'][''])
        if 'status' in variables:
            self.status = int(variables['status'][''])
        if 'value' in variables:
            # Unpack commodity structure
            for c in variables['value']:
                if c in self.value:
                    self.value[c] = float(variables['value'][c])
                else:
                    export_log(
                        'Attempted to update a project value for a non-existent project commodity. Variable update skipped.',
                        output_path=log_file, print_on=0)
        if 'discovery_year' in variables:
            self.discovery_year = int(variables['discovery_year'][''])
        if 'start_year' in variables:
            self.start_year = int(variables['start_year'][''])
        if 'grade' in variables:
            # Unpack commodity structure
            for c in variables['grade']:
                if c in self.grade:
                    self.grade[c] = float(variables['grade'][c])
                else:
                    export_log(
                        'Attempted to update a project grade for a non-existent project commodity. Variable update skipped.',
                        output_path=log_file, print_on=0)
        if 'recovery' in variables:
            for c in variables['recovery']:
                if c in self.recovery:
                    self.recovery[c] = float(variables['recovery'][c])
                else:
                    export_log(
                        'Attempted to update a project recovery for a non-existent project commodity. Variable update skipped.',
                        output_path=log_file, print_on=0)
        if 'end_year' in variables:
            self.end_year = int(variables['end_year'][''])
        if 'development_probability' in variables:
            self.development_probability = float(variables['development_probability'][''])


    def supply(self, ext_demand, year, ext_demand_commodity, marginal_recovery=False):
        """
        Mine.supply(ext_demand, year, ext_demand_commodity)
        Checks mine's ability to supply and determines ore production based upon resource and supply capacity constraints.
        Converts external commodity demand into ore demand based upon Mine.grade and Mine.recovery.
        If supply is triggered, all Mine commodities will be supplied.

        ext_demand | mass of commodity demand
        year | time period for the production
        ext_demanded_commodity | demanded commodity
        marginal_recovery | False, commodity extraction based on total project recovery value.
                            True, commodity extraction based on marginal recovery value from next ore tranche.

        *** Supply Criteria ***
        Does the mine's value exceed the value threshold?
        Does the mine produce the demanded commodity?
        Does demand for this commodity trigger this mine's supply?
        Does the mine have a start year and has this been passed?
        Has the mine passed the development probability test?
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
        if marginal_recovery is False:
            if self.value['ALL']['ALL'] < 0:
                # Deposit is not valuable enough to mine.
                self.status = -2
                return 0
        else:
            if self.value[self.current_tranche]['ALL'] < 0:
                # Deposit's current ore tranche is not valuable enough to mine.
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
            if random.random() <= self.development_probability:
                # Mine development probability test
                # Record year of mine becoming active
                self.status = 1
                self.start_year = year
            else:
                # Deposit failed the development probability test
                self.status = -3
                return 0

        if self.status == -1:
            # Mine is depleted
            return 0
        elif self.status == 2:
            # Mine already produced this time period.
            return 0
        else:
            demand_residual = ext_demand
            production_capacity_residual = self.production_capacity
            production_ore = 0
            production_ore_content = {c: float(0) for c in self.production_intermediate}
            production_intermediate = {c: float(0) for c in self.production_intermediate}
            tranche_status = []

            for tranche, _ in enumerate(self.remaining_resource):

                if production_capacity_residual > 0 and demand_residual > 0 and self.grade[ext_demand_commodity][tranche] != 0: # Checking for grade == 0 is to avoid divide by zero bugs in supply requirement calculation.
                    self.current_tranche = tranche
                    # Convert residual external demand into tranche ore demand by accounting for recovery and tranche specific ore grade
                    supply_requirement = demand_residual / self.grade[ext_demand_commodity][tranche] / self.recovery[ext_demand_commodity]
                    if supply_requirement <= self.remaining_resource[tranche]:
                        # Not resource constrained
                        if supply_requirement <= production_capacity_residual:
                            # Not supply capacity constrained, supply requirements fully met
                            tranche_production_ore = supply_requirement
                            tranche_status.append(2)
                        else:
                            # Supply capacity constrained, supply requirements not fully met
                            tranche_production_ore = production_capacity_residual
                            tranche_status.append(2)
                    else:
                        # Resource constrained
                        if self.remaining_resource[tranche] <= production_capacity_residual:
                            # Not supply capacity constrained, resource will be fully depleted, supply requirements not fully met
                            tranche_production_ore = self.remaining_resource[tranche]
                            tranche_status.append(-1)
                            self.end_year = year
                        else:
                            # Supply capacity constrained, supply at full capacity, supply requirements not fully met
                            tranche_production_ore = production_capacity_residual
                            tranche_status.append(2)

                    self.remaining_resource[tranche] -= tranche_production_ore
                    production_ore += tranche_production_ore

                    # Convert ore production to commodity production
                    tranche_production_ore_content = {c: float(0) for c in self.production_intermediate}
                    tranche_production_intermediate = {c: float(0) for c in self.production_intermediate}
                    for c in self.production_intermediate:
                        # Record mined ore content
                        tranche_production_ore_content[c] = tranche_production_ore * self.grade[c][tranche]
                        production_ore_content[c] += tranche_production_ore_content[c]
                        # Extract intermediate commodities with a positive value
                        if marginal_recovery is False:
                            if self.value['ALL'][c] >= 0:
                                # Recovery of c from this project generates positive or neutral value. c recovered from ore and supplied
                                tranche_production_intermediate[c] = tranche_production_ore_content[c] * self.recovery[c]
                                production_intermediate[c] += tranche_production_intermediate[c]
                        else:
                            if self.value[tranche][c] >= 0:
                                # Recovery of c from this ore tranche generates positive or neutral value. c recovered from ore and supplied
                                tranche_production_intermediate[c] = tranche_production_ore_content[c] * self.recovery[c]
                                production_intermediate[c] += tranche_production_intermediate[c]

                    # Adjust residuals for next tranche
                    production_capacity_residual -= tranche_production_ore
                    demand_residual -= tranche_production_intermediate[ext_demand_commodity]
                else:
                    #
                    tranche_status.append(0)

            # Check there was ore production.
            if production_ore > 0:
                # Record mined ore grade
                self.production_ore[year] = production_ore
                for c in production_ore_content:
                    self.grade_timeseries[c][year] = production_ore_content[c] / production_ore
                    self.production_intermediate[c][year] = production_intermediate[c]
                # Set Mine status based on tranche status
                if 2 in tranche_status:
                    self.status = 2
                if tranche_status[-1] == -1:
                    self.status = -1
                # Return Mine as having supplied
                return 1
            else:
                # Return Mine as having not supplied
                return 0


    def resource_expansion(self, year):
        """
        Mine.resource_expansion(year)
        Adds a tranche of brownfield ore to remaining resource and grade based on the brownfield tonnage and
        brownfield grade factors.
        Added ore = remaining resource * brownfield tonnage factor
        Grade of added ore = grade[commodity] * brownfield grade factor[commodity]

        # Note - value of added tranche is the same as the last existing tranche
        # If global parameters update_values is 1 then brownfield tranche will immediately have value re-updated afterwards
        """

        # Determine the size of the new ore tranche
        self.expansion[year] = sum(self.remaining_resource) * self.brownfield_tonnage

        for c in self.commodity:
            average_grade = sum([x*y for x, y in zip(self.remaining_resource, self.grade[c])]) / sum(self.remaining_resource)

            # Add grade of the new brownfield ore tranche
            self.grade[c].append(average_grade * self.brownfield_grade[c])

            # Record the amount of commodity contained in added ore
            self.expansion_contained[c][year] = self.grade[c][-1] * self.expansion[year]

        # Add ore tranche to the remaining resource
        self.remaining_resource.append(self.expansion[year])

        last_tranche = len(self.remaining_resource) - 2

        self.value.update({last_tranche + 1: self.value[last_tranche]})

    def value_update(self, log_file=None):
        """
        Mine.value_update()
        Updates Mine.value based upon the current Mine object variables and value model.
        self.value = {'ALL': {'ALL': net value, c: net recovery value}, tranche: {'ALL': net value, c: net recovery value}}
        """
        self.value['ALL'] = defaultdict(float)

        for tranche, _ in enumerate(self.remaining_resource):
            tranche_value_dict = value_generate(self.value_factors, self.remaining_resource, self.grade, self.recovery, tranche=tranche, log_file=log_file)
            self.value.update({tranche: tranche_value_dict})
            for c in tranche_value_dict:  # should include 'ALL'
                self.value['ALL'][c] += tranche_value_dict[c]


# ------------------------------------------------ #
# Functions for discovering and defining resources 
# ------------------------------------------------ #

def resource_discovery(f, current_year, is_background, id_number, log_file=None):
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

    development_probability = f['development_probability'][index]

    # Generate an ore grade based upon the deposit type's grade distribution model.
    grade = [grade_generate(f['grade_model'][index], grade_factors, log_file=log_file)]

    # Generate a resource size based upon deposit type's tonnage distribution model.
    tonnage = [tonnage_generate(f['tonnage_model'][index], tonnage_factors, grade, log_file=log_file)]

    # Lookup default recovery factor for deposit type
    recovery = f['recovery'][index]

    # Estimate supply capacity, check that within mine life constraints
    capacity = capacity_generate(tonnage[0], f['capacity_a'][index], f['capacity_b'][index], f['capacity_sigma'][index], f['life_min'][index], f['life_max'][index])

    # Generate Value
    value = value_generate(value_factors, tonnage, {commodity: grade}, {commodity: recovery}, tranche=0, log_file=log_file)
    generated_value = {'ALL': value,
                       0: value}

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
                       generated_value, discovery_time, start_time, development_probability, brownfield_tonnage_factor, brownfield_grade_factor, value_factors, aggregation)

    # Generate project coproduct parameters using the region and production factors given in input_exploration_production_factors.csv
    for x in range(0, len(f['coproduct_commodity'][index])):
        if len(f['coproduct_commodity'][index]) != 0:
            c = f['coproduct_commodity'][index][x]
            if c != '':
                g = coproduct_grade_generate(new_project, f, index, x, log_file=log_file)
                r = f['coproduct_recovery'][index][x]
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
                new_project.add_commodity(c, g, r, st, bgf, vf, tranche=0)
    return new_project


def grade_generate(grade_model, factors, grade_dictionary={}, tranche=0, log_file=None):
    """
    grade_generate()
    Returns a mass ratio of commodity mass to total mass of the ore deposit, generated in accordance with defined grade
    distributions.
    'factors' input must be a dictionary with 'grade_model', 'a', 'b', 'c' and 'd' defined.
    grade_model = 'fixed' | 'a' = grade
    grade_model = 'multiple' | 'a' = grade, 'b' = multiplier
    grade_model = 'lognormal' |
        a = mu, mean
        b = sigma, standard deviation
        c = max grade

    Note | Factors passed from coproduct_grade_generate are likely to be strings and need type conversion.
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
        grade = grade_dictionary[a][tranche] * float(b)
    elif grade_model == "lognormal":
        # Lognormal grade distribution
        # Distribution | 'a' = mean mu, 'b' = standard deviation sigma, 'c' = max value
        grade = abs(random.lognormvariate(float(a), float(b)))
        if grade > float(c):
            grade = float(c)
    else:
        export_log('Invalid grade model ' + str(grade_model), output_path=log_file, print_on=1)
    return grade


def coproduct_grade_generate(project, factors, factor_index, commodity_index, log_file=None):
    """
    coproduct_grade_generate_
    Returns a mass ratio of commodity mass to total mass of the ore deposit, based on coproduct commodity grade models.

    factors[f][factor_index][commodity_index] where f can = 'a', 'b', 'c' or 'd'
    factor_index = exploration_production_factors row index number
    commodity_index = coproduct commodity index from exploration_production_factors cell .split()

    Note | Likely to pass
    """

    grade_model = factors['coproduct_grade_model'][factor_index][commodity_index]
    f = {'a': factors['coproduct_a'][factor_index][commodity_index],
         'b': factors['coproduct_b'][factor_index][commodity_index],
         'c': factors['coproduct_c'][factor_index][commodity_index],
         'd': factors['coproduct_d'][factor_index][commodity_index]}
    grade = []
    for tranche in project.remaining_resource:
        grade.append(grade_generate(grade_model, f, project.grade, tranche=tranche, log_file=log_file))
    return grade


def tonnage_generate(size_model, factors, grade, log_file=None):
    """
    Returns a resource tonnage, generated in accordance with defined distributions.
    'factors' input must be a dictionary with 'a', 'b', 'c' and 'd' defined.
    tonnage_model : 1. Fixed tonnage distribution, 2. Lognormal tonnage distribution, 3. Lognormal-grade dependent
    tonnage distribution, 4. User-defined tonnage distribution
    """
    a = factors['a']
    b = factors['b']
    c = factors['c']
    d = factors['d']

    if size_model == "fixed":
        # Fixed tonnage | 'a' = tonnage
        tonnage = float(a)
    elif size_model == "lognormal":
        # Lognormal tonnage distribution
        # Distribution | 'a' = mean mu, 'b' = standard deviation sigma, 'c' = max value
        tonnage = abs(random.lognormvariate(float(a), float(b)))
        if tonnage > float(c):
            tonnage = float(c)
    else:
        export_log('Invalid tonnage model ' + str(size_model), output_path=log_file, print_on=1)
    return tonnage


def lognormal_factors(value_list):
    """
    This function can be called to logtransform a list of data points and derive mu and stdev for use with the lognormal tonnage and grade distribution models.
    """
    log_transformed_list = [log(v) for v in value_list]
    mu = mean(log_transformed_list)
    standard_dev = stdev(log_transformed_list)
    return mu, standard_dev


def value_generate(value_factors, resource, ore_grade, recovery, tranche=int(0), log_file=None):
    """
    value_generate()
    Generates net value based upon the current Mine object variables and value model.
    value_factors = {'MINE': {'cost': {'model': string, 'a': value, 'b', value: 'c': value, 'd': value},
                     commodity: {'revenue': {'model': string, 'a': value, 'b', value: 'c': value, 'd': value},
                                {'cost': {'model': string, 'a': value, 'b', value: 'c': value, 'd': value}}
    return_value = {'ALL': net_value, c: net_recovery_value}
    """
    # Establish net value under 'ALL' commodity
    return_value = {'ALL': float(0)}

    # Loop through commodities
    for c in value_factors:
        return_value[c] = 0

        # Check for 'MINE' costs to avoid passing c to ore_grade and recovery.
        if c == 'MINE':
            res = resource
            grade = ore_grade
            rec = recovery
        else:
            res = resource[tranche]
            grade = ore_grade[c][tranche]
            rec = recovery[c]

        # Loop through revenue and cost models
        for k in value_factors[c]:

            value = (value_model(value_factors[c][k], res, grade, rec, log_file=log_file))
            if k == "revenue":
                return_value[c] += value
                return_value['ALL'] += value
            elif k == "cost":
                return_value[c] -= value
                return_value['ALL'] -= value
    return return_value


def value_model(value_factors, ore, ore_grade, recovery, log_file=None):
    """
    value_generate(value_factors, ore, ore_grade, recovery)
    Generates value based upon the value model selected in the input_exploration_production_factors.csv

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
    elif model == "size":
        return ore
    elif model == "grade":
        return ore_grade
    elif model == "grade_recoverable":
        return ore_grade * recovery
    elif model == "contained":
        return ore * ore_grade
    elif model == "contained_recoverable":
        return ore * ore_grade * recovery
    elif model == "size_value":
        return ore * a
    elif model == "grade_value":
        return ore_grade * a
    elif model == "grade_recoverable_value":
        return ore_grade * recovery * a
    elif model == "contained_value":
        return ore * ore_grade * a
    elif model == "contained_recoverable_value":
        return ore * ore_grade * recovery * a
    else:
        export_log('Invalid value model ' + str(model), output_path=log_file, print_on=1)


def capacity_generate(resource_tonnage, a, b, sigma, minimum_life, maximum_life):
    """
    Returns a production capacity based upon the taylor rule factors and uncertainty given input_exploration_production_factors.csv
    production_capacity = random gaussian distribution (a * resource_tonnage ** b, sigma), constrained to between the min and max mine life

    sigma = standard deviation
    """
    capacity_mean = a * resource_tonnage ** b
    production_capacity = random.gauss(capacity_mean, sigma)

    mine_life = resource_tonnage / production_capacity
    if mine_life < minimum_life:
        production_capacity = resource_tonnage / minimum_life
    elif mine_life > maximum_life:
        production_capacity = resource_tonnage / maximum_life

    return production_capacity


def update_exploration_production_factors(factors, updates):
    """
    Updates the exploration_production_factors data structure
    factors | a dictionary containing lists of exploration_production_factor variables
    updates | a nested dictionary of structure {region: {deposit_type: {variable: {commodity: value}, variable: value}}}

    returns updated factors

    Note: Ignores any production variables. # Can't remember the purpose of this comment, but keeping just in case.
    """
    for r in updates:
        for d in updates[r]:
            # Build a set of factor indexes to be updates
            # Check if update for "ALL" regions or deposit types
            index_set = set()
            if r == "ALL" and d == "ALL":
                for reg in factors['lookup_table']:
                    for dep in factors['lookup_table'][reg]:
                        index_set.add(factors['lookup_table'][reg][dep])
            elif r == "ALL":
                for reg in factors['lookup_table']:
                    index_set.add(factors['lookup_table'][reg][d])
            elif d == "ALL":
                for dep in factors['lookup_table'][r]:
                    index_set.add(factors['lookup_table'][r][dep])
            else:
                index_set.add(factors['lookup_table'][r][d])
            for v in updates[r][d]:
                for c in updates[r][d][v]:
                    if c == '':
                        variable_split = updates[r][d][v][c].split(';')
                        if len(variable_split) == 1:
                            # Attempt to convert to float, otherwise store as string.
                            try:
                                for i in index_set:
                                    factors[v][i] = float(variable_split[0])
                            except:
                                for i in index_set:
                                    factors[v][i] = variable_split[0]
                        else:
                            variable_rebuilt = []
                            # Attempt to convert values to floats
                            for x in range(0, len(variable_split)):
                                try:
                                    variable_rebuilt.append(float(variable_split[x]))
                                except:
                                    variable_rebuilt.append(variable_split[x])
                            for i in index_set:
                                factors[v][i] = variable_rebuilt
                    else:
                        # Replicated incase ever want to add functionality for selective changes to a commodities values. This section would need modifying to allow that.
                        # Should work but not tested.
                        variable_split = updates[r][d][v][c].split(';')
                        if len(variable_split) == 1:
                            try:
                                for i in index_set:
                                    factors[v][i][c] = float(variable_split[0])
                            except:
                                for i in index_set:
                                    factors[v][i][c] = variable_split[0]
                        else:
                            variable_rebuilt = []
                            for x in range(0, len(variable_split)):
                                try:
                                    variable_rebuilt.append(float(variable_split[x]))
                                except:
                                    variable_rebuilt.append(variable_split[x])
                            for i in index_set:
                                factors[v][i][c] = variable_rebuilt
    return factors

# TODO: def inventory_create():

# TODO: def inventory_start():

# TODO: def inventory_supply():

# TODO: def inventory_care_and_maintenance()

# TODO: def inventory_end()

# TODO: def inventory_perpetual()

# TODO: def inventory_report()