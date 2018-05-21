#!/bin/bash

# Get the path to THIS script
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd $DIR

# Have we setup the local python environment we need?
if ! [ -d $DIR/venv ]; then
    echo 'Error: please run: ./setup_python.sh
Exiting.'
    exit 1
fi

# If there is a current python virtual environment, deactivate it.
if ! [ -z "${VIRTUAL_ENV}" ] ; then
    deactivate
fi

# Activate the python env for this bash process
source $DIR/venv/bin/activate

# Note remove the pytest -s arg to not show print()s from the test code.

if [ $# -eq 0 ]; then
  # No command line args to this script, so run all tests:
  python -m pytest -s tests 
else
  # Run any tests passed on the command line of this script:
  python -m pytest -s $@
fi
