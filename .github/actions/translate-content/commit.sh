#!/bin/bash
echo "The current files:"
find. -type f | sort
git add content/es/
git diff --cached
git commit -m "Auto-Translation"
