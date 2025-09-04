"""
TPS2 Database Service
Connects to the TPS2 SQL Server database to retrieve phone numbers for DNC checking
"""
import pyodbc
import asyncio
from typing import List, Dict, Any, Optional
from loguru import logger
from do_not_call.config import settings


class TPSDatabaseService:
    """Service for connecting to TPS2 SQL Server database"""
    
    def __init__(self):
        self.connection_string = self._build_connection_string()
        
    def _build_connection_string(self) -> str:
        """Build SQL Server connection string"""
        trust_cert = "yes" if settings.TPS_DB_TRUST_CERT else "no"
        
        return (
            f"DRIVER={{{settings.TPS_DB_DRIVER}}};"
            f"SERVER={settings.TPS_DB_SERVER};"
            f"DATABASE={settings.TPS_DB_NAME};"
            f"UID={settings.TPS_DB_USER};"
            f"PWD={settings.TPS_DB_PASSWORD};"
            f"TrustServerCertificate={trust_cert};"
            "Encrypt=yes;"
        )
    
    async def get_phone_numbers(self, limit: int = 1000) -> List[Dict[str, Any]]:
        """
        Retrieve phone numbers from TPS2 database using the provided SQL query
        
        Args:
            limit: Maximum number of phone numbers to retrieve (default: 1000)
            
        Returns:
            List of phone number records with metadata
        """
        try:
            # Run the query in a thread pool to avoid blocking
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(None, self._execute_query, limit)
            return result
            
        except Exception as e:
            logger.error(f"Error retrieving phone numbers from TPS2: {e}")
            raise

    async def get_cases_by_phone(self, phone_number: str) -> List[Dict[str, Any]]:
        """
        Retrieve all cases matching a given phone number across all phone fields.

        Returns a list of dictionaries including CaseID, CreatedDate, LastModifiedDate (if available),
        StatusID, StatusName (if available), and which PhoneType matched.
        """
        try:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(None, self._execute_cases_by_phone_query, phone_number)
            return result
        except Exception as e:
            logger.error(f"Error retrieving cases for phone {phone_number} from TPS2: {e}")
            raise

    def _execute_cases_by_phone_query(self, phone_number: str) -> List[Dict[str, Any]]:
        """Execute SQL to fetch cases matching a phone across possible fields."""
        try:
            sql_query = f"""
            WITH Matches AS (
                SELECT CaseID, CreatedDate, ModifiedDate, StatusID, 'HomePhone' AS PhoneType
                FROM [tps2].[dbo].[Cases]
                WHERE HomePhone = ?
                UNION ALL
                SELECT CaseID, CreatedDate, ModifiedDate, StatusID, 'WorkPhone' AS PhoneType
                FROM [tps2].[dbo].[Cases]
                WHERE WorkPhone = ?
                UNION ALL
                SELECT CaseID, CreatedDate, ModifiedDate, StatusID, 'CellPhone' AS PhoneType
                FROM [tps2].[dbo].[Cases]
                WHERE CellPhone = ?
                UNION ALL
                SELECT CaseID, CreatedDate, ModifiedDate, StatusID, 'SpouseHomePhone' AS PhoneType
                FROM [tps2].[dbo].[Cases]
                WHERE SpouseHomePhone = ?
                UNION ALL
                SELECT CaseID, CreatedDate, ModifiedDate, StatusID, 'SpouseWorkPhone' AS PhoneType
                FROM [tps2].[dbo].[Cases]
                WHERE SpouseWorkPhone = ?
                UNION ALL
                SELECT CaseID, CreatedDate, ModifiedDate, StatusID, 'SpouseCellPhone' AS PhoneType
                FROM [tps2].[dbo].[Cases]
                WHERE SpouseCellPhone = ?
                UNION ALL
                SELECT CaseID, CreatedDate, ModifiedDate, StatusID, 'SpouseDaytimePhone' AS PhoneType
                FROM [tps2].[dbo].[Cases]
                WHERE SpouseDaytimePhone = ?
            )
            SELECT M.CaseID, M.CreatedDate, M.ModifiedDate AS LastModifiedDate, M.StatusID, S.StatusName, M.PhoneType
            FROM Matches M
            LEFT JOIN [tps2].[dbo].[Status] S ON S.StatusID = M.StatusID
            ORDER BY M.CreatedDate DESC
            """

            with pyodbc.connect(self.connection_string) as conn:
                cursor = conn.cursor()
                params = [phone_number] * 7
                try:
                    cursor.execute(sql_query, params)
                except pyodbc.Error as e:
                    # Fallback if Status table name doesn't exist; return without StatusName
                    if 'Invalid object name' in str(e):
                        fallback_sql = f"""
                        WITH Matches AS (
                            SELECT CaseID, CreatedDate, ModifiedDate, StatusID, 'HomePhone' AS PhoneType FROM [tps2].[dbo].[Cases] WHERE HomePhone = ?
                            UNION ALL
                            SELECT CaseID, CreatedDate, ModifiedDate, StatusID, 'WorkPhone' AS PhoneType FROM [tps2].[dbo].[Cases] WHERE WorkPhone = ?
                            UNION ALL
                            SELECT CaseID, CreatedDate, ModifiedDate, StatusID, 'CellPhone' AS PhoneType FROM [tps2].[dbo].[Cases] WHERE CellPhone = ?
                            UNION ALL
                            SELECT CaseID, CreatedDate, ModifiedDate, StatusID, 'SpouseHomePhone' AS PhoneType FROM [tps2].[dbo].[Cases] WHERE SpouseHomePhone = ?
                            UNION ALL
                            SELECT CaseID, CreatedDate, ModifiedDate, StatusID, 'SpouseWorkPhone' AS PhoneType FROM [tps2].[dbo].[Cases] WHERE SpouseWorkPhone = ?
                            UNION ALL
                            SELECT CaseID, CreatedDate, ModifiedDate, StatusID, 'SpouseCellPhone' AS PhoneType FROM [tps2].[dbo].[Cases] WHERE SpouseCellPhone = ?
                            UNION ALL
                            SELECT CaseID, CreatedDate, ModifiedDate, StatusID, 'SpouseDaytimePhone' AS PhoneType FROM [tps2].[dbo].[Cases] WHERE SpouseDaytimePhone = ?
                        )
                        SELECT CaseID, CreatedDate, ModifiedDate AS LastModifiedDate, StatusID, NULL AS StatusName, PhoneType
                        FROM Matches
                        ORDER BY CreatedDate DESC
                        """
                        cursor.execute(fallback_sql, params)
                    else:
                        raise

                columns = [column[0] for column in cursor.description]
                rows = cursor.fetchall()

                results: List[Dict[str, Any]] = []
                for row in rows:
                    entry: Dict[str, Any] = {}
                    for i, column in enumerate(columns):
                        value = row[i]
                        if hasattr(value, 'isoformat'):
                            value = value.isoformat()
                        entry[column] = value
                    results.append(entry)

                return results

        except pyodbc.Error as e:
            logger.error(f"Database error: {e}")
            raise Exception(f"Database query failed: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            raise
    
    def _execute_query(self, limit: int) -> List[Dict[str, Any]]:
        """Execute the SQL query to get phone numbers"""
        try:
            # Build the SQL query with TOP limit
            sql_query = f"""
            SELECT DISTINCT TOP ({limit})
                PhoneNumber,
                CaseID,
                CreatedDate,
                StatusID,
                PhoneType
            FROM (
                SELECT DISTINCT 
                    HomePhone as PhoneNumber, 
                    CaseID, 
                    StatusID,
                    CreatedDate,
                    'HomePhone' as PhoneType
                FROM [tps2].[dbo].[Cases] 
                WHERE HomePhone IS NOT NULL 
                  AND HomePhone != '' 
                  AND YEAR(CreatedDate) = 2025
                
                UNION ALL
                
                SELECT DISTINCT 
                    WorkPhone as PhoneNumber, 
                    CaseID, 
                    StatusID,
                    CreatedDate,
                    'WorkPhone' as PhoneType
                FROM [tps2].[dbo].[Cases] 
                WHERE WorkPhone IS NOT NULL 
                  AND WorkPhone != '' 
                  AND YEAR(CreatedDate) = 2025
                
                UNION ALL
                
                SELECT DISTINCT 
                    CellPhone as PhoneNumber, 
                    CaseID, 
                    StatusID,
                    CreatedDate,
                    'CellPhone' as PhoneType
                FROM [tps2].[dbo].[Cases] 
                WHERE CellPhone IS NOT NULL 
                  AND CellPhone != '' 
                  AND YEAR(CreatedDate) = 2025
                
                UNION ALL
                
                SELECT DISTINCT 
                    SpouseHomePhone as PhoneNumber, 
                    CaseID, 
                    StatusID,
                    CreatedDate,
                    'SpouseHomePhone' as PhoneType
                FROM [tps2].[dbo].[Cases] 
                WHERE SpouseHomePhone IS NOT NULL 
                  AND SpouseHomePhone != '' 
                  AND YEAR(CreatedDate) = 2025
                
                UNION ALL
                
                SELECT DISTINCT 
                    SpouseWorkPhone as PhoneNumber, 
                    CaseID, 
                    StatusID,
                    CreatedDate,
                    'SpouseWorkPhone' as PhoneType
                FROM [tps2].[dbo].[Cases] 
                WHERE SpouseWorkPhone IS NOT NULL 
                  AND SpouseWorkPhone != '' 
                  AND YEAR(CreatedDate) = 2025
                
                UNION ALL
                
                SELECT DISTINCT 
                    SpouseCellPhone as PhoneNumber, 
                    CaseID, 
                    StatusID,
                    CreatedDate,
                    'SpouseCellPhone' as PhoneType
                FROM [tps2].[dbo].[Cases] 
                WHERE SpouseCellPhone IS NOT NULL 
                  AND SpouseCellPhone != '' 
                  AND YEAR(CreatedDate) = 2025
                
                UNION ALL
                
                SELECT DISTINCT 
                    SpouseDaytimePhone as PhoneNumber, 
                    CaseID, 
                    StatusID,
                    CreatedDate,
                    'SpouseDaytimePhone' as PhoneType
                FROM [tps2].[dbo].[Cases] 
                WHERE SpouseDaytimePhone IS NOT NULL 
                  AND SpouseDaytimePhone != '' 
                  AND YEAR(CreatedDate) = 2025
            ) AllPhoneNumbers
            ORDER BY CreatedDate DESC, PhoneNumber
            """
            
            # Connect to database and execute query
            with pyodbc.connect(self.connection_string) as conn:
                cursor = conn.cursor()
                cursor.execute(sql_query)
                
                # Fetch results
                columns = [column[0] for column in cursor.description]
                rows = cursor.fetchall()
                
                # Convert to list of dictionaries
                results = []
                for row in rows:
                    result = {}
                    for i, column in enumerate(columns):
                        value = row[i]
                        # Handle datetime objects
                        if hasattr(value, 'isoformat'):
                            value = value.isoformat()
                        result[column] = value
                    results.append(result)
                
                logger.info(f"Retrieved {len(results)} phone numbers from TPS2 database")
                return results
                
        except pyodbc.Error as e:
            logger.error(f"Database error: {e}")
            raise Exception(f"Database connection failed: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            raise
    
    async def test_connection(self) -> bool:
        """Test database connection"""
        try:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(None, self._test_connection_sync)
            return result
        except Exception as e:
            logger.error(f"Connection test failed: {e}")
            return False
    
    def _test_connection_sync(self) -> bool:
        """Synchronous connection test"""
        try:
            with pyodbc.connect(self.connection_string) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT 1")
                cursor.fetchone()
                return True
        except Exception as e:
            logger.error(f"Connection test failed: {e}")
            return False


# Create global instance
tps_database = TPSDatabaseService()
