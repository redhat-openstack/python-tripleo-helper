============
Introduction
============

What is Rdo-m-Helper ?
======================

Rdo-m-Helper is a Python tool which help you to deploy and test an
Openstack_ infrastructure based on the Rdo-Manager_ installer.

.. _Rdo-Manager: https://www.rdoproject.org/rdo-manager
.. _Openstack: https://www.openstack.org

How it works ?
==============

Currently Rdo-m-Helper will basically automate the TripleO_ documentation to
get a fully Undercloud and Overcloud deployed.

.. _TripleO: http://docs.openstack.org/developer/tripleo-docs


Once installed you get access to the chainsaw command. The chainsaw command
accept a configuration file (we will explain it below) through the command:

.. code-block:: shell

  $ chainsaw --config-file ~/rdomhelper.conf

Chainsaw will do the following actions:

- Instantiate a virtual machine on an Openstack (you should source your openrc
  or specify your OS credentials through chainsaw cli). This machine is
  referred to as Host0. Currently we only support RHEL distribution, Centos
  will be supported soon.
- Register Host0 on the machine in RHN.
- Install install the required packages and configure libvirt on Host0.
- Instantiate and configure the Undercloud virtual machine.
- Deploy the Overcloud.

Once the overcloud is running, you can run tempest on it.
