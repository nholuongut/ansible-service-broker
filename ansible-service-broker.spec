%if 0%{?fedora} || 0%{?rhel} >= 6
%global with_devel 1
%global with_bundled 0
%global with_debug 0
%global with_check 0
%global with_unit_test 0
%else
%global with_devel 0
%global with_bundled 0
%global with_debug 0
%global with_check 0
%global with_unit_test 0
%endif

%if 0%{?with_debug}
%global _dwz_low_mem_die_limit 0
%else
%global debug_package %{nil}
%endif

%global provider github
%global provider_tld com
%global project openshift
%global repo ansible-service-broker
%global openshift_release latest

%global provider_prefix %{provider}.%{provider_tld}/%{project}/%{repo}
%global import_path %{provider_prefix}

%global gopath /usr/share/gocode

%if 0%{?copr}
%define build_timestamp .%(date +"%Y%m%d%H%M%%S")
%else
%define build_timestamp %{nil}
%endif

%define selinux_variants targeted
%define moduletype apps
%define modulename ansible-service-broker

Name: %{repo}
Epoch: 1
Version: 1.4.5
Release: 1%{build_timestamp}%{?dist}
Summary: Ansible Service Broker
License: ASL 2.0
URL: https://%{provider_prefix}
Source0: https://%{provider_prefix}/archive/%{name}-%{version}.tar.gz

# e.g. el6 has ppc64 arch without gcc-go, so EA tag is required
#ExclusiveArch: %%{?go_arches:%%{go_arches}}%%{!?go_arches:%%{ix86} x86_64 % {arm}}
ExclusiveArch: %{ix86} x86_64 %{arm} aarch64 ppc64le %{mips} s390x
BuildRequires: golang

Requires(pre): shadow-utils
Requires: %{name}-selinux

BuildRequires: device-mapper-devel
BuildRequires: btrfs-progs-devel
%if ! 0%{?with_bundled}
%endif

%description
%{summary}

%package -n automation-broker-apb-role
Summary: APB Role for the broker
BuildArch: noarch

%description -n automation-broker-apb-role
APB role for the broker

%package container-scripts
Summary: scripts required for running ansible-service-broker in a container
BuildArch: noarch

%description container-scripts
containers scripts for ansible-service-broker

%package selinux
Summary: selinux policy module for %{name}
BuildRequires: checkpolicy, selinux-policy-devel, hardlink, policycoreutils
BuildRequires: /usr/bin/pod2man
Requires(post): /usr/sbin/semodule, /sbin/restorecon, /usr/sbin/setsebool, /usr/sbin/selinuxenabled, /usr/sbin/semanage
Requires(post): policycoreutils-python
Requires(post): selinux-policy-targeted
Requires(postun): /usr/sbin/semodule, /sbin/restorecon
BuildArch: noarch

%description selinux
selinux policy module for %{name}

%post selinux
for selinuxvariant in %{selinux_variants}
do
  /usr/sbin/semodule -s ${selinuxvariant} -i \
    %{_datadir}/selinux/${selinuxvariant}/%{modulename}.pp.bz2 > /dev/null
done

%postun selinux
if [ $1 -eq 0 ] ; then
  for selinuxvariant in %{selinux_variants}
  do
    /usr/sbin/semodule -s ${selinuxvariant} -r %{modulename} > /dev/null
  done
fi

%pre
getent group ansibleservicebroker || groupadd -r ansibleservicebroker
getent passwd ansibleservicebroker || \
  useradd -r -g ansibleservicebroker -d /var/lib/ansibleservicebroker -s /sbin/nologin \
  ansibleservicebroker
exit 0

%post
%systemd_post %{name}.service

%postun
%systemd_postun

%if 0%{?with_devel}
%package devel
Summary: %{summary}
BuildArch: noarch

Requires: golang
Requires: device-mapper-devel
Requires: btrfs-progs-devel

%description devel
devel for %{name}
%{import_path} prefix.
%endif

%if 0%{?with_unit_test} && 0%{?with_devel}
%package unit-test
Summary: Unit tests for %{name} package
BuildRequires: golang

%if 0%{?with_check}
#Here comes all BuildRequires: PACKAGE the unit tests
#in %%check section need for running
%endif

# test subpackage tests code from devel subpackage
Requires: %{name}-devel = %{version}-%{release}

%description unit-test
unit-test for %{name}
%endif

%prep
%setup -q -n %{repo}-%{version}
%if !0%{?copr}
patch -p1 < downstream.patch
%endif

ln -sf vendor src
mkdir -p src/github.com/openshift/ansible-service-broker
cp -r pkg src/github.com/openshift/ansible-service-broker

%build
export GOPATH=$(pwd):%{gopath}
go build -tags "seccomp selinux" -ldflags "-s -w" ./cmd/broker
go build -tags "seccomp selinux" -ldflags "-s -w" ./cmd/migration
go build -tags "seccomp selinux" -ldflags "-s -w" ./cmd/dashboard-redirector

#Build selinux modules
# create selinux-friendly version from VR and replace it inplace
perl -i -pe 'BEGIN { $VER = join ".", grep /^\d+$/, split /\./, "%{version}.%{release}"; } s!\@\@VERSION\@\@!$VER!g;' extras/%{modulename}.te

%if 0%{?rhel} >= 6
    distver=rhel%{rhel}
%endif
%if 0%{?fedora} >= 18
    distver=fedora%{fedora}
%endif

for selinuxvariant in %{selinux_variants}
do
    pushd extras
    make NAME=${selinuxvariant} -f /usr/share/selinux/devel/Makefile DISTRO=${distver}
    bzip2 -9 %{modulename}.pp
    mv %{modulename}.pp.bz2 %{modulename}.ppbz2.${selinuxvariant}
    make NAME=${selinuxvariant} -f /usr/share/selinux/devel/Makefile clean DISTRO=${distver}
    popd
done


rm -rf src

%install
install -d -p %{buildroot}%{_bindir}
install -p -m 755 broker %{buildroot}%{_bindir}/asbd
install -p -m 755 migration %{buildroot}%{_bindir}/migration
install -p -m 755 dashboard-redirector %{buildroot}%{_bindir}/dashboard-redirector
# broker apb
mkdir -p %{buildroot}/opt/apb/ %{buildroot}/opt/ansible/roles/automation-broker-apb
mv ansible_role/playbooks %{buildroot}/opt/apb/actions
mv ansible_role/defaults ansible_role/files ansible_role/tasks ansible_role/templates ansible_role/vars %{buildroot}/opt/ansible/roles/automation-broker-apb
sed -i "s/\(broker_image_tag:\).*/\1 %{openshift_release}/" \
    %{buildroot}/opt/ansible/roles/automation-broker-apb/defaults/main.yml
sed -i "s/\(broker_dockerhub_tag:\).*/\1 %{openshift_release}/" \
    %{buildroot}/opt/ansible/roles/automation-broker-apb/defaults/main.yml
install -p -m 755 build/entrypoint.sh %{buildroot}%{_bindir}/entrypoint.sh
install -d -p %{buildroot}%{_sysconfdir}/%{name}
install -p -m 644 etc/example-config.yaml %{buildroot}%{_sysconfdir}/%{name}/config.yaml
install -d -p %{buildroot}%{_libexecdir}/%{name}
cp -r scripts/* %{buildroot}%{_libexecdir}/%{name}
install -d -p %{buildroot}%{_unitdir}
install -p extras/%{name}.service  %{buildroot}%{_unitdir}/%{name}.service
install -d -p %{buildroot}%{_var}/log/%{name}
touch %{buildroot}%{_var}/log/%{name}/asb.log

# install selinux policy modules
for selinuxvariant in %{selinux_variants}
  do
    install -d %{buildroot}%{_datadir}/selinux/${selinuxvariant}
    install -p -m 644 extras/%{modulename}.ppbz2.${selinuxvariant} \
        %{buildroot}%{_datadir}/selinux/${selinuxvariant}/%{modulename}.pp.bz2
  done

# install interfaces
install -d %{buildroot}%{_datadir}/selinux/devel/include/%{moduletype}
install -p -m 644 extras/%{modulename}.if %{buildroot}%{_datadir}/selinux/devel/include/%{moduletype}/%{modulename}.if

# hardlink identical policy module packages together
/usr/sbin/hardlink -cv %{buildroot}%{_datadir}/selinux

# source codes for building projects
%if 0%{?with_devel}
install -d -p %{buildroot}/%{gopath}/src/%{import_path}/
# find all *.go but no *_test.go files and generate devel.file-list
for file in $(find . -iname "*.go" \! -iname "*_test.go" | grep -v "^./Godeps") ; do
    echo "%%dir %%{gopath}/src/%%{import_path}/$(dirname $file)" >> devel.file-list
    install -d -p %{buildroot}/%{gopath}/src/%{import_path}/$(dirname $file)
    cp -pav $file %{buildroot}/%{gopath}/src/%{import_path}/$file
    echo "%%{gopath}/src/%%{import_path}/$file" >> devel.file-list
done
for file in $(find . -iname "*.proto" | grep -v "^./Godeps") ; do
    echo "%%dir %%{gopath}/src/%%{import_path}/$(dirname $file)" >> devel.file-list
    install -d -p %{buildroot}/%{gopath}/src/%{import_path}/$(dirname $file)
    cp -pav $file %{buildroot}/%{gopath}/src/%{import_path}/$file
    echo "%%{gopath}/src/%%{import_path}/$file" >> devel.file-list
done
%endif

# testing files for this project
%if 0%{?with_unit_test} && 0%{?with_devel}
install -d -p %{buildroot}/%{gopath}/src/%{import_path}/
# find all *_test.go files and generate unit-test.file-list
for file in $(find . -iname "*_test.go" | grep -v "^./Godeps"); do
    echo "%%dir %%{gopath}/src/%%{import_path}/$(dirname $file)" >> devel.file-list
    install -d -p %{buildroot}/%{gopath}/src/%{import_path}/$(dirname $file)
    cp -pav $file %{buildroot}/%{gopath}/src/%{import_path}/$file
    echo "%%{gopath}/src/%%{import_path}/$file" >> unit-test.file-list
done
%endif

%if 0%{?with_devel}
sort -u -o devel.file-list devel.file-list
%endif

%check
%if 0%{?with_check} && 0%{?with_unit_test} && 0%{?with_devel}
%if ! 0%{?with_bundled}
export GOPATH=%{buildroot}/%{gopath}:%{gopath}
%else
export GOPATH=%{buildroot}/%{gopath}:$(pwd)/Godeps/_workspace:%{gopath}
%endif

%if ! 0%{?gotest:1}
%global gotest go test
%endif

# FAIL: TestFactoryNewTmpfs (0.00s), factory_linux_test.go:59: operation not permitted
#%%gotest %%{import_path}/libcontainer
%gotest %{import_path}/libcontainer/cgroups
# --- FAIL: TestInvalidCgroupPath (0.00s)
#  apply_raw_test.go:16: couldn't get cgroup root: mountpoint for cgroup not found
#  apply_raw_test.go:25: couldn't get cgroup data: mountpoint for cgroup not found
#%%gotest %%{import_path}/libcontainer/cgroups/fs
%gotest %{import_path}/libcontainer/configs
%gotest %{import_path}/libcontainer/devices
# undefined reference to `nsexec'
#%%gotest %%{import_path}/libcontainer/integration
%gotest %{import_path}/libcontainer/label
# Unable to create tstEth link: operation not permitted
#%%gotest %%{import_path}/libcontainer/netlink
# undefined reference to `nsexec'
#%%gotest %%{import_path}/libcontainer/nsenter
%gotest %{import_path}/libcontainer/selinux
%gotest %{import_path}/libcontainer/stacktrace
#constant 2147483648 overflows int
#%%gotest %%{import_path}/libcontainer/user
#%%gotest %%{import_path}/libcontainer/utils
#%%gotest %%{import_path}/libcontainer/xattr
%endif

#define license tag if not already defined
%{!?_licensedir:%global license %doc}

%files
%license LICENSE
%{_bindir}/asbd
%{_bindir}/migration
%{_bindir}/dashboard-redirector
%attr(750, ansibleservicebroker, ansibleservicebroker) %dir %{_sysconfdir}/%{name}
%attr(640, ansibleservicebroker, ansibleservicebroker) %config %{_sysconfdir}/%{name}/config.yaml
%{_unitdir}/%{name}.service
%{_libexecdir}/%{name}
%attr(750, ansibleservicebroker, ansibleservicebroker) %dir %{_var}/log/%{name}
%attr(640, ansibleservicebroker, ansibleservicebroker) %{_var}/log/%{name}/asb.log

%files -n automation-broker-apb-role
/opt/apb/actions
/opt/ansible/roles

%files container-scripts
%{_bindir}/entrypoint.sh

%files selinux
%attr(0600,root,root) %{_datadir}/selinux/*/%{modulename}.pp.bz2
%{_datadir}/selinux/devel/include/%{moduletype}/%{modulename}.if

%if 0%{?with_devel}
%files devel -f devel.file-list
%license LICENSE
%dir %{gopath}/src/%{provider}.%{provider_tld}/%{project}
%dir %{gopath}/src/%{import_path}
%endif

%if 0%{?with_unit_test} && 0%{?with_devel}
%files unit-test -f unit-test.file-list
%license LICENSE
%endif

%changelog
* Mon Feb 11 2019 jesus m. rodriguez <jesusr@redhat.com> 1.4.5-1
- Bump bundle-lib release to 0.2.17 (#1180) (jmrodri@gmail.com)
- Use new operator (#1175) (dzager@redhat.com)
- Nit fixes (erik@nsk.io)
- Add operator config doc (erik@nsk.io)

* Fri Feb 01 2019 Jason Montleon <jmontleo@redhat.com> 1.4.4-1
- Adding 2018-11-27 meeting notes (#1176) (jmrodri@gmail.com)
- Tweaks (erik@nsk.io)
- Add more operator related RBAC (erik@nsk.io)
- Explicitly set kubeconfig on lookups (erik@nsk.io)
- Add missing operator env vars (erik@nsk.io)
- Bump csv version (#1170) (dzager@redhat.com)
- Fix typo (erik@nsk.io)
- Add missing task name (erik@nsk.io)
- Disable reconcile period (erik@nsk.io)
- Redeploy broker on config changes (erik@nsk.io)
- Add configurable registries (erik@nsk.io)
- Add OLM support to new operator (erik@nsk.io)
- Use old operator builds until new one stabalizes (erik@nsk.io)
- bundle-lib 0.2.16 release (erik@nsk.io)
- Simple fixes (david.j.zager@gmail.com)
- Rewrite asb operator for operator-sdk (david.j.zager@gmail.com)
- Update container names for 311 back compat (erik@nsk.io)
- Update test to use non openshift prefixed ns (erik@nsk.io)
- Update dr & asb route names for 311 (erik@nsk.io)
- Update svc and route name for 311 backwards compat (erik@nsk.io)
- Update dc for 311 compat (erik@nsk.io)
- Update for 311 backwards compat (erik@nsk.io)
- Use 3.11 version of asb image (david.j.zager@gmail.com)
- Put all the olm bits in olm-catalog (david.j.zager@gmail.com)
- Add install modes (david.j.zager@gmail.com)
- Add operator csv (#1160) (dzager@redhat.com)
- Update OWNERS (ernelson@redhat.com)
- Add Derek to OWNERS file (erik@nsk.io)
- Fix ansible assertion syntax (#1159) (dzager@redhat.com)
- Revert "Add ASB operator deployment manifest assets." (#1156)
  (dzager@redhat.com)
- Check for truthy since these values are always defined
  (david.j.zager@gmail.com)
- Update operator Dockerfile to use AO master, add subresource in CRD
  (derekwhatley@gmail.com)
- Make it possible to run tests only (jmontleo@redhat.com)
- Add Dockerfile link to prepare for automated downstream builds
  (jmontleo@redhat.com)
- Fix downstream container builds (jmontleo@redhat.com)
- Fix operator image and add "IMAGE" environment variable.
  (derekwhatley@gmail.com)
- Move ASB operator manifests from /manifests/0.1.0 to /manifests
  (derekwhatley@gmail.com)
- Fix ASB catalogsource configmap (derekwhatley@gmail.com)
- Change name/source values in CatalogSource and Subscription
  (derekwhatley@gmail.com)
- Add ASB operator 0.1.0 deployment manifest assets. (derekwhatley@gmail.com)
- Update operator playbook to use IMAGE from environment (#1150)
  (dzager@redhat.com)
- Check if ca-bundle configmap already exists to avoid contention with cert-
  signer operator (#1147) (derekwhatley@gmail.com)
- Fix caBundle population for 4.0 deploys (#1146) (derekwhatley@gmail.com)

* Tue Dec 04 2018 Jason Montleon <jmontleo@redhat.com> 1.4.3-1
- Add epoch to package (#1141) (jmontleo@redhat.com)
- Filter to bool when waiting for broker (#1140) (dzager@redhat.com)
- Clean up .travis.yml and remove duplicate tests (#1133) (jmontleo@redhat.com)
- Add djzager to OWNERS (#1134) (dzager@redhat.com)
- Add jmontleon to OWNERS (#1132) (jmontleo@redhat.com)
- Fix operator lint task in openshift CI (#1131) (jmontleo@redhat.com)
- Automation Broker meeting 20181113 (#1129) (jmrodri@gmail.com)
- add linting for operator role (#1128) (jmontleo@redhat.com)
- Set OLM_MANAGED to true by default in the operator Dockerfile (#1127)
  (jmontleo@redhat.com)
- Operator should use meta from AO (#1126) (dzager@redhat.com)
- Remove unused asbcli. (#1125) (jmrodri@gmail.com)
- 2018-10-30 Automation Broker IRC meeting logs (#1124) (jmrodri@gmail.com)
- 1062 - disallow the SAME UUID for instance and bindings (#1081)
  (jmrodri@gmail.com)

* Thu Oct 25 2018 jesus m. rodriguez <jmrodri@gmail.com> 1.4.2-1
- Bug 1643303 - Update to bundle-lib 0.2.15 to fix net-policy issue (#1111) (jmrodri@gmail.com)
- Fix kubernetes test failures (#1118) (jmontleo@redhat.com)
- Fix APB/Operator ansible task order. (#1116) (jmontleo@redhat.com)
- Use 3.11 instead of latest for ansible-service-broker image (#1108) (jmontleo@redhat.com)
- Additional OLM support (#1106) (ernelson@redhat.com)
- Get golint changed upstream. (#1109) (bas.meijer@me.com)
- Fix deploy template default value (#1103) (jmontleo@redhat.com)
- Fix Makefile (#1101) (jmontleo@redhat.com)
- Fix canary, use same tag for canary/nightly broker and apb's (#1100) (jmontleo@redhat.com)
- Automation broker meeting logs 10/02/2018 (#1099) (jmrodri@gmail.com)
- Fix v3.10 automation-broker-apb Dockerfile (#1095) (jmontleo@redhat.com)
- add v3.9 Dockerfile (#1093) (jmontleo@redhat.com)
- Fix dockerfile typo (#1091) (jmontleo@redhat.com)
- Update rpm spec and add apb Dockerfiles (#1090) (jmontleo@redhat.com)
- Fix RPM build (#1086) (ernelson@redhat.com)
- Add broker operator support (#1078) (ernelson@redhat.com)
- Disable travis kube until it can be fixed (#1085) (ernelson@redhat.com)
- Add dockerfiles for old releases (#1084) (jmontleo@redhat.com)
- Use the 4.0 releaser branch (#1080) (jmrodri@gmail.com)

* Tue Sep 11 2018 jesus m. rodriguez <jmrodri@gmail.com> 1.4.1-1
- Prepare for 1.4 release (#1079) (jmrodri@gmail.com)
- add operation and param validation (#1077) (jmrodri@gmail.com)
- Disable keeping namespace on error in ASB (#1075) (jmontleo@redhat.com)

* Fri Sep 07 2018 Dylan Murray <dymurray@redhat.com> 1.3.17-1
- Bump bundle-lib release to 0.2.14 (#1074) (dymurray@redhat.com)
- Add 2018-09-04 meeting notes (#1069) (jmrodri@gmail.com)
- Bug 1625809 - accept quoted apb argument (#1072) (ernelson@redhat.com)

* Tue Sep 04 2018 Dylan Murray <dymurray@redhat.com> 1.3.16-1
- Bump bundle-lib release to 0.2.13 (#1070) (dymurray@redhat.com)

* Thu Aug 30 2018 Dylan Murray <dymurray@redhat.com> 1.3.15-1
- Update bundle-lib release to 0.2.12 (#1068) (dymurray@redhat.com)
- Prevent deprovision of brokers with instances (#1067) (ernelson@redhat.com)
- Default to NOT deleting shared broker resources (#1066) (ernelson@redhat.com)

* Tue Aug 28 2018 Dylan Murray <dymurray@redhat.com> 1.3.14-1
- Update bundle-lib to 0.2.11 (#1065) (dymurray@redhat.com)
- use the new osb prefix (#1064) (jmrodri@gmail.com)
- Fix downstream patch for capabilities check (#1063) (jmontleo@redhat.com)

* Tue Aug 28 2018 Dylan Murray <dymurray@redhat.com> 1.3.13-1
- Check for capabilities instead of openshift during APB install (#1060)
  (jmontleo@redhat.com)
- Bug 1622491 - Use fully qualified downstream image (#1061)
  (ernelson@redhat.com)

* Wed Aug 22 2018 David Zager <david.j.zager@gmail.com> 1.3.12-1
- Bug 1615787 - Make a registry configurable via apb (#1057)
  (dzager@redhat.com)

* Tue Aug 21 2018 Dylan Murray <dymurray@redhat.com> 1.3.11-1
- Update source0 in rpm spec (#1055) (dymurray@redhat.com)

* Tue Aug 21 2018 Dylan Murray <dymurray@redhat.com> 1.3.10-1
- Bug 1581106 - Add bind labels to extcred secret (#1054) (ernelson@redhat.com)
- Fix broker rpm spec (#1053) (dzager@redhat.com)
- Add 2018-08-21 meeting notes (#1052) (jmrodri@gmail.com)
- Bug 1615723 - check for not found ext creds (#1051) (jmrodri@gmail.com)
- Bug 1615787 - Add APB Spec to Broker APB (#1048) (dzager@redhat.com)
- Bug 1610714 - pass bindingid to unbind jobs (#1050) (jmrodri@gmail.com)

* Wed Aug 15 2018 David Zager <david.j.zager@gmail.com> 1.3.9-1
- Add bundle-lib metrics registration (#1034) (ernelson@redhat.com)
- Update bundle-lib (#1045) (dzager@redhat.com)
- Fix broker route to line up with service (#1043) (dzager@redhat.com)
- Bug 1599522 - Include skip_verify_tls doc info for registries (#1040)
  (dymurray@redhat.com)
- fix coverage to fail when tests fail (#1038) (jmrodri@gmail.com)

* Fri Aug 10 2018 David Zager <david.j.zager@gmail.com> 1.3.8-1
- Standardize broker endpoints (#1029) (dzager@redhat.com)
- Add mock for the call to DeleteExtractedCredential (#1039)
  (jmrodri@gmail.com)
- Add route timeout annotation (#1033) (jmontleo@redhat.com)
- Bug 1583503 Always run updates (#1032) (jmontleo@redhat.com)
- Add 2018-08-07 meeting notes (#1031) (jmrodri@gmail.com)

* Mon Aug 06 2018 David Zager <david.j.zager@gmail.com> 1.3.7-1
- Bug 1583587 - lower loglevel to debug, wrap others (#1030)
  (jmrodri@gmail.com)
- Bug 1577797 - call flag...Parse to prevent logging error (#1027)
  (jmrodri@gmail.com)
- Bug 1585951 - Delete prov creds on deprovision (#1024) (ernelson@redhat.com)
- remove newline from version log (#1026) (jmrodri@gmail.com)

* Tue Jul 31 2018 David Zager <david.j.zager@gmail.com> 1.3.6-1
- Update galaxy-adapter to include galaxy URL (#1023) (dzager@redhat.com)
- update for quay adapter (#1002) (jkim@redhat.com)
- Add galaxy adapter (#1016) (dzager@redhat.com)
- Add namespaced broker docs (#1021) (ernelson@redhat.com)
- update obj form definition (#954) (2183506+odra@users.noreply.github.com)
- Improve logging when wait_for_broker fails (#1020) (dzager@redhat.com)
- Show broker version in logs for easier debugging (#1017) (jmrodri@gmail.com)
- 938 - remove run_template from docs (#1018) (jmrodri@gmail.com)
- add documentation for API v2 adapter usage (#1003) (jkim@redhat.com)
- include FQName in spec logging, ID isn't useful enough (#1022)
  (jmrodri@gmail.com)

* Mon Jul 23 2018 David Zager <david.j.zager@gmail.com> 1.3.5-1
- Enhance spec reconciliation, using async bootstrap (#1008)
  (alay1431@gmail.com)
- Add tag field to ASB registry configuration doc (#1012)
  (mario.loriedo@gmail.com)
- Add ns broker support to the broker's apb (#1015) (ernelson@redhat.com)
- Broker apb rpm (#1014) (dzager@redhat.com)
- remove golang macros (#1011) (jmontleo@redhat.com)
- Fix default APB_IMAGE (#1013) (ernelson@redhat.com)
- removing subject rules review auth and using aggregated rules. (#995)
  (smhurley00@gmail.com)
- Add parsing of param dependencies (#928) (pgough@redhat.com)
- Automation Broker meeting 7/10/2018 (#1004) (jmrodri@gmail.com)
- Simple ci (#1005) (dzager@redhat.com)
- Use broker-apb test playbook to test the broker (#990) (dzager@redhat.com)
- Use docker cp instead of mounting host volume (#1000) (dzager@redhat.com)
- Add IRC meeting notes (#1001) (jmrodri@gmail.com)
- Update docs for helm adapter (#998) (dzager@redhat.com)
- adds docs and plumbing for the skip_verify_tls setting on the rhcc adapter
  (#989) (mhrivnak@hrivnak.org)
- Support building a debuggable image for development (#926)
  (pgough@redhat.com)

* Wed Jun 20 2018 David Zager <david.j.zager@gmail.com> 1.3.4-1
- Login for deploy on tag (#994) (dzager@redhat.com)

* Tue Jun 19 2018 David Zager <david.j.zager@gmail.com> 1.3.3-1
- Use travis_tag on tag builds (#993) (dzager@redhat.com)
- Add hostname to test scripts (#985) (alay1431@gmail.com)

* Tue Jun 19 2018 David Zager <david.j.zager@gmail.com> 1.3.2-1
- Pass in namespace to runtime (#991) (maleck13@users.noreply.github.com)
- adding unit tests for broker package (#983) (smhurley00@gmail.com)
- Remove tag from deployment (#988) (dzager@redhat.com)
- Fix deployment stage (#987) (dzager@redhat.com)
- Tie together container images of broker & broker-apb (#986)
  (dzager@redhat.com)
- ensure initial state set when job started. reduce repition in job
  definitions. Allow jobs to be mocked out at broker level (#909)
  (maleck13@users.noreply.github.com)

* Sun Jun 10 2018 jesus m. rodriguez <jmrodri@gmail.com> 1.3.1-1
- Bug 1585649 - wait group should be added to before go function is kicked off (#977) (smhurley00@gmail.com)
- Bug 1583064 - missing action causes many sandboxes (#972) (jmrodri@gmail.com)
- Bug 1581580 - skip if bind instance does not have credentials (#964) (smhurley00@gmail.com)
- Bug 1578319 - send _apb* parameters to unbind (#960) (jmrodri@gmail.com)
- Bug 1572129 - recover deprovision jobs (#953) (jmrodri@gmail.com)
- Bug 1576728 - Fixes multiple requests to a CR (#947) (smhurley00@gmail.com)
- Bug 1577127 - adding back metrics (#948) (smhurley00@gmail.com)
- Bug 1577144 - fixing logging so it is more clear (#949)
- Bump bundle-lib to 0.2.3 (#981) (jmrodri@gmail.com)
- reformat tables to be readable without rendering (#980) (jmrodri@gmail.com)
- remove coverage badge (jmrodri@gmail.com)
- Bundle lib 0.2 (#946) (smhurley00@gmail.com)
- Travis should run only for master/release branches (#978) (dzager@redhat.com)
- Make ci should not do deployment (#975) (dzager@redhat.com)
- Add Broker APB source to project (#939) (dzager@redhat.com)
- add v3.10 install method to README (#967) (jmontleo@redhat.com)
- Add requested parameters when not in existing service instance (#935) (dzager@redhat.com)
- Switch from go-logging to logrus (#961) (jmrodri@gmail.com)
- dep prune vendor (#962) (jmrodri@gmail.com)
- Bump version for next release (#955) (dzager@redhat.com)
- update config.md for partner registry adapter (#950) (jkim@redhat.com)
- Update releases in README (#952) (rhallise@redhat.com) (smhurley00@gmail.com)
- doc to show how to use broker via vendor (#940) (jmrodri@gmail.com)

* Thu May 10 2018 David Zager <david.j.zager@gmail.com> 1.2.11-1
- Bug 1550418 - Return op token on depro in progress (#942)
  (ernelson@redhat.com)
- bump bundle-lib to 0.1.5 (#937) (jmrodri@gmail.com)
- Allow Automation Broker to be useful when used as a dependency (#933)
  (jmrodri@gmail.com)

* Fri May 04 2018 David Zager <david.j.zager@gmail.com> 1.2.10-1
- Spell check a bunch of items (#930) (jmrodri@gmail.com)
- Add fix for get si npe (#929) (ernelson@redhat.com)
- Bug 1572470 - use binding id as instance, do not error on conflict (#924)
  (jmrodri@gmail.com)
- Bug 1572129 - remove unnecessary SetState (#927) (jmrodri@gmail.com)
- Run the apb in a different project (#923) (dzager@redhat.com)
- Remove dashboard-redirector binary (#925) (pgough@redhat.com)
- Create broker-apb dir, add install yaml (#916) (dzager@redhat.com)

* Tue May 01 2018 David Zager <david.j.zager@gmail.com> 1.2.9-1
- Bug 1565545 - Adding migration of extracted credentials (#895)
  (smhurley00@gmail.com)
- Update AA to APB in docs (#918) (ernelson@redhat.com)
- Lock helm version for ci (#915) (dzager@redhat.com)

* Fri Apr 27 2018 David Zager <david.j.zager@gmail.com> 1.2.8-1
- Frustration release target (#910) (jmrodri@gmail.com)
- Bug 1566924 - renaming crd resources (#907) (smhurley00@gmail.com)
- Bug 1533425 - protect against simultaneous updates (#898) (jmrodri@gmail.com)

* Wed Apr 25 2018 David Zager <david.j.zager@gmail.com> 1.2.7-1
- Clone into broker path (david.j.zager@gmail.com)
- Use git clone for canary (#906) (dzager@redhat.com)
- Build migration into canary image (#905) (dzager@redhat.com)
- fix statements with formatting (#904) (jmrodri@gmail.com)
- Bug 1569220 - Add dashboard redirector feature (#897) (ernelson@redhat.com)
- Update scripts to use the broker apb (#891) (dzager@redhat.com)
- Bug 1567004 - Delete extracted credentials secret during synchronous unbind.
  (#899) (derekwhatley@gmail.com)
- Fix typo in run_latest_build.sh (#903) (marko.luksa@gmail.com)

* Thu Apr 19 2018 David Zager <david.j.zager@gmail.com> 1.2.6-1
- Point to v3.9.0 release of origin (#894) (dzager@redhat.com)
- link broken - typo fixed (#892)
  (SaravanaStorageNetwork@users.noreply.github.com)
- Workaround minikube regression for travis (#890) (dzager@redhat.com)
- add copyright to migration (#888) (jmrodri@gmail.com)
- Issue 882 - Simple broker template use release-1.1 (#885) (dzager@redhat.com)
- expose _apb_service_binding_id to bind role (#883) (pbraun@redhat.com)
- Fix bug 1564542 (#881) (maleck13@users.noreply.github.com)
- Add a table to track release dates (#879) (rhallise@redhat.com)

* Fri Apr 06 2018 David Zager <david.j.zager@gmail.com> 1.2.5-1
- Changes to subscriber pattern (#828) (maleck13@users.noreply.github.com)
- Add relist docs (#873) (ernelson@redhat.com)
- Add migration command (#870) (smhurley00@gmail.com)
- Fix docs - enabling RBAC for minikube (#862) (veverka.kuba@gmail.com)
- removing config package from bundle lib. bump to new release (#860)
  (Shawn.Hurley21@gmail.com)
- make CRD the defaults for all templates (#838) (Shawn.Hurley21@gmail.com)
- make more than one stage for all the tasks we want to do. (#863)
  (Shawn.Hurley21@gmail.com)
- Warn in the logs that a spec failed to load and continue (#855)
  (rhallise@redhat.com)
- Make a not to give the developer use cluster-admin (#857)
  (rhallise@redhat.com)
- Pull the latest ansible version in travis scripts (#856)
  (rhallise@redhat.com)
- Use the correct versions (#854) (Shawn.Hurley21@gmail.com)
- Use bundle lib (#848) (Shawn.Hurley21@gmail.com)
- Add dep to travis (#849) (rhallise@redhat.com)
- make username available for APB in the serviceInstance (#832)
  (jkim@redhat.com)
- minor updates to proposal to clarify a few points (#842)
  (maleck13@users.noreply.github.com)
- Reformatted (#845) (jmrodri@gmail.com)
- Create CODE_OF_CONDUCT.md (#841) (jmrodri@gmail.com)
- Only grab the token the broker sa is using (#844) (rhallise@redhat.com)
- Display Custom Error Message for the APB via termination-log (#837)
  (jkim@redhat.com)

* Mon Mar 19 2018 David Zager <david.j.zager@gmail.com> 1.2.4-1
- Format nits (#836) (jmrodri@gmail.com)
- APB state support (#809) (maleck13@users.noreply.github.com)
- Proposal for Helm Chart Registry Adapter (#830) (dzager@redhat.com)
- pass provision credentials during deprovision (#821)
  (maleck13@users.noreply.github.com)
- make headings smaller (#831) (jmrodri@gmail.com)

* Fri Mar 09 2018 jesus m. rodriguez <jmrodri@gmail.com> 1.2.3-1
- Add a note to run latest about current user (#829) (ernelson@redhat.com)
- Default to an open localregistry policy (#827) (ernelson@redhat.com)
- return the token for a unbind in progress (#824) (Shawn.Hurley21@gmail.com)
- remove extra deletion of extracted credentials in broker package (#825) (Shawn.Hurley21@gmail.com)
- adding a blank line to the help output (#826) (jmrodri@gmail.com)
- Add breadcrumbs to release notes (#820) (david.j.zager@gmail.com)
- switching dependency management from glide to dep (#817) (Shawn.Hurley21@gmail.com)
- Document the Broker's versioning strategy (#810) (david.j.zager@gmail.com)
- parameterize dao:type. Defaults to etcd (#816) (jmrodri@gmail.com)
- Adds Service Bundle contract document (#808) (mhrivnak@hrivnak.org)
- Removing links to older fusor GH org (#814) (matzew@apache.org)
- Initial pass at proposal to change subscribers (#727) (maleck13@users.noreply.github.com)
- Broker client dao (#795) (Shawn.Hurley21@gmail.com)
- Force canary image be built from master (#805) (david.j.zager@gmail.com)
- parameterize the 'ansible-service-broker' namespace with the NAMESPACE variable (#800) (jkim@redhat.com)
- Bug 1550385 - Add .default to proxy docs NO_PROXY (#807) (ernelson@redhat.com)
- Remove tmp note re: minishift-addon (#802) (ernelson@redhat.com)
- Broker client vendor update (#794) (Shawn.Hurley21@gmail.com)
- Save extracted credentials into a secret (#775) (Shawn.Hurley21@gmail.com)
- Bug 1548311 - Return success on depro extcred miss (#791) (ernelson@redhat.com)
- Temporarily link to minishift-addons fork (#796) (ernelson@redhat.com)
- Adds docs for installing the broker in minikube. (#792) (mhrivnak@hrivnak.org)
- Filter everything when whitelist is empty (#781) (rhallise@redhat.com)

* Fri Feb 23 2018 jesus m. rodriguez <jmrodri@gmail.com> 1.2.2-1
- Bug 1539542 - return bindings_retrievable (#776) (jmrodri@gmail.com)
- Bug 1543521 - fix async bind when job already in-progress (#764) (mhrivnak@hrivnak.org)
- Bug 1541461 - Deal with buggy encoded scopes from service catalog. (#754) (Shawn.Hurley21@gmail.com)
- Bug 1543029 - last_operation returns correct body with 410 response (#746) (mhrivnak@hrivnak.org)
- Bug 1542387 - Print out status of response from RHCC registry if not 200 (#742) (dymurray@redhat.com)
- Bug 1539308 - Do not report errors on dupe depros (#739) (ernelson@redhat.com)
- Bug 1540121 - Return 400 for bad update requests (#736) (ernelson@redhat.com)
- Bug 1541335 - fix auth config parsing (#728) (jmrodri@gmail.com)
- Lock asb-brew releaser to 3.10 branch (#788) (david.j.zager@gmail.com)
- rename file to be more consistent. (#779) (jmrodri@gmail.com)
- Fix last op endpoint unbind response (#765) (pgough@redhat.com)
- apb pkg public interface overhaul (#773) (ernelson@redhat.com)
- fixing k8s ansible service broker template to include namespace config (#777) (Shawn.Hurley21@gmail.com)
- 475 last operation description (#619) (maleck13@users.noreply.github.com)
- Remove plan dao methods (#766) (Shawn.Hurley21@gmail.com)
- Proposal for saving extracted credentials (#768) (Shawn.Hurley21@gmail.com)
- Add a warning that the client is an older version (#769) (rhallise@redhat.com)
- Remove upgrade from Ubuntu 14.0 to 16.04 (#762) (rhallise@redhat.com)
- Remove minishift docs and link to golden source (#672) (ernelson@redhat.com)
- Add a mailing list subscribe badge (#758) (rhallise@redhat.com)
- Update simple-broker-template to include necessary roles for local_openshift reg (#749) (dymurray@redhat.com)
- Remove redundant validation copy (#741) (ernelson@redhat.com)
- Travis merges commits so do a diff against HEAD^ (#737) (rhallise@redhat.com)
- Make the endpoints headless for local brokers (#731) (rhallise@redhat.com)
- Fix vet test (#733) (rhallise@redhat.com)
- initial prop for custom resources. (#722) (Shawn.Hurley21@gmail.com)
- partial fix for PR #722 Work Item 1 (#725) (Shawn.Hurley21@gmail.com)

* Fri Feb 02 2018 jesus m. rodriguez <jmrodri@gmail.com> 1.2.1-1
- Bug 1541265 - avoid broker panic, check for nil (#723) (jmrodri@gmail.com)
- Bug 1538986 - Remove bad enum values from Update Request (#713) (jmontleo@redhat.com)
- Bug 1533425 - handle missing pod action error (#716) (jmrodri@gmail.com)
- Bug 1534957 - Add namespace to broker config docs (#712) (ernelson@redhat.com)
- Bug 1539757 - async unbind returns http 202 (#704) (mhrivnak@hrivnak.org)
- Bug 1537367 - fix the test for last_operation (#688) (jmrodri@gmail.com)
- No longer only search for apbs that end with -apb (#719) (rhallise@redhat.com)
- revert image back to match blog post in simple broker template. (#714) (Shawn.Hurley21@gmail.com)
- Proposes solutions for tracking state of BindInstance creation (#680) (mhrivnak@hrivnak.org)
- Check that all the containers in a pod are running (#706) (rhallise@redhat.com)
- Ignore IDE extras (#703) (ernelson@redhat.com)
- Add fall through case to deprovision handler (#700) (pgough@redhat.com)
- update copyright date to 2018 (#699) (jmrodri@gmail.com)
- Make the k8s CI scripts consumable with curl (#695) (rhallise@redhat.com)
- Adding ability for Subject Rules Review to do the correct check. (#693) (Shawn.Hurley21@gmail.com)
- Remove unecessary dao ref from DeproJob (#691) (ernelson@redhat.com)
- add a 3.10 releaser (#690) (jmrodri@gmail.com)
- bump version to 1.2 (jmrodri@gmail.com)

* Thu Jan 25 2018 jesus m. rodriguez <jmrodri@gmail.com> 1.1.8-1
- Add proxy docs (#634) (ernelson@redhat.com)
- Bug 1536629 - Send job msg immediately as job starts. (#671) (maleck13@users.noreply.github.com)
- Bug 1537367 - missing last_operation for bindings (#677) (jmrodri@gmail.com)
- Continue to load specs even when a spec fails to load (#682) (rhallise@redhat.com)
- Bug 1506978 - Include lowercase proxy vars (#683) (ernelson@redhat.com)
- One CI fix and a few improvements (#679) (rhallise@redhat.com)
- add ASB debugging guide (#676) (jkim@redhat.com)
- Bug 1536659 - bind PUT returns http code 202 when operation runs async (#669) (mhrivnak@hrivnak.org)

* Tue Jan 23 2018 Jason Montleon <jmontleo@redhat.com> 1.1.7-1
- Skip running the travis job if we're only changing docs (#678)
  (rhallise@redhat.com)
- fixes #665 - remove many of the TODOs (#673) (jmrodri@gmail.com)
- Add a second job that runs the broker on k8s (#643) (rhallise@redhat.com)
- Update test bash scripts (#668) (jmrodri@gmail.com)
- Fail faster with travis (#658) (rhallise@redhat.com)
- Remove old comment re: platform version header (#661) (ernelson@redhat.com)
- Remove ancient comment with app startup (#664) (ernelson@redhat.com)

* Fri Jan 19 2018 David Zager <david.j.zager@gmail.com> 1.1.6-1
- Bug 1536629 - send job state and credentials from job (#610)
  (maleck13@users.noreply.github.com)
- Bug 1536088 - fixes panic when bind can't find ServiceInstance (#653)
  (mhrivnak@hrivnak.org)
- Fix linting on ProxyConfig (#662) (ernelson@redhat.com)
- Bug 1534957 - Fix secret parameters regression (#659) (ernelson@redhat.com)
- make build-image isn't retrying (#656) (rhallise@redhat.com)
- Add some missing networking permissions to the k8s template (#657)
  (rhallise@redhat.com)
- Bug 1535182 - adding ability to retrieve an array of subconfigs (#655)
  (Shawn.Hurley21@gmail.com)
- Bug 1506978 - Apply proxy settings to running APBs (#654)
  (ernelson@redhat.com)
- Bug 1535652 - return 200 to bind PUT when a binding already exists (#650)
  (mhrivnak@hrivnak.org)
- Bug 1534715 - Moves BindInstance retrieval and error handling to handler.go
  (#648) (mhrivnak@hrivnak.org)
- Bug 1534467 - apiserver was not told how to output error response (#647)
  (Shawn.Hurley21@gmail.com)
- Print information on any pod failures (#646) (rhallise@redhat.com)
- vendor bump to k8s 1.9.1 (#645) (Shawn.Hurley21@gmail.com)

* Tue Jan 16 2018 David Zager <david.j.zager@gmail.com> 1.1.5-1
- Bug 1534715 - unbind checks for existence of binding before trying to delete
  it (#642) (mhrivnak@hrivnak.org)
- quiet errors related to docker0 address (#641) (Shawn.Hurley21@gmail.com)
- Bug 1526949 - Set registry user/pass if auth_type is not defined (#635)
  (dymurray@redhat.com)
- Openshift Multi-tenant Sandbox Hooks (#600) (Shawn.Hurley21@gmail.com)
- Async bind feature (#625) (jmrodri@gmail.com)
- Fix debug statement for ISV registry to be more verbose (#633)
  (dymurray@redhat.com)
- Add minishift documentation (#627) (ernelson@redhat.com)
- Update config doc to document storing creds in a secret (#628)
  (dymurray@redhat.com)
- Bug 588 - Run latest build with a default public ip. (#626)
  (Shawn.Hurley21@gmail.com)
- Bug 1533208 - Re adding registry auth as secrets and files (#629)
  (Shawn.Hurley21@gmail.com)
- fixing handler tests in master branch (#630) (Shawn.Hurley21@gmail.com)
- uses "exec" so bash process gets replaced instead of retained (#624)
  (mhrivnak@hrivnak.org)
- Bug 1472226 - Add additional field validations for JSON Schema. (#615)
  (cchase@redhat.com)
- fixes typo in a log statement (#622) (mhrivnak@hrivnak.org)
- Add 3.8/3.9 releasers to tito (#620) (david.j.zager@gmail.com)

* Mon Jan 08 2018 David Zager <david.j.zager@gmail.com> 1.1.4-1
- Use the router prefix for apb tool endpoints (#616) (rhallise@redhat.com)
- Bug 1526887 - Handle case when whitelist/blacklist set to "" (#609)
  (Shawn.Hurley21@gmail.com)
- Bug 617 - fixing issue with versioning the rbac API. (#618)
  (Shawn.Hurley21@gmail.com)
- fix potential nil pointer panic (#613) (maleck13@users.noreply.github.com)
- fix incorrect check in if statement (#611)
  (maleck13@users.noreply.github.com)
- Bug 1512042 - Allowing error messages to make it from apb to user. (#607)
  (Shawn.Hurley21@gmail.com)
- The config should only use type as a key when name does not exist. (#606)
  (Shawn.Hurley21@gmail.com)
- Remove WorkMsg interface to avoid unneeded marshalling and
  unmarshalling.(#604) (maleck13@users.noreply.github.com)
- remove the different job msg types to avoid duplication of code (#603)
  (maleck13@users.noreply.github.com)

* Thu Dec 21 2017 Jason Montleon <jmontleo@redhat.com> 1.1.3-1
- Fixes labels on asb Endpoint in local dev template (#598)
  (mhrivnak@hrivnak.org)
- Adding local openshift adapter (#601) (matzew@apache.org)
- allows parameter types to be case-insensitive (#599) (mhrivnak@hrivnak.org)
- Execute into a pod with API for runtime V1 (#596) (Shawn.Hurley21@gmail.com)
- Simple template to support my blog post (#597) (jmrodri@gmail.com)
- Bug 1525817 - remove duplicate help output and return 0 exit code. (#594)
  (cchase@redhat.com)
- stop multiple update apb containers from launching (#595)
  (jmontleo@redhat.com)
- Initial proposal for dealing with network isolation SDNs (#572)
  (Shawn.Hurley21@gmail.com)
- Remove logging from function and structs. (#582) (Shawn.Hurley21@gmail.com)
- Upgrading dependancies to K8s 1.8.5 (#589) (Shawn.Hurley21@gmail.com)
- Change the python path to /usr/bin/env (#591) (rhallise@redhat.com)
- Notify the apb what cluster it's running on with extravars (#577)
  (rhallise@redhat.com)
- Make prep-local explicit and update docs (#587) (ernelson@redhat.com)
- Bug 1510486 - Return 403 for disallowed actions (#586)
  (Shawn.Hurley21@gmail.com)
- Resolve runtime version from local openshift (#581) (david.j.zager@gmail.com)
- fixes a typo and clarifies the name of "kube-service-catalog" (#583)
  (mhrivnak@hrivnak.org)
- Adding ability to warn and filter out bad specs. (#571)
  (Shawn.Hurley21@gmail.com)
- Remove unused ocLogin function (#580) (rhallise@redhat.com)
- fixes README to reflect behavioral changes (#578) (mhrivnak@hrivnak.org)
- Config impl (#567) (Shawn.Hurley21@gmail.com)
- Identify the cluster in the NewRuntime call (#574) (rhallise@redhat.com)

* Mon Dec 04 2017 Jason Montleon <jmontleo@redhat.com> 1.1.2-1
- Broker should extract credentials from secret (#555)
  (david.j.zager@gmail.com)

* Mon Dec 04 2017 Jason Montleon <jmontleo@redhat.com> 1.1.1-1
- docs and ci template updates for apb name changes (#573)
  (jmontleo@redhat.com)
- Use the rbac API when creating and deleting policy (#556)
  (rhallise@redhat.com)
- Few fixes to the local deploy templates (#568) (rhallise@redhat.com)
- Give cluster client the log object (#565) (rhallise@redhat.com)
- Rebase k8s templates to pickup etcd name change (#563) (rhallise@redhat.com)
- Create a Kubernetes Client struct (#561) (rhallise@redhat.com)
- Update vendor directory (#562) (rhallise@redhat.com)
- First pass at last_operation description proposal (#537)
  (maleck13@users.noreply.github.com)
- Pull apb templates from their respective git repos (#560)
  (rhallise@redhat.com)
- adding ability to connnect over SSL w/o authentication. (#558)
  (Shawn.Hurley21@gmail.com)
- Update copr link in Makefile comments (#559) (jmontleo@redhat.com)
- Integrate a new ci framework for travis (#463) (rhallise@redhat.com)
- Use the Kubernetes API for namespaces check (#552) (rhallise@redhat.com)
- using table driven testing (#551) (jmrodri@gmail.com)
- Setup tls support for k8s deployments (#496) (rhallise@redhat.com)
- Proposal to improve bind credential extraction (#550)
  (david.j.zager@gmail.com)
- Expose the pod name/namespace to APB (#546) (david.j.zager@gmail.com)
- remove unneeded paragraph from license header (#549) (jmrodri@gmail.com)
- Integrate with coveralls for code coverage (#548) (jmrodri@gmail.com)
- Create release notes script to grab changes (#545) (david.j.zager@gmail.com)
- bump version for next release (#547) (jmrodri@gmail.com)

* Tue Nov 07 2017 David Zager <david.j.zager@gmail.com> 1.0.19-1
- Bug 1507111 - Do not force image tag to be IP + Port (#540)
  (dymurray@redhat.com)

* Mon Nov 06 2017 jesus m. rodriguez <jesusr@redhat.com> 1.0.18-1
- Bug 1507111 - Update docs and example configs for local openshift adapter (#538) (dymurray@redhat.com)
- Improve logging for missing tags (#536) (rhallise@redhat.com)

* Mon Nov 06 2017 Jason Montleon <jmontleo@redhat.com> 1.0.17-1
- Attempting fix for image name. (#539) (Shawn.Hurley21@gmail.com)

* Mon Nov 06 2017 Jason Montleon <jmontleo@redhat.com>
- Attempting fix for image name. (#539) (Shawn.Hurley21@gmail.com)

* Fri Nov 03 2017 jesus m. rodriguez <jesusr@redhat.com> 1.0.15-1
- Bug 1504927 - if apbs fail, mark them as failed. (#534) (jmrodri@gmail.com)
- Bug 1507111 - Add support for a local OpenShift Registry adapter (#527) (dymurray@redhat.com)
- Bug 1476173 - Cleanup deleting namespaces (#529) (cchase@redhat.com)
- Bug 1501523 - Add spec plan to image during apb push (#533) (dymurray@redhat.com)
- Look for the url in the proper place (#535) (rhallise@redhat.com)
- Setting generated local dev template to autoescalate: false (#532) (cchase@redhat.com)
- setting default value for the deployment template. (#528) (Shawn.Hurley21@gmail.com)

* Thu Nov 02 2017 Shawn Hurley <shurley@redhat.com> 1.0.14-1
- Bug 1507617 - Adding SSL and Authentication to etcd (#522)
  (Shawn.Hurley21@gmail.com)
- grep for correct asb-token for local dev. (#526) (cchase@redhat.com)
- Changing the default for auto escalate to false (#503)
  (Shawn.Hurley21@gmail.com)
- Bug 1502044 - add buffer size and work_engine test (#510) (jmrodri@gmail.com)
- add ServiceClassID and ServiceInstanceID parameters during provision and bind
  (#515) (maleck13@users.noreply.github.com)
- when building the broker for image also build for linux OS. (#525)
  (Shawn.Hurley21@gmail.com)
- Call the correct service-catalog namespace (#524) (rhallise@redhat.com)
- Remove checks for DOCKER_USER and DOCKER_PASSWORD (#523)
  (rhallise@redhat.com)

* Mon Oct 30 2017 Jason Montleon <jmontleo@redhat.com> 1.0.13-1
- Bug 1503289 - Move registry credentials to a secret (#502)
  (dymurray@redhat.com)

* Mon Oct 30 2017 Jason Montleon <jmontleo@redhat.com> 1.0.12-1
- Bug 1476173 - Skip deprovision if the namespace is being deleted since we
  (#520) (cchase@redhat.com)
- Bug 1506713 - handle updatable enum parameters properly in schema output
  (#517) (jmontleo@redhat.com)
- Bug 1504250 - Keep listening for deprovision messages (#508)
  (david.j.zager@gmail.com)
- Bug 1504957 - Broker should use recreate strategy (#511)
  (david.j.zager@gmail.com)
- Bug 1504729 - Log job state when getting last op (#505)
  (david.j.zager@gmail.com)
- update resource field names (#519) (jmontleo@redhat.com)
- Adding docs for prometheus. (#507) (Shawn.Hurley21@gmail.com)
- accept update with bad params and log warnings instead of erroring (#516)
  (jmontleo@redhat.com)
- Fix gate for Openshift 3.7 (#513) (jmontleo@redhat.com)

* Mon Oct 23 2017 Jason Montleon <jmontleo@redhat.com> 1.0.11-1
- Update schema for instance-update (#444) (jmontleo@redhat.com)
- remove trailing spaces from supporting files (#493) (jmrodri@gmail.com)
- Look at the apbs in the catalog for a matching name when creating a secret
  (#438) (fabian@fabianism.us)
- Adding prometheus metrics for ASB (#497) (Shawn.Hurley21@gmail.com)
- Bug 1499622 - Return 202 if provisioning job is in progress (#498)
  (dymurray@redhat.com)
- Bug 1503233 - Add liveness and readiness checks to ASB dc (#500)
  (dymurray@redhat.com)
- Bug 1502044 - deprovision fixes (#494) (david.j.zager@gmail.com)
- Bug 1501523 - Set plan name for APB push sourced specs (#495)
  (dymurray@redhat.com)
- Bug 1497839 - copy secrets to transient namespace and always run (#473)
  (Shawn.Hurley21@gmail.com)
- Fix api auth for ci test (#492) (jmontleo@redhat.com)

* Fri Oct 13 2017 Jason Montleon <jmontleo@redhat.com> 1.0.10-1
- Move the gate to 3.7 (#489) (rhallise@redhat.com)
- Bug 1497766 - Adding ablity to specify keeping namespace alive (#474)
  (Shawn.Hurley21@gmail.com)
- Bug 1496572 - Clean up error message for invalid registry credentials. (#490)
  (Shawn.Hurley21@gmail.com)
- Update secrets docs to account for new fqname. (#487) (fabian@fabianism.us)

* Thu Oct 12 2017 jesus m. rodriguez <jmrodri@gmail.com> 1.0.9-1
- Bug 1500930 - Prevent multiple deprovision pods from spawning (#488) (ernelson@redhat.com)
- Bug 1501512 - bind issue when multiple calls to create the same binding (#486) (Shawn.Hurley21@gmail.com)
- Update deployment template to match latest service-catalog in origin (#485) (jwmatthews@gmail.com)

* Wed Oct 11 2017 jesus m. rodriguez <jmrodri@gmail.com> 1.0.8-1
- Bug 1500934 - Dynamic broker ns for secrets (#482) (ernelson@redhat.com)
- Bug 1500048 - make plan ids globally unique (#480) (jmrodri@gmail.com)
- Add troubleshooting documentation to the broker (#479) (david.j.zager@gmail.com)
- Bug 1498954 - Broker in developer mode must support apb push (#476) (david.j.zager@gmail.com)
- Bug 1498933 - Do not delete apb-push sourced specs when bootstrapping (#477) (dymurray@redhat.com)
- Bug 1498992 - Ansible Service Broker template should default (#478) (david.j.zager@gmail.com)
- Bug 1498618 - Support bind parameters. (#467) (cchase@redhat.com)
- Update run_latest_build w/ origin latest default (#471) (david.j.zager@gmail.com)
- Creating proposals for keeping transient namespace alive (#464) (Shawn.Hurley21@gmail.com)

* Wed Oct 04 2017 Jason Montleon <jmontleo@redhat.com> 1.0.7-1
- Bug 1498185 - Adjust versioning check so that it is done in the registry
  package (#468) (dymurray@redhat.com)

* Wed Oct 04 2017 Jason Montleon <jmontleo@redhat.com> 1.0.6-1
- Bug 1497819 - Broker should not rely on image field of APB yaml (#433)
  (david.j.zager@gmail.com)
- Bug 1498203 - Extracted Credentials were leaking into new bindings (#469)
  (Shawn.Hurley21@gmail.com)
- add 3.7 releaser to releasers.conf (#465) (jmrodri@gmail.com)
- Provide an environment variable to deploy latest with run_latest_build (#466)
  (karimboumedhel@gmail.com)
- Pass in args to the deploy scripts (#462) (rhallise@redhat.com)
- Make the prep_local_devel_env script work for Kubernetes & Openshift (#434)
  (rhallise@redhat.com)
- Bearer auth documentation (#460) (Shawn.Hurley21@gmail.com)
- Split the deploy.sh script to work with both kube & openshift (#432)
  (rhallise@redhat.com)
- Bump wait times (#461) (rhallise@redhat.com)
- changing default for 3.6 run_latest_build to function correctly (#458)
  (Shawn.Hurley21@gmail.com)
- Added versioning check to Broker on bootstrap (#457) (dymurray@redhat.com)
- fix asbcli to work with bearer auth (#455) (jmontleo@redhat.com)
- User Impersonation Implementation  (#428) (Shawn.Hurley21@gmail.com)
- Remove provision parameters from being reused as binding parameters. (#456)
  (cfc@chasenc.com)

* Tue Sep 26 2017 Jason Montleon <jmontleo@redhat.com> 1.0.5-1
- removing proposal that never happened (#450) (jmrodri@gmail.com)
- Bearer Token Auth via kubernetes Apiserver (#445) (Shawn.Hurley21@gmail.com)
- allowing the user to authenticate to retrieve private repos (#449)
  (Shawn.Hurley21@gmail.com)
- Some of the 3.6 & 3.7 gate changes are causing issues (#453)
  (rhallise@redhat.com)
- The run_latest_build script is missing an auth param (#451)
  (rhallise@redhat.com)
- Make the gate use 3.6 defaults (#446) (rhallise@redhat.com)
- The docker organization name was changed in catasb (#447)
  (rhallise@redhat.com)
- first pass at administration documentation (#430) (Shawn.Hurley21@gmail.com)
- adding ability to pass in the CA Bundle for ServiceBroker (#441)
  (Shawn.Hurley21@gmail.com)

* Tue Sep 19 2017 Jason Montleon <jmontleo@redhat.com> 1.0.4-1
- Update broker defaults for current service-catalog version (#437)
  (jmontleo@redhat.com)
- fix asbcli provision (#440) (jmontleo@redhat.com)
- pass in BROKER_KIND (#436) (jmrodri@gmail.com)
- Proposal to host static assets for APBs (#423) (cfc@chasenc.com)
- Remove image field from APB spec (#431) (david.j.zager@gmail.com)
- updating irc links to go to asbroker channel (#435)
  (Shawn.Hurley21@gmail.com)
- Default for no filter mode is to not contain a single APB. (#411)
  (Shawn.Hurley21@gmail.com)
- Kube template (#412) (rhallise@redhat.com)
- update template to support newer service-catalogs (#422)
  (jmontleo@redhat.com)
- User Impersonation (#418) (Shawn.Hurley21@gmail.com)
- Update updates-first-pass.md (#426) (ernelson@redhat.com)
- updating default values for configuration values needed. (#419)
  (Shawn.Hurley21@gmail.com)
- Force delete the mediawiki pod (#420) (rhallise@redhat.com)
- add docs for secrets (#421) (fabian@fabianism.us)
- Move variable assignment for clarity in script (#416)
  (david.j.zager@gmail.com)
- Proposal: CI Framework (#413) (rhallise@redhat.com)
- Add secret support to the Broker (#345) (fabian@fabianism.us)
- Update build to also work with Fedora 27 (#414) (jmontleo@redhat.com)
- Put the broker creation inside deploy template (#410)
  (david.j.zager@gmail.com)
- Proposals to make configuration easier to use. (#407)
  (Shawn.Hurley21@gmail.com)
- Add group titles for forms in OpenShift UI. (#409) (cfc@chasenc.com)

* Tue Aug 29 2017 Jason Montleon <jmontleo@redhat.com> 1.0.3-1
- 399 - APB Sandbox Role should be configurable (#403)
  (david.j.zager@gmail.com)
- 82 - add copyright headers to each file (#402) (jmrodri@gmail.com)
- delete line (#406) (jmrodri@gmail.com)
- make comments consistent '// ' (#405) (jmrodri@gmail.com)
- ignore the broker only at the root (#404) (jmrodri@gmail.com)
- 377 - The service name returned by asb is invalid (#380)
  (Shawn.Hurley21@gmail.com)
- Improve CONTRIBUTING guide (#389) (david.j.zager@gmail.com)
- add unbind and deprovision checks (#384) (jmontleo@redhat.com)
- Add proposal for logging changes (#381) (Shawn.Hurley21@gmail.com)
- Fixed duplicate parameter after group. (#398) (cfc@chasenc.com)
- Fix spelling in logs (#397) (david.j.zager@gmail.com)

* Thu Aug 24 2017 Jason Montleon <jmontleo@redhat.com> 1.0.2-1
- Reduce broker/apb sandbox permissions (#393) (david.j.zager@gmail.com)
- Added UI form information to metadata fields for parsing by OpenShift (#386)
  (cfc@chasenc.com)
- adding broker build to build of image. (#396) (Shawn.Hurley21@gmail.com)
- Updates first-pass proposal (#368) (ernelson@redhat.com)
- Update Dockerfile names (#382) (jmontleo@redhat.com)
- Allow dockerhub credentials to be specified as env variables without being
  written directly in the script (#392) (jason.dobies@redhat.com)
- Label APBs with their FQNames (#390) (ernelson@redhat.com)
- Added documentation update for openshift registry (#383)
  (dymurray@redhat.com)
- Form metadata proposal. (#376) (cfc@chasenc.com)
- Move the client calls to the runtime pkg (#362) (rhallise@redhat.com)

* Fri Aug 18 2017 Jason Montleon <jmontleo@redhat.com> 1.0.1-1
- rename Dockerfiles to reflect the tags being used for (#375)
  (jmontleo@redhat.com)
- bearer token proposal (#373) (jmrodri@gmail.com)
- Use origin-ansible-service-broker docker image (#371)
  (david.j.zager@gmail.com)
- Point doc readers to subscribe to mailing list (#374)
  (david.j.zager@gmail.com)
- Update version to the release instead of RC (#370) (jason.dobies@redhat.com)
- Allow PUBLIC_IP to be overridden without editing the script (#369)
  (jason.dobies@redhat.com)
- Allow specifying a tag for apbs (#357) (jmontleo@redhat.com)
- Improve user facing documentation for broker (#367) (david.j.zager@gmail.com)
- document auth configuration (#363) (jmrodri@gmail.com)
- Update Copr Releasers (#365) (jmontleo@redhat.com)
- move specs to proposals (#366) (jmrodri@gmail.com)
- Update ssl doc (#361) (jmrodri@gmail.com)
- Spell check docs (#364) (jmrodri@gmail.com)
- Fix rebase mistake (#360) (rhallise@redhat.com)
- Prevent CI failures when building the broker (#348) (rhallise@redhat.com)
- Adding documentation for ssl and tls with openshift. (#359)
  (Shawn.Hurley21@gmail.com)
- Work Topics and Deprovision Fixes (#358) (ernelson@redhat.com)
- Give make more targets for the project (#350) (david.j.zager@gmail.com)
- Fixed a few typos in docs (#356) (jwmatthews@gmail.com)
- Add basic auth switch (default off) to run_latest_build.sh (#355)
  (derekwhatley@gmail.com)
- Add local etcd support for local env (#354) (ernelson@redhat.com)
- Match template registry name (#353) (ernelson@redhat.com)
- Add an insecure option to the openshift template (#334) (rhallise@redhat.com)
- Allow the local broker to run in insecure mode (#346) (rhallise@redhat.com)
- Spec: Kubernetes and COE agnostic support (#329) (rhallise@redhat.com)
- Added openshift registry adapter (#280) (dymurray@redhat.com)
- Explicitly use project name for ASB secrets (#349) (dymurray@redhat.com)
- Handle err when generating Dockerhub token (#339) (david.j.zager@gmail.com)
- Improve CI logging (#344) (rhallise@redhat.com)
- Retry pod preset check instead of sleeping (#343) (rhallise@redhat.com)
- Updated deployment template to use string substitution when applicable (#340)
  (dymurray@redhat.com)
- Accept ints from exported credentials (#337) (ernelson@redhat.com)
- Update AddApb to use FQNames (#336) (ernelson@redhat.com)
- Adding ability to pass credentials to bind and unbind actions. (#302)
  (Shawn.Hurley21@gmail.com)
- remove trailing slash (#332) (jmrodri@gmail.com)
- Introduce authentication to the broker (#308) (jmrodri@gmail.com)
- Move travis to using make ci (#331) (rhallise@redhat.com)
- Configurable refresh interval of Broker updating specs (#326)
  (rhallise@redhat.com)
- Run the CI test locally (#317) (rhallise@redhat.com)
- updating handler to use FormValue call to retrieve data from query param
  (#327) (Shawn.Hurley21@gmail.com)
- fusor test will now print out details on the actual file that caused the
  issue. (#328) (Shawn.Hurley21@gmail.com)
- Zero param fix (#325) (ernelson@redhat.com)
- readme formatting (#323) (ttomecek@redhat.com)
- Fix the plan name in broker ci object (#321) (jmontleo@redhat.com)
- get both tls.key AND tls.crt not two tls.keys (#316) (jmrodri@gmail.com)
- Multi-plan support (#298) (ernelson@redhat.com)
- reformat the comments to be readable. (#315) (jmrodri@gmail.com)
- Contributing doc (#313) (rhallise@redhat.com)
- Add a PR and Issues template (#314) (rhallise@redhat.com)
- The broker now has two container in a single pod (#310) (rhallise@redhat.com)
- Create a spec template (#312) (rhallise@redhat.com)
- Remove bogus selinux requires in rpm spec (#311) (jmontleo@redhat.com)
- Update local scripts to run etcd with a local broker (#309)
  (dymurray@redhat.com)
- [Proposal]: New Bind and Unbind Workflow (#293) (Shawn.Hurley21@gmail.com)
- Change deployment to deploymentconfig in prep script (#307)
  (dymurray@redhat.com)
- Broker CI with Travis (#291) (rhallise@redhat.com)
- Added deployment config to broker template (#304) (dymurray@redhat.com)
- Remove usage of jq dependency (#305) (andy.block@gmail.com)
- Update the broker-ci spec to include jenkins and travis (#292)
  (rhallise@redhat.com)
- 1468173- Error out when bootstrap fails (#301)
  (fabianvf@users.noreply.github.com)
- [Proposal] Plan support (#294) (ernelson@redhat.com)
- Increase bind timeout to 2 hours (#284) (rhallise@redhat.com)
- Added a minimal run_latest_build.sh with instructions (#296)
  (jwmatthews@gmail.com)
- Updated template default values (#295) (jwmatthews@gmail.com)
- Improve the broker bind output by using error returned from RunCommand (#276)
  (rhallise@redhat.com)
- Document Image Tags in the README (#282) (rhallise@redhat.com)
- add tls files to really-clean (#290) (jmrodri@gmail.com)
- Update my_local_dev_vars.example (#289) (ernelson@redhat.com)
- HTTPS for asb route (#281) (Shawn.Hurley21@gmail.com)
- Broker CI spec (#277) (rhallise@redhat.com)
- Filtering documentation (#279) (ernelson@redhat.com)
- Downgrade ext_cred retry logs to Info (#278) (ernelson@redhat.com)
- Asbcli bind (#262) (rhallise@redhat.com)
- White/Black List Filtering and Multiple Registries Refactor (#271)
  (Shawn.Hurley21@gmail.com)
- 1470860 - Remove broker project creation (#275) (ernelson@redhat.com)
- SPEC: broker authentication spec (#260) (jmrodri@gmail.com)
- Fix lint problems (#272) (ernelson@redhat.com)
- Broker bind output rework (#124) (rhallise@redhat.com)
- 1467852 - add ENV HOME to Dockerfile#263) (#268) (jmontleo@redhat.com)
- Add bootstrap_on_startup feature (#267) (ernelson@redhat.com)
- Only print out error messages only once (#266) (rhallise@redhat.com)
- 1467905 - Added error handling for images with improper APB Spec (#259)
  (dymurray@redhat.com)
- technical debt: make scripts run from anywhere (#252) (jmrodri@gmail.com)
- 201 - remove ProjectRoot (#255) (jmrodri@gmail.com)
- Fix typos found by goreportcard. (#254) (jmrodri@gmail.com)
- Adding go report card and updating a go vet problem (#253)
  (Shawn.Hurley21@gmail.com)
- remove unused template file (#251) (jmrodri@gmail.com)
- Configurable, external broker auth support (#249) (ernelson@redhat.com)
- techdebt: fix Makefile deploy (#250) (jmrodri@gmail.com)
- Add IMAGE_PULL_POLICY to broker template (#247) (ernelson@redhat.com)
- With a newer Etcd, we can use the GetVersion function (#223)
  (rhallise@redhat.com)
- Fixes BZ#1466031 add Accept header with application/json to RHCC get (#243)
  (#246) (cfc@chasenc.com)
- Make the ImagePullPolicy Configurable (#237) (rhallise@redhat.com)
- Only Extract the Credentials once (#242) (rhallise@redhat.com)
- Automated builds from Dockerhub (#240) (rhallise@redhat.com)
- Refactor apb/client contents (#238) (ernelson@redhat.com)
- Makefile technical debt (#239) (jmrodri@gmail.com)
- Asbcli was using the wrong var name in bind (#241) (rhallise@redhat.com)
- Golint fixes (#225) (Shawn.Hurley21@gmail.com)
- removing go-dockerclient (#232) (Shawn.Hurley21@gmail.com)
- Breakup all the Broker Clients into a clients pkg (#222)
  (rhallise@redhat.com)
- remove mockregistry (#236) (jmrodri@gmail.com)
- techdebt: speed up builds (#234) (jmrodri@gmail.com)
- Cleanup local pod split (#208) (rhallise@redhat.com)
- Remove refresh login function (#197) (rhallise@redhat.com)
- * adding ability for development brokers to delete specs (#209)
  (Shawn.Hurley21@gmail.com)
- remove trailing whitespace (#226) (jmrodri@gmail.com)
- removing unnecessary function that just add's indirection. (#200)
  (Shawn.Hurley21@gmail.com)
- bump version, prepare for GA work (#224) (jmrodri@gmail.com)

* Thu Jun 22 2017 jesus m. rodriguez <jesusr@redhat.com> 0.9.4-1
- 1463798 - Fix stale APBs present in ASB after bootstrap (#221) (Shawn.Hurley21@gmail.com)
- use the correct source name in the rpm spec (#220) (jmontleo@redhat.com)

* Thu Jun 22 2017 jesus m. rodriguez <jesusr@redhat.com> 0.9.3-1
- Fixing builds and standardize on a config file name (#218) (Shawn.Hurley21@gmail.com)
- strip makefile whitespace (#210) (ernelson@redhat.com)

* Wed Jun 21 2017 jesus m. rodriguez <jesusr@redhat.com> 0.9.2-1
- use a different source url for copr (#216) (jmrodri@gmail.com)
- Expect a config file to be mounted  (#211) (fabianvf@users.noreply.github.com)

* Wed Jun 21 2017 jesus m. rodriguez <jesusr@redhat.com> 0.9.1-1
- new package built with tito (jesusr@redhat.com)
- bump version (jesusr@redhat.com)
- add version template to keep in sync with tito (#212) (jmrodri@gmail.com)
- Prepare repo for use with tito (#204) (jmrodri@gmail.com)
- Starting point for running broker local to simulate InCluster (#192) (jwmatthews@gmail.com)
- Check for empty spec dir when querying for catalog. (#195) (cfc@chasenc.com)
- Packaging fix for #171 (#191) (jmontleo@redhat.com)
- Recover jobs when broker restarted (#131) (jmrodri@gmail.com)
- implement deprovision (#172) (fabianvf@users.noreply.github.com)
- Run as arbitrary user (#146) (fabianvf@users.noreply.github.com)
- add selinux policy and update rpm spec to build the sub package (#160) (jmontleo@redhat.com)
- Updated to create/use service account for broker (#165) (jwmatthews@gmail.com)
- Add namespace parameter from service context. (#161) (cfc@chasenc.com)
- Add parameter schema support (#156) (jmrodri@gmail.com)
- Fix the APB repo url. (#163) (warmchang@outlook.com)
- Deprovison spec compliance (#117) (Shawn.Hurley21@gmail.com)
- log in with serviceaccount certs and token (#154) (fabianvf@users.noreply.github.com)
- Add Endpoint for ABP Tool to push Specs (#152) (Shawn.Hurley21@gmail.com)
- fixing bug where we attempt to deference nil parameters. (#149) (Shawn.Hurley21@gmail.com)
- Get all images (#132) (Shawn.Hurley21@gmail.com)
- better facilitate automate copr and manual brew builds (#145) (jmontleo@redhat.com)
- Added new registry adapter for RHCC (#135) (dymurray@redhat.com)
- Remove jq since PR#121 merged (#141) (rhallise@redhat.com)
- Rename fusor to openshift (#133) (jmrodri@gmail.com)
- Replace get_images_from_org (#121) (rhallise@redhat.com)
- Kubernetes client object (#115) (rhallise@redhat.com)
