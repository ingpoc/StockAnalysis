# Stock Analysis Project Guidelines

## Project Overview
This is a Python-based Stock Analysis application that scrapes financial data from MoneyControl and other sources, stores it in MongoDB, analyzes stock performance, and provides API endpoints for frontend integration.

## Backend API Endpoints

This section documents all the API endpoints exposed by the backend. All endpoints are prefixed with `/api/v1`.

### Market Data Endpoints (`market_data.py`)

- **GET** `/market-data`
  - Description: Fetches market overview data including top/worst performers and latest results
  - Query Parameters:
    - `quarter` (optional): Specific quarter to fetch data for
    - `force_refresh` (optional): Boolean to force refresh cache
  - Response: Market overview data with stocks categorized by performance

- **GET** `/quarters`
  - Description: Retrieves a list of all available quarters in the database
  - Query Parameters:
    - `force_refresh` (optional): Boolean to force refresh cache
  - Response: List of quarter strings (e.g., "Q1 2023", "Q2 2023")

### Stock Endpoints (`stock.py`)

- **GET** `/stock/{symbol}`
  - Description: Gets detailed financial information for a specific stock
  - Path Parameters:
    - `symbol`: Stock ticker symbol
  - Response: Detailed stock information with financial metrics

- **POST** `/stock/batch`
  - Description: Fetches details for multiple stocks in a single request
  - Request Body: Array of stock symbols
  - Response: Object mapping symbols to stock details

- **POST** `/stock/{symbol}/refresh-analysis`
  - Description: Triggers a refresh of the analysis for a specific stock
  - Path Parameters:
    - `symbol`: Stock ticker symbol
  - Response: Success message

### Portfolio Endpoints (`portfolio.py`)

- **GET** `/portfolio/holdings`
  - Description: Retrieves all holdings in the user's portfolio
  - Response: Array of holdings

- **GET** `/portfolio/holdings/enriched`
  - Description: Gets holdings with current price and performance data
  - Response: Array of enriched holdings with calculated metrics

- **POST** `/portfolio/holdings`
  - Description: Adds a new holding to the portfolio
  - Request Body: Holding details
  - Response: Created holding object

- **PUT** `/portfolio/holdings/{holding_id}`
  - Description: Updates an existing holding
  - Path Parameters:
    - `holding_id`: ID of the holding to update
  - Request Body: Updated holding details
  - Response: Updated holding object

- **DELETE** `/portfolio/holdings/{holding_id}`
  - Description: Removes a holding from the portfolio
  - Path Parameters:
    - `holding_id`: ID of the holding to delete
  - Response: Success message

- **DELETE** `/portfolio/holdings`
  - Description: Clears all holdings from the portfolio
  - Response: Success message

- **POST** `/portfolio/import-csv`
  - Description: Imports holdings from a CSV file
  - Request Body: CSV data
  - Response: Import results

### Analysis Endpoints (`analysis.py`)

- **GET** `/analysis/{symbol}`
  - Description: Gets the AI-generated analysis for a stock
  - Path Parameters:
    - `symbol`: Stock ticker symbol
  - Response: Analysis content and metadata

- **GET** `/analysis/{symbol}/history`
  - Description: Retrieves historical analyses for a stock
  - Path Parameters:
    - `symbol`: Stock ticker symbol
  - Response: List of historical analysis entries

- **POST** `/analysis/{symbol}/refresh`
  - Description: Triggers a new analysis generation for a stock
  - Path Parameters:
    - `symbol`: Stock ticker symbol
  - Response: New analysis data

### Database Management Endpoints (`database_management.py`)

- **POST** `/admin/backup-database`
  - Description: Creates a backup of the database
  - Response: Backup status and location

- **POST** `/admin/restore`
  - Description: Restores the database from a backup
  - Request Body: Backup file details
  - Response: Restore operation status

- **GET** `/admin/database-stats`
  - Description: Gets statistics about the database
  - Response: Collection counts and sizes

### AI Insights Endpoints (`ai_insights.py`)

- **GET** `/ai/insights/{symbol}`
  - Description: Retrieves AI-generated insights for a stock
  - Path Parameters:
    - `symbol`: Stock ticker symbol
  - Response: AI insights and sentiment analysis

### Scraper Integration

The scraper functionality is integrated through:

- **POST** `/scraper/scrape`
  - Description: Triggers the scraping process for financial data
  - Request Body: Scraping parameters and options
  - Response: Scraping results or job status

- **POST** `/scraper/remove-quarter`
  - Description: Removes all scraped data for a specific quarter (standard way to remove quarterly data)
  - Request Body: Quarter to remove (e.g., {"quarter": "Q1 2023"})
  - Response: Deletion status and count of affected documents

### Frontend-Backend Integration

This section documents the relationship between the frontend and backend, highlighting which endpoints are actively used by the frontend application.

#### Actively Used Endpoints

The following endpoints are actively called by the frontend application:

1. **Market Data Endpoints**:
   - `GET /api/v1/market-data` - Used by `fetchMarketData()` to display stock dashboard
   - `GET /api/v1/quarters` - Used by `getQuarters()` to populate quarter selection dropdown

2. **Stock Endpoints**:
   - `GET /api/v1/stock/{symbol}` - Used by `getStockDetails()` for individual stock pages
   - `POST /api/v1/stock/batch` - Used by `getBatchStockDetails()` for efficient multi-stock data loading
   - `POST /api/v1/stock/{symbol}/refresh-analysis` - Used by `refreshStockAnalysis()` to update analysis

3. **Portfolio Endpoints**:
   - All portfolio endpoints are used by corresponding frontend functions for portfolio management
   - Primary usage in portfolio page for CRUD operations on holdings

4. **Analysis Endpoints**:
   - Used by `getAnalysisContent()`, `getStockAnalysisHistory()`, and `refreshAnalysis()`
   - Displayed in stock detail pages to show AI-generated analysis

#### Integration Patterns

The frontend-backend integration follows these patterns:

1. **API Client**:
   - All API calls are centralized in `stockanalysisgui/src/lib/api.ts`
   - Each endpoint has a corresponding TypeScript function
   - Proper error handling and type definitions are implemented

2. **Data Flow**:
   - Frontend components request data through API client functions
   - Backend processes requests and returns structured JSON responses
   - Frontend transforms and displays the data as needed

3. **Error Handling**:
   - Backend returns appropriate HTTP status codes and error messages
   - Frontend catches errors and displays user-friendly notifications
   - Network errors are handled gracefully with retry options

4. **Authentication**:
   - JWT-based authentication for protected endpoints
   - Token refresh mechanism for session persistence
   - Role-based access control for administrative functions

#### Less Used Endpoints

The following endpoints are implemented but used less frequently:

1. **AI Insights Endpoints**:
   - `GET /api/v1/ai/insights/{symbol}` - May be integrated in future feature updates

2. **Database Management Endpoints**:
   - Used primarily for administrative operations like backups and database validation
   - Not directly exposed in the regular user interface
   - Quarter data removal is handled through the scraper interface using `/scraper/remove-quarter`

### API Organization and Structure

The API endpoints have been consolidated for better maintainability and visibility. The organization follows these principles:

#### Centralized Registry

All API endpoints are now registered in a single location:

- `src/api/registry.py` serves as the central registry for all endpoints
- This file provides a complete overview of the API structure
- Each endpoint is documented with its method, path, parameters, and description

#### Modular Implementation

While the registry provides a centralized view, the implementation remains modular:

- Each module (portfolio, stock, market-data, etc.) has its own router file
- Endpoint logic is kept separate in their respective modules
- The registry imports and configures all routers in one place

#### API Prefix Management

To avoid routing issues, prefix management follows these guidelines:

- API prefix (`/api/v1`) is added only once in `main.py` through `settings.API_PREFIX`
- Individual feature routers (like `scraper_router`) should have an empty prefix (`prefix=""`) in their router definition
- The actual prefix for each router is defined in the API registry (`src/api/registry.py`) in the `ROUTER_CONFIG` list
- The registry router in `src/api/registry.py` should not include a prefix

This configuration ensures that endpoints are accessible at the correct URL path. For example:
- The scraper router is registered with prefix `/scraper` in the registry
- The router itself has an empty prefix
- This makes endpoints accessible at `/api/v1/scraper/...`

If an endpoint returns a 404 error:
- Check that the router prefix is correctly configured
- Ensure that the router is properly registered in the API registry
- Verify that the frontend API client is using the correct URL structure
- Use the `test_endpoints.py` script to verify endpoint accessibility

#### Documentation Endpoint

A dedicated documentation endpoint is available:

- `GET /api/documentation` provides a structured list of all available endpoints
- This endpoint serves as a runtime reference for developers
- It includes endpoint counts and categorization for better navigation

#### Frontend API Client

The frontend also follows a consolidated approach for API calls:

- `stockanalysisgui/src/lib/api.ts` serves as the single central client for all API calls
- All backend endpoints are accessible through typed TypeScript functions
- Consistent error handling and response parsing across all API calls
- NextJS API routes use these centralized functions instead of direct fetch calls

#### End-to-End API Traceability

With both backend and frontend API handling consolidated, you can easily trace any API flow:

1. Frontend component calls a function from `api.ts`
2. The function in `api.ts` makes a request to the backend endpoint
3. The backend endpoint is defined in the appropriate router file
4. All endpoints are registered in the central registry

This provides complete visibility of the API flow from frontend to backend.

#### Benefits of This Approach

1. **Single Source of Truth**: One file in backend and one in frontend show all available endpoints
2. **Easier Maintenance**: Adding or modifying endpoints is more straightforward
3. **Better Discoverability**: New developers can quickly understand the API structure
4. **Consistency**: Enforces consistent naming and organization patterns
5. **Reduced Redundancy**: Prevents duplicate endpoint implementations
6. **Type Safety**: Frontend functions are properly typed with TypeScript interfaces

When adding new endpoints:
1. Implement the endpoint in the appropriate backend module file
2. Update the registry's `API_DOCUMENTATION` to include the new endpoint
3. Add a corresponding function to the frontend `api.ts` file
4. Update any Next.js API routes to use the centralized function

### Project Maintenance and Cleanup

## API Testing with Curl

For quick validation and debugging of API endpoints, curl commands can be used directly from the terminal. This approach is particularly useful for:
- Verifying endpoint accessibility
- Testing specific API responses
- Debugging routing issues
- Ad-hoc testing during development

### Common Curl Commands for API Testing

#### 1. Test API Documentation Endpoint
```bash
curl -X GET http://localhost:8000/api/documentation | json_pp
```

#### 2. Test Quarters Endpoint (with cache refresh)
```bash
curl -X GET "http://localhost:8000/api/v1/quarters?force_refresh=true" | json_pp
```

#### 3. Test Market Data Endpoint (for specific quarter)
```bash
curl -X GET "http://localhost:8000/api/v1/market-data?quarter=Q2%20FY24-25" | json_pp
```

#### 4. Test Scraper Endpoint
```bash
curl -X POST http://localhost:8000/api/v1/scraper/scrape \
  -H "Content-Type: application/json" \
  -d '{"result_type": "LR", "url": null, "refresh_connection": false}' | json_pp
```

#### 5. Test Remove-Quarter Endpoint
```bash
curl -X POST http://localhost:8000/api/v1/scraper/remove-quarter \
  -H "Content-Type: application/json" \
  -d '{"quarter": "Q1 FY24-25"}' | json_pp
```

#### 6. Test Stock Details Endpoint
```bash
curl -X GET http://localhost:8000/api/v1/stock/HDFCBANK | json_pp
```

#### 7. Test Portfolio Holdings Endpoint
```bash
curl -X GET http://localhost:8000/api/v1/portfolio/holdings | json_pp
```

### Best Practices for Curl Testing

1. **Use `json_pp` or `jq`** for formatting JSON responses:
   ```bash
   curl -X GET http://localhost:8000/api/v1/quarters | json_pp
   # or with jq if installed
   curl -X GET http://localhost:8000/api/v1/quarters | jq
   ```

2. **Test Specific Fields** using grep:
   ```bash
   curl -X GET http://localhost:8000/api/v1/market-data | grep -c "all_stocks"
   ```

3. **Check Response Status Codes**:
   ```bash
   curl -I http://localhost:8000/api/v1/quarters
   ```

4. **Save Response to File** for larger outputs:
   ```bash
   curl -X GET http://localhost:8000/api/v1/market-data > market-data.json
   ```

5. **URL Encode Special Characters** in parameters:
   ```bash
   # Q1 FY24-25 becomes Q1%20FY24-25
   curl -X GET "http://localhost:8000/api/v1/market-data?quarter=Q1%20FY24-25"
   ```

This approach complements the `test_endpoints.py` script by providing a more flexible way to test specific aspects of endpoints during development or debugging.

