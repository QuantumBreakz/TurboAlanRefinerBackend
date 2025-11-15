#!/usr/bin/env python3
"""
Helper script to prepare Google credentials JSON for Vercel environment variable.
This script reads the credentials file and outputs a properly formatted JSON string
that can be safely pasted into Vercel's environment variable field.
"""
import json
import sys
from pathlib import Path

def prepare_credentials_for_env(creds_file: str) -> str:
    """Read credentials file and return JSON string ready for environment variable."""
    creds_path = Path(creds_file)
    
    if not creds_path.exists():
        print(f"Error: Credentials file not found: {creds_file}", file=sys.stderr)
        sys.exit(1)
    
    # Read the credentials file
    with open(creds_path, 'r') as f:
        creds_data = json.load(f)
    
    # Ensure private_key has proper newlines (should already be correct in file)
    if 'private_key' in creds_data:
        private_key = creds_data['private_key']
        # Replace any escaped newlines with actual newlines
        if '\\n' in private_key:
            creds_data['private_key'] = private_key.replace('\\n', '\n')
    
    # Convert back to JSON string (this will escape newlines properly for env var)
    json_str = json.dumps(creds_data)
    
    return json_str

if __name__ == '__main__':
    if len(sys.argv) < 2:
        creds_file = 'config/google_credentials.json'
    else:
        creds_file = sys.argv[1]
    
    try:
        json_output = prepare_credentials_for_env(creds_file)
        print("\n" + "="*80)
        print("Copy the following JSON and paste it into Vercel's GOOGLE_CREDENTIALS_JSON environment variable:")
        print("="*80)
        print(json_output)
        print("="*80 + "\n")
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

