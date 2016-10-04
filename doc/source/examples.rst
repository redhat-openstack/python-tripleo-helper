=======
Example
=======


Use of the CLI to deploy a TripleO (OSP8)
=========================================

Deploy OSP8 is a RHEL7.2 on an existing OpenStack (a.k.a
OpenStack Virtual Baremetal)::

    chainsaw-ovb --config-file tripleohelper_osp.yaml provisioning
    chainsaw-ovb --config-file tripleohelper_osp.yaml undercloud
    chainsaw-ovb --config-file tripleohelper_osp.yaml overcloud

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
