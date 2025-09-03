# FreeDNCList.com API Replication

This backend now includes a complete replication of the FreeDNCList.com API workflow for checking phone numbers against Do Not Call lists.

## API Endpoints

### 1. Process CSV File
**POST** `/api/dnc/process`

Replicates the `process.php` endpoint from FreeDNCList.com.

**Request:**
- `file`: CSV file upload (multipart/form-data)
- `column_index`: Which column contains phone numbers (form field, default: 0)
- `format`: Output format (form field, default: "json")

**Response:**
```json
{
    "success": true,
    "file": "./uploads/contacts_DNC_checked_20250903_163048_ee4bca44.csv",
    "processing_id": "4e5ab98a-03ab-41a4-ac7c-f0026dd1f5d8"
}
```

**Example Usage:**
```bash
curl -X POST "http://localhost:8000/api/dnc/process" \
  -F "file=@contacts.csv" \
  -F "column_index=2" \
  -F "format=json"
```

### 2. Download Processed File
**GET** `/api/dnc/uploads/{filename}`

Downloads the processed CSV file with DNC status column added.

**Example Usage:**
```bash
curl -O "http://localhost:8000/api/dnc/uploads/contacts_DNC_checked_20250903_163048_ee4bca44.csv"
```

### 3. Check Processing Status
**GET** `/api/dnc/status/{processing_id}`

Returns the status of a processing job.

## CSV Processing

The API processes CSV files and adds a `DNC_Status` column with the following values:

- **SAFE**: Phone number is safe to call
- **DNC_MATCH**: Phone number is on Do Not Call list
- **INVALID_FORMAT**: Phone number format is invalid
- **CHECK_ERROR**: Error occurred during DNC check
- **PROCESSING_ERROR**: Error processing the row

## DNC Checking Logic

Currently, the system uses pattern-based DNC checking for demonstration:

1. **Pattern Matching**: Checks against predefined DNC patterns
2. **Range Checking**: Identifies numbers in specific ranges as DNC
3. **Ending Patterns**: Marks numbers ending with 0000 or 9999 as DNC

**To integrate with real DNC services:**

1. **Update `backend/do_not_call/core/dnc_service.py`**
2. **Replace the `_check_pattern_dnc` method** with calls to:
   - FCC DNC API
   - Twilio DNC API
   - CallFire DNC API
   - Your own DNC database

3. **Add your DNC API keys** to the config:
   ```python
   FCC_API_KEY = "your-fcc-api-key"
   ```

## File Management

- **Uploads Directory**: `./uploads/` (created automatically)
- **File Naming**: `{original_name}_checked_{timestamp}_{unique_id}.csv`
- **Security**: Filenames are sanitized to prevent path traversal attacks
- **Cleanup**: Implement file cleanup for old processed files

## Testing

Test the API with the provided sample files:

```bash
# Test with basic contacts
curl -X POST "http://localhost:8000/api/dnc/process" \
  -F "file=@test_contacts.csv" \
  -F "column_index=2" \
  -F "format=json"

# Test with DNC patterns
curl -X POST "http://localhost:8000/api/dnc/process" \
  -F "file=@test_contacts_dnc.csv" \
  -F "column_index=2" \
  -F "format=json"
```

## Integration with Frontend

The frontend DNC Checker component can now use these endpoints:

1. **Upload CSV** → Call `/api/dnc/process`
2. **Get file path** → Extract from JSON response
3. **Download results** → Call `/api/dnc/uploads/{filename}`

## Next Steps

1. **Replace demo DNC logic** with real DNC API calls
2. **Add authentication** if required
3. **Implement file cleanup** for old processed files
4. **Add rate limiting** for production use
5. **Add monitoring** and logging for DNC check performance
