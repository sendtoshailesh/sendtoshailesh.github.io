#!/usr/bin/env python3
"""
Secure GitHub API Deployer - EC2 Version
Deploy directly to GitHub using API without exposing credentials
"""

import os
import sys
import json
import base64
import requests
import getpass
from pathlib import Path
from datetime import datetime

class EC2GitHubAPIDeployer:
    def __init__(self):
        self.github_username = "sendtoshailesh"
        self.repo_name = f"{self.github_username}.github.io"
        self.api_base = "https://api.github.com"
        self.token = None
        self.headers = None
        self.website_files = ["index.html", "styles.css", "script.js", "README.md"]
    
    def print_status(self, message, status="INFO"):
        icons = {"INFO": "ℹ️", "SUCCESS": "✅", "WARNING": "⚠️", "ERROR": "❌"}
        print(f"{icons.get(status, '')} {message}")
    
    def load_token_secure(self):
        """Load GitHub token securely"""
        # Try environment variable first
        self.token = os.getenv('GITHUB_TOKEN') or os.getenv('GH_TOKEN')
        
        if self.token:
            self.print_status("Using token from environment variable", "SUCCESS")
            return True
        
        # Try secure config file
        config_file = Path.home() / '.github_config.json'
        if config_file.exists():
            try:
                with open(config_file, 'r') as f:
                    config = json.load(f)
                    self.token = config.get('token')
                if self.token:
                    self.print_status("Using token from config file", "SUCCESS")
                    return True
            except Exception:
                pass
        
        # Secure input
        self.print_status("GitHub Personal Access Token required", "INFO")
        self.print_status("Get token from: https://github.com/settings/tokens", "INFO")
        
        try:
            self.token = getpass.getpass("Enter GitHub token (hidden): ")
            return bool(self.token)
        except KeyboardInterrupt:
            return False
    
    def setup_headers(self):
        """Setup API headers"""
        if self.token:
            self.headers = {
                'Authorization': f'token {self.token}',
                'Accept': 'application/vnd.github.v3+json',
                'Content-Type': 'application/json'
            }
    
    def verify_auth(self):
        """Verify GitHub authentication"""
        self.setup_headers()
        try:
            response = requests.get(f"{self.api_base}/user", headers=self.headers, timeout=10)
            if response.status_code == 200:
                user_data = response.json()
                self.print_status(f"Authenticated as: {user_data.get('login')}", "SUCCESS")
                return True
            else:
                self.print_status("Authentication failed", "ERROR")
                return False
        except Exception as e:
            self.print_status(f"Auth error: {str(e)}", "ERROR")
            return False
    
    def get_file_sha(self, file_path):
        """Get SHA of existing file"""
        try:
            response = requests.get(
                f"{self.api_base}/repos/{self.github_username}/{self.repo_name}/contents/{file_path}",
                headers=self.headers, timeout=10
            )
            if response.status_code == 200:
                return response.json().get('sha')
        except Exception:
            pass
        return None
    
    def upload_file(self, file_path, content):
        """Upload file to GitHub"""
        try:
            content_encoded = base64.b64encode(content.encode('utf-8')).decode('utf-8')
            sha = self.get_file_sha(file_path)
            
            data = {
                'message': f'Update {file_path} from EC2 - {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}',
                'content': content_encoded,
                'branch': 'main'
            }
            
            if sha:
                data['sha'] = sha
            
            response = requests.put(
                f"{self.api_base}/repos/{self.github_username}/{self.repo_name}/contents/{file_path}",
                headers=self.headers, json=data, timeout=30
            )
            
            if response.status_code in [200, 201]:
                action = "Updated" if sha else "Created"
                self.print_status(f"{action} {file_path}", "SUCCESS")
                return True
            else:
                self.print_status(f"Failed to upload {file_path}", "ERROR")
                return False
                
        except Exception as e:
            self.print_status(f"Upload error for {file_path}: {str(e)}", "ERROR")
            return False
    
    def deploy(self):
        """Main deployment function"""
        self.print_status("🚀 Starting secure GitHub API deployment...", "INFO")
        
        if not self.load_token_secure():
            self.print_status("Token required for deployment", "ERROR")
            return False
        
        if not self.verify_auth():
            return False
        
        success_count = 0
        for file_name in self.website_files:
            file_path = Path(file_name)
            
            if not file_path.exists():
                self.print_status(f"Skipping {file_name} (not found)", "WARNING")
                continue
            
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                if self.upload_file(file_name, content):
                    success_count += 1
                    
            except Exception as e:
                self.print_status(f"Error reading {file_name}: {str(e)}", "ERROR")
        
        if success_count > 0:
            self.print_status(f"🎉 Deployment completed! {success_count} files uploaded", "SUCCESS")
            self.print_status("🌐 Website: https://sendtoshailesh.github.io", "SUCCESS")
            return True
        else:
            self.print_status("No files were uploaded", "ERROR")
            return False

def main():
    deployer = EC2GitHubAPIDeployer()
    success = deployer.deploy()
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
