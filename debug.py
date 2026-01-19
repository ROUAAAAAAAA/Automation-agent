# debug_imports.py

import sys
from pathlib import Path

current_dir = Path(__file__).parent
sys.path.insert(0, str(current_dir))
sys.path.insert(0, str(current_dir.parent))

# Try to trace imports
print("Testing imports...")

try:
    print("1. Trying to import main_workflow...")
    from main_workflow import run_workflow_from_json
    print("✓ Successfully imported main_workflow")
except Exception as e:
    print(f"✗ Failed to import main_workflow: {e}")
    import traceback
    traceback.print_exc()

print("\n2. Checking what main_workflow imports...")
try:
    import main_workflow
    print(f"main_workflow file: {main_workflow.__file__}")
    print(f"main_workflow imports: {main_workflow.__dict__.keys()}")
except Exception as e:
    print(f"Error: {e}")

print("\n3. Checking ai_agent.agent imports...")
try:
    import ai_agent.agent
    print(f"ai_agent.agent file: {ai_agent.agent.__file__}")
except Exception as e:
    print(f"Error: {e}")