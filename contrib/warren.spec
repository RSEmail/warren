Name:           warren
Version:        20140304
Release:        1%{?dist}
Summary:        Utility for managing a cluster of RabbitMQ nodes.
Group:          Applications/System

License:        MIT
URL:            https://github.com/icgood/warren
Source:         warren-%{version}.tar.gz

BuildArch:      noarch
BuildRequires:  python, python-setuptools
Requires:       python, python-setuptools

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
* Tue Mar 04 2014 Ian Good <icgood@gmail.com> 20140304-1
- Initial spec
