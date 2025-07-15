#!/usr/bin/env python3
"""
Test runner script for kactus-predict project.
Run this script to execute all tests.
"""

import sys
import subprocess

def run_tests():
    """Run all tests using pytest."""
    try:
        # Run pytest with verbose output
        result = subprocess.run([
            sys.executable, "-m", "pytest", 
            "tests/", 
            "-v",
            "--tb=short"
        ], capture_output=False, text=True)
        
        return result.returncode
    except Exception as e:
        print(f"Error running tests: {e}")
        return 1

if __name__ == "__main__":
    exit_code = run_tests()
    sys.exit(exit_code) 