import os
import json
import ast
import glob
import re
import shutil
from datetime import datetime
from typing import Dict, List, Any, Tuple

class ProjectTracker:
    def __init__(self, backend_dir: str, frontend_dir: str):
        self.backend_dir = backend_dir
        self.frontend_dir = frontend_dir
        self.state_file = os.path.join(backend_dir, "tools", "project_state.json")
        self.backup_dir = os.path.join(backend_dir, "tools", "backups")
        os.makedirs(self.backup_dir, exist_ok=True)
        self.state = self.load_state()

    def load_state(self) -> Dict:
        try:
            if os.path.exists(self.state_file):
                with open(self.state_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            print(f"Error loading state: {e}")
        return self._create_default_state()

    def _create_default_state(self) -> Dict:
        return {
            "version": "1.0.0",
            "last_updated": datetime.now().isoformat(),
            "backend": {
                "completed_features": [],
                "in_progress": [],
                "implemented_apis": {},
                "db_schemas": {}
            },
            "frontend": {
                "completed_components": [],
                "in_progress": [],
                "implemented_features": {},
                "state_management": {},
                "ui_components": {}
            }
        }

    def save_state(self):
        try:
            self.state["last_updated"] = datetime.now().isoformat()
            backup_path = self.create_backup(self.state_file)
            with open(self.state_file, 'w', encoding='utf-8') as f:
                json.dump(self.state, f, indent=2)
            print(f"State saved. Backup created at: {backup_path}")
        except Exception as e:
            print(f"Error saving state: {e}")

    def check_state(self):
        print("\nProject State Summary:")
        print("-" * 50)
        print(f"Last updated: {self.state.get('last_updated', 'Unknown')}")
        
        backend = self.state.get('backend', {})
        frontend = self.state.get('frontend', {})
        
        print("\nBackend Status:")
        print(f"APIs: {len(backend.get('implemented_apis', {}))}")
        print(f"DB Schemas: {len(backend.get('db_schemas', {}))}")
        print(f"Completed Features: {len(backend.get('completed_features', []))}")
        
        print("\nFrontend Status:")
        print(f"Total Components: {len(frontend.get('ui_components', {}))}")
        print(f"Completed: {len(frontend.get('completed_components', []))}")
        print(f"In Progress: {len(frontend.get('in_progress', []))}")
        
        features = frontend.get('implemented_features', {})
        if features:
            print("\nFeature Implementation Status:")
            for name, status in features.items():
                print(f"- {name}: {status.get('status', 'unknown')}")
                missing = status.get('missing', [])
                if missing:
                    print(f"  Pending: {', '.join(missing)}")

    def analyze_backend_endpoints(self):
        try:
            api_dir = os.path.join(self.backend_dir, "src", "api")
            if not os.path.exists(api_dir):
                print(f"API directory not found: {api_dir}")
                return

            api_files = glob.glob(os.path.join(api_dir, "**/*.py"), recursive=True)
            for file_path in api_files:
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        tree = ast.parse(f.read())
                        for node in ast.walk(tree):
                            if isinstance(node, ast.FunctionDef):
                                route_info = self._extract_route_info(node)
                                if route_info:
                                    self.state["backend"]["implemented_apis"][node.name] = route_info
                except Exception as e:
                    print(f"Error processing {file_path}: {e}")
            print("Backend analysis completed")
        except Exception as e:
            print(f"Error analyzing endpoints: {e}")

    def analyze_frontend_components(self):
        try:
            for ext in ['jsx', 'tsx']:
                pattern = os.path.join(self.frontend_dir, "src", "**", f"*.{ext}")
                for comp_path in glob.glob(pattern, recursive=True):
                    name = os.path.basename(comp_path).split('.')[0]
                    with open(comp_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                    self.state["frontend"]["ui_components"][name] = {
                        "path": os.path.relpath(comp_path, self.frontend_dir),
                        "type": "component",
                        "dependencies": self._extract_imports(content)
                    }
            print("Frontend analysis completed")
        except Exception as e:
            print(f"Error analyzing components: {e}")

    def _extract_route_info(self, node: ast.AST) -> Dict:
        route_info = {
            "path": f"/api/{node.name.replace('_', '-')}",
            "method": "GET",
            "params": []
        }
        
        for decorator in node.decorator_list:
            if isinstance(decorator, ast.Call):
                if isinstance(decorator.func, ast.Attribute):
                    route_info["method"] = decorator.func.attr.upper()
        
        for arg in node.args.args:
            if arg.arg != 'self':
                route_info["params"].append(arg.arg)
        
        return route_info

    def _extract_imports(self, content: str) -> List[str]:
        try:
            import_pattern = re.compile(r'import\s+.*?\s+from\s+[\'"]([^\'"]+)[\'"]')
            return list(set(import_pattern.findall(content)))
        except Exception as e:
            print(f"Error extracting imports: {e}")
            return []

    def create_backup(self, file_path: str) -> str:
        try:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_name = f"{os.path.basename(file_path)}.{timestamp}"
            backup_path = os.path.join(self.backup_dir, backup_name)
            shutil.copy2(file_path, backup_path)
            return backup_path
        except Exception as e:
            print(f"Error creating backup: {e}")
            return ""

    def cleanup_old_backups(self, days: int = 7):
        try:
            cutoff = datetime.now().timestamp() - (days * 86400)
            for backup in os.listdir(self.backup_dir):
                backup_path = os.path.join(self.backup_dir, backup)
                if os.path.getctime(backup_path) < cutoff:
                    os.remove(backup_path)
            print(f"Cleaned up backups older than {days} days")
        except Exception as e:
            print(f"Error cleaning backups: {e}")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description='Project Tracker')
    parser.add_argument('--check', action='store_true', help='Check current state')
    parser.add_argument('--update', action='store_true', help='Update project state')
    parser.add_argument('--cleanup', type=int, help='Clean up backups older than N days')
    args = parser.parse_args()
    
    tracker = ProjectTracker(
        backend_dir="H:\\projects\\StockAnalysis",
        frontend_dir="H:\\projects\\StockAnalysisUI"
    )
    
    if args.check:
        tracker.check_state()
    if args.update:
        tracker.analyze_backend_endpoints()
        tracker.analyze_frontend_components()
        tracker.save_state()
        print("\nFinal state after update:")
        tracker.check_state()
    if args.cleanup:
        tracker.cleanup_old_backups(args.cleanup)