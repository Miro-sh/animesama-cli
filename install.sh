#!/usr/bin/env bash

set -e

if [ -f /etc/debian_version ]; then
    DISTRO="debian"
elif [ -f /etc/arch-release ]; then
    DISTRO="arch"
else
    echo "Distribution non supportée. Ce script ne fonctionne que sur Debian/Ubuntu et Arch Linux."
    exit 1
fi

echo "Distribution détectée : $DISTRO"

echo "Mise à jour des paquets..."
if [ "$DISTRO" = "debian" ]; then
    sudo apt update
    echo "Installation de python3, python3-pip, mpv, ..."
    sudo apt install -y python3 python3-pip mpv
    echo "Installation des modules Python nécessaires (via pip)..."
    pip3 install --user --upgrade pip
    pip3 install --user requests beautifulsoup4
elif [ "$DISTRO" = "arch" ]; then
    sudo pacman -Sy --noconfirm
    echo "Installation de python, python-pip, mpv, ..."
    sudo pacman -S --noconfirm python python-pip mpv
    echo "Installation des modules Python nécessaires (via pacman)..."
    sudo pacman -S --noconfirm python-requests python-beautifulsoup4
fi

echo "\nInstallation terminée !"
echo "Pour lancer l'application :"
echo "  python3 anime-sama.py" 