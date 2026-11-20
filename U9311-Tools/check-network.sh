#!/bin/sh
# Read only the four-byte xar header from Apple's Sequoia installer.
url='https://swcdn.apple.com/content/downloads/35/30/142-54123-A_L1FDSOKH17/4v632s6ip8ranyhu7hc09akv6d5239x9tq/InstallAssistant.pkg'
if header=$(/usr/bin/curl --fail --silent --show-error --location \
    --proto '=https' --proto-redir '=https' --connect-timeout 8 --max-time 25 \
    --range 0-3 --max-filesize 4 "$url") && [ "$header" = 'xar!' ]; then
    printf '%s\n' 'PASS - Apple returned the Sequoia installer package header.'
else
    printf '%s\n' 'CHECK NETWORK - could not read the Apple package header. See section 2 of the guide.' >&2
    exit 1
fi
