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
    echo "Installation de python3, mpv, git et dépendances..."
    sudo apt install -y python3 python3-pip mpv git python3-requests python3-bs4 python3-venv
    
    # Vérifier si les packages système sont installés correctement
    if ! dpkg -l | grep -q python3-requests || ! dpkg -l | grep -q python3-bs4; then
        echo "Création d'un environnement virtuel pour les dépendances Python..."
        python3 -m venv ~/.local/share/animesama-venv
        source ~/.local/share/animesama-venv/bin/activate
        pip install --upgrade pip
        pip install requests beautifulsoup4
        deactivate
    fi
elif [ "$DISTRO" = "arch" ]; then
    sudo pacman -Sy --noconfirm
    echo "Installation de python, python-pip, mpv, git..."
    sudo pacman -S --noconfirm python python-pip mpv git python-requests python-beautifulsoup4
fi

# Cloner le dépôt Git
echo "Clonage du dépôt Git animesama-cli..."
if [ -d "$HOME/animesama-cli" ]; then
    echo "Le répertoire animesama-cli existe déjà."
    echo "Mise à jour du dépôt..."
    cd "$HOME/animesama-cli"
    git pull
    cd - > /dev/null
else
    git clone https://github.com/DictateurMiro/animesama-cli.git "$HOME/animesama-cli"
fi

# Créer un lien symbolique vers le script dans /usr/local/bin
echo "Création d'un lien symbolique dans /usr/local/bin..."
SCRIPT_PATH="$HOME/animesama-cli/anime-sama.py"
chmod +x "$SCRIPT_PATH"

# Créer un wrapper script pour simplifier l'exécution
if [ "$DISTRO" = "debian" ] && [ -d "$HOME/.local/share/animesama-venv" ]; then
    # Version avec environnement virtuel si nécessaire
    cat > /tmp/animesama-cli << EOF
#!/bin/bash
source "$HOME/.local/share/animesama-venv/bin/activate"
python3 "$SCRIPT_PATH" "\$@"
deactivate
EOF
else
    # Version standard
    cat > /tmp/animesama-cli << EOF
#!/bin/bash
python3 "$SCRIPT_PATH" "\$@"
EOF
fi

sudo mv /tmp/animesama-cli /usr/local/bin/
sudo chmod +x /usr/local/bin/animesama-cli

echo -e "\nInstallation terminée !"
echo "Vous pouvez maintenant lancer l'application en tapant simplement:"
echo "  animesama-cli" 