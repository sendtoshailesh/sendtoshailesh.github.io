#!/bin/bash

# GitHub Pages Deployment Script
# Generated automatically for secure deployment

echo "🚀 Starting GitHub Pages deployment from EC2..."
echo "Repository: sendtoshailesh.github.io"
echo "Directory: /home/ubuntu/sendtoshailesh.github.io"
echo "=========================================="

cd /home/ubuntu/sendtoshailesh.github.io

# Check if files exist
echo "📋 Checking files..."
for file in index.html styles.css script.js README.md; do
    if [ -f "$file" ]; then
        echo "✅ Found: $file"
    else
        echo "⚠️  Missing: $file"
    fi
done

# Initialize git repository if not exists
if [ ! -d ".git" ]; then
    echo "📁 Initializing Git repository..."
    git init
    git branch -M main
fi

# Configure git
echo "🔧 Configuring Git..."
git config user.name "Shailesh Mishra"
git config user.email "sendtoshailesh@gmail.com"

# Add remote if not exists
if ! git remote get-url origin > /dev/null 2>&1; then
    echo "🔗 Adding GitHub remote..."
    git remote add origin https://github.com/sendtoshailesh/sendtoshailesh.github.io.git
fi

# Add and commit files
echo "📝 Adding files to Git..."
git add .

# Check if there are changes to commit
if git diff --staged --quiet; then
    echo "⚠️  No changes to commit"
    exit 0
fi

# Commit changes
COMMIT_MSG="Update professional website - $(date '+%Y-%m-%d %H:%M:%S')"
echo "💾 Committing changes..."
git commit -m "$COMMIT_MSG"

if [ $? -ne 0 ]; then
    echo "❌ Failed to commit changes"
    exit 1
fi

echo "🚀 Ready to push to GitHub..."
echo "📋 Next steps:"
echo "1. Authenticate with GitHub (if needed)"
echo "2. Run: git push origin main"
echo ""
echo "🔐 For authentication, you can:"
echo "   - Use GitHub CLI: gh auth login"
echo "   - Use personal access token as password"
echo "   - Configure SSH keys"
echo ""
echo "✅ Deployment script completed successfully!"
