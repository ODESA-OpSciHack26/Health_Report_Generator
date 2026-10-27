#!/bin/sh
# macOS and Linux: ./stop.sh stops the home page.
cd "$(dirname "$0")" && docker compose down
