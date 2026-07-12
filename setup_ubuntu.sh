#!/usr/bin/env bash

if [ ${EUID:-0} -ne 0 ] || [ "$(id -u)" -ne 0 ]; then
    echo ""
else
    # if already root and no sudo available like in docker:
    alias sudo="" && shopt -s expand_aliases
fi

# determine the python version to install from .python-version (fallback: 3.10)
# accepts "3.11" or "3.11.4" (uses the leading major.minor); run from the repo root
PYTHON_VERSION="3.10"
if [ -f .python-version ]; then
    _pv="$(head -n1 .python-version | tr -d '[:space:]')"
    if [[ "$_pv" =~ ^([0-9]+\.[0-9]+) ]]; then
        PYTHON_VERSION="${BASH_REMATCH[1]}"
    fi
fi
PYBIN="python${PYTHON_VERSION}"
echo "Using ${PYBIN} (from .python-version, default 3.10)"

sudo apt update && DEBIAN_FRONTEND=noninteractive apt install -y git
# git clone https://github.com/autopkg/jgstew-recipes.git

# setup python via deadsnakes PPA: https://gist.github.com/rutcreate/c0041e842f858ceb455b748809763ddb
sudo DEBIAN_FRONTEND=noninteractive apt install -y software-properties-common git
sudo add-apt-repository ppa:deadsnakes/ppa -y && apt update

sudo DEBIAN_FRONTEND=noninteractive apt install -y ${PYBIN} ${PYBIN}-venv ${PYBIN}-dev

# https://pip.pypa.io/en/stable/installation/#ensurepip
sudo ${PYBIN} -m ensurepip --upgrade

# update python pip
sudo ${PYBIN} -m pip install --upgrade pip

# update python basics
sudo ${PYBIN} -m pip install --upgrade setuptools wheel build

# install packages needed for installing python requirements and using python processors
sudo DEBIAN_FRONTEND=noninteractive apt install -y python-dev-is-python3 speech-dispatcher libcairo2-dev libmagic-dev jq p7zip-full msitools curl git wget build-essential libncursesw5-dev libssl-dev libsqlite3-dev tk-dev libgdbm-dev libc6-dev libbz2-dev libffi-dev zlib1g-dev

# install yq (Mike Farah's Go yq) for FileYamlReadYq - not in apt, so download the
# release binary matching this machine's architecture (amd64/arm64):
if ! command -v yq >/dev/null 2>&1; then
    YQ_ARCH="$(dpkg --print-architecture 2>/dev/null || echo amd64)"
    sudo wget -q "https://github.com/mikefarah/yq/releases/latest/download/yq_linux_${YQ_ARCH}" -O /usr/local/bin/yq
    sudo chmod +x /usr/local/bin/yq
fi

# This may solve a weird issue:
# python3 -m pip install -U 'pyasn1<0.5.0'
# python3 -m pip install -U pyasn1-modules<0.5.0 --ignore-installed pyasn1-modules

# if autopkg does not exist
if [ ! -f  ../autopkg ] ; then
git clone https://github.com/autopkg/autopkg.git ../autopkg
bash -c "cd ../autopkg && git checkout dev"
fi

# create virtual environment
${PYBIN} -m venv ../autopkg/.venv
./../autopkg/.venv/bin/python3 -m pip install --upgrade pip
./../autopkg/.venv/bin/python3 -m pip install --upgrade setuptools wheel build

# install autopkg requirements
./../autopkg/.venv/bin/python3 -m pip install --requirement ../autopkg/gh_actions_requirements.txt

# create folder for autopkg recipe map
mkdir -p ~/Library/AutoPkg

# create folder for autopkg config
mkdir -p ~/.config/Autopkg

# if config file does not exist, create it:
if [ ! -f  ~/.config/Autopkg/config.json ] ; then
echo {} > ~/.config/Autopkg/config.json
fi

# add required recipe repos for jgstew-recipes
for line in $(cat .autopkg_repos.txt); do ./../autopkg/.venv/bin/python3 ../autopkg/Code/autopkg repo-add $line; done

# install jgstew-recipes requirements:
./../autopkg/.venv/bin/python3 -m pip install --requirement requirements.txt

# fix issue with new openssl and a processor
# https://github.com/wbond/oscrypto/issues/78#issuecomment-2210120532
./../autopkg/.venv/bin/python3 -m pip install -I git+https://github.com/wbond/oscrypto.git

# test:
./../autopkg/.venv/bin/python3 ../autopkg/Code/autopkg run -v Test-Recipes/AutopkgCore.test.recipe.yaml
./../autopkg/.venv/bin/python3 ../autopkg/Code/autopkg run -v com.github.jgstew.test.AutopkgBuildRecipeListTest

# get autopkg version
./../autopkg/.venv/bin/python3 ../autopkg/Code/autopkg version

# because this is relative path, it will only work within the recipe or autopkg folder:
echo 'alias autopkg="./../autopkg/.venv/bin/python3 ../autopkg/Code/autopkg"' >> ~/.bashrc
alias autopkg="./../autopkg/.venv/bin/python3 ../autopkg/Code/autopkg"

# further test: ./../autopkg/.venv/bin/python3 ../autopkg/Code/autopkg run -vv --recipe-list Test-Recipes/Test-Recipes.recipelist.txt
