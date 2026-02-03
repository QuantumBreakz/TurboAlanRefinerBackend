"""
Shared test utilities for all test files.
"""
from dataclasses import dataclass
from typing import List
import time


@dataclass
class TestResult:
    """Stores test results for reporting"""
    name: str
    passed: bool
    message: str = ""
    duration: float = 0


class TestRunner:
    """Simple test runner for standalone execution"""
    def __init__(self):
        self.results: List[TestResult] = []
        self.passed = 0
        self.failed = 0
    
    def run_test(self, name: str, test_func):
        """Run a single test and record result"""
        print(f"\n{'='*80}")
        print(f"Running: {name}")
        print('='*80)
        
        start = time.time()
        try:
            test_func()
            duration = time.time() - start
            self.results.append(TestResult(name, True, "Passed", duration))
            self.passed += 1
            print(f"✅ PASSED in {duration:.2f}s")
        except AssertionError as e:
            duration = time.time() - start
            error_msg = str(e) or "Assertion failed"
            self.results.append(TestResult(name, False, error_msg, duration))
            self.failed += 1
            print(f"❌ FAILED in {duration:.2f}s: {error_msg}")
        except Exception as e:
            duration = time.time() - start
            error_msg = f"{type(e).__name__}: {str(e)}"
            self.results.append(TestResult(name, False, error_msg, duration))
            self.failed += 1
            print(f"❌ ERROR in {duration:.2f}s: {error_msg}")
    
    def print_summary(self):
        """Print test summary"""
        print(f"\n{'='*80}")
        print("TEST SUMMARY")
        print('='*80)
        
        total = self.passed + self.failed
        print(f"\nTotal Tests: {total}")
        print(f"Passed: {self.passed} ({100 * self.passed // total if total > 0 else 0}%)")
        print(f"Failed: {self.failed} ({100 * self.failed // total if total > 0 else 0}%)")
        
        if self.failed > 0:
            print("\n❌ Failed Tests:")
            for result in self.results:
                if not result.passed:
                    print(f"  - {result.name}: {result.message}")
        
        print(f"\n{'='*80}")
        
        return self.failed == 0


class TestTracker:
    """Alternative test tracker with simpler interface"""
    def __init__(self):
        self.results: List[TestResult] = []
        self.passed = 0
        self.failed = 0
    
    def record(self, name: str, passed: bool, message: str = "", duration: float = 0):
        self.results.append(TestResult(name, passed, message, duration))
        if passed:
            self.passed += 1
        else:
            self.failed += 1
    
    def print_results(self):
        """Print test results"""
        print(f"\n{'='*80}")
        print("TEST RESULTS")
        print('='*80)
        
        for result in self.results:
            status = "✅ PASS" if result.passed else "❌ FAIL"
            duration_str = f" ({result.duration:.2f}s)" if result.duration > 0 else ""
            print(f"{status}: {result.name}{duration_str}")
            if not result.passed and result.message:
                print(f"  → {result.message}")
        
        total = self.passed + self.failed
        print(f"\n{'='*80}")
        print(f"Total: {total} | Passed: {self.passed} | Failed: {self.failed}")
        print('='*80)
        
        return self.failed == 0
