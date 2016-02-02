============
Installation
============


Python versions
===============

Python-RDO-M-Helper is tested under Python 3.4.

Basic installation
==================

.. code-block:: shell

   $ mkdir jubilant-testing
   $ virtualenv jubilant-testing
   $ cd jubilant-testing
   $ git clone https://github.com/redhat-cip/python-rdo-m-helper
   $ source ./bin/activate
   $ pip install -r ./python-rdo-m-helper/requirements.txt
   $ pip install -e ./python-rdo-m-helper
