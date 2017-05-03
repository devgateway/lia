import logging, json

from ldap3 import ObjectDef, Reader
from ldap3.utils.dn import safe_rdn

from .connection import ldap_connect
from .config import get_config, MissingConfigValue
from .tree import LdapTree

_log = logging.getLogger(__name__)

_ldap = ldap_connect()
_cfg = get_config()

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

        try:
            sub = _cfg.hosts.scope.lower() == "sub"
        except MissingConfigValue:
            sub = True

        reader = Reader(connection = _ldap,
                query = cls.__attr_name + ":" + name,
                base = cls.__base,
                object_def = cls.__def,
                sub_tree = sub)

        entries = reader.search(attributes = cls.__attr)
        return cls(entries[0])

    @classmethod
    def load_all(cls):
        by_name = {}
        by_dn = {}

        try:
            size = _cfg.page
        except MissingConfigValue:
            size = 100

        reader = Reader(connection = _ldap,
                base = cls.__base,
                object_def = cls.__def,
                sub_tree = sub)

        entries = reader.search_paged(paged_size = size,
                attributes = cls.__attr)
        for entry in entries:
            host = cls(entry)
            by_name[host.name] = host
            by_dn[host.dn] = host

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
    def __init__(self, entry, settings):
        self._hosts = set()
        self._name = entry_name(entry, settings.attr.name)
        self._vars = {}
        for json_vars in entry[settings.attr.var].values:
            self.vars.update(json.loads(json_vars))

    def __str__(self):
        return self._name

class AttributalGroup(Group):
    def __init__(self, entry, settings, inventory):
        super().__init__(entry, settings)

        self.want_dn = settings.attr.host_is_dn
        self._keys = entry[settings.attr.host].values

    def keys(self):
        return iter(self._keys)

class StructuralGroup(Group):
    def __init__(self, entry, settings):
        super().__init__(entry, settings)

        self._children = set()

class Inventory:
    def __init__(self):
        pass
