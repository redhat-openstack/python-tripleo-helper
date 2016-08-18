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
You will need the following configuration in the tenant:

- a network called private with a subnet called private (192.168.1.0/24).
- a router called router with a public interface and an interface on the
  private network
- two floating IP
- a glance image of ipxe called ipxe.usb::
    curl -O http://boot.ipxe.org/ipxe.usb
    glance image-create --name ipxe.usb \
    --disk-format raw --container-format bare < ipxe.usb
- you need to create a SSH key without password and register it in your
  configuration file (`ssh.private_key`). You should then create a keypair
  with the associated SSH key and store its name in `provisioner.keypair`.
