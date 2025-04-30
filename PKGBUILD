# Maintainer: Miro
pkgname=animesama-cli
pkgver=1.0.3
pkgrel=1
pkgdesc="Outil CLI pour Anime-Sama"
arch=('any')
url="https://github.com/DictateurMiro/animesama-cli"
license=('GPL3')
depends=('python' 'mpv')
source=("$pkgname-$pkgver.tar.gz::https://github.com/DictateurMiro/animesama-cli/archive/refs/tags/v$pkgver.tar.gz")
sha256sums=('SKIP')

package() {
  cd "$srcdir/$pkgname-$pkgver"
  
  # Install the Python script
  install -Dm644 anime-sama.py "$pkgdir/usr/share/animesama-cli/anime-sama.py"
  
  # Create a wrapper script
  cat > "$pkgdir/usr/bin/animesama-cli" << 'EOF'
#!/bin/bash
exec python3 /usr/share/animesama-cli/anime-sama.py "$@"
EOF
  chmod 755 "$pkgdir/usr/bin/animesama-cli"
}
