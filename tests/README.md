# Stock Analysis Test Suite

This directory contains test scripts for the Stock Analysis project. These scripts test various components of the system, including the scraper, database operations, and API endpoints.

## Prerequisites

Before running the tests, make sure you have:

1. Set up the required environment variables in a `.env` file:
   - `MONGODB_URI`: MongoDB connection string
   - `MONEYCONTROL_USERNAME`: Username for MoneyControl
   - `MONEYCONTROL_PASSWORD`: Password for MoneyControl
   - `API_BASE_URL`: Base URL for the API (default: http://localhost:8000/api)

2. Installed the required dependencies:
   ```
   pip install -r requirements.txt
   ```

3. Started the API server (for API tests):
   ```
   python -m src.main
   ```

## Available Tests

### Scraper Flow Test

The `test_scraper_flow.py` script tests the complete flow of the scraping functionality:
1. Login to MoneyControl
2. Scrape earnings data
3. Save data to the database
4. Validate the saved data
5. Test API endpoints that return the data

To run the scraper flow test:
```
python -m tests.test_scraper_flow
```

### Individual Tests

You can also run individual tests:

- **Login Test**: Tests the login functionality for MoneyControl
  ```
  python -m tests.test_login
  ```

- **Async Scraper Test**: Tests the scraper functionality without saving to the database
  ```
  python -m tests.test_async_scraper
  ```

- **API Test**: Tests the API endpoints
  ```
  python -m tests.test_api
  ```

- **Database Validation**: Validates the data in the database
  ```
  python -m tests.validate_database
  ```

### Test Runner

The `run_scraper_tests.py` script provides a convenient way to run multiple tests:

```
python -m tests.run_scraper_tests [--test TEST_NAME] [--all]
```

Options:
- `--test TEST_NAME`: Run a specific test (login, scrape, api, flow)
- `--all`: Run all tests in sequence

Examples:
```
# Run the login test
python -m tests.run_scraper_tests --test login

# Run the complete flow test
python -m tests.run_scraper_tests --test flow

# Run all tests
python -m tests.run_scraper_tests --all
```

## Utility Scripts

The tests directory also includes utility scripts:

- **clear_chromedriver_cache.py**: Clears the ChromeDriver cache
  ```
  python -m tests.clear_chromedriver_cache
  ```

- **backup_database.py**: Backs up the database to a JSON file
  ```
  python -m tests.backup_database
  ```

- **restore_database.py**: Restores the database from a backup
  ```
  python -m tests.restore_database [--file BACKUP_FILE]
  ```

- **reset_database.py**: Resets the database to a clean state
  ```
  python -m tests.reset_database
  ```

## Troubleshooting

If you encounter issues with the tests:

1. Check the log files in the tests directory
2. Verify that the API server is running (for API tests)
3. Check that your MongoDB instance is accessible
4. Verify that your MoneyControl credentials are correct
5. Try clearing the ChromeDriver cache with `python -m tests.clear_chromedriver_cache` 