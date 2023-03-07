from csv import writer
from logging import getLogger
from pathlib import Path
from typing import List, Union
import zipfile
from dateparser import parse as parse_date
import itertools

from io import BytesIO

from src.infra.repository_vessel import VesselRepository, Vessel

logger = getLogger()


class DataDoesNotExist(Exception):
    "Error triggered when no data match a filter"


class DataFile(BytesIO):
    def __init__(self, csv_paths: List[Path], zip_data: bool = True) -> None:
        # Geopandas use fiona to load files which only 
        # handles zip when fed with bytes.

        if zip_data:
            self._load_zip(csv_paths)
        else:
            self._load_plain(csv_paths)

        self.seek(0)

    def _load_plain(self, csv_paths):
        for csv_path in csv_paths:
            with open(csv_path, "rb") as fd:
                self.write(fd.read())
            
    def _load_zip(self, csv_paths):
        with zipfile.ZipFile(self, 'w') as z:
            data = b""
            for csv_path in csv_paths:
                with open(csv_path, "rb") as fd:
                    data += fd.read()
            
            z.writestr('data.csv', data)
        

    def readable(self):
        return True
    

class SplitVesselRepository(VesselRepository):
    def __init__(self):
        super().__init__()
        self.results_path = Path.joinpath(Path.cwd(), "data", "csv")

    def _get_vessel_csv_path(self, vessel: Vessel) -> Path:
        """Returns the path where to save a vessel.
        
        Args:
            vessel: The vessel to save
        
        Returns:
            Path: The path where to save the vessel.
        """

        parsed_date = vessel.timestamp.strftime('%Y-%m-%d')
        file_path = Path.joinpath(self.results_path, parsed_date, f"{vessel.IMO}.csv")
        file_path.parent.mkdir(parents=True, exist_ok=True)

        return file_path
    
    def save_vessels(self, vessels_list: List[Vessel]):
        logger.info(
            f"Saving vessels positions : {[vessel.IMO for vessel in vessels_list]}"
        )

        for vessel in vessels_list:
            file_path = self._get_vessel_csv_path(vessel)

            with open(file_path, "a", newline="") as write_obj:
                csv_writer = writer(write_obj)
                csv_writer.writerow(vessel.to_list())

    def load_data(
        self, 
        vessel_IMOs: Union[int, str, List[Union[int, str]]] = None, 
        date_strings: Union[List[str], str] = None
    ) -> DataFile:
        if date_strings:
            if not isinstance(date_strings, list):
                date_strings = [date_strings]

            dates = [
                parse_date(date_string).strftime('%Y-%m-%d') 
                for date_string in date_strings
            ]
        else:
            dates = ["**"]
        
        if vessel_IMOs:
            if not isinstance(vessel_IMOs, list):
                vessel_IMOs = [vessel_IMOs]
        else:
            vessel_IMOs = ["*"]
            
        logger.info(
            f"Load data from vessels {vessel_IMOs}' at dates {dates}."
        )
        
        files = []
        for date_str, IMO in itertools.product(dates, vessel_IMOs):
            files.extend(self.results_path.glob(f'{date_str}/{IMO}.csv'))
        
        if not files:
            raise DataDoesNotExist("No data has been found with the given filters.")
    
        return DataFile(files)
    
    def load_vessel(self, vessel_IMO: Union[int, str]) -> DataFile:
        logger.info(
            f"Load vessel {vessel_IMO}'s historic"
        )

        return self.load_data(vessel_IMOs=vessel_IMO)
    
    def load_day(self, date_string: str = "today") -> DataFile:
        logger.info(
            f"Load {date_string}'s historic"
        )

        return self.load_data(date_strings=date_string)


_split_vessel_repository = SplitVesselRepository()

def get_vessel_file(vessel_IMO: Union[int, str]) -> DataFile:
    """Return a file like object containing the data of a vessel.

    Args:
        vessel_IMO: The IMO of the vessel to get.
    
    Returns:
        DataFile: An object that encapsulate all the data
            of this vessel and can be read with geo_pandas
    
    Raises:
        DataDoesNotExist: Raise this error when no data are found.
    """

    return _split_vessel_repository.load_vessel(vessel_IMO)

def get_day_file(date_string: str = "today") -> DataFile:
    """Return a file like object containing the data of a given day.

    Args:
        date_string: A string representing a day. As we use
            dateparser to parse it, it can be given under a large
            variety of way such as "today", "two days ago", "10/10/2021",
            ect...
    
    Returns:
        DataFile: An object that encapsulate all the data
            of this day and can be read with geo_pandas
    
    Raises:
        DataDoesNotExist: Raise this error when no data are found.
    """

    return _split_vessel_repository.load_day(date_string)

def get_data_file(
        vessel_IMOs: Union[int, str, List[Union[int, str]]] = None, 
        date_strings: Union[List[str], str] = None
    ) -> DataFile:
    """Return a file like object containing the data given filters.

    Args:
        date_strings: A string or a list of strings representing (a) day(s). 
            As we use dateparser to parse it, it can be given under a large
            variety of way such as "today", "two days ago", "10/10/2021",
            ect... If none are given, all the historical data is returned.
        vessel_IMOs: A string or a list of strings representing the IMO 
            of (a) vessel(s) to get. if none are given, the data of all
            vessels is returned.

    Returns:
        DataFile: An object that encapsulate all the data
            of this day and can be read with geo_pandas
    
    Raises:
        DataDoesNotExist: Raise this error when no data are found.
    """

    return _split_vessel_repository.load_data(vessel_IMOs, date_strings)