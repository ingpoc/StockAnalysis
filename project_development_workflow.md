# MCPServer Project Development Workflow

## Project Tracker Commands

### State Check Command
```bash
python tools/project_tracker.py --check
```
- Validates current project state
- Displays implementation progress

### Update State Command
```bash
python tools/project_tracker.py --update
```
- Analyzes project endpoints
- Updates project state file
- Creates timestamped backup

### Backup Cleanup Command
```bash
python tools/project_tracker.py --cleanup 7
```
- Removes backup files older than 7 days

## Optimization Guidelines

### API Configuration
1. Check .env for existing API configuration
2. Verify necessity of proxy middleware
3. Remove redundant configuration layers
4. Document API versioning approach

### Configuration Management
1. Review package.json for unused dependencies
2. Compare actual API usage with configuration
3. Remove unnecessary configuration files
4. Run state update after changes
5. Document simplified configurations

### Directory Structure
1. Validate frontend and service directories
2. Check API endpoint patterns for consistency
3. Document accepted patterns
4. Maintain standard project structure

### Change Process
1. Backup state before configuration changes
2. Document changes in relevant files
3. Run state update after modifications
4. Verify service functionality
5. Update documentation with new patterns
