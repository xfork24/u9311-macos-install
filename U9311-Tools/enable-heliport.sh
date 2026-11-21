#!/bin/sh
# Run as the logged-in desktop user on the U9311.
set -eu
user=$(id -un)
[ "$(stat -f %Su /dev/console)" = "$user" ] || { echo "Run in the desktop user's session." >&2; exit 1; }
if /usr/bin/kmutil showloaded 2>/dev/null | /usr/bin/grep -qF 'org.forbiddenitlwm.ForbiddenItlwm '; then
    echo "This EFI uses the macOS Wi-Fi menu. HeliPort is only used with the older itlwm EFI."
    exit 0
fi
app=/Applications/HeliPort.app
[ -x "$app/Contents/MacOS/HeliPort" ] || { echo "Install HeliPort.app in Applications first." >&2; exit 1; }
label=local.u9311.heliport-login
source=$(dirname "$0")/$label.plist
folder="$HOME/Library/LaunchAgents"
target="$folder/$label.plist"
plutil -lint "$source" >/dev/null
mkdir -p "$folder"
if [ -e "$target" ]; then
    cmp -s "$source" "$target" || { echo "Different existing HeliPort login configuration: $target" >&2; exit 1; }
else
    install -m 644 "$source" "$target"
fi
domain="gui/$(id -u)"
launchctl print "$domain/$label" >/dev/null 2>&1 || launchctl bootstrap "$domain" "$target"
if [ "$(defaults read com.apple.controlcenter 'NSStatusItem Visible WiFi' 2>/dev/null || :)" != 0 ] ||
   [ "$(defaults -currentHost read com.apple.controlcenter WiFi 2>/dev/null || :)" != 24 ]; then
    defaults write com.apple.controlcenter 'NSStatusItem Visible WiFi' -bool false
    defaults -currentHost write com.apple.controlcenter WiFi -int 24
    killall -u "$user" ControlCenter || true
fi
open -g -a "$app"
