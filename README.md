# Stock Analysis

A Python application for analyzing stock data from MoneyControl and other sources.

## Features

- Scrape financial data from MoneyControl
- Store data in MongoDB
- Analyze stock performance
- Generate investment recommendations
- API endpoints for frontend integration

## Installation

1. Clone the repository
2. Create a virtual environment:
   ```
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```
3. Install dependencies:
   ```
   pip install -r requirements.txt
   ```
4. Set up environment variables in `.env` file (see `.env.example`)

## Project Structure

```
StockAnalysis/
├── src/                # Source code
│   ├── api/            # API endpoints
│   ├── models/         # Data models
│   ├── routers/        # API routers
│   ├── schemas/        # Pydantic schemas
│   ├── scraper/        # Web scrapers
│   ├── services/       # Business logic
│   └── utils/          # Utility functions
├── tests/              # Test files
├── tools/              # Utility tools
│   └── scripts/        # Utility scripts
├── logs/               # Log files
├── data/               # Data files
├── db_backups/         # Database backups
├── docs/               # Documentation
└── .env                # Environment variables
```

## Usage

Run the application:

```
python run.py
```

## API Endpoints

The API is available at `http://localhost:8000/api/v1/` with the following endpoints:

- `/portfolio/holdings` - Manage portfolio holdings
- `/market/data` - Get market data
- `/market/quarters` - Get available quarters
- `/stock/details/{symbol}` - Get stock details
- `/analysis/history/{symbol}` - Get analysis history
- `/analysis/content/{id}` - Get analysis content
- `/analysis/refresh/{symbol}` - Refresh analysis
- `/scraper/moneycontrol` - Scrape data from MoneyControl

## Testing

The project includes various test files in the `tests` directory:

- `test_api.py` - Tests for API endpoints
- `test_scraper.py` - Tests for the MoneyControl scraper
- `test_async_scraper.py` - Tests for asynchronous MongoDB operations
- `test_login.py` - Tests for MoneyControl login functionality
- `debug_selectors.py` - Debug utility for HTML selectors

To run tests:

```
python -m tests.test_api
python -m tests.test_scraper
```

## Utility Scripts

The project includes several utility scripts in the `tools/scripts` directory:

- `backup_db.py` - Backup MongoDB database
- `check_mongo.py` - Check MongoDB connection
- `clean_holdings.py` - Clean portfolio holdings
- `examine_db.py` - Examine database contents
- `import_holdings.py` - Import holdings from CSV
- `list_collections.py` - List MongoDB collections
- `remove_q3_data.py` - Remove Q3 data from database
- `fix_holdings.py` - Fix issues with portfolio holdings

To run a utility script:

```
python -m tools.scripts.backup_db
python -m tools.scripts.check_mongo
```

## License

This project is licensed under the MIT License - see the LICENSE file for details.
