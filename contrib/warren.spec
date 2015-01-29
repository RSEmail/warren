%define py_basever %{nil}

%if 0%{?centos_version} == 505 || 0%{?rhel_version} == 505
%define py_basever 26
%global __python /usr/bin/python2.6
%global python_sitelib /usr/lib/python2.6/site-packages
%endif


Name:           warren
Version: 0.1.3
Release: 18%{?dist}
Summary:        Utility for managing a cluster of RabbitMQ nodes.
Group:          Applications/System

License:        MIT
URL:            https://github.com/icgood/warren
Source:         warren-%{version}.tar.gz
BuildRoot:      %{_tmppath}/%{name}-%{version}-%{release}-buildroot

BuildArch:      noarch
BuildRequires:  python%{py_basever}, python%{py_basever}-setuptools
Requires:       python%{py_basever}, python%{py_basever}-setuptools

%description
Utility for managing a cluster of RabbitMQ nodes.

%prep
%setup -q -n warren-%{version}

%build
%{__python} setup.py build

%install
%{__python} setup.py install --single-version-externally-managed --root %{buildroot}

%pre

%files
%defattr(-,root,root,-)
%{python_sitelib}/warren*
/usr/bin/warren

%changelog
* Wed Apr 02 2014 Justin Witrick <github@thewitricks.com> 20140402-1
- Updated spec for el5 builds

* Tue Mar 04 2014 Ian Good <icgood@gmail.com> 20140304-1
- Initial spec
