#!/bin/bash
echo "Pulling latest code..."
cd ~/MagicMirror
git pull origin master

echo "Restarting MagicMirror..."
pm2 restart magicmirror

