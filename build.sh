#!/bin/bash

# Initialize variables
build_cfg=""

# Parse command-line arguments
while getopts "p:" opt; do
  case ${opt} in
    p ) build_cfg=$OPTARG ;;
    * ) echo "Usage: $0 -p <scons parameter>"; exit 1 ;;
  esac
done

module unload gcc
module unload libfabric

module load gcc-native/13.2
module load swig/4.1.1
module load rocm/6.2.4
module load cray-python/3.11.7
module use /sw/crusher/ums/ompix/DEVELOP/cce/13.0.0/modules/
module load libfabric/ompix-upstream-borg-r

ml

python3 defw_cleanup_build.py $build_cfg

scons CONFIG=$build_cfg
