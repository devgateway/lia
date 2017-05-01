import logging, json

from ldap3 import ObjectDef, Reader

from .connection import ldap_connect
from .config import get_config, MissingConfigValue

_log = logging.getLogger(__name__)

_ldap = ldap_connect()
_cfg = get_config()

class Host:
    _by_name = {}
    _by_dn = {}
    _object_def = ObjectDef(schema = _ldap,
            object_class = _cfg.hosts.objectclass)
    # attributes to request from LDAP
    _attr_name = _cfg.hosts.attr.name
    _attr_var = _cfg.hosts.attr.var
    _attr = [_attr_name, _attr_var]

    @classmethod
    def get(cls, name = None, dn = None):
        """Factory to instantiate hosts or return loaded ones."""

        if name:
            try:
                host = cls._by_name[name]
            except KeyError:
                host = cls._find(name)
                cls._by_name[name] = host
                cls._by_dn[host._dn] = host
        elif dn:
            try:
                host = cls._by_dn[dn]
            except KeyError:
                host = cls._load(dn)
                cls._by_name[host.name] = host
                cls._by_dn[dn] = host
        else:
            raise ValueError("Either host name or DN required")

        return host

    @classmethod
    def _load(cls, dn):
        """Create Host instance from DN."""

        reader = Reader(connection = _ldap,
                base = dn,
                object_def = cls._object_def,
                sub_tree = False)
        entries = reader.search_object(attributes = cls._attr)

        return cls(entries[0])

    @classmethod
    def _find(cls, name):
        """Create Host instance from common name."""

        query = _cfg.hosts.attr + ":" + name

        try:
            sub = _cfg.hosts.scope.lower() == "sub"
        except MissingConfigValue:
            sub = True

        reader = Reader(connection = _ldap,
                query = query,
                base = _cfg.hosts.base,
                object_def = object_def,
                sub_tree = sub)

        try:
            size = _cfg.page
        except MissingConfigValue:
            size = 100

        entries = reader.search_paged(attributes = cls._attr, paged_size = size)
        for entry in entries:
            return cls(entry)

    def __init__(self, entry):
        self._dn = entry.entry_dn

        # select a consistent name value, if there are several

        # parse vars values

    def __repr__(self):
        return json.dumps(self.vars, indent = 2)

class Inventory:

    def __init__(self):
        pass
