============
Introduction
============

This library provides a complete Python API to drive an OpenStack deployment
(TripleO).

.. _Openstack: https://www.openstack.org
.. _TripleO: http://docs.openstack.org/developer/tripleo-docs

This library has been designed to make it easier to test real life scenarios.
For example:

- deploy 4 nodes with HA
- add a node
- execute tempest testing

At this point, you can deploy your OpenStack on an existing public
OpenStack (OVB).

The documentation is available online here:
[http://python-tripleo-helper.readthedocs.org/en/latest/](http://python-tripleo-helper.readthedocs.org/en/latest/).

Installation
------------

[http://python-tripleo-helper.readthedocs.org/en/latest/installation.html](installation).

Command
--------

We provide a command called **chainsaw-ovb**:

- `chainsaw-ovb --config-file tripleo-helper_osp.conf provisioning`:
  prepare the OVB environmnent
- `chainsaw-ovb --config-file tripleo-helper_osp.conf undercloud`:
  initialize the undercloud OpenStack on the undercloud host.
- `chainsaw-ovb --config-file tripleo-helper_osp.conf overcloud`:
  deploy the overcloud
