#!/bin/sh
# macOS and Linux: ./start.sh starts the home page and opens it in the browser.
# The first start builds the image (about 3 minutes). Stop with ./stop.sh.
set -e
cd "$(dirname "$0")"

if ! docker info >/dev/null 2>&1; then
    echo 'Docker is not running. Start Docker Desktop, wait for "Engine running", then try again.'
    exit 1
fi

# Files the container writes to results/ belong to you, not to another user. On Windows
# (Git Bash) the compose.yaml default is right; its user ids do not exist in Docker.
case "$(uname -s)" in
    Linux | Darwin)
        LOCAL_UID="$(id -u)" LOCAL_GID="$(id -g)"
        export LOCAL_UID LOCAL_GID
        ;;
esac
docker compose up -d app

echo 'Waiting for the page...'
tries=0
until curl -fs http://localhost:8501/_stcore/health >/dev/null 2>&1; do
    tries=$((tries + 1))
    if [ "$tries" -ge 60 ]; then
        echo 'The page did not start. See: docker compose logs app'
        exit 1
    fi
    sleep 2
done

url=http://localhost:8501
if command -v open >/dev/null; then open "$url"
elif command -v xdg-open >/dev/null; then xdg-open "$url" >/dev/null 2>&1 &
fi
echo "The page is open at $url - stop it with ./stop.sh."
