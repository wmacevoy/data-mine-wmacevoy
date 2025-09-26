Uranium Dataset: Data sources and schema
This dataset is derived from the U.S. Geological Survey (USGS) Mineral Resources Data System (MRDS)
datacommons.psu.edu
. The MRDS contains records describing metallic and non‑metallic mineral occurrences, including deposit name, location, commodities and production history. The uranium_mines.csv in this package is a filtered subset of MRDS that retains only records mentioning uranium in one of the commodity fields. Additional cleaning and, optionally, merging with state permit databases can be performed by running uranium_dataset_pipeline.py (see README.md for details).
The table below lists each column in uranium_mines.csv, its data type (as inferred by pandas) and a brief description. Definitions are adapted from USGS metadata where available
portal1-geo.sabu.mtu.edu
. Columns with sparse or unclear definitions have been approximated based on their names.
Column	Type	Description
dep_id	integer	Deposit identification number. A unique 12‑digit sequence number referencing a mineral property record
portal1-geo.sabu.mtu.edu
.
url	string	URL of the MRDS report for this record.
mrds_id	string	Legacy MRDS identifier for the deposit.
mas_id	float	Legacy identifier from the MAS/MILS system; may be missing.
site_name	string	Name of the site, deposit or operation
portal1-geo.sabu.mtu.edu
.
latitude	float	Geographic latitude in decimal degrees (WGS 84)
portal1-geo.sabu.mtu.edu
.
longitude	float	Geographic longitude in decimal degrees (WGS 84)
portal1-geo.sabu.mtu.edu
.
region	float	Code indicating the geographic region (two‑character code)
portal1-geo.sabu.mtu.edu
.
country	string	Name of the country in which the site is located
portal1-geo.sabu.mtu.edu
.
state	string	Name or abbreviation of the U.S. state or province
portal1-geo.sabu.mtu.edu
.
county	string	County in which the site is located
portal1-geo.sabu.mtu.edu
.
com_type	string	Commodity type code; indicates the significance of listed commodities (primary, secondary, tertiary).
commod1	string	Primary commodities present at the site
portal1-geo.sabu.mtu.edu
. A comma‑separated list with qualifiers after a hyphen.
commod2	string	Secondary commodities present
portal1-geo.sabu.mtu.edu
.
commod3	string	Tertiary commodities present
portal1-geo.sabu.mtu.edu
.
oper_type	string	Type of operation (e.g. Surface, Underground, Placer, Well). Enumerated categories are described in USGS metadata
portal1-geo.sabu.mtu.edu
.
dep_type	string	Deposit type classification (e.g. vein, stratabound). Many records have missing values.
prod_size	string	Approximate production size category: Y (yes), N (no), S (small), M (medium), L (large), U (unknown)
portal1-geo.sabu.mtu.edu
.
dev_stat	string	Development status of the deposit (e.g. Occurrence, Producer, Past Producer).
ore	string	Names of ore minerals found at the site
portal1-geo.sabu.mtu.edu
.
gangue	string	Names of gangue (non‑economic) minerals
portal1-geo.sabu.mtu.edu
.
other_matl	string	Other materials or by‑products present (e.g. gravel, water).
orebody_fm	string	Form of the orebody (e.g. Tabular, Irregular).
work_type	string	General type of workings at the site (e.g. Surface, Underground, Prospect)
portal1-geo.sabu.mtu.edu
.
model	string	Deposit model code or name, referencing a USGS deposit model.
alteration	string	Types of alteration associated with the deposit (e.g. Hydrothermal, Oxidation).
conc_proc	string	Concentration processes used (e.g. Flotation, Leaching).
names	string	Alternate or historical names for the site.
ore_ctrl	string	Geological controls on ore distribution (e.g. Structure, Stratigraphy).
reporter	string	Person(s) who reported or compiled the record.
hrock_unit	string	Host rock stratigraphic unit (lithostratigraphic name).
hrock_type	string	Host rock lithology (e.g. Sandstone, Granite).
arock_unit	string	Adjacent (wall or cap rock) stratigraphic unit.
arock_type	string	Adjacent rock type (lithology).
structure	string	Structural features associated with the deposit (e.g. faults, folds).
tectonic	string	Tectonic setting (e.g. Intra-continental, Arc-related).
ref	string	Bibliographic references supporting the record
portal1-geo.sabu.mtu.edu
. Multiple references are delimited by braces.
yfp_ba	string	Unknown; likely year first production (before something).
yr_fst_prd	float	Year when production first occurred (numeric).
ylp_ba	string	Unknown; possibly last production year (before something).
yr_lst_prd	float	Year when production last occurred (numeric).
dy_ba	string	Unknown; possibly days of production.
disc_yr	float	Year of discovery.
prod_yrs	string	List or range of production years.
discr	string	Record discriminant or grade (A–E) reflecting completeness; records graded A have more information
datacommons.psu.edu
.
score	string	Overall quality score of the record (A–E); similar to discr. A indicates highly detailed records; E indicates minimal information
datacommons.psu.edu
.
Notes on missing values
Many fields in MRDS are sparsely populated. In our filtered uranium subset most records lack detailed geological information (hrock_unit, structure, etc.) but still provide basic location and commodity data. Missing values are represented as empty strings or NaN in the CSV. When summarising deposit types or commodities, consider replacing missing values with a placeholder (e.g. <missing>) as demonstrated in eda.py and the R notebook.
Source citations
Descriptions above draw on USGS metadata for the MRDS dataset
portal1-geo.sabu.mtu.edu
. For further information and definitions of specific fields, consult the USGS MRDS documentation and related metadata
datacommons.psu.edu
.