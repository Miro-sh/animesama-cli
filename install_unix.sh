#!/usr/bin/env bash

set -e

if [ -f /etc/debian_version ]; then
    echo "Distribution détectée : Debian/Ubuntu"
    sudo apt update
    sudo apt install -y mpv pipx
elif [ -f /etc/arch-release ]; then
    echo "Distribution détectée : Arch Linux"
    echo "Conseil : le paquet AUR 'animesama-cli' est disponible (yay -S animesama-cli)."
    sudo pacman -Sy --noconfirm mpv pipx
else
    echo "Distribution non supportée. Ce script ne fonctionne que sur Debian/Ubuntu et Arch Linux."
    exit 1
fi

echo "Installation de animesama-cli via pipx..."
pipx ensurepath
pipx install --force animesama-cli

mkdir -p "$HOME/.local/share/animesama-cli"

echo ""
echo "Installation terminée !"
echo "Ouvre un nouveau terminal (ou recharge ton shell), puis lance :"
echo "  animesama-cli"
