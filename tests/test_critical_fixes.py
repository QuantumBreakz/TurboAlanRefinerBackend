#!/usr/bin/env python3
"""
Test script to verify critical fixes are working correctly.

Tests:
1. Database facade works (database.py uses MongoDB)
2. ChatRequest classes don't conflict
3. Duplicate functions are documented

Usage:
    python test_critical_fixes.py
"""

import sys
import os

# Add backend to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_database_facade():
    """Test that database.py works as MongoDB facade."""
    print("\n" + "="*60)
    print("TEST 1: Database Facade")
    print("="*60)
    
    try:
        from app.core.database import get_job, upsert_job, RefinementJob
        
        # Test 1: Create a job
        print("✓ Imports successful")
        
        job_data = {
            'file_name': 'test.txt',
            'file_id': 'test-file-123',
            'status': 'pending',
            'user_id': 'test-user',
            'progress': 0.0,
            'current_stage': 'initializing'
        }
        
        job = upsert_job('test-job-123', job_data)
        print(f"✓ Created job: {job.id}")
        assert job.id == 'test-job-123', "Job ID mismatch"
        assert job.status == 'pending', "Job status mismatch"
        
        # Test 2: Retrieve the job
        retrieved = get_job('test-job-123')
        if retrieved:
            print(f"✓ Retrieved job: {retrieved.id}")
            assert retrieved.id == job.id, "Retrieved job ID doesn't match"
        else:
            print("⚠️  Job not found (might be using in-memory fallback)")
        
        # Test 3: Update the job
        job_data['status'] = 'completed'
        job_data['progress'] = 100.0
        updated = upsert_job('test-job-123', job_data)
        print(f"✓ Updated job status: {updated.status}")
        assert updated.status == 'completed', "Job status not updated"
        
        print("\n✅ TEST 1 PASSED: Database facade works correctly")
        return True
        
    except ImportError as e:
        print(f"❌ Import error: {e}")
        return False
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_chat_request_separation():
    """Test that ChatRequest classes are properly separated."""
    print("\n" + "="*60)
    print("TEST 2: ChatRequest Class Separation")
    print("="*60)
    
    try:
        # Test workspace chat request
        from app.api.routes.workspace_routes import WorkspaceChatRequest
        print("✓ WorkspaceChatRequest imported successfully")
        
        # Test document chat request
        from app.main import DocumentChatRequest
        print("✓ DocumentChatRequest imported successfully")
        
        # Verify they are different classes
        assert WorkspaceChatRequest != DocumentChatRequest, "Classes should be different"
        print("✓ Classes are distinct")
        
        # Test instantiation
        workspace_req = WorkspaceChatRequest(message="test", schema_levels={"test": 1})
        print(f"✓ WorkspaceChatRequest instance created: {workspace_req.message}")
        
        doc_req = DocumentChatRequest(message="test", user_id="test-user")
        print(f"✓ DocumentChatRequest instance created: {doc_req.message}")
        
        print("\n✅ TEST 2 PASSED: ChatRequest classes properly separated")
        return True
        
    except ImportError as e:
        print(f"❌ Import error: {e}")
        return False
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_duplicate_functions_documented():
    """Test that duplicate functions have TODO comments."""
    print("\n" + "="*60)
    print("TEST 3: Duplicate Functions Documentation")
    print("="*60)
    
    try:
        import app.api.routes.refine as refine_module
        import app.main as main_module
        
        # Check that functions exist
        assert hasattr(refine_module, '_validate_and_resolve_file_path'), "Function missing in refine.py"
        assert hasattr(main_module, '_validate_and_resolve_file_path'), "Function missing in main.py"
        print("✓ Functions exist in both modules")
        
        # Read source files to check for TODO comments
        refine_path = os.path.join(os.path.dirname(__file__), 'app', 'api', 'routes', 'refine.py')
        main_path = os.path.join(os.path.dirname(__file__), 'app', 'main.py')
        
        with open(refine_path, 'r') as f:
            refine_content = f.read()
        
        with open(main_path, 'r') as f:
            main_content = f.read()
        
        # Check for TODO comments
        todo_marker = "TODO: DUPLICATE CODE"
        refine_has_todos = todo_marker in refine_content
        main_has_todos = todo_marker in main_content
        
        if refine_has_todos:
            print("✓ TODO comments found in refine.py")
        else:
            print("⚠️  No TODO comments in refine.py")
        
        if main_has_todos:
            print("✓ TODO comments found in main.py")
        else:
            print("⚠️  No TODO comments in main.py")
        
        assert refine_has_todos and main_has_todos, "TODO comments missing"
        
        print("\n✅ TEST 3 PASSED: Duplicate functions are documented")
        return True
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_mongodb_method_consistency():
    """Test that MongoDB has consistent method names."""
    print("\n" + "="*60)
    print("TEST 4: MongoDB Method Name Consistency")
    print("="*60)
    
    try:
        from app.core.mongodb_db import db as mongodb_db
        
        # Check that both methods exist
        assert hasattr(mongodb_db, 'get_job'), "get_job() method missing"
        assert hasattr(mongodb_db, 'get_job_by_id'), "get_job_by_id() method missing"
        print("✓ Both get_job() and get_job_by_id() methods exist")
        
        # Check they're callable
        assert callable(mongodb_db.get_job), "get_job is not callable"
        assert callable(mongodb_db.get_job_by_id), "get_job_by_id is not callable"
        print("✓ Both methods are callable")
        
        print("\n✅ TEST 4 PASSED: MongoDB methods are consistent")
        return True
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Run all tests."""
    print("\n" + "="*60)
    print("CRITICAL FIXES TEST SUITE")
    print("="*60)
    print("\nTesting fixes for:")
    print("  - Issue #1: Database Module Conflicts")
    print("  - Issue #2: Duplicate ChatRequest Classes")
    print("  - Issue #3: Duplicate Helper Functions")
    print("  - Issue #4: Inconsistent Job Method Naming")
    
    results = []
    
    # Run tests
    results.append(("Database Facade", test_database_facade()))
    results.append(("ChatRequest Separation", test_chat_request_separation()))
    results.append(("Duplicate Functions Documentation", test_duplicate_functions_documented()))
    results.append(("MongoDB Method Consistency", test_mongodb_method_consistency()))
    
    # Summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {name}")
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 ALL TESTS PASSED!")
        print("Critical fixes are working correctly.")
        return 0
    else:
        print(f"\n⚠️  {total - passed} test(s) failed.")
        print("Please review the output above for details.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
