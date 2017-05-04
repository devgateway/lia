from ldap3.utils.dn import parse_dn

class NodeNotEmptyError(Exception):
    def __init__(self, path):
        self.dn = ",".join(reversed(path))

    def __str__(self):
        return "Node already added: " + self.dn

class TreePetrifiedError(Exception):
    def __str__(self):
        return "Tree has become read-only, adding nodes not permitted"

class LdapNode:
    def __init__(self, parent):
        self.parent = parent
        self.children = {}
        self.descendants = None
        self.data = None
        self.toplevel = True # TBD

class LdapTree:
    def __init__(self):
        self.__top = LdapNode(parent = None)
        self.__nodes_with_data = set()
        self.__petrified = False

    def _add_node(self, data):
        if self.__petrified:
            raise TreePetrifiedError()

        path = __class__._dn_to_path(data.dn)
        # start from top node
        node = self.__top
        toplevel = True
        # descend to destination
        for name in path:
            # select or create each node in path
            try:
                node = node.children[name]
            except KeyError:
                parent = node
                node = LdapNode(parent = parent)
                parent.children[name] = node

            # if any parent has data, child is definitely not top level
            if node.data:
                toplevel = False

        if node.data:
            raise NodeNotEmptyError(path)
        else:
            node.data = data
            node.toplevel = toplevel
            self.__nodes_with_data.add(node)

        return node

    def add_node(self, data, is_leaf):
        node = self._add_node(data)
        if not is_leaf:
            node.descendants = set()

    def __iter__(self):
        if not self.__petrified:
            self._petrify()

        return iter(self.__nodes_with_data)

    def _petrify(self):
        for node in self.__nodes_with_data:
            if node.toplevel:
                # try to prove it by traversing the tree upwards
                # and looking for possible parent
                parent = node.parent
                while True:
                    if parent == self.__top: # no parents found
                        break
                    elif parent.data and parent.descendants is not None: # found the parent
                        node.toplevel = False
                        parent.descendants.add(node)
                        break
                    else: # continue traversing
                        parent = node.parent

        self.__petrified = True

    @staticmethod
    def _dn_to_path(dn):
        """Split DN into top-down normalized node names."""

        path = []
        rdn = []

        for component in parse_dn(dn):
            rdn.append(component[0] + "=" + component[1])

            if component[2] != "+":
                path.append( "+".join(sorted(rdn)) )
                rdn.clear()

        return reversed(path)
