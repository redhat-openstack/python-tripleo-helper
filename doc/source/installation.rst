============
Installation
============


Python versions
===============

Python-TripleO-Helper is tested under Python 3.4.

Basic installation
==================

.. code-block:: shell

   $ virtualenv -p /usr/bin/python3 test
   $ source test/bin/activate
   $ pip install git+https://github.com/redhat-openstack/python-tripleo-helper


OpenStack tenant configuration
==============================

We strongly advise you to dedicate an OpenStack tenant to tripleo-helper.
You will need the following configuration:

- a network called private with a subnet called private.
- a router called router with a public interface
- a glance image of ipxe called ipxe.usb::
    curl -O http://boot.ipxe.org/ipxe.usb
    glance image-create --name ipxe.usb \
    --disk-format raw --container-format bare < ipxe.usb
