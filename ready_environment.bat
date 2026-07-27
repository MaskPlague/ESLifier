call conda create -n eslifier_env python=3.14 -y

call conda activate eslifier_env

call conda install -y leveldb

call conda install -y --file requirements.txt --channel conda-forge