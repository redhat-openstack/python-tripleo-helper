=======
Example
=======


Use of the library to deploy a TripleO
======================================

In this example, we use instack-virt-setup in a Nova virtual machine
(nested KVM).

.. code-block:: python

    host0 = deploy_host0(
        os_auth_url, os_username, os_password,
        os_project_id, config)
    host0.enable_repositories(
        repositories)
    host0.install_nosync()
    host0.create_stack_user()
    host0.deploy_hypervisor()
    # Our hypervisor is ready, we can now create the undercloud VM
    undercloud = host0.build_undercloud_on_libvirt()
    undercloud.configure(repositories)

    # and finally the overcloud
    undercloud.start_overcloud_deploy()


The repositories are described in this kind of structure:

.. code-block:: YAML

    - type: yum_repo
      content: |
          [RH7-RHOS-8.0]
          name=RH7-RHOS-8.0
          baseurl=http://192.168.1.2/rel-eng/OpenStack/8.0-RHEL-7/2016-01-22.1/RH7-RHOS-8.0/x86_64/os/
          gpgcheck=0
          enabled=1
      dest: /etc/yum.repos.d/rhos-release-8.repo
    - type: yum_repo
      content: |
          [RH7-RHOS-8.0-director]
          name=RH7-RHOS-8.0-director
          baseurl=http://192.168.1.2/rel-eng/OpenStack/8.0-RHEL-7-director/2015-12-03.1/RH7-RHOS-8.0-director/x86_64/os/
          gpgcheck=0
          enabled=1
      dest: /etc/yum.repos.d/rhos-release-8-director.repo


Use of the CLI to deploy a TripleO (OSP8)
=========================================

Deploy OSP8 is a RHEL7.2 on an existing OpenStack (a.k.a
OpenStack Virtual Baremetal)::

    chainsaw-ovb --config-file tripleohelper_osp.conf

.. code-block:: YAML


    ---
    rhsm:
        login: my_login
        password: my_password
    provisioner:
        image:
            name: RHEL 7.2 x86_64
        flavor: m1.hypervisor
        network: private
        keypair: DCI
        security-groups:
            - ssh
            - rhos-mirror-user
    ssh:
        private_key: /home/goneri/.ssh/DCI/id_rsa
    # the repositories to enable
    repositories: &DEFAULT_REPOSITORIES
        - type: yum_repo
          content: |
              [RH7-RHOS-8.0]
              name=RH7-RHOS-8.0
              baseurl=http://192.168.1.2/rel-eng/OpenStack/8.0-RHEL-7/2016-03-24.2/RH7-RHOS-8.0/x86_64/os/
              gpgcheck=0
              enabled=1
          dest: /etc/yum.repos.d/rhos-release-8.repo
        - type: yum_repo
          content: |
              [RH7-RHOS-8.0-director]
              name=RH7-RHOS-8.0-director
              baseurl=http://192.168.1.2/rel-eng/OpenStack/8.0-RHEL-7-director/2016-03-29.3/RH7-RHOS-8.0-director/x86_64/os/
              gpgcheck=0
              enabled=1
          dest: /etc/yum.repos.d/rhos-release-8-director.repo
