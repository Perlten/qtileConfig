#!/usr/bin/bash 

# Programs
picom & # Compositor
nitrogen --restore & # Wallpaper
blueman-applet & # Bluetooth applet
nm-applet & # Network Manager Applet
volumeicon & # PulseAudio applet
xss-lock betterlockscreen -l &  # Lock screen on suspend
pamac-tray & # pacman update applet
dunst & # notification daemon
clipster -d & # Clipboard manager
autokey-gtk & # Auto keybindings
# keymouse & # Controls mouse with keyboard

# Commands
xset s off # Disable screen saver
xset -dpms # Disable DPMS (Energy Star) features.