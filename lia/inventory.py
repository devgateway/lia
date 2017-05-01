import logging, json

from ldap3 import ObjectDef, Reader

from .connection import ldap_connect
from .config import get_config, MissingConfigValue

_log = logging.getLogger(__name__)

_ldap = ldap_connect()
_cfg = get_config()

class NotFoundError(Exception):
    def __init__(self, items):
        self.items = items

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

        # parse vars values

    def __repr__(self):
        return json.dumps(self.vars, indent = 2)

    def __str__(self):
        return self.name

class Inventory:
    _host_def = ObjectDef(schema = _ldap,
            object_class = _cfg.hosts.objectclass)
    # attributes to request from LDAP
    _host_attr_name = _cfg.hosts.attr.name
    _host_attr_var = _cfg.hosts.attr.var
    _host_attr = [_host_attr_name, _host_attr_var]

    def __init__(self, host_name = None):
        self._hosts_by_name = {}
        self._hosts_by_dn = {}
        self._host_names = set()
        self._host_dns = set()

        # as we load hosts
        self._hosts_by_name[host.name] = host
        self._hosts_by_dn[host.dn] = host

    def __iter__(self):
        yield from self._hosts_by_dn.values()

    def _load(cls, dn): # TODO
        """Create Host instance from DN."""

        reader = Reader(connection = _ldap,
                base = dn,
                object_def = cls._host_def,
                sub_tree = False)
        entries = reader.search_object(attributes = cls._host_attr)

        return cls(entries[0])

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

        new_names = list(set(names) - self._host_names)
        found = set()

        batch_size = 2000
        _log.debug("Searching for %i hosts, %i at a time" % (len(new_names), batch_size))

        for start in new_names[::batch_size]:
            end = start + batch_size
            _log.debug("Searching for hosts from %i to %i" % (start, end))
            batch = new_names[start:end]

            query = _cfg.hosts.attr + ":" + ";".join(batch)

            reader = Reader(connection = _ldap,
                    query = query,
                    base = _cfg.hosts.base,
                    object_def = __class__._host_def,
                    sub_tree = sub)

            try:
                size = _cfg.page
            except MissingConfigValue:
                size = 100

            entries = reader.search_paged(attributes = cls._host_attr, paged_size = size)
            for entry in entries:
                host = self._add_host(entry)
                found.add(host.name)

        missing = set(new_names) - found
        if missing:
            raise NamesNotFoundError(missing)

