#!/bin/bash
echo "Pulling latest code..."
git pull origin master

echo "Restarting MagicMirror..."
pm2 restart magicmirror

