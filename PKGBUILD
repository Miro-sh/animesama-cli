# Maintainer: Miro
pkgname=animesama-cli
pkgver=1.0.0
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
  install -Dm755 anime-sama.py "$pkgdir/usr/bin/animesama-cli"
}