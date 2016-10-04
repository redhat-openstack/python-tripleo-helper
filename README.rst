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

At this point, you can deploy your OpenStack on:

- an existing public OpenStack (OVB)
- a hypervisor with libvirt (instack-virt-setup)
- baremetal nodes

Documentation: http://python-tripleo-helper.readthedocs.org/en/latest

Commands
--------

In addition, we provide two commands that you can use as an example:

- **chainsaw-libvirt**: this command will create a hypervisor VM on an
  OpenStack cloud and deploy an OpenStack on it.
- **chainsaw-ovb**: this command will do the same, but on a OpenStack directly.

chainsaw-libvirt will do the following actions:

- Instantiate a virtual machine on an Openstack (you should source your openrc
  or specify your OS credentials through the chainsaw CLI). This machine is
  referred to as Host0. Currently we only support the RHEL distribution, CentOS
  will be supported soon.
- Register Host0 on the machine in RHN.
- Install the required packages and configure libvirt on Host0.
- Instantiate and configure the Undercloud virtual machine.
- Deploy the Overcloud.

Once the overcloud is running, you can run tempest on it.
