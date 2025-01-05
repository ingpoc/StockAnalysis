# Stock Analysis Backend

FastAPI-based backend service for stock market analysis with MongoDB integration.

## Tech Stack
- FastAPI framework
- MongoDB with Motor
- Python 3.9+
- Async operations
- TTL caching

## Getting Started

### Prerequisites
- Python 3.9 or higher
- MongoDB 4.4+
- Virtual environment tool (venv/poetry)

### Installation
```bash
# Create and activate virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Start development server
uvicorn src.main:app --reload
```

### Environment Variables
Create a `.env` file in the root directory:
```
MONGODB_URI=mongodb://localhost:27017
DATABASE_NAME=stock_analysis
API_KEY=your_market_data_api_key
CACHE_TTL=3600
LOG_LEVEL=INFO
```

## Project Structure
```
src/
├── api/           # API routes and endpoints
├── models/        # Data models and schemas
├── services/      # Business logic and services
├── utils/         # Utility functions
├── config/        # Configuration management
└── tests/         # Test suite
```

## Development Guidelines
- Follow PEP 8 style guide
- Use Python type hints
- Maximum line length: 100 characters
- Implement proper error handling
- Document API endpoints with OpenAPI

## API Documentation
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

## Contributing
1. Create feature branch (`feature/your-feature-name`)
2. Commit changes using Conventional Commits
3. Write/update tests as needed
4. Submit pull request for review

## Testing
- pytest for unit and integration tests
- Run `pytest` to execute test suite
- Maintain minimum 80% test coverage

## Monitoring
- Logging to `app.log`
- Metrics collection via FastAPI middleware
- Error tracking and reporting
