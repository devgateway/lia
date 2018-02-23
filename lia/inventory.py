# Copyright 2017, Development Gateway, Inc.
# This file is part of lia, see COPYING.

import logging, json

from ldap3 import ObjectDef, Reader
from ldap3.utils.dn import safe_rdn

from .connection import ldap_connect
from .config import get_config, MissingConfigValue, Config
from .tree import LdapTree
from .cache import CacheExpiredError, load_cached, cache_data

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
        name = None
        # find the attribute used in RDN
        for component in safe_rdn(entry.entry_dn, decompose = True):
            if component[0] == name_attr:
                name = component[1]
                break

        if name is None:
            # values not in RDN at all; use first name alphabetically
            name = sorted(values)[0]

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

    def get_data(self):
        return self.vars

    def __str__(self):
        return "Host %s" % self.name

class Group():
    __ungrouped = None

    def __init__(self, name, var_array):
        self._hosts = set()
        self.name = name
        self._vars = {}
        self.dn = None
        for json_vars in var_array:
            self._vars.update( json.loads(json_vars) )

    def __str__(self):
        return "Group %s" % self.name

    def get_data(self):
        data = {}

        if self._hosts:
            data["hosts"] = [host.name for host in self._hosts]

        if self._vars:
            data["vars"] = self._vars

        return data

    @classmethod
    def load_all(cls, hosts_by_name, hosts_by_dn):
        def load_groups(settings):
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

        tree = LdapTree()
        ungrouped_hosts = set(hosts_by_dn.values())
        all_groups = set()

        for settings in _cfg.groups:
            groups = load_groups( Config(settings) )
            for group in groups:
                tree.add_node(group, is_leaf = False)

        for host in hosts_by_dn.values():
            tree.add_node(host, is_leaf = True)

        for branch in tree:
            group = branch.data
            all_groups.add(group)
            try:
                group.populate_group(hosts_by_name, hosts_by_dn)
            except AttributeError:
                group.add_children(branch.descendants)

            ungrouped_hosts -= group._hosts

        # update or create special group 'ungrouped'
        # 'ungrouped' may contain hosts, but no vars
        try:
            cls.__ungrouped.name = "ungrouped"
            ungrouped = cls.__ungrouped
        except AttributeError:
            ungrouped = cls(name = "ungrouped", var_array = [])
            cls.__ungrouped = ungrouped
            all_groups.add(ungrouped)
        ungrouped._hosts |= ungrouped_hosts
        # 'ungrouped' can't have child groups
        try:
            ungrouped._groups.clear()
        except AttributeError:
            pass
        _log.debug( "%i hosts ungrouped" % len(ungrouped._hosts) )

        # move ungrouped vars to special group 'all'
        # 'all' may contain vars, but no hosts
        if ungrouped._vars:
            all = cls(name = "all", var_array = [])
            all._vars = ungrouped._vars
            ungrouped._vars = {}
            all_groups.add(all)

        return all_groups

class AttributalGroup(Group):
    def __init__(self, entry, settings):
        super().__init__(name = entry[settings.attr.name].value,
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
                self._hosts.add(host_dict[key])
            except KeyError:
                _log.warning("In group %s ignoring unknown host %s" % (self.name, key))
        msg = "%s: %i hosts" % (str(self), len(self._hosts))
        _log.debug(msg)

    def __str__(self):
        return "Attributal group '%s'" % self.name

class StructuralGroup(Group):
    def __init__(self, entry, settings):
        super().__init__(name = entry[settings.attr.name].value,
                var_array = entry[settings.attr.var].values)
        self._groups = set()

    def add_children(self, children):
        for child in children:
            if isinstance(child.data, Group):
                self._groups.add(child.data)
            else:
                self._hosts.add(child.data)
        msg = "%s: %i groups, %i hosts" % (
                str(self), len(self._groups), len(self._hosts) )
        _log.debug(msg)

    def __str__(self):
        return "Structural group '%s'" % self.name

    def get_data(self):
        data = super(__class__, self).get_data()

        if self._groups:
            data["children"] = [child.name for child in self._groups]

        return data

class Inventory:
    def __init__(self):
        try:
            self._data = load_cached()
        except CacheExpiredError:
            self._data = self._load_from_ldap()

    def _load_from_ldap(self):
        data = {}

        (hosts_by_name, hosts_by_dn) = Host.load_all()
        groups = Group.load_all(hosts_by_name, hosts_by_dn)

        for group in groups:
            group_data = group.get_data()
            if group_data:
                data[group.name] = group_data

        hostvars = {}
        data["_meta"] = {"hostvars": hostvars}

        for name, host in hosts_by_name.items():
            host_data = host.get_data()
            if host_data:
                hostvars[name] = host_data

        try:
            cache_data(data)
        except:
            pass

        return data

    def __repr__(self):
        return __class__.encode(self._data)

    @staticmethod
    def encode(data):
        return json.dumps(data, indent = 2)
