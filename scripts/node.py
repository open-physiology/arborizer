class Node(object):
    # generate new node
    def __init__(self, id, name, data):
        self.id = id
        self.name = name
        self.data = data
        self.children = []

    # append a child node to parent (self)
    def child(self, id, name, data):
        # check if child already exists in parent
        child_found = [c for c in self.children if c.id == id]
        if not child_found:
            # if it is a new child, create new node for this child
            _child = Node(id, name, data)
            # append new child node to parent's children list
            self.children.append(_child)
        else:
            # if the same, save this child
            _child = child_found[0]
        # return child object for later add
        return _child

    def add_child(self, node):
        child_found = [c for c in self.children if c.id == node.id]
        if not child_found:
            self.children.append(node)

    # convert the whole object to dict
    def as_dict(self):
        return {'id': self.id, 'name': self.name, 'data': self.data, 'children': [c.as_dict() for c in self.children]}
