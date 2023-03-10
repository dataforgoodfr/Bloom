"""This package contains all the infra related code.

Three functions allow us to get ship data from S3 storage.
Each function yield an object than geopandas can read:

>>> import geopandas as geopd
>>> from src.infra import get_vessel_file

>>> file = get_vessel_file(8224418)
>>> df = geopd.read_file(file)
>>> print(df)

Here are the three functions, please use `help(the_function)` 
to get more information about them.

get_data_file(
    vessel_IMOs: Union[int, str, List[Union[int, str]]] = None, 
    date_strings: Union[List[str], str] = None
) -> DataFile:

get_day_file(date_string: str = "today") -> DataFile
get_vessel_file(vessel_IMO: Union[int, str]) -> DataFile
 
"""

from src.infra.split_repository_vessel import get_day_file, get_vessel_file, get_data_file