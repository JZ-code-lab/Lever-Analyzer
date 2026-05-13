#!/usr/bin/env bash
# Render build script — installs system + Python dependencies.
# To use: in the Render dashboard, set this service's Build Command to:
#     ./build.sh
# (or paste the contents directly into the Build Command field).
set -o errexit

# antiword is needed for parsing legacy .doc (binary Word) resumes.
sudo apt-get update -qq
sudo apt-get install -y -qq antiword

pip install -r requirements.txt
