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
    base = _cfg.hosts.base

    @classmethod
    def get_one(cls, name):
        """Fetch a single host (inventory host mode)."""

        reader = Reader(connection = _ldap,
                query = cls.__attr_name + ":" + name,
                base = cls.base,
                object_def = cls.__def,
                sub_tree = sub(_cfg.hosts))

        entries = reader.search(attributes = cls.__attr)
        return cls(entries[0])

    @classmethod
    def load_all(cls):
        by_name = {}
        by_dn = {}

        reader = Reader(connection = _ldap,
                base = cls.base,
                object_def = cls.__def,
                sub_tree = sub(_cfg.hosts))

        entries = reader.search_paged(paged_size = _page_size,
                attributes = cls.__attr)
        for entry in entries:
            host = cls(entry)
            by_name[host.name] = host
            by_dn[host.dn] = host

        _log.info("Loaded %i hosts" % len(by_dn))
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
    __ungrouped = None

    def __init__(self, name, var_array):
        self.hosts = set()
        self._name = name
        self._vars = {}
        self.dn = None
        for json_vars in var_array:
            self._vars.update( json.loads(json_vars) )

    def __str__(self):
        return self._name

    def add_host(self, host):
        self.hosts.add(host)

    @classmethod
    def from_settings(cls, settings):
        groups = []

        attrs = [settings.attr.name, settings.attr.var]
        try:
            attrs.append(settings.attr.host)
            group_type = "attributal"
            new_cls = AttributalGroup
        except MissingConfigValue:
            host_attr = None
            group_type = "structural"
            new_cls = StructuralGroup

        _log.info("Loading %s groups from %s" % (group_type, settings.base))
        obj_def = ObjectDef(schema = _ldap, object_class = settings.objectclass)
        reader = Reader(connection = _ldap,
                base = settings.base,
                object_def = obj_def,
                sub_tree = sub(settings))

        entries = reader.search_paged(paged_size = _page_size, attributes = attrs)
        for entry in entries:
            group = new_cls(entry, settings)
            group.dn = entry.entry_dn
            if group.dn == Host.base:
                # if host base itself is a group, read its vars
                _log.debug("Found root group at " + group.dn)
                cls.__ungrouped = group

            try:
                group._want_dn = settings.attr.host_is_dn
            except MissingConfigValue:
                pass
            groups.append(group)

        _log.info("Loaded %i groups" % len(groups))
        return groups

    @classmethod
    def get_default_group(cls):
        if not cls.__ungrouped:
            _log.debug("Creating a default group for ungrouped hosts")
            cls.__ungrouped = __class__(name = None, var_array = {})

        cls.__ungrouped.name = "ungrouped"
        return cls.__ungrouped

class AttributalGroup(Group):
    def __init__(self, entry, settings):
        super().__init__(name = entry[settings.attr.name],
                var_array = entry[settings.attr.var].values)
        self._host_keys = entry[settings.attr.host].values
        self._want_dn = None

    def populate_group(self, by_name, by_dn):
        if self._want_dn:
            host_dict = by_dn
        else:
            host_dict = by_name

        for key in self._host_keys:
            try:
                self.add_host(host_dict[key])
            except KeyError:
                _log.warning("In group %s ignoring unknown host %s" % (self.name, key))

class StructuralGroup(Group):
    def __init__(self, entry, settings):
        super().__init__(name = entry[settings.attr.name],
                var_array = entry[settings.attr.var].values)

class Inventory:
    def __init__(self):
        self._tree = LdapTree()
        (self._hosts_by_name, self._hosts_by_dn) = Host.load_all()
        unclaimed_hosts = set(self._hosts_by_dn.values())

        for settings in _cfg.groups:
            cfg = Config(settings)
            groups = Group.from_settings(cfg)
            for group in groups:
                self._tree.add_node(group, is_leaf = False)

        for node in self._tree:
            obj = node.data
            if isinstance(obj, Group):
                try:
                    obj.populate_group(self._hosts_by_name, self._hosts_by_dn)
                except AttributeError:
                    obj.add_children(node.descendants)

                for host in obj.hosts:
                    unclaimed_hosts.remove(host)
