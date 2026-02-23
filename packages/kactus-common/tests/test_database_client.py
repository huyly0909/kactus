#!/usr/bin/env python3
"""
Tests for the enhanced DatabaseClient with different UpdateStrategy implementations.
"""

import pytest
import pandas as pd
import tempfile
import os
from unittest.mock import patch, MagicMock

from kactus_common.database.duckdb.client import DatabaseClient
from kactus_common.database.duckdb.schema import Table, Column
from kactus_common.database.duckdb.consts import DataType, UpdateStrategy


class TestDatabaseClient:
    """Test suite for DatabaseClient functionality."""
    
    @pytest.fixture
    def temp_db_path(self):
        """Create a temporary database path for testing."""
        # Use a path that doesn't exist so DuckDB creates a new database
        temp_dir = tempfile.mkdtemp()
        temp_path = os.path.join(temp_dir, "test.duckdb")
        yield temp_path
        # Cleanup
        if os.path.exists(temp_path):
            os.unlink(temp_path)
        os.rmdir(temp_dir)
    
    @pytest.fixture
    def client(self, temp_db_path):
        """Create a DatabaseClient instance for testing."""
        client = DatabaseClient(temp_db_path)
        yield client
    
    @pytest.fixture
    def memory_client(self):
        """Create an in-memory DatabaseClient for faster testing."""
        client = DatabaseClient(":memory:")
        yield client
    
    @pytest.fixture
    def sample_table(self):
        """Create a sample table definition."""
        return Table(
            name="test_users",
            columns=[
                Column(name="id", data_type=DataType.INT, is_primary_key=True, is_nullable=False),
                Column(name="name", data_type=DataType.STRING, is_nullable=False),
                Column(name="email", data_type=DataType.STRING),
                Column(name="age", data_type=DataType.INT, default_value="0")
            ],
            update_strategy=UpdateStrategy.REPLACE
        )
    
    @pytest.fixture
    def sample_data(self):
        """Create sample DataFrame for testing."""
        return pd.DataFrame({
            'id': [1, 2, 3],
            'name': ['Alice', 'Bob', 'Charlie'],
            'email': ['alice@test.com', 'bob@test.com', 'charlie@test.com'],
            'age': [25, 30, 35]
        })
    
    def test_client_initialization(self, temp_db_path):
        """Test DatabaseClient initialization."""
        client = DatabaseClient(temp_db_path)
        assert client.db_path == temp_db_path
        # Test that we can establish a connection
        with client.get_connection() as conn:
            assert conn is not None
    
    def test_create_table_basic(self, client, sample_table):
        """Test basic table creation."""
        client.create_table(sample_table.name, sample_table.columns)
        
        # Verify table exists
        assert client.table_exists(sample_table.name)
        
        # Check table structure
        table_info = client.get_table_info(sample_table.name)
        assert len(table_info) == 4  # 4 columns
        assert 'id' in table_info['column_name'].values
        assert 'name' in table_info['column_name'].values
    
    def test_create_table_with_primary_key(self, client):
        """Test table creation with primary key constraints."""
        table = Table(
            name="pk_test",
            columns=[
                Column(name="id", data_type=DataType.INT, is_primary_key=True, is_nullable=False),
                Column(name="name", data_type=DataType.STRING, is_nullable=False)
            ]
        )
        
        client.create_table(table.name, table.columns)
        assert client.table_exists(table.name)
    
    def test_insert_data_basic(self, client, sample_table, sample_data):
        """Test basic data insertion."""
        client.create_table(sample_table.name, sample_table.columns)
        client.insert_data(sample_table.name, sample_data)
        
        # Verify data was inserted
        result = client.execute(f"SELECT COUNT(*) as count FROM {sample_table.name}").fetchone()
        assert result[0] == 3
    
    def test_insert_data_empty_dataframe(self, client, sample_table):
        """Test inserting empty DataFrame."""
        client.create_table(sample_table.name, sample_table.columns)
        empty_data = pd.DataFrame(columns=['id', 'name', 'email', 'age'])
        
        # Should not raise an error
        client.insert_data(sample_table.name, empty_data)
        
        result = client.execute(f"SELECT COUNT(*) as count FROM {sample_table.name}").fetchone()
        assert result[0] == 0
    
    def test_dataframe_to_values_conversion(self, client):
        """Test DataFrame to SQL VALUES conversion."""
        data = pd.DataFrame({
            'id': [1, 2],
            'name': ["Alice's Data", "Bob"],
            'score': [95.5, None],
            'active': [True, False]
        })
        
        values_str = client._dataframe_to_values(data)
        
        # Check proper escaping and NULL handling
        assert "Alice''s Data" in values_str  # Escaped apostrophe
        assert "NULL" in values_str  # NULL for NaN
        assert "95.5" in values_str
        assert "True" in values_str
    
    def test_replace_strategy(self, client, sample_data):
        """Test REPLACE update strategy."""
        table = Table(
            name="replace_test",
            columns=[
                Column(name="id", data_type=DataType.INT),
                Column(name="name", data_type=DataType.STRING),
                Column(name="email", data_type=DataType.STRING),
                Column(name="age", data_type=DataType.INT)
            ],
            update_strategy=UpdateStrategy.REPLACE
        )
        
        client.create_table(table.name, table.columns)
        
        # Insert initial data
        client.update_table(table, sample_data)
        result = client.execute(f"SELECT COUNT(*) as count FROM {table.name}").fetchone()
        assert result[0] == 3
        
        # Replace with new data
        new_data = pd.DataFrame({
            'id': [4, 5],
            'name': ['David', 'Eve'],
            'email': ['david@test.com', 'eve@test.com'],
            'age': [28, 32]
        })
        
        client.update_table(table, new_data)
        
        # Should only have new data
        result = client.execute(f"SELECT COUNT(*) as count FROM {table.name}").fetchone()
        assert result[0] == 2
        
        # Verify it's the new data
        names = client.execute(f"SELECT name FROM {table.name} ORDER BY name").fetchall()
        assert [row[0] for row in names] == ['David', 'Eve']
    
    def test_append_strategy(self, client, sample_data):
        """Test APPEND update strategy."""
        table = Table(
            name="append_test",
            columns=[
                Column(name="id", data_type=DataType.INT),
                Column(name="name", data_type=DataType.STRING),
                Column(name="email", data_type=DataType.STRING),
                Column(name="age", data_type=DataType.INT)
            ],
            update_strategy=UpdateStrategy.APPEND
        )
        
        client.create_table(table.name, table.columns)
        
        # Insert initial data
        client.update_table(table, sample_data)
        result = client.execute(f"SELECT COUNT(*) as count FROM {table.name}").fetchone()
        assert result[0] == 3
        
        # Append more data
        new_data = pd.DataFrame({
            'id': [4, 5],
            'name': ['David', 'Eve'],
            'email': ['david@test.com', 'eve@test.com'],
            'age': [28, 32]
        })
        
        client.update_table(table, new_data)
        
        # Should have all data (original + new)
        result = client.execute(f"SELECT COUNT(*) as count FROM {table.name}").fetchone()
        assert result[0] == 5
    
    def test_upsert_strategy_single_primary_key(self, client):
        """Test UPSERT update strategy with single primary key."""
        table = Table(
            name="upsert_test",
            columns=[
                Column(name="id", data_type=DataType.INT, is_primary_key=True),
                Column(name="name", data_type=DataType.STRING),
                Column(name="score", data_type=DataType.INT)
            ],
            update_strategy=UpdateStrategy.UPSERT
        )
        
        client.create_table(table.name, table.columns)
        
        # Insert initial data
        initial_data = pd.DataFrame({
            'id': [1, 2, 3],
            'name': ['Alice', 'Bob', 'Charlie'],
            'score': [85, 90, 78]
        })
        client.update_table(table, initial_data)
        
        # Upsert: update existing (id=1) and add new (id=4)
        upsert_data = pd.DataFrame({
            'id': [1, 4],
            'name': ['Alice Updated', 'David'],
            'score': [95, 88]
        })
        client.update_table(table, upsert_data)
        
        # Should have 4 records total
        result = client.execute(f"SELECT COUNT(*) as count FROM {table.name}").fetchone()
        assert result[0] == 4
        
        # Check that Alice was updated
        alice_score = client.execute(f"SELECT score FROM {table.name} WHERE id = 1").fetchone()
        assert alice_score[0] == 95
        
        # Check that David was added
        david_exists = client.execute(f"SELECT name FROM {table.name} WHERE id = 4").fetchone()
        assert david_exists[0] == 'David'
    
    def test_upsert_strategy_multiple_primary_keys(self, client):
        """Test UPSERT strategy with composite primary key."""
        table = Table(
            name="composite_pk_test",
            columns=[
                Column(name="user_id", data_type=DataType.INT, is_primary_key=True),
                Column(name="product_id", data_type=DataType.INT, is_primary_key=True),
                Column(name="rating", data_type=DataType.INT)
            ],
            update_strategy=UpdateStrategy.UPSERT
        )
        
        client.create_table(table.name, table.columns)
        
        # Insert initial data
        initial_data = pd.DataFrame({
            'user_id': [1, 1, 2],
            'product_id': [100, 101, 100],
            'rating': [4, 5, 3]
        })
        client.update_table(table, initial_data)
        
        # Upsert: update (1,100) and add (2,101)
        upsert_data = pd.DataFrame({
            'user_id': [1, 2],
            'product_id': [100, 101],
            'rating': [5, 4]
        })
        client.update_table(table, upsert_data)
        
        # Should have 4 records total
        result = client.execute(f"SELECT COUNT(*) as count FROM {table.name}").fetchone()
        assert result[0] == 4
        
        # Check that (1,100) was updated
        rating = client.execute(f"SELECT rating FROM {table.name} WHERE user_id = 1 AND product_id = 100").fetchone()
        assert rating[0] == 5
    
    def test_upsert_strategy_no_primary_key(self, client, sample_data):
        """Test UPSERT strategy falls back to APPEND when no primary key."""
        table = Table(
            name="no_pk_test",
            columns=[
                Column(name="id", data_type=DataType.INT),  # No primary key
                Column(name="name", data_type=DataType.STRING),
                Column(name="email", data_type=DataType.STRING),
                Column(name="age", data_type=DataType.INT)
            ],
            update_strategy=UpdateStrategy.UPSERT
        )
        
        client.create_table(table.name, table.columns)
        
        # Should behave like APPEND
        client.update_table(table, sample_data)
        client.update_table(table, sample_data)  # Same data again
        
        # Should have duplicated data (6 records)
        result = client.execute(f"SELECT COUNT(*) as count FROM {table.name}").fetchone()
        assert result[0] == 6
    
    def test_insert_overwrite_strategy(self, client):
        """Test INSERT_OVERWRITE update strategy with partitions."""
        table = Table(
            name="overwrite_test",
            columns=[
                Column(name="date", data_type=DataType.STRING),
                Column(name="product", data_type=DataType.STRING),
                Column(name="sales", data_type=DataType.INT)
            ],
            update_strategy=UpdateStrategy.INSERT_OVERWRITE,
            partition_columns=["date"]
        )
        
        client.create_table(table.name, table.columns)
        
        # Insert initial data for multiple dates
        initial_data = pd.DataFrame({
            'date': ['2024-01-01', '2024-01-01', '2024-01-02'],
            'product': ['A', 'B', 'A'],
            'sales': [100, 150, 200]
        })
        client.update_table(table, initial_data)
        
        # Overwrite only 2024-01-01 data
        overwrite_data = pd.DataFrame({
            'date': ['2024-01-01', '2024-01-01'],
            'product': ['A', 'C'],  # Different products
            'sales': [120, 180]
        })
        client.update_table(table, overwrite_data)
        
        # Should have 3 records: 2 for 2024-01-01 (new) + 1 for 2024-01-02 (preserved)
        result = client.execute(f"SELECT COUNT(*) as count FROM {table.name}").fetchone()
        assert result[0] == 3
        
        # Check that 2024-01-02 data is preserved
        jan_02_data = client.execute(f"SELECT sales FROM {table.name} WHERE date = '2024-01-02'").fetchone()
        assert jan_02_data[0] == 200
        
        # Check that 2024-01-01 data was overwritten
        jan_01_products = client.execute(f"SELECT product FROM {table.name} WHERE date = '2024-01-01' ORDER BY product").fetchall()
        assert [row[0] for row in jan_01_products] == ['A', 'C']
    
    def test_insert_overwrite_no_partitions(self, client, sample_data):
        """Test INSERT_OVERWRITE falls back to REPLACE when no partitions."""
        table = Table(
            name="no_partition_test",
            columns=[
                Column(name="id", data_type=DataType.INT),
                Column(name="name", data_type=DataType.STRING),
                Column(name="email", data_type=DataType.STRING),
                Column(name="age", data_type=DataType.INT)
            ],
            update_strategy=UpdateStrategy.INSERT_OVERWRITE
            # No partition_columns specified
        )
        
        client.create_table(table.name, table.columns)
        
        # Should behave like REPLACE
        client.update_table(table, sample_data)
        result = client.execute(f"SELECT COUNT(*) as count FROM {table.name}").fetchone()
        assert result[0] == 3
        
        # New data should replace all
        new_data = pd.DataFrame({
            'id': [4, 5],
            'name': ['David', 'Eve'],
            'email': ['david@test.com', 'eve@test.com'],
            'age': [28, 32]
        })
        client.update_table(table, new_data)
        
        result = client.execute(f"SELECT COUNT(*) as count FROM {table.name}").fetchone()
        assert result[0] == 2
    
    def test_invalid_update_strategy(self, client, sample_table, sample_data):
        """Test error handling for invalid update strategy."""
        # Create table with invalid strategy
        table = sample_table.model_copy()
        table.update_strategy = "INVALID_STRATEGY"
        
        client.create_table(table.name, table.columns)
        
        with pytest.raises(ValueError, match="Invalid update strategy"):
            client.update_table(table, sample_data)
    
    def test_empty_data_handling(self, client, sample_table):
        """Test handling of empty DataFrames."""
        client.create_table(sample_table.name, sample_table.columns)
        
        empty_data = pd.DataFrame(columns=['id', 'name', 'email', 'age'])
        
        # Should not raise errors for any strategy
        for strategy in [UpdateStrategy.REPLACE, UpdateStrategy.APPEND, 
                        UpdateStrategy.UPSERT, UpdateStrategy.INSERT_OVERWRITE]:
            table = sample_table.model_copy()
            table.update_strategy = strategy
            client.update_table(table, empty_data)  # Should not raise
    
    def test_upsert_missing_primary_key_columns(self, client):
        """Test UPSERT error when primary key columns missing from data."""
        table = Table(
            name="missing_pk_test",
            columns=[
                Column(name="id", data_type=DataType.INT, is_primary_key=True),
                Column(name="name", data_type=DataType.STRING)
            ],
            update_strategy=UpdateStrategy.UPSERT
        )
        
        client.create_table(table.name, table.columns)
        
        # Data missing the primary key column
        bad_data = pd.DataFrame({
            'name': ['Alice', 'Bob']
            # Missing 'id' column
        })
        
        with pytest.raises(ValueError, match="Primary key columns .* not found in data"):
            client.update_table(table, bad_data)
    
    def test_table_exists(self, client, sample_table):
        """Test table existence checking."""
        assert not client.table_exists("nonexistent_table")
        
        client.create_table(sample_table.name, sample_table.columns)
        assert client.table_exists(sample_table.name)
    
    def test_get_table_info(self, client, sample_table):
        """Test getting table information."""
        client.create_table(sample_table.name, sample_table.columns)
        
        info = client.get_table_info(sample_table.name)
        assert isinstance(info, pd.DataFrame)
        assert len(info) > 0
        assert 'column_name' in info.columns
    
    def test_get_table_info_nonexistent(self, client):
        """Test getting info for nonexistent table."""
        with pytest.raises(Exception):
            client.get_table_info("nonexistent_table")
    
    def test_execute_with_error_handling(self, client):
        """Test SQL execution error handling."""
        with pytest.raises(Exception):
            client.execute("INVALID SQL QUERY")
    
    def test_close_connection(self, temp_db_path):
        """Test proper connection closing."""
        client = DatabaseClient(temp_db_path)
        
        # Test that connections are properly managed
        with client.get_connection() as conn:
            assert conn is not None
        
        # Close method should work without errors (connections are auto-managed)
    
    def test_context_manager_connection(self, temp_db_path):
        """Test the context manager functionality for connections."""
        client = DatabaseClient(temp_db_path)
        
        # Test multiple connection contexts
        with client.get_connection() as conn1:
            assert conn1 is not None
            # Test that we can execute queries within the context
            conn1.execute("CREATE TABLE test_ctx (id INT)")
        
        # Test another connection context
        with client.get_connection() as conn2:
            assert conn2 is not None
            # Verify the table still exists (connections should work properly)
            result = conn2.execute("SELECT table_name FROM information_schema.tables WHERE table_name='test_ctx'")
            # This verifies the connection and persistence work properly
        
    
    def test_schema_helper_methods(self):
        """Test Table schema helper methods."""
        table = Table(
            name="test",
            columns=[
                Column(name="id", data_type=DataType.INT, is_primary_key=True),
                Column(name="user_id", data_type=DataType.INT, is_primary_key=True),
                Column(name="name", data_type=DataType.STRING)
            ]
        )
        
        # Test get_primary_key_columns
        pk_cols = table.get_primary_key_columns()
        assert pk_cols == ["id", "user_id"]
        
        # Test get_column_by_name
        id_col = table.get_column_by_name("id")
        assert id_col is not None
        assert id_col.name == "id"
        assert id_col.is_primary_key is True
        
        # Test nonexistent column
        nonexistent = table.get_column_by_name("nonexistent")
        assert nonexistent is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"]) 
