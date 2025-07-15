from main.data_source.data_source import DataSource
from datetime import datetime
from typing import Dict, Any
import requests

from main.data_source.schema import SyncDataResponse

class MihongDataSource(DataSource):
    """
    Mihong.vn gold price data source implementation.
    """
    
    def __init__(self, xsrf_token: str):
        super().__init__("https://www.mihong.vn/api/v1/gold/prices/codes", "mihong")
        self.xsrf_token = xsrf_token
    
    def sync(self, start_date: datetime.date, end_date: datetime.date, code: str) -> SyncDataResponse:
        """
        Sync gold price data from Mihong.vn API.
        
        Args:
            start_date: Start date for the price data
            end_date: End date for the price data
            code: Gold type code (e.g., 'SJC', '999')
            
        Returns:
            Dictionary containing the API response data
        """
        params = {
            'code': code,
            'startDate': self._format_request_date(start_date, is_end_date=False),
            'endDate': self._format_request_date(end_date, is_end_date=True)
        }
        
        try:
            response = self._make_request(self.base_url, params)
            data = response.json()
            
            return SyncDataResponse(
                success=True,
                data_source=self.name,
                code=code,
                start_date=start_date.isoformat(),
                end_date=end_date.isoformat(),
                data=data,
                timestamp=datetime.now().isoformat()
            )
            
        except requests.RequestException as ex:
            return SyncDataResponse(
                success=False,
                data_source=self.name,
                code=code,
                start_date=start_date.isoformat(),
                end_date=end_date.isoformat(),
                data={},
                error={
                    'message': str(ex),
                    'status_code': response.status_code,
                },
                timestamp=datetime.now().isoformat()
            )
    
    def _format_request_date(self, date_obj: datetime.date, is_end_date: bool = False) -> str:
        """
        Format date for Mihong API: M/d/yyyy HH:mm:ss
        Start dates use 00:00:00, end dates use 23:59:59
        """
        if hasattr(date_obj, 'hour'):  # If it's already a datetime
            return date_obj.strftime('%-m/%-d/%Y %H:%M:%S')
        else:  # If it's a date, set time based on whether it's start or end
            if is_end_date:
                datetime_obj = datetime.combine(date_obj, datetime.max.time().replace(microsecond=0))
            else:
                datetime_obj = datetime.combine(date_obj, datetime.min.time())
            return datetime_obj.strftime('%-m/%-d/%Y %H:%M:%S')
    
    def _get_headers(self) -> Dict[str, str]:
        """
        Get required headers for Mihong API requests.
        """
        return {
            'referer': 'https://www.mihong.vn/vi/gia-vang-trong-nuoc',
            'x-requested-with': 'XMLHttpRequest'
        }
    
    def _get_cookies(self) -> Dict[str, str]:
        """
        Get required cookies for Mihong API requests.
        """
        return {
            'XSRF-TOKEN': self.xsrf_token,
        }
