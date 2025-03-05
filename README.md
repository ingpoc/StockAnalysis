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
- `clear_chromedriver_cache.py` - Clear the ChromeDriver cache to fix browser compatibility issues
- `examine_db.py` - Examine database contents
- `import_holdings.py` - Import holdings from CSV
- `list_collections.py` - List MongoDB collections
- `remove_q3_data.py` - Remove Q3 data from database
- `fix_holdings.py` - Fix issues with portfolio holdings

To run a utility script:

```
python -m tools.scripts.backup_db
python -m tools.scripts.check_mongo
python -m tools.scripts.clear_chromedriver_cache
```

## Browser Configuration

By default, the scraper uses Google Chrome for web scraping. You can now also use Brave browser by setting the `BROWSER` environment variable:

```bash
# To use Brave browser
export BROWSER=brave

# To use Chrome browser (default)
export BROWSER=chrome
```

You can also set this in your `.env` file:

```
BROWSER=brave
```

The scraper will automatically detect the location of the Brave browser on your system. If Brave is not found, it will fall back to Chrome.

### Browser Version Compatibility

The scraper now automatically detects the version of your Brave browser and downloads a compatible ChromeDriver. This ensures that you won't encounter version mismatch errors between your browser and ChromeDriver.

For Python 3.12 users, the scraper includes an enhanced compatibility feature that:
1. Detects your exact Brave browser version (e.g., 132.0.6834.111)
2. Attempts to download the exact matching ChromeDriver version directly from Google's servers
3. Falls back to the webdriver-manager approach if the direct download fails

This ensures maximum compatibility between your browser and ChromeDriver, preventing version mismatch errors.

If you encounter any issues with browser compatibility, you can try:

1. Updating your Brave browser to the latest version
2. Clearing the ChromeDriver cache using the provided utility script:
   ```
   python -m tools.scripts.clear_chromedriver_cache
   ```
3. Setting the `WDM_LOG_LEVEL=0` environment variable for more detailed logs from WebDriver Manager

#### Python 3.12 Compatibility

The scraper is fully compatible with Python 3.12. The code has been updated to work with the latest version of webdriver-manager (4.0.1+), which has different API requirements compared to earlier versions.

The scraper now automatically detects the installed webdriver-manager version and uses the appropriate API:
- For webdriver-manager 4.x (used with Python 3.12), it uses the environment variable approach
- For older versions, it attempts to use the version parameter with a fallback mechanism

When using Brave browser with Python 3.12:
- The scraper will detect the Brave browser version
- Due to compatibility issues between webdriver-manager 4.x and Brave, the scraper will automatically fall back to using the Chrome driver (which is compatible with Brave)
- This ensures that the scraper works correctly with Brave browser on Python 3.12

If you're upgrading from an older Python version, make sure to:

1. Run `pip install -r requirements.txt` to ensure you have the correct package versions
2. Clear the ChromeDriver cache using the provided utility script:
   ```
   python -m tools.scripts.clear_chromedriver_cache
   ```

## License

This project is licensed under the MIT License - see the LICENSE file for details.
