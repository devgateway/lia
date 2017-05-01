import logging, json

from ldap3 import ObjectDef, Reader
from ldap3.utils.dn import safe_rdn

from .connection import ldap_connect
from .config import get_config, MissingConfigValue

_log = logging.getLogger(__name__)

_ldap = ldap_connect()
_cfg = get_config()
_host_attr_name = _cfg.hosts.attr.name
_host_attr_vars = _cfg.hosts.attr.var

def batch(items, batch_size = 2000):
    length = len(items)
    _log.debug("Grouping %i items in batches of %i" % (length, batch_size))
    for start in range(0, length, batch_size):
        end = start + batch_size
        yield items[start:end]

def entry_name(entry, name_attr):
    """Return consistent scalar entry common name."""

    values = entry[name_attr].values

    if len(values) == 1:
        # if there's just one value, use it
        name = values[0]
    else:
        name_vals = set(values)

        # find, if any of them are in RDN
        rdn_vals = set()
        for component in safe_rdn(entry.entry_dn, decompose = True):
            if component[0] == name_attr:
                rdn_vals.add(component[1])

        common_vals = rdn_vals & name_vals
        matched = len(common_vals)
        if matched == 1:
            # only one value used in RDN
            name = list(common_vals)[0]
        elif matched:
            # multiple values in RDN; use first of them alphabetically
            name = sorted(list(common_vals))[0]
        else:
            # none in RDN at all; use first name alphabetically
            name = sorted(list(name_vals))[0]

    return name

class NotFoundError(Exception):
    def __init__(self, items):
        self.items = list(items)

class NamesNotFoundError(NotFoundError):
    def __str__(self):
        return "Names not found: " + ", ".join(self.items)

class DNsNotFoundError(NotFoundError):
    def __str__(self):
        return "DNs not found:\n" + "\n".join(self.items)

class Host:
    def __init__(self, entry):
        self.dn = entry.entry_dn

        # select a consistent name value, if there are several
        self.name = entry_name(entry, _host_attr_name)

        # parse vars values
        self.vars = json.loads(entry[_host_attr_vars].value)

    def __repr__(self):
        return json.dumps(self.vars, indent = 2)

    def __str__(self):
        return self.name

class Inventory:
    _host_def = ObjectDef(schema = _ldap,
            object_class = _cfg.hosts.objectclass)
    # attributes to request from LDAP
    _host_attr = [_host_attr_name, _host_attr_vars]

    def __init__(self, host_name = None):
        self._hosts_by_name = {}
        self._hosts_by_dn = {}
        self._host_names = set()
        self._host_dns = set()

    def __iter__(self):
        yield from self._hosts_by_dn.values()

    def _add_host(self, entry):
        """Add host object to internal indexes."""

        host = Host(entry)

        name = host.name
        dn = host.dn
        self._hosts_by_name[name] = host
        self._hosts_by_dn[dn] = host
        self._host_names.add(name)
        self._host_dns.add(dn)

        return host

    def add_hosts_by_name(self, names):
        """Load hosts by common names."""

        try:
            sub = _cfg.hosts.scope.lower() == "sub"
        except MissingConfigValue:
            sub = True

        try:
            size = _cfg.page
        except MissingConfigValue:
            size = 100

        new_names = list(set(names) - self._host_names)
        found = set()

        for hosts in batch(new_names):
            query = _cfg.hosts.attr.name + ":" + ";".join(hosts)

            reader = Reader(connection = _ldap,
                    query = query,
                    base = _cfg.hosts.base,
                    object_def = __class__._host_def,
                    sub_tree = sub)

            entries = reader.search_paged(attributes = __class__._host_attr, paged_size = size)
            for entry in entries:
                host = self._add_host(entry)
                found.add(host.name)

        missing = set(new_names) - found
        if missing:
            raise NamesNotFoundError(missing)

    def add_hosts_by_dn(self, dns):
        """Load hosts by DN."""

        for dn in dns:
            reader = Reader(connection = _ldap,
                    base = dn,
                    object_def = __class__._host_def,
                    sub_tree = False)
            entries = reader.search_object(attributes = __class__._host_attr)

            if entries:
                self._add_host(entries[0])
            else:
                raise DNsNotFoundError([dn])
