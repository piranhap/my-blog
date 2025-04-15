#!/bin/bash
echo "The current files:"
find . -type f | sort
echo "Stagin translated files"
git add content/es/
git commit -m "Auto-Translation"
git push origin main
