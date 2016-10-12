#!/bin/bash
set -eux
PROJ_NAME=python-tripleo-helper
DATE=$(date +%Y%m%d%H%M)
SHA=$(git rev-parse HEAD | cut -c1-8)

# Configure rpmmacros to enable signing packages
#
echo '%_signature gpg' >> ~/.rpmmacros
echo '%_gpg_name Distributed-CI' >> ~/.rpmmacros

# Create the proper filesystem hierarchy to proceed with srpm creatioon
#
rm -rf ${HOME}/rpmbuild
rpmdev-setuptree
cp ${PROJ_NAME}.spec ${HOME}/rpmbuild/SPECS/
# TODO(Goneri): we should use python setup.py sdist here instead
git archive HEAD --format=tgz --output=${HOME}/rpmbuild/SOURCES/${PROJ_NAME}-0.0.${DATE}git${SHA}.tgz
sed -i "s/VERS/${DATE}git${SHA}/g" ${HOME}/rpmbuild/SPECS/${PROJ_NAME}.spec
rpmbuild -bs ${HOME}/rpmbuild/SPECS/${PROJ_NAME}.spec

# Build the RPMs in a clean chroot environment with mock to detect missing
# BuildRequires lines.
for arch in epel-7-x86_64; do

    if [[ "$arch" == "epel-7-x86_64" ]]; then
        RPATH='el/7/x86_64'
    fi

    # NOTE(spredzy): Include the openstack repo in mock env
    #
    mkdir -p ${HOME}/.mock
    head -n -1 /etc/mock/${arch}.cfg > ${HOME}/.mock/${arch}-with-openstack-repo.cfg
    cat <<EOF >> ${HOME}/.mock/${arch}-with-openstack-repo.cfg
[centos-openstack-mitaka]
name=CentOS-7 - OpenStack mitaka
baseurl=http://mirror.centos.org/centos/7/cloud/x86_64/openstack-mitaka/
gpgcheck=0
enabled=1
"""
config_opts['plugin_conf']['sign_enable'] = True
config_opts['plugin_conf']['sign_opts'] = {}
config_opts['plugin_conf']['sign_opts']['cmd'] = 'rpmsign'
config_opts['plugin_conf']['sign_opts']['opts'] = '--addsign %(rpms)s'
config_opts['use_host_resolv'] = False
config_opts['files']['etc/hosts'] = """
127.0.0.1 pypi.python.org
"""
EOF
    mkdir -p development
    mock -r ${HOME}/.mock/${arch}-with-openstack-repo.cfg rebuild --resultdir=development/${RPATH} ${HOME}/rpmbuild/SRPMS/${PROJ_NAME}*
done
