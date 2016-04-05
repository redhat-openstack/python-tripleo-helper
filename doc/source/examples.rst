===
API
===


Example
=======

In this example, we use instack-virt-setup in a Nova virtual machine
(nested KVM).

.. code-block:: python

    host0 = deploy_host0(
        os_auth_url, os_username, os_password,
        os_tenant_name, config)
    host0.enable_repositories(
        repositories)
    host0.install_nosync()
    host0.create_stack_user()
    host0.deploy_hypervisor()
    # Our hypervisor is ready, we can now create the undercloud VM
    undercloud = host0.instack_virt_setup()
    undercloud.enable_repositories(repositories)

    # enable nosync to avoid sync() call and speed up the deployment
    undercloud.install_nosync()

    undercloud.create_stack_user()
    undercloud.install_base_packages()
    undercloud.clean_system()
    undercloud.yum_update()

    # install the OSP distribution
    undercloud.install_osp()

    # deploy the undercloud
    undercloud.openstack_undercloud_install(
        guest_image_path,
        guest_image_checksum,
        files)

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
