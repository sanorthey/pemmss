# pemmss
### Primary Exploration, Mining and Metal Supply Scenario (PEMMSS) model
This scenario modeling framework evaluates the rates of mine development, mineral exploration and co-product recovery required to meet primary demand over-time.

PEMMSS codebase contributors:
- Stephen.A. Northey | PEMMSS Architect and Lead Developer 
- Jayden Hyman | PEMMSS GUI Developer (app.py) and Expert User 
- Bernardo Mendonca Severiano | PEMMSS Developer (spatial.py) and Expert User

PEMMSS model initial conceptualisation: S.A. Northey, S. Pauliuk, S. Klose, M. Yellishetty, D. Giurco

For further information or enquiries email:
    stephen.northey@uts.edu.au

### How to use:
1. #### Install python and dependent packages
This version of the model has been developed and tested using python 3.13.5. Additional required packages and the version used during development and testing are shown in requirements.txt. Install using pip:

```angular2html
cd <\path_to_pemmss_folder>
pip install -r requirements.txt
```

2. #### Scenario Data Input and Calibration
Adjust scenario parameters and calibrate the model by modifying the CSV files located in the **input_files/** subdirectory.

The expected structure and data formats for each CSV file are documented in the associated import function defined in modules/file_import.py.

Example input files are available in the **input_files_examples/** subdirectory and can be copied into the **input_files/** directory to get started.

3. #### Execute pemmss.py
Run the model by executing pemmss.py using python.

4. #### View Results Data and Graphs
The results will be saved to a new sub-directory created for model execution, **output_files/[EXECUTION_DATE_TIME]/**

This will include:
- A folder containing copies of the input files used for the model run to ensure reproduceability.
- A folder containing data generated for each demand scenario, with individual results CSVs for each iteration of this.
- A folder containing aggregated statistics from all demand scenarios and iterations.
- A folder containing any generated graphs.
- A log file containing information useful for benchmarking and debugging.

5. #### Alternative GUI interface
Run app.py using python.

Please note that this may not run correctly when ran from IDEs without native Jupyter notebook support such as Pycharm Community version. Has been tested to work with Pycharm Professional, VScode and when ran from the terminal (need to cd into pemmss folder to ensure it is the working directory).

### License:
This model is licensed under a BSD 3-Clause License. See LICENSE.md for further information.

### Attribution and Citation:
We request that any reference to this model in publications or presentations cite the Zenodo repository (https://doi.org/10.5281/zenodo.7001908) and the journal article (https://doi.org/10.1016/j.rcradv.2023.200137) describing the core model design and rationale. See CITATION.cff or below for specific details:

Northey, S.A., Klose, S., Pauliuk, S., Yellishetty, M., Giurco, D. (2023). Primary Exploration, Mining and Metal Supply Scenario (PEMMSS) model: Towards a stochastic understanding of the mineral discovery, mine development and co-product recovery requirements to meet demand in a low-carbon future. Resources, Conservation & Recycling Advances 17: 200137. https://doi.org/10.1016/j.rcradv.2023.200137 

### Keep track of updates
Don't forget about PEMMSS. Smash your GitHub Watch and Star buttons to follow along!

[![Star History Chart](https://api.star-history.com/svg?repos=sanorthey/pemmss&type=Date)](https://www.star-history.com/#sanorthey/pemmss&Date)