"""
Test SerpManager Integration
"""

import os
import sys

# Add path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "nomad", "src"))

from tools.serpapi import SerpManager, search_flights


def test_basic_initialization():
    """Test 1: Basic Initialization"""
    print("✅ Test 1: Basic Initialization")
    try:
        manager = SerpManager()
        print("  Successfully created SerpManager instance")
        return True
    except Exception as e:
        print(f"  ❌ Failed: {e}")
        return False


def test_cache_directory():
    """Test 2: Cache Directory"""
    print("\n✅ Test 2: Cache Directory")
    try:
        manager = SerpManager()
        cache_dir = manager.cache_dir
        print(f"  Cache directory: {cache_dir}")
        
        # Check if directory exists
        if os.path.isdir(cache_dir):
            print(f"  Directory exists ✓")
            # List existing caches
            cache_files = [f for f in os.listdir(cache_dir) if f.endswith(".json")]
            print(f"  Existing cache files: {len(cache_files)}")
            return True
        else:
            print(f"  ❌ Directory does not exist")
            return False
    except Exception as e:
        print(f"  ❌ Failed: {e}")
        return False


def test_backward_compatibility():
    """Test 3: Backward Compatibility"""
    print("\n✅ Test 3: Backward Compatibility")
    try:
        # Test if old function interface still works
        from tools.serpapi import search_flights, search_hotels, search_places
        print("  Successfully imported old interface functions")
        print("  - search_flights ✓")
        print("  - search_hotels ✓")
        print("  - search_places ✓")
        return True
    except Exception as e:
        print(f"  ❌ Failed: {e}")
        return False


def test_snapshot_initialization():
    """Test 4: Snapshot Initialization"""
    print("\n✅ Test 4: Snapshot Initialization")
    try:
        # Use fake snapshot path
        manager = SerpManager(snapshot_path="/tmp/fake_snapshot.json")
        print("  Successfully created SerpManager instance with snapshot")
        print(f"  Snapshot path: /tmp/fake_snapshot.json")
        return True
    except Exception as e:
        print(f"  ❌ Failed: {e}")
        return False


def test_dispatch_integration():
    """Test 5: Dispatch Integration"""
    print("\n✅ Test 5: Dispatch Integration")
    try:
        from tools.dispatch import get_serp_manager
        manager = get_serp_manager()
        print("  Successfully created global SerpManager instance")
        return True
    except Exception as e:
        print(f"  ❌ Failed: {e}")
        return False


def test_cache_key_generation():
    """Test 6: Cache Key Generation"""
    print("\n✅ Test 6: Cache Key Generation")
    try:
        manager = SerpManager()
        
        # Test that same parameters generate same cache key
        key1 = manager._generate_cache_key("google_flights", origin="BOS", dest="SEA")
        key2 = manager._generate_cache_key("google_flights", origin="BOS", dest="SEA")
        
        if key1 == key2:
            print(f"  Same parameters → Same cache key ✓")
            print(f"  Cache key: {key1}")
            return True
        else:
            print(f"  ❌ Cache keys inconsistent")
            return False
    except Exception as e:
        print(f"  ❌ Failed: {e}")
        return False


def test_file_naming():
    """Test 7: File Naming"""
    print("\n✅ Test 7: Cache File Naming")
    try:
        manager = SerpManager()
        
        # Test filename generation
        filename = manager._get_cache_filename("google_flights", "abc123def456")
        expected = "google_flights_abc123def456.json"
        
        if filename == expected:
            print(f"  Filename format correct: {filename} ✓")
            return True
        else:
            print(f"  ❌ Filename format incorrect")
            print(f"     Expected: {expected}")
            print(f"     Actual: {filename}")
            return False
    except Exception as e:
        print(f"  ❌ Failed: {e}")
        return False


def main():
    """Run all tests"""
    print("=" * 50)
    print("SerpManager Integration Test Suite")
    print("=" * 50)
    
    tests = [
        test_basic_initialization,
        test_cache_directory,
        test_backward_compatibility,
        test_snapshot_initialization,
        test_dispatch_integration,
        test_cache_key_generation,
        test_file_naming,
    ]
    
    results = []
    for test in tests:
        try:
            result = test()
            results.append(result)
        except Exception as e:
            print(f"  ❌ Test exception: {e}")
            results.append(False)
    
    # Summary
    print("\n" + "=" * 50)
    passed = sum(results)
    total = len(results)
    print(f"Test results: {passed}/{total} passed")
    
    if passed == total:
        print("✅ All tests passed!")
    else:
        print(f"❌ {total - passed} test(s) failed")
    
    print("=" * 50)
    return passed == total


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
