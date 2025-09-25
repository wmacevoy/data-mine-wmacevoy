#!/bin/bash
cd -- "$(dirname -- "${BASH_SOURCE[0]}")" || exit 1

version=25.3.1-0
installer=Miniforge3-$version-$(uname)-$(uname -m).sh
if [ ! -f $installer ]
then
    curl -L -o $installer https://github.com/conda-forge/miniforge/releases/download/$version/$installer
fi
chmod +x $installer
./$installer "$@"


