============
Installation
============


Python versions
===============

Python-RDO-M-Helper is tested under Python 3.4.

Basic installation
==================

.. code-block:: shell

   $ virtualenv -p /usr/bin/python3 test
   $ source test/bin/activate
   $ pip install git+https://github.com/redhat-cip/python-rdo-m-helper


OpenStack tenant configuration
==============================

We strongly advise you to dedicate an OpenStack tenant to rdo-m-helper.
You will need the following configuration:

- a network called private with a subnet called private.
- a router called router with a public interface
- a glance image of ipxe ISO called ipxe.iso::
    curl -O http://boot.ipxe.org/ipxe.iso
    glance image-create --name ipxe.iso \
    --disk-format raw --container-format bare < ipxe.iso
