import duckdb
import pandas as pd
import logging
from typing import Optional, List
from contextlib import contextmanager

from kactus_common.database.duckdb.consts import UpdateStrategy
from kactus_common.database.duckdb.schema import Column, Table

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class MockResult:
    """Mock result object that holds fetched data from closed connections."""
    
    def __init__(self, data, description):
        self.data = data or []
        self.description = description
        self._index = 0
    
    def fetchone(self):
        """Fetch one row from the result."""
        if self.data and self._index < len(self.data):
            row = self.data[self._index]
            self._index += 1
            return row
        return None
    
    def fetchall(self):
        """Fetch all remaining rows from the result."""
        if self.data:
            remaining = self.data[self._index:]
            self._index = len(self.data)
            return remaining
        return []
    
    def df(self):
        """Convert result to pandas DataFrame."""
        if self.data and self.description:
            columns = [desc[0] for desc in self.description]
            return pd.DataFrame(self.data, columns=columns)
        return pd.DataFrame()

class DatabaseClient:
    
    def __init__(self, db_path: str):
        self.db_path = db_path
    
    @contextmanager
    def get_connection(self):
        """Context manager for database connections."""
        conn = None
        try:
            conn = duckdb.connect(self.db_path)
            logger.debug(f"Opened connection to {self.db_path}")
            yield conn
        except Exception as e:
            logger.error(f"Database connection error: {str(e)}")
            raise
        finally:
            if conn:
                conn.close()
                logger.debug(f"Closed connection to {self.db_path}")
    
    def execute(self, query: str):
        """Execute a SQL query and return the result."""
        try:
            with self.get_connection() as conn:
                result = conn.execute(query)
                # For SELECT queries, fetch all results before connection closes
                if query.strip().upper().startswith('SELECT'):
                    return MockResult(result.fetchall(), result.description)
                else:
                    # For non-SELECT queries, return a mock result that indicates success
                    return MockResult(None, None)
        except Exception as e:
            logger.error(f"Error executing query: {query}. Error: {str(e)}")
            raise
    
    def create_table(self, table_name: str, columns: list[Column]):
        """Create a table with the specified columns if it doesn't exist."""
        column_definitions = []
        primary_keys = []
        
        for column in columns:
            col_def = f"{column.name} {column.data_type}"
            if not column.is_nullable:
                col_def += " NOT NULL"
            if column.default_value:
                col_def += f" DEFAULT {column.default_value}"
            column_definitions.append(col_def)
            
            if column.is_primary_key:
                primary_keys.append(column.name)
        
        columns_str = ", ".join(column_definitions)
        
        # Add primary key constraint if any primary keys are defined
        if primary_keys:
            pk_str = ", ".join(primary_keys)
            columns_str += f", PRIMARY KEY ({pk_str})"
        
        query = f"CREATE TABLE IF NOT EXISTS {table_name} ({columns_str})"
        with self.get_connection() as conn:
            conn.execute(query)
        logger.info(f"Table {table_name} created/verified with primary keys: {primary_keys}")
    
    def insert_data(self, table_name: str, data: pd.DataFrame):
        """Insert data into a table using basic INSERT."""
        if data.empty:
            logger.warning(f"No data to insert into {table_name}")
            return
        
        # Convert DataFrame to records for DuckDB
        values_str = self._dataframe_to_values(data)
        query = f"INSERT INTO {table_name} VALUES {values_str}"
        with self.get_connection() as conn:
            conn.execute(query)
        logger.info(f"Inserted {len(data)} rows into {table_name}")
    
    def update_table(self, table: Table, data: pd.DataFrame):
        """Update table based on the specified update strategy."""
        if data.empty:
            logger.warning(f"No data to update in {table.name}")
            return
        
        logger.info(f"Updating table {table.name} with strategy {table.update_strategy}")
        
        if table.update_strategy == UpdateStrategy.REPLACE:
            self._replace_table_data(table.name, data)
        elif table.update_strategy == UpdateStrategy.APPEND:
            self._append_table_data(table.name, data)
        elif table.update_strategy == UpdateStrategy.UPSERT:
            self._upsert_table_data(table, data)
        elif table.update_strategy == UpdateStrategy.INSERT_OVERWRITE:
            self._insert_overwrite_table_data(table, data)
        else:
            raise ValueError(f"Invalid update strategy: {table.update_strategy}")
    
    def _replace_table_data(self, table_name: str, data: pd.DataFrame):
        """Replace all data in the table with new data."""
        try:
            with self.get_connection() as conn:
                # Delete all existing data
                conn.execute(f"DELETE FROM {table_name}")
                logger.info(f"Cleared all data from {table_name}")
                
                # Insert new data
                if not data.empty:
                    values_str = self._dataframe_to_values(data)
                    query = f"INSERT INTO {table_name} VALUES {values_str}"
                    conn.execute(query)
                    logger.info(f"Inserted {len(data)} rows into {table_name}")
            
        except Exception as e:
            logger.error(f"Error in REPLACE operation for {table_name}: {str(e)}")
            raise
    
    def _append_table_data(self, table_name: str, data: pd.DataFrame):
        """Append new data to the table without checking for duplicates."""
        try:
            if not data.empty:
                values_str = self._dataframe_to_values(data)
                query = f"INSERT INTO {table_name} VALUES {values_str}"
                with self.get_connection() as conn:
                    conn.execute(query)
                logger.info(f"Inserted {len(data)} rows into {table_name}")
        except Exception as e:
            logger.error(f"Error in APPEND operation for {table_name}: {str(e)}")
            raise
    
    def _upsert_table_data(self, table: Table, data: pd.DataFrame):
        """Insert new records or update existing ones based on primary key conflicts."""
        try:
            # Get primary key columns from the table definition
            primary_key_columns = table.get_primary_key_columns()
            
            if not primary_key_columns:
                logger.warning(f"No primary keys defined for table {table.name}, performing APPEND instead")
                self._append_table_data(table.name, data)
                return
            
            # Check if all primary key columns exist in the data
            missing_pk_cols = [col for col in primary_key_columns if col not in data.columns]
            if missing_pk_cols:
                raise ValueError(f"Primary key columns {missing_pk_cols} not found in data for UPSERT operation")
            
            with self.get_connection() as conn:
                # Build WHERE clause for deletion based on primary key values
                if len(primary_key_columns) == 1:
                    # Single primary key - use IN clause
                    pk_col = primary_key_columns[0]
                    values_list = data[pk_col].unique()
                    if len(values_list) > 0:
                        values_str = "', '".join(str(v) for v in values_list)
                        delete_query = f"DELETE FROM {table.name} WHERE {pk_col} IN ('{values_str}')"
                        conn.execute(delete_query)
                        logger.info(f"Deleted existing rows with conflicting {pk_col} values")
                else:
                    # Multiple primary keys - need to build more complex WHERE clause
                    where_conditions = []
                    for _, row in data.iterrows():
                        pk_conditions = []
                        for pk_col in primary_key_columns:
                            value = row[pk_col]
                            if pd.isna(value):
                                pk_conditions.append(f"{pk_col} IS NULL")
                            elif isinstance(value, str):
                                escaped_value = value.replace("'", "''")
                                pk_conditions.append(f"{pk_col} = '{escaped_value}'")
                            elif isinstance(value, (int, float)):
                                pk_conditions.append(f"{pk_col} = {value}")
                            else:
                                # datetime, date, and other types — quote as string
                                escaped_value = str(value).replace("'", "''")
                                pk_conditions.append(f"{pk_col} = '{escaped_value}'")
                        where_conditions.append(f"({' AND '.join(pk_conditions)})")
                    
                    if where_conditions:
                        delete_query = f"DELETE FROM {table.name} WHERE {' OR '.join(where_conditions)}"
                        conn.execute(delete_query)
                        logger.info(f"Deleted existing rows with conflicting primary key combinations")
                
                # Insert the new/updated data
                if not data.empty:
                    values_str = self._dataframe_to_values(data)
                    query = f"INSERT INTO {table.name} VALUES {values_str}"
                    conn.execute(query)
                    logger.info(f"Inserted {len(data)} rows into {table.name}")
            
        except Exception as e:
            logger.error(f"Error in UPSERT operation for {table.name}: {str(e)}")
            raise
    
    def _insert_overwrite_table_data(self, table: Table, data: pd.DataFrame):
        """Insert data, overwriting specific partitions or conditions."""
        try:
            # Use partition columns from table definition
            partition_columns = table.partition_columns
            
            # If partition columns are specified, delete only those partitions
            if partition_columns:
                with self.get_connection() as conn:
                    for col in partition_columns:
                        if col in data.columns:
                            unique_values = data[col].unique()
                            values_str = "', '".join(str(v) for v in unique_values)
                            delete_query = f"DELETE FROM {table.name} WHERE {col} IN ('{values_str}')"
                            conn.execute(delete_query)
                            logger.info(f"Deleted partition data for {col} values: {unique_values}")
                        else:
                            logger.warning(f"Partition column {col} not found in data, skipping partition deletion")
                    
                    # Insert new data
                    if not data.empty:
                        values_str = self._dataframe_to_values(data)
                        query = f"INSERT INTO {table.name} VALUES {values_str}"
                        conn.execute(query)
                        logger.info(f"Inserted {len(data)} rows into {table.name}")
            else:
                # If no partition columns specified, behave like REPLACE
                logger.warning(f"No partition columns specified for INSERT_OVERWRITE on table {table.name}, using REPLACE strategy")
                self._replace_table_data(table.name, data)
                return
            
        except Exception as e:
            logger.error(f"Error in INSERT_OVERWRITE operation for {table.name}: {str(e)}")
            raise
    
    def _dataframe_to_values(self, data: pd.DataFrame) -> str:
        """Convert DataFrame to VALUES clause format for SQL INSERT."""
        # Handle None/NaN values and proper quoting
        records = []
        for _, row in data.iterrows():
            values = []
            for value in row:
                if pd.isna(value):
                    values.append("NULL")
                elif isinstance(value, str):
                    # Escape single quotes in strings
                    escaped_value = value.replace("'", "''")
                    values.append(f"'{escaped_value}'")
                elif isinstance(value, (int, float)):
                    values.append(str(value))
                else:
                    # datetime, date, Timestamp, and other types — quote as string
                    escaped_value = str(value).replace("'", "''")
                    values.append(f"'{escaped_value}'")
            records.append(f"({', '.join(values)})")
        
        return ', '.join(records)
    
    def table_exists(self, table_name: str) -> bool:
        """Check if a table exists in the database."""
        try:
            with self.get_connection() as conn:
                conn.execute(f"SELECT 1 FROM {table_name} LIMIT 1")
            return True
        except:
            return False
    
    def get_table_info(self, table_name: str) -> pd.DataFrame:
        """Get information about table structure."""
        try:
            with self.get_connection() as conn:
                return conn.execute(f"DESCRIBE {table_name}").df()
        except Exception as e:
            logger.error(f"Error getting table info for {table_name}: {str(e)}")
            raise
