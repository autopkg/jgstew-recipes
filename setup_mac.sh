#!/usr/bin/env bash

# this script is intended to setup a mac from scratch to be able to develop or build autopkg recipes

# determine the python version to install from .python-version (fallback: 3.10)
# accepts "3.11" or "3.11.4" (uses the leading major.minor); run from the repo root
PYTHON_VERSION="3.10"
if [ -f .python-version ]; then
    _pv="$(head -n1 .python-version | tr -d '[:space:]')"
    if [[ "$_pv" =~ ^([0-9]+\.[0-9]+) ]]; then
        PYTHON_VERSION="${BASH_REMATCH[1]}"
    fi
fi
echo "Using Python ${PYTHON_VERSION} (from .python-version, default 3.10)"

# check xcode command line tools install:
# xcode-select --print-path

# install homebrew:
if [ ! -f /usr/local/bin/brew ] ; then
NONINTERACTIVE=1 /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/029184a90aecb8afff8b3ad56a2ea4f1be68cec6/install.sh)"
fi

# get brew to work on PATH
eval $(/opt/homebrew/bin/brew shellenv)

# NONINTERACTIVE=1 brew tap microsoft/git

NONINTERACTIVE=1 brew install --adopt "python@${PYTHON_VERSION}" sevenzip msitools visual-studio-code libmagic jq yq git-credential-manager-core cairo libffi

python3 -m pip install --upgrade pip

python3 -m pip install --upgrade setuptools build wheel

# if autopkg does not exist
if [ ! -f  ../autopkg ] ; then
git clone https://github.com/autopkg/autopkg.git ../autopkg
fi

# if autopkg Library folder does not exist
if [ ! -f  ~/Library/AutoPkg ] ; then
mkdir -p ~/Library/AutoPkg
fi

# mkdir -p ~/.config/Autopkg

# install autopkg requirements
python3 -m pip install --requirement ../autopkg/gh_actions_requirements.txt --user

# add required recipe repos for jgstew-recipes
for line in $(cat .autopkg_repos.txt); do python3 ../autopkg/Code/autopkg repo-add $line; done

# install jgstew-recipes requirements:
python3 -m pip install --requirement requirements.txt --user
