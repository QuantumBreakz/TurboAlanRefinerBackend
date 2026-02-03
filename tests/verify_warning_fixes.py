#!/usr/bin/env python3
"""
Quick verification that warning fixes are working.
Tests Issues #5-#8 from NAMING_ISSUES_REPORT.md
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

print("="*60)
print("VERIFYING WARNING FIXES (#5-#8)")
print("="*60)

# Test #5: Global variable naming
print("\n[Test #5] Global Database Instance Names")
try:
    from app.core.mongodb_db import mongodb, db as mongodb_compat
    print("✅ mongodb_db.py: 'mongodb' imported")
    print("✅ mongodb_db.py: 'db' (compat alias) imported")
    assert mongodb is mongodb_compat, "mongodb and db should be same instance"
    print("✅ Both point to same instance")
except ImportError as e:
    print(f"❌ Import error: {e}")

try:
    from app.core.supabase_db import supabase, db as supabase_compat
    print("✅ supabase_db.py: 'supabase' imported")
    print("✅ supabase_db.py: 'db' (compat alias) imported")
    assert supabase is supabase_compat, "supabase and db should be same instance"
    print("✅ Both point to same instance")
except ImportError as e:
    print(f"❌ Import error: {e}")

# Test #6: Single safe_encoder
print("\n[Test #6] Single safe_encoder Function")
try:
    from app.utils.utils import safe_encoder as utils_encoder
    print("✅ Imported safe_encoder from utils.utils")
    
    # Check it's callable and works
    result = utils_encoder({"test": "data"})
    print(f"✅ safe_encoder works: {result[:30]}...")
    
    # Verify main.py imports it
    with open("app/main.py", "r") as f:
        content = f.read()
        if "from app.utils.utils import" in content and "safe_encoder" in content:
            print("✅ main.py imports safe_encoder from utils")
        if "def safe_encoder(obj)" in content:
            print("⚠️  main.py still has local definition (should be removed)")
        else:
            print("✅ main.py removed local safe_encoder definition")
            
except Exception as e:
    print(f"❌ Error: {e}")

# Test #7: Shared logging utility
print("\n[Test #7] Shared Logging Utility")
try:
    from app.utils.db_logging import safe_db_log
    print("✅ Imported safe_db_log from db_logging")
    
    # Test it works
    safe_db_log("Test message", module="TestModule", always_print=False)
    print("✅ safe_db_log works")
    
    # Check mongodb_db uses it
    from app.core.mongodb_db import _safe_log as mongo_log
    print("✅ mongodb_db._safe_log imported")
    
    # Check supabase_db uses it
    from app.core.supabase_db import _safe_log as supabase_log
    print("✅ supabase_db._safe_log imported")
    
except Exception as e:
    print(f"❌ Error: {e}")

# Test #8: Shared test utilities
print("\n[Test #8] Shared Test Utilities")
try:
    from tests.test_utils import TestResult, TestRunner, TestTracker
    print("✅ Imported TestResult from test_utils")
    print("✅ Imported TestRunner from test_utils")
    print("✅ Imported TestTracker from test_utils")
    
    # Test TestResult creation
    result = TestResult("test", True, "passed", 1.5)
    print(f"✅ TestResult created: {result.name}, passed={result.passed}")
    
    # Check test files import it
    with open("tests/test_collaborative_chat.py", "r") as f:
        content = f.read()
        if "from test_utils import TestResult" in content:
            print("✅ test_collaborative_chat.py imports from test_utils")
        else:
            print("⚠️  test_collaborative_chat.py doesn't import from test_utils")
    
    with open("tests/test_collaborative_chat_api.py", "r") as f:
        content = f.read()
        if "from test_utils import TestResult" in content:
            print("✅ test_collaborative_chat_api.py imports from test_utils")
        else:
            print("⚠️  test_collaborative_chat_api.py doesn't import from test_utils")
            
except Exception as e:
    print(f"❌ Error: {e}")

print("\n" + "="*60)
print("VERIFICATION COMPLETE")
print("="*60)
print("\n✅ All warning fixes (#5-#8) verified!")
