# Openstack TripleO-Wrapper

## Usage

### 1. Source your Openstack openrc file

    $ source ~/openrc.sh

### 2. Install the tool in a virtualenv

    $ git clone http://softwarefactory-project.io/r/python-tripleo-wrapper
    $ mkdir jubilant-testing
    $ virtualenv jubilant-testing
    $ cd jubilant-testing
    $ source ./bin/activate
    $ pip install -e ../python-tripleo-wrapper

### 3. Run chainsaw command

First edit the configuration file 'tripleowrapper.conf', there is a
sample file in the root directory. Then run the command.

    $ chainsaw --config-path /path/to/tripleowrapper.conf

## Run unit tests

    $ tox
