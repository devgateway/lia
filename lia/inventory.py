import logging, json

from ldap3 import ObjectDef, Reader
from ldap3.utils.dn import safe_rdn

from .connection import ldap_connect
from .config import get_config, MissingConfigValue, Config
from .tree import LdapTree

_log = logging.getLogger(__name__)

_ldap = ldap_connect()
_cfg = get_config()
try:
    _page_size = _cfg.page
except MissingConfigValue:
    _page_size = 100

def sub(settings):
    try:
        sub = settings.scope.lower() == "sub"
    except MissingConfigValue:
        sub = True

    return sub

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

class Host():
    __def = ObjectDef(schema = _ldap, object_class = _cfg.hosts.objectclass)
    # attributes to request from LDAP
    __attr_name = _cfg.hosts.attr.name
    __attr_vars = _cfg.hosts.attr.var
    __attr = [__attr_name, __attr_vars]
    __base = _cfg.hosts.base

    @classmethod
    def get_one(cls, name):
        """Fetch a single host (inventory host mode)."""

        reader = Reader(connection = _ldap,
                query = cls.__attr_name + ":" + name,
                base = cls.__base,
                object_def = cls.__def,
                sub_tree = sub(_cfg.hosts))

        entries = reader.search(attributes = cls.__attr)
        return cls(entries[0])

    @classmethod
    def load_all(cls):
        by_name = {}
        by_dn = {}

        reader = Reader(connection = _ldap,
                base = cls.__base,
                object_def = cls.__def,
                sub_tree = sub(_cfg.hosts))

        entries = reader.search_paged(paged_size = _page_size,
                attributes = cls.__attr)
        for entry in entries:
            host = cls(entry)
            by_name[host.name] = host
            by_dn[host.dn] = host

        return (by_name, by_dn)

    def __init__(self, entry):
        self.dn = entry.entry_dn

        # select a consistent name value, if there are several
        self.name = entry_name(entry, __class__.__attr_name)

        # parse vars values
        self.vars = {}
        for json_vars in entry[__class__.__attr_vars].values:
            self.vars.update( json.loads(json_vars) )

    def __repr__(self):
        return json.dumps(self.vars, indent = 2)

    def __str__(self):
        return self.name

class Group():
    def __init__(self, name):
        self._hosts = set()
        self._name = name
        self._vars = {}

    def __str__(self):
        return self._name

    def add_host(self, host):
        self._hosts.add(host)

    @staticmethod
    def from_settings(settings):
        groups = []

        attrs = [settings.attr.name, settings.attr.var]
        try:
            attrs.append(settings.attr.host)
            want_dn = settings.attr.host_is_dn
            group_type = "attributal"
            cls = AttributalGroup
        except MissingConfigValue:
            host_attr = None
            group_type = "structural"
            cls = StructuralGroup

        _log.info("Loading %s groups from %s" % (group_type, settings.base))
        obj_def = ObjectDef(schema = _ldap, object_class = settings.objectclass)
        reader = Reader(connection = _ldap,
                base = settings.base,
                object_def = obj_def,
                sub_tree = sub(settings))

        entries = reader.search_paged(paged_size = _page_size, attributes = attrs)
        for entry in entries:
            group = cls(entry, settings)
            groups.append(group)

        return groups

class AttributalGroup(Group):
    def __init__(self, entry, settings):
        name = entry[settings.attr.name]
        super().__init__(name)

        for json_vars in entry[settings.attr.var].values:
            self._vars.update(json.loads(json_vars))

        self._keys = entry[settings.attr.host].values

    def __iter__(self):
        return iter(self._keys)

class StructuralGroup(Group):
    def __init__(self, entry, settings):
        name = entry[settings.attr.name]
        super().__init__(name)

        for json_vars in entry[settings.attr.var].values:
            self._vars.update(json.loads(json_vars))

    def add_group(self, group):
        self._groups.add(group)

    @classmethod
    def from_entry(cls, entry, settings):
        name = entry[settings.attr.name]
        for json_vars in entry[settings.attr.var].values:
            group._vars.update(json.loads(json_vars))

class Inventory:
    def __init__(self):
        self._tree = LdapTree()
        (self._hosts_by_name, self._hosts_by_dn) = Host.load_all()

        self._groups = []
        for settings in _cfg.groups:
            cfg = Config(settings)
            self._groups.extend( Group.from_settings(cfg) )
