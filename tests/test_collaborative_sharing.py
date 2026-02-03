"""
Test Collaborative Chat Sharing Features
This script verifies that the sharing functionality works correctly.
"""
import requests
import json
from typing import Optional

# Configuration
BASE_URL = "http://localhost:8000"
TEST_USER_ID = "test-owner@example.com"
TEST_PARTICIPANT_EMAIL = "participant@example.com"

class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    END = '\033[0m'

def print_success(msg: str):
    print(f"{Colors.GREEN}✅ {msg}{Colors.END}")

def print_error(msg: str):
    print(f"{Colors.RED}❌ {msg}{Colors.END}")

def print_info(msg: str):
    print(f"{Colors.BLUE}ℹ️  {msg}{Colors.END}")

def print_warning(msg: str):
    print(f"{Colors.YELLOW}⚠️  {msg}{Colors.END}")

def test_create_session(user_id: str) -> Optional[str]:
    """Test creating a chat session"""
    print_info("Test 1: Creating a chat session...")
    
    try:
        response = requests.post(
            f"{BASE_URL}/chat/sessions",
            params={"user_id": user_id},
            json={"title": "Test Collaborative Session"}
        )
        
        if response.status_code == 200:
            data = response.json()
            session_id = data.get("session_id")
            print_success(f"Created session: {session_id}")
            return session_id
        else:
            print_error(f"Failed to create session: {response.status_code}")
            print(response.text)
            return None
    except Exception as e:
        print_error(f"Exception creating session: {e}")
        return None

def test_share_session(session_id: str, user_id: str) -> bool:
    """Test enabling sharing for a session"""
    print_info("Test 2: Enabling sharing...")
    
    try:
        response = requests.post(
            f"{BASE_URL}/chat/sessions/{session_id}/share",
            params={"user_id": user_id},
            json={"participant_emails": []}
        )
        
        if response.status_code == 200:
            data = response.json()
            if data.get("is_shared"):
                print_success("Session sharing enabled")
                return True
            else:
                print_error("Session not marked as shared")
                return False
        else:
            print_error(f"Failed to enable sharing: {response.status_code}")
            print(response.text)
            return False
    except Exception as e:
        print_error(f"Exception enabling sharing: {e}")
        return False

def test_get_participants(session_id: str, user_id: str) -> bool:
    """Test getting participant list"""
    print_info("Test 3: Getting participants...")
    
    try:
        response = requests.get(
            f"{BASE_URL}/chat/sessions/{session_id}/participants",
            params={"user_id": user_id}
        )
        
        if response.status_code == 200:
            data = response.json()
            participants = data.get("participants", [])
            print_success(f"Got {len(participants)} participant(s)")
            
            # Check if owner is in participants
            owner_found = any(p.get("user_id") == user_id for p in participants)
            if owner_found:
                print_success("Owner is in participant list")
                for p in participants:
                    is_owner = " (OWNER)" if p.get("is_owner") else ""
                    print(f"  - {p.get('name', 'Unknown')} ({p.get('email')}){is_owner}")
                return True
            else:
                print_error("Owner NOT in participant list")
                return False
        else:
            print_error(f"Failed to get participants: {response.status_code}")
            print(response.text)
            return False
    except Exception as e:
        print_error(f"Exception getting participants: {e}")
        return False

def test_add_participant(session_id: str, user_id: str, participant_email: str) -> bool:
    """Test adding a participant"""
    print_info(f"Test 4: Adding participant '{participant_email}'...")
    
    try:
        response = requests.post(
            f"{BASE_URL}/chat/sessions/{session_id}/participants",
            params={"user_id": user_id},
            json={"email": participant_email}
        )
        
        if response.status_code == 200:
            print_success(f"Added participant: {participant_email}")
            return True
        else:
            print_error(f"Failed to add participant: {response.status_code}")
            print(response.text)
            return False
    except Exception as e:
        print_error(f"Exception adding participant: {e}")
        return False

def test_participant_access(session_id: str, participant_id: str) -> bool:
    """Test that participant can access the session"""
    print_info("Test 5: Checking participant access...")
    
    try:
        # Test getting messages as participant
        response = requests.get(
            f"{BASE_URL}/chat/sessions/{session_id}/messages",
            params={"user_id": participant_id, "limit": 10}
        )
        
        if response.status_code == 200:
            print_success("Participant can access messages")
            return True
        elif response.status_code == 403:
            print_error("Participant denied access (403 Forbidden)")
            return False
        else:
            print_warning(f"Unexpected status: {response.status_code}")
            return False
    except Exception as e:
        print_error(f"Exception checking participant access: {e}")
        return False

def test_unauthorized_access(session_id: str) -> bool:
    """Test that unauthorized user cannot access"""
    print_info("Test 6: Checking unauthorized access is blocked...")
    
    unauthorized_user = "unauthorized@example.com"
    
    try:
        response = requests.get(
            f"{BASE_URL}/chat/sessions/{session_id}/messages",
            params={"user_id": unauthorized_user, "limit": 10}
        )
        
        if response.status_code == 403:
            print_success("Unauthorized user correctly blocked (403)")
            return True
        elif response.status_code == 200:
            print_error("SECURITY ISSUE: Unauthorized user can access!")
            return False
        else:
            print_warning(f"Unexpected status: {response.status_code}")
            return False
    except Exception as e:
        print_error(f"Exception checking unauthorized access: {e}")
        return False

def test_remove_participant(session_id: str, user_id: str, participant_id: str) -> bool:
    """Test removing a participant"""
    print_info(f"Test 7: Removing participant '{participant_id}'...")
    
    try:
        response = requests.delete(
            f"{BASE_URL}/chat/sessions/{session_id}/participants/{participant_id}",
            params={"user_id": user_id}
        )
        
        if response.status_code == 200:
            print_success(f"Removed participant: {participant_id}")
            return True
        else:
            print_error(f"Failed to remove participant: {response.status_code}")
            print(response.text)
            return False
    except Exception as e:
        print_error(f"Exception removing participant: {e}")
        return False

def test_unshare_session(session_id: str, user_id: str) -> bool:
    """Test making session private again"""
    print_info("Test 8: Making session private...")
    
    try:
        response = requests.delete(
            f"{BASE_URL}/chat/sessions/{session_id}/share",
            params={"user_id": user_id}
        )
        
        if response.status_code == 200:
            data = response.json()
            if not data.get("is_shared"):
                print_success("Session made private")
                return True
            else:
                print_error("Session still marked as shared")
                return False
        else:
            print_error(f"Failed to unshare: {response.status_code}")
            print(response.text)
            return False
    except Exception as e:
        print_error(f"Exception making private: {e}")
        return False

def run_all_tests():
    """Run all collaborative sharing tests"""
    print("\n" + "="*60)
    print("🧪 COLLABORATIVE CHAT SHARING - TEST SUITE")
    print("="*60 + "\n")
    
    results = []
    session_id = None
    
    # Test 1: Create session
    session_id = test_create_session(TEST_USER_ID)
    results.append(("Create Session", session_id is not None))
    
    if not session_id:
        print_error("\n❌ Cannot continue without session. Aborting.")
        return
    
    print()
    
    # Test 2: Enable sharing
    share_result = test_share_session(session_id, TEST_USER_ID)
    results.append(("Enable Sharing", share_result))
    print()
    
    # Test 3: Get participants (should include owner)
    participants_result = test_get_participants(session_id, TEST_USER_ID)
    results.append(("Get Participants", participants_result))
    print()
    
    # Test 4: Add participant
    add_result = test_add_participant(session_id, TEST_USER_ID, TEST_PARTICIPANT_EMAIL)
    results.append(("Add Participant", add_result))
    print()
    
    # Test 5: Participant can access
    access_result = test_participant_access(session_id, TEST_PARTICIPANT_EMAIL)
    results.append(("Participant Access", access_result))
    print()
    
    # Test 6: Unauthorized user cannot access
    security_result = test_unauthorized_access(session_id)
    results.append(("Block Unauthorized", security_result))
    print()
    
    # Test 7: Remove participant
    remove_result = test_remove_participant(session_id, TEST_USER_ID, TEST_PARTICIPANT_EMAIL)
    results.append(("Remove Participant", remove_result))
    print()
    
    # Test 8: Make private
    unshare_result = test_unshare_session(session_id, TEST_USER_ID)
    results.append(("Make Private", unshare_result))
    print()
    
    # Print summary
    print("\n" + "="*60)
    print("📊 TEST SUMMARY")
    print("="*60 + "\n")
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = f"{Colors.GREEN}✅ PASS{Colors.END}" if result else f"{Colors.RED}❌ FAIL{Colors.END}"
        print(f"{test_name:.<40} {status}")
    
    print(f"\n{'='*60}")
    if passed == total:
        print(f"{Colors.GREEN}🎉 ALL TESTS PASSED ({passed}/{total}){Colors.END}")
    else:
        print(f"{Colors.RED}⚠️  SOME TESTS FAILED ({passed}/{total}){Colors.END}")
    print("="*60 + "\n")
    
    return passed == total

if __name__ == "__main__":
    try:
        success = run_all_tests()
        exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n⚠️  Tests interrupted by user")
        exit(1)
    except Exception as e:
        print(f"\n\n❌ Fatal error: {e}")
        exit(1)
