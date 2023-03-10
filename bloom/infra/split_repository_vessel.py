from csv import writer
from logging import getLogger
from pathlib import Path
from typing import List, Union, Callable, Any
import zipfile
import inspect
import functools
from dateparser import parse as parse_date
import itertools

from io import BytesIO

from src.infra.repository_vessel import VesselRepository, Vessel

logger = getLogger()


class DataDoesNotExistError(Exception):
    "Error triggered when no data matchs a filter"

    def __init__(self) -> None:
        super().__init__("No data has been found with the given filter.")

class DataFile(BytesIO):
    """A mock file agnostic to the csv split method."""

    def __init__(self, csv_paths: List[Path]):
        self._csv_paths = csv_paths
        self._is_initialized = False

        self._add_context_to_reading_methods()

    def _add_context_to_reading_methods(self) -> None:
        """Add a context aware data loader at each reading method.
        
        As the context is only known when the reading action
        occurs, the data is loaded at this moment. All the read methods
        are therefore augmented to load the data if it has not been done
        previously.
        """

        for method_name in dir(self):
            if method_name.startswith(("read", "get")):
                method = getattr(self, method_name)
                method = self._add_context_aware_loader(method)
                setattr(self, method_name, method)
        
    def _load_as_plain(self) -> None:
        """Load a plain csv file."""

        for csv_path in self._csv_paths:
            with Path.open(csv_path, "rb") as fd:
                self.write(fd.read())
            
    def _load_as_zip(self) -> None:
        """ Load zipfile data.
        
        This method is used when reading a file with Geopandas.
        Geopandas only handles zip files when reading bytes for now.
        """
        
        with zipfile.ZipFile(self, 'w') as z:
            data = b""
            for csv_path in self._csv_paths:
                with Path.open(csv_path, "rb") as fd:
                    data += fd.read()
            
            z.writestr('data.csv', data)
    
    def _load_data(self) -> None:
        """Loads data depending on the context.
        
        This method loads a content tailored to the reader.
        """

        current_frame, read_frame, caller_frame, *parent_frames = inspect.stack()

        if "geopandas" in caller_frame.filename:
            self._load_as_zip()
        else:
            self._load_as_plain()

        self.seek(0)
        self._is_initialized = True

    def _add_context_aware_loader(self, read_method: Callable) -> Callable:
        """Decorator that loads data before each first reading."""
        
        @functools.wraps(read_method)
        def read_wrapper(*args: Any, **kwargs: Any) -> bytes:
            if not self._is_initialized:
                self._load_data()
            
            return read_method(*args, **kwargs)

        return read_wrapper


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
    
    def save_vessels(self, vessels_list: List[Vessel]) -> None:
        logger.info(
            f"Saving vessels positions : {[vessel.IMO for vessel in vessels_list]}"
        )

        for vessel in vessels_list:
            file_path = self._get_vessel_csv_path(vessel)

            with Path.open(file_path, "a", newline="") as write_obj:
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
            raise DataDoesNotExistError()
    
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
        DataDoesNotExistError: Raise this error when no data are found.
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
        DataDoesNotExistError: Raise this error when no data are found.
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
        DataDoesNotExistError: Raise this error when no data are found.
    """

    return _split_vessel_repository.load_data(vessel_IMOs, date_strings)
