# Stock Analysis Project Guidelines

## Project Overview
This is a Python-based Stock Analysis application that scrapes financial data from MoneyControl and other sources, stores it in MongoDB, analyzes stock performance, and provides API endpoints for frontend integration.

## Cursor Rules

### General Code Style and Structure
- Follow PEP 8 style guidelines for Python code
- Use type hints for function parameters and return values
- Organize imports alphabetically within their groups
- Maintain a clean separation of concerns between layers (API, services, models)
- Use async/await patterns consistently throughout the codebase
- Document all public functions, classes, and methods with docstrings
- Keep functions focused on a single responsibility
- Limit function length to maintain readability (max ~50 lines)
- Use meaningful variable and function names that describe their purpose

### API Development
- Follow RESTful API design principles
- Group related endpoints in the same router file
- Use Pydantic models for request/response validation
- Implement proper error handling with appropriate HTTP status codes
- Include pagination for endpoints that return collections
- Document all endpoints with clear descriptions and example responses
- Use dependency injection for services and repositories
- Implement proper authentication and authorization checks

### Database Operations
- Use MongoDB's asynchronous driver (motor) for all database operations
- Create indexes for frequently queried fields
- Implement proper error handling for database operations
- Use transactions for operations that modify multiple documents
- Implement data validation before storing in the database
- Use appropriate data types for MongoDB documents
- Implement proper connection pooling and resource management

### Scraping and Data Collection
- Implement rate limiting to avoid overloading target websites
- Use proper error handling and retry mechanisms for network requests
- Implement caching to reduce duplicate requests
- Use asynchronous requests to improve performance
- Validate and clean data before storing
- Implement proper logging for debugging and monitoring
- Handle authentication and session management properly

### Testing
- Write unit tests for all business logic
- Implement integration tests for API endpoints
- Use mocking for external dependencies
- Maintain high test coverage for critical components
- Implement proper test fixtures and setup/teardown
- Use parameterized tests for testing multiple scenarios
- Implement proper error handling in tests

### Error Handling and Logging
- Use structured logging with appropriate log levels
- Include contextual information in log messages
- Implement proper exception handling with specific exception types
- Log all exceptions with stack traces
- Use a centralized error handling mechanism
- Implement proper monitoring and alerting

### Security
- Implement proper authentication and authorization
- Use secure password hashing
- Implement rate limiting for authentication endpoints
- Validate and sanitize all user inputs
- Use HTTPS for all external communications
- Implement proper CORS configuration
- Keep dependencies updated to avoid security vulnerabilities

### Performance
- Use asynchronous programming for I/O-bound operations
- Implement caching for frequently accessed data
- Use connection pooling for database connections
- Optimize database queries with proper indexing
- Implement pagination for large data sets
- Use efficient data structures and algorithms
- Monitor and optimize resource usage

### Deployment and DevOps
- Use environment variables for configuration
- Implement proper logging and monitoring
- Use containerization for consistent environments
- Implement CI/CD pipelines for automated testing and deployment
- Use infrastructure as code for reproducible deployments
- Implement proper backup and recovery procedures
- Monitor application health and performance

### Documentation
- Maintain up-to-date API documentation
- Document database schema and relationships
- Include setup and installation instructions
- Document deployment procedures
- Include troubleshooting guides
- Document configuration options and environment variables
- Include examples for common use cases

### Feature Development Process
- Create a clear specification before implementation
- Break down large features into smaller, manageable tasks
- Implement features incrementally with proper testing
- Review code before merging
- Update documentation as part of feature development
- Consider backward compatibility when making changes
- Test thoroughly before deployment

These guidelines should be followed for all new code and should be used as a reference when refactoring existing code. They are designed to ensure code quality, maintainability, and performance while allowing for rapid development and evolution of the application. 