# StockAnalysis API Documentation

## Base URL
```
http://localhost:8000/api/v1
```

## Authentication
Currently, the API does not require authentication.

## Error Handling
All endpoints follow a consistent error handling pattern. Error responses have the following format:

```json
{
  "detail": "Error description"
}
```

Common HTTP status codes:
- `200 OK`: Request succeeded
- `201 Created`: Resource successfully created (for POST requests)
- `400 Bad Request`: Invalid request (e.g., invalid format of IDs)
- `404 Not Found`: Resource not found
- `422 Unprocessable Entity`: Validation error (missing required fields)
- `500 Internal Server Error`: Server-side error

## API Endpoints

### 1. Portfolio Management

#### 1.1 Get All Holdings
```
GET /portfolio/holdings
```

**Response (200 OK)**
```json
[
  {
    "_id": "67c29e323d92bd4cbfe46c45",
    "symbol": "AAPL",
    "company_name": "Apple Inc.",
    "quantity": 10,
    "average_price": 150.75,
    "purchase_date": "2023-01-15T00:00:00",
    "notes": "Long-term investment",
    "timestamp": "2024-02-15T12:30:45"
  },
  // ... more holdings
]
```

#### 1.2 Add New Holding
```
POST /portfolio/holdings
```

**Request Body**
```json
{
  "symbol": "MSFT",
  "company_name": "Microsoft Corporation",
  "quantity": 5,
  "average_price": 280.50,
  "purchase_date": "2023-03-10T00:00:00",
  "notes": "Tech sector diversification"
}
```

**Response (200 OK)** - *Note: Should be 201 Created per API standards*
```json
{
  "_id": "67c29e323d92bd4cbfe46c46",
  "symbol": "MSFT",
  "company_name": "Microsoft Corporation",
  "quantity": 5,
  "average_price": 280.50,
  "purchase_date": "2023-03-10T00:00:00",
  "notes": "Tech sector diversification",
  "timestamp": "2024-02-15T12:35:22"
}
```

#### 1.3 Update Holding
```
PUT /portfolio/holdings/{holding_id}
```

**Path Parameters**
- `holding_id`: The ID of the holding to update

**Request Body**
```json
{
  "symbol": "MSFT",
  "company_name": "Microsoft Corporation",
  "quantity": 8,
  "average_price": 275.25,
  "purchase_date": "2023-03-10T00:00:00",
  "notes": "Increased position"
}
```

**Response (200 OK)**
```json
{
  "_id": "67c29e323d92bd4cbfe46c46",
  "symbol": "MSFT",
  "company_name": "Microsoft Corporation",
  "quantity": 8,
  "average_price": 275.25,
  "purchase_date": "2023-03-10T00:00:00",
  "notes": "Increased position",
  "timestamp": "2024-02-15T12:35:22"
}
```

**Important Note**: All fields must be included in the update request, as this endpoint performs a complete replacement.

#### 1.4 Delete Holding
```
DELETE /portfolio/holdings/{holding_id}
```

**Path Parameters**
- `holding_id`: The ID of the holding to delete

**Response (200 OK)**
```json
{
  "message": "Holding deleted successfully"
}
```

#### 1.5 Clear All Holdings
```
DELETE /portfolio/holdings
```

**Response (200 OK)**
```json
{
  "message": "Deleted 10 holdings"
}
```

#### 1.6 Import Holdings from CSV
```
POST /portfolio/holdings/import
```

**Request**
- Content-Type: `multipart/form-data`
- Form field name: `file`
- File format: CSV with headers

**CSV Headers**
- `symbol` (required)
- `company_name` (required)
- `quantity` (required)
- `average_price` (required)
- `purchase_date` (optional, ISO format)
- `notes` (optional)

**Example CSV**
```
symbol,company_name,quantity,average_price,purchase_date,notes
AAPL,Apple Inc.,10,150.75,2023-01-15T00:00:00,Long-term investment
MSFT,Microsoft Corporation,5,280.50,2023-03-10T00:00:00,Tech sector diversification
GOOG,Alphabet Inc.,3,2100.25,2023-02-20T00:00:00,Growth potential
```

**Response (200 OK)**
```json
[
  {
    "_id": "67c29e323d92bd4cbfe46c50",
    "symbol": "AAPL",
    "company_name": "Apple Inc.",
    "quantity": 10,
    "average_price": 150.75,
    "purchase_date": "2023-01-15T00:00:00",
    "notes": "Long-term investment",
    "timestamp": "2024-02-15T12:40:15"
  },
  // ... more imported holdings
]
```

**Important Note**: This endpoint will clear all existing holdings before importing new ones.

### 2. Market Data

#### 2.1 Market Overview
```
GET /market-data
```

**Query Parameters**
- `quarter` (optional): Specific quarter to retrieve data for (e.g., "Q1 2023")
- `force_refresh` (optional): Boolean to force data refresh (default: false)

**Response (200 OK)**
```json
{
  "quarter": "Q1 2023",
  "top_performers": [
    {
      "symbol": "AAPL",
      "company_name": "Apple Inc.",
      "growth": "15.7%",
      "sector": "Technology"
    },
    // ... more stocks
  ],
  "worst_performers": [
    // ... list of worst performing stocks
  ],
  "latest_results": [
    // ... list of stocks with recent results
  ],
  "all_stocks": [
    // ... list of all stocks
  ],
  "last_updated": "2024-02-15T10:30:00"
}
```

#### 2.2 Stock Details
```
GET /stock/{symbol}
```

**Path Parameters**
- `symbol`: Stock symbol (e.g., "AAPL")

**Response (200 OK)**
```json
{
  "stock": {
    "company_name": "Apple Inc.",
    "symbol": "AAPL",
    "financial_metrics": [
      {
        "market_cap": "2.5T",
        "face_value": "0.01",
        "book_value": "4.25",
        "dividend_yield": "0.5%",
        "ttm_eps": "6.15",
        "ttm_pe": "28.5",
        // ... more metrics
      }
    ],
    "timestamp": "2024-02-15T10:30:00"
  },
  "formatted_metrics": {
    // Processed metrics for display
  }
}
```

#### 2.3 Available Quarters
```
GET /quarters
```

**Response (200 OK)**
```json
{
  "quarters": [
    "Q1 2023",
    "Q4 2022",
    "Q3 2022",
    // ... more quarters
  ]
}
```

### 3. AI Insights

#### 3.1 Stock Insights
```
GET /ai_insights/stock/{symbol}
```

**Path Parameters**
- `symbol`: Stock symbol (e.g., "AAPL")

**Query Parameters**
- `timeframe` (optional): Time period for analysis (default: "1d")

**Response (200 OK)**
```json
{
  "symbol": "AAPL",
  "sentiment": {
    "score": 0.75,
    "label": "Bullish"
  },
  "analysis": {
    "summary": "Apple shows strong fundamentals with growing service revenue...",
    "key_factors": [
      "Strong cash position",
      "Service revenue growth",
      // ... more factors
    ]
  },
  "recommendation": "Buy"
}
```

#### 3.2 Market Sentiment
```
GET /ai_insights/market/sentiment
```

**Response (200 OK)**
```json
{
  "overall_sentiment": {
    "score": 0.6,
    "label": "Moderately Bullish"
  },
  "sector_sentiment": {
    "Technology": {
      "score": 0.8,
      "label": "Bullish"
    },
    // ... more sectors
  },
  "market_summary": "Markets are trending upward with technology leading the gains..."
}
```

#### 3.3 Analysis History
```
GET /stock/{symbol}/analysis-history
```

**Path Parameters**
- `symbol`: Stock symbol (e.g., "SHAKTIPUMP", "JUBLPHARMA")

**Response (200 OK)**
```json
{
  "analyses": [
    {
      "id": "67c29e323d92bd4cbfe46c60",
      "timestamp": "2024-02-15T10:30:00",
      "label": "Today 10:30"
    },
    {
      "id": "67c29e323d92bd4cbfe46c61",
      "timestamp": "2024-02-14T15:45:00",
      "label": "Yesterday 15:45"
    },
    // ... more analyses
  ]
}
```

#### 3.4 Analysis Content
```
GET /analysis/{analysis_id}
```

**Path Parameters**
- `analysis_id`: ID of the analysis to retrieve

**Response (200 OK)**
```json
{
  "_id": "67c29e323d92bd4cbfe46c60",
  "company_name": "Apple Inc.",
  "symbol": "AAPL",
  "analysis": {
    "sentiment_summary": "Apple continues to show strength in its core business...",
    "key_factors": [
      "iPhone sales exceeding expectations",
      "Services growth acceleration",
      // ... more factors
    ],
    "news_impact": [
      "Positive response to new product announcements",
      // ... more news items
    ],
    "risks_opportunities": {
      "risks": [
        "Supply chain constraints in Asia",
        // ... more risks
      ],
      "opportunities": [
        "Expansion into AR/VR market",
        // ... more opportunities
      ]
    },
    "forward_outlook": "Continued growth expected in the coming quarters..."
  },
  "sentiment": {
    "score": 0.75,
    "label": "Bullish"
  },
  "recommendation": "Buy",
  "timestamp": "2024-02-15T10:30:00"
}
```

#### 3.5 Refresh Analysis
```
POST /stock/{symbol}/refresh-analysis
```

**Path Parameters**
- `symbol`: Stock symbol (e.g., "SHAKTIPUMP", "JUBLPHARMA")

**Response (200 OK)**
```json
{
  "id": "67c29e323d92bd4cbfe46c65",
  "content": {
    // Analysis content (same structure as GET /analysis/{analysis_id})
  },
  "timestamp": "2024-02-15T12:45:30",
  "recommendation": "Buy"
}
```

## Data Models

### Holding
```json
{
  "_id": "string",
  "symbol": "string",
  "company_name": "string",
  "quantity": "integer",
  "average_price": "number",
  "purchase_date": "string (ISO date)",
  "notes": "string (optional)",
  "timestamp": "string (ISO date)"
}
```

### FinancialMetric
```json
{
  "market_cap": "string",
  "face_value": "string",
  "book_value": "string",
  "dividend_yield": "string",
  "ttm_eps": "string",
  "ttm_pe": "string",
  "pb_ratio": "string",
  // ... more metrics (refer to schemas.py for full list)
}
```

### AIAnalysis
```json
{
  "_id": "string",
  "company_name": "string",
  "symbol": "string",
  "analysis": {
    "sentiment_summary": "string",
    "key_factors": ["string"],
    "news_impact": ["string"],
    "risks_opportunities": {
      "risks": ["string"],
      "opportunities": ["string"]
    },
    "forward_outlook": "string"
  },
  "sentiment": {
    "score": "number",
    "label": "string"
  },
  "recommendation": "string",
  "timestamp": "string (ISO date)"
}
```

## Integration Examples

### Fetching Portfolio Holdings (JavaScript)
```javascript
async function getHoldings() {
  try {
    const response = await fetch('http://localhost:8000/api/v1/portfolio/holdings');
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }
    const holdings = await response.json();
    return holdings;
  } catch (error) {
    console.error('Error fetching holdings:', error);
    return [];
  }
}
```

### Adding a New Holding (JavaScript)
```javascript
async function addHolding(holding) {
  try {
    const response = await fetch('http://localhost:8000/api/v1/portfolio/holdings', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(holding),
    });
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }
    return await response.json();
  } catch (error) {
    console.error('Error adding holding:', error);
    throw error;
  }
}
```

### Importing Holdings from CSV (JavaScript)
```javascript
async function importHoldings(file) {
  try {
    const formData = new FormData();
    formData.append('file', file);
    
    const response = await fetch('http://localhost:8000/api/v1/portfolio/holdings/import', {
      method: 'POST',
      body: formData,
    });
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }
    return await response.json();
  } catch (error) {
    console.error('Error importing holdings:', error);
    throw error;
  }
}
```

### Getting AI Analysis for a Stock (JavaScript)
```javascript
async function getStockAnalysis(symbol) {
  try {
    const response = await fetch(`http://localhost:8000/api/v1/stock/${symbol}/refresh-analysis`, {
      method: 'POST',
    });
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }
    return await response.json();
  } catch (error) {
    console.error(`Error getting analysis for ${symbol}:`, error);
    throw error;
  }
}
```

## Notes for Frontend Developers

1. **CORS Support**: The API has CORS enabled with support for `http://localhost:3000` and `https://localhost:3000`. If your frontend is hosted elsewhere, the backend CORS settings will need to be updated.

2. **Status Codes**: Note that the POST endpoints currently return a 200 OK status instead of the standard 201 Created. Your frontend should handle both status codes for compatibility.

3. **Date Handling**: All dates are returned in ISO format (e.g., "2024-02-15T10:30:00"). You may need to format these for display.

4. **Validation Errors**: Pay special attention to the 422 Unprocessable Entity errors, which indicate validation failures. Proper error handling and user messaging should be implemented.

5. **PUT vs. PATCH**: The current API uses PUT for updates which requires all fields to be present. Your forms should ensure all required fields are included in update requests.

6. **API Route Structure**: Note that the analysis endpoints have a special routing structure:
   - Analysis history is accessed via `/stock/{symbol}/analysis-history`
   - Analysis content is accessed via `/analysis/{analysis_id}`
   - Refresh analysis is requested via `/stock/{symbol}/refresh-analysis`

7. **Symbol Validation**: Always use symbols that exist in the database. The system currently contains data for symbols like "SHAKTIPUMP" and "JUBLPHARMA". When testing with non-existent symbols, you may receive 404 or 500 errors.

8. **Server Restart**: If you encounter connection issues or "Address already in use" errors when starting the server, use the following command to kill existing processes and restart:
   ```
   pkill -f "python run.py" && python run.py
   ```
