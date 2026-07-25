#!/usr/bin/env python3

import json
import os
import re
import subprocess
import sys
import urllib.request

PACKAGE = "animesama"
HOMEPAGE = "https://github.com/Miro-sh/animesama-cli"
DESC = "Browse and watch anime from anime-sama.fr directly in your terminal"

FORMULA_TEMPLATE = """class Animesama < Formula
  include Language::Python::Virtualenv

  desc "{desc}"
  homepage "{homepage}"
  url "{url}"
  sha256 "{sha256}"
  license "GPL-3.0-only"

  depends_on "mpv"
  depends_on "python@3.12"

{resources}
  def install
    virtualenv_install_with_resources
  end

  test do
    system bin/"animesama-cli", "--help"
  end
end
"""

RESOURCE_TEMPLATE = """  resource "{name}" do
    url "{url}"
    sha256 "{sha256}"
  end
"""


def pypi_json(name, version=None):
    url = f"https://pypi.org/pypi/{name}/json" if version is None else f"https://pypi.org/pypi/{name}/{version}/json"
    with urllib.request.urlopen(url) as resp:
        return json.load(resp)


def sdist_info(name, version):
    data = pypi_json(name, version)
    for file in data["urls"]:
        if file["packagetype"] == "sdist":
            return file["url"], file["digests"]["sha256"]
    raise RuntimeError(f"No sdist found for {name}=={version}")


def installed_packages():
    output = subprocess.check_output(
        [sys.executable, "-m", "pip", "list", "--format", "json"],
        text=True,
    )
    skip = {"pip", "setuptools", "wheel"}
    return [
        (pkg["name"], pkg["version"])
        for pkg in json.loads(output)
        if pkg["name"].lower() not in skip
    ]


def main():
    version = os.environ.get("VERSION")
    if not version:
        if len(sys.argv) > 1:
            version = sys.argv[1]
        else:
            version = pypi_json(PACKAGE)["info"]["version"]

    url, sha256 = sdist_info(PACKAGE, version)

    resources = []
    for name, pkg_version in installed_packages():
        if name.lower() == PACKAGE:
            continue
        r_url, r_sha256 = sdist_info(name, pkg_version)
        resources.append(RESOURCE_TEMPLATE.format(name=name, url=r_url, sha256=r_sha256))

    formula = FORMULA_TEMPLATE.format(
        desc=DESC,
        homepage=HOMEPAGE,
        url=url,
        sha256=sha256,
        resources="".join(resources),
    )

    out_dir = sys.argv[2] if len(sys.argv) > 2 else "Formula"
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, f"{PACKAGE}.rb")
    with open(out_path, "w") as f:
        f.write(formula)
    print(f"Formula written to {out_path}")


if __name__ == "__main__":
    main()
