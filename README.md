# pemmss
Primary Exploration, Mining and Metal Supply Scenario (PEMMSS) model

Developed by Stephen A. Northey
in collaboration with S. Pauliuk, S. Klose, M. Yellishetty and D. Giurco

For further information or enquiries email:
    stephen.northey@uts.edu.au

This scenario model evaluates the rates of mine development, mineral exploration and co-product recovery required to meet primary demand over-time.

### How to use:
1. #### Install python and the matplotlib package
The model has been developed and tested using python 3.11.1, matplotlib 3.6.2, numpy 1.24.1, pandas 2.0.1 and imageio 2.23.0.

Instructions for installing python are available at: https://www.python.org/

Instructions for installing matplotlib are available at: https://matplotlib.org/


3. #### Scenario Data Input and Calibration
Adjust scenario parameters and calibrate the model by modifying the CSV files located in the **input_files/** sub-directory.

The expected structure and data formats for each CSV file are documented in the associated import function defined in modules/file_import.py.

2. #### Execute pemmss.py
Run the model by executing pemmss.py using python.

3. #### View Results Data and Graphs
The results will be saved to a new sub-directory created for model execution, **output_files/[EXECUTION_DATE_TIME]/**

This will include:
- A folder containing copies of the input files used for the model run to ensure reproduceability.
- A folder containing data generated for each demand scenario, with individual results CSVs for each iteration of this.
- A folder containing aggregated statistics from all demand scenarios and iterations.
- A folder containing any generated graphs.
- A log file containing information useful for benchmarking and debugging.

### Developed and Tested Using:
python 3.11.1

matplotlib 3.6.2

imageio 2.23.0

numpy 1.24.1

pandas 2.0.1

### License:
This model is licensed under a BSD 3-Clause License. See LICENSE.md for further information.

### Attribution and Citation:
We request that any reference to this model in publications or presentations cite this GitHub repository and the journal article describing the model design and rationale. See CITATION.cff for specific details.
