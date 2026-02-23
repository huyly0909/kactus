from abc import ABC, abstractmethod
from datetime import date, datetime
from typing import Dict, List, Any, Optional
import urllib.parse
import requests

from kactus_data.schemas.data_source import SyncDataResponse


class DataSource(ABC):
    """
    Abstract base class for data sources.
    Provides a common interface for fetching data from different providers.
    """
    
    def __init__(self, base_url: str, name: str):
        self.base_url = base_url
        self.name = name
    
    @abstractmethod
    def sync(self, start_date: datetime.date, end_date: datetime.date, code: str) -> SyncDataResponse:
        """
        Fetch gold price data for the specified date range and code.
        
        Args:
            start_date: Start date for the price data
            end_date: End date for the price data  
            code: Gold type code (e.g., 'SJC', '999')
            
        Returns:
            Dictionary containing the fetched price data
            
        Raises:
            Exception: If the API request fails or returns invalid data
        """
        pass
    
    @abstractmethod
    def _format_request_date(self, date_obj: datetime.date, is_end_date: bool = False) -> str:
        """
        Format date according to the data source's expected format.
        
        Args:
            date_obj: Date object to format
            is_end_date: Whether this is an end date (affects time component)
            
        Returns:
            Formatted date string
        """
        pass
    
    @abstractmethod
    def _get_headers(self) -> Dict[str, str]:
        """
        Get required headers for API requests.
        
        Returns:
            Dictionary of HTTP headers
        """
        pass
    
    @abstractmethod
    def _get_cookies(self) -> Dict[str, str]:
        """
        Get required cookies for API requests.
        
        Returns:
            Dictionary of cookies
        """
        pass
    
    def _make_request(self, url: str, params: Dict[str, str]) -> requests.Response:
        """
        Make HTTP request with proper headers and cookies.
        
        Args:
            url: Request URL
            params: Query parameters
            
        Returns:
            Response object
        """
        response = requests.get(
            url,
            params=params,
            headers=self._get_headers(),
            cookies=self._get_cookies()
        )
        response.raise_for_status()
        return response
