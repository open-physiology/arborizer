# import os
import json
import csv
from flask import Flask, render_template, request
from scripts.neo4j_connector import NEO4JConnector
from scripts.node import Node

login = json.load(open('../credentials/api_neo4j_db.json', 'r'))
neo4j_address, neo4j_pwd = (login.values())

neo4j_db = NEO4JConnector(neo4j_address, "neo4j", neo4j_pwd)
fma_list = neo4j_db.query_fma()


def path():
    input_data = list(request.form.values())
    values = [x for x in input_data]

    caption = "Is there a path? "
    path = []
    source = ""
    target = ""
    root = Node('data')

    if len(values) > 1:
        source = values[0].split(':')[0]
        target = values[1].split(':')[0]
        path = neo4j_db.query_path(source, target)
        caption = 'Path between {0} and {1}'.format(source, target)

        tree = neo4j_db.query_tree(source, target)
        nodes = {}
        root = Node(tree[0]["source"])
        nodes[root.id] = root
        for edge in tree:
            parent = nodes[edge["source"]]
            child = parent.child(edge["target"])
            nodes[child.id] = child

        # print(json.dumps(root.as_dict(), indent=4))

    return render_template('index.html', caption=caption,
                           fma_list=fma_list, source=source, target=target,
                           path=path,
                           data=json.dumps(root.as_dict())
                           )