import json
from flask import Flask, render_template, request
from scripts.mysql_connector import MySQLConnector
from scripts.node import Node

app = Flask(__name__)

login = json.load(open('./credentials/api_mysql_db_nk.json', 'r'))
db_name, db_user, db_pwd, db_server, db_port = (login.values())

mysql_db = MySQLConnector(db_name, db_user, db_pwd, db_server, db_port)

vessel_map_all = {}
branches = []
groups = {}
root = {}
vessels = []


def get_vascular_targets(node_map, edges):
    used_set = set()
    for edge in edges:
        used_set.add(edge["source"])
        used_set.add(edge["target"])
    nodes = []
    for obj in node_map.values():
        if obj["nodeID"] not in used_set:
            nodes.append(obj)
    return nodes


def create_tree():
    global mysql_db, vessel_map_all, branches, groups, root, vessels

    vessel_map_all = mysql_db.query_vascular_nodes_map()
    branches = mysql_db.query_vascular_edges()
    groups = {}
    node_map = {}

    for branch in branches:
        s_id = branch["source"]
        t_id = branch["target"]

        # id and fmaID are the same in node map
        def create_node(x_id):
            if x_id not in node_map:
                x = vessel_map_all[x_id]
                node_map[x["nodeID"]] = {"id": x_id, "name": x["name"], "fmaID": x["fmaID"]}

        create_node(s_id)
        create_node(t_id)

    # Create links
    prev_s_id = None
    prev_m_id = None
    source_name = "origin"
    lyph_template = None

    group_id = None
    tree = []

    for branch in branches:
        s_id = branch["source"]
        t_id = branch["target"]
        sequence = branch["order"]
        order = sequence if 0 < sequence < 1000 else 0
        total = branch["total"] if "total" in branch else 1
        color = branch["color"]

        if prev_s_id == s_id:
            s = node_map[prev_m_id]
        else:
            s = node_map[s_id]
            source_name = s["name"]
            lyph_template = "wbkg:" + branch["lyph_template"] if branch["lyph_template"] else ""
            group_id = "g_" + s_id
            groups[group_id] = {"id": group_id, "name": source_name}

        t = node_map[t_id]

        # Create links
        if total == 1:
            lnk_id = "lnk-" + s["id"] + "_" + t_id
            lnk = {
                "id": lnk_id, "conveyingLyph": lyph_template, "source": s["id"], "target": t_id,
                "fmaID": t["fmaID"], "color": color, "group": group_id,
                "order": 0, "branch": branch["id"]
            }
            tree.append(lnk)
            group_id = None
        else:
            m_id = s_id + "_" + t_id
            # To ensure unique ID
            test = m_id
            count = 2
            while test in node_map:
                test = m_id + "({0})".format(count)
                count += 1
            if count > 2:
                m_id = test

            m_label = source_name + " -> " + t["name"]

            # Create connector nodes
            node_map[m_id] = {"id": m_id, "name": m_label, "fmaID": ""}

            lnk1_id = "lnk-" + s["id"] + "_" + m_id
            lnk1 = {
                "id": lnk1_id, "conveyingLyph": lyph_template, "source": s["id"], "target": m_id,
                "fmaID": branch['source_fma'], "color": color, "group": group_id,
                "connector": 1, "order": order, "branch": branch["id"]
            }

            lyph_id = "lyph-" + branch["target"]

            lnk2_id = "lnk-" + m_id + "_" + t_id
            lnk2 = {
                "id": lnk2_id, "conveyingLyph": lyph_id, "source": m_id, "target": t_id,
                "fmaID": branch["target_fma"], "color": color, "group": group_id, "branch": branch["id"]
            }

            tree.append(lnk1)
            tree.append(lnk2)

            prev_m_id = m_id

        prev_s_id = s_id

    nodes = {}
    root_id = "all"
    root = Node(root_id, "All", None)
    nodes[root.id] = root
    for edge in tree:
        if not edge["source"] in nodes:
            parent = root.child(edge["source"], node_map[edge["source"]]["name"], edge)
            nodes[parent.id] = parent
        parent = nodes[edge["source"]]
        child = parent.child(edge["target"], node_map[edge["target"]]["name"], edge)
        nodes[child.id] = child


@app.route('/')
def index():
    global mysql_db, root, vessels
    mysql_db = MySQLConnector(db_name, db_user, db_pwd, db_server, db_port)
    create_tree()
    vessels = get_vascular_targets(vessel_map_all, branches)
    return render_template('index.html', data=json.dumps(root.as_dict()), groups=groups, vessels=vessels)


@app.route('/edit', methods=['GET', 'POST'])
def edit():
    global mysql_db, root, vessels
    mysql_db = MySQLConnector(db_name, db_user, db_pwd, db_server, db_port)

    actions = json.loads(request.args.get('actions'))
    mysql_db.execute_actions(actions)

    create_tree()
    vessels = get_vascular_targets(vessel_map_all, branches)

    return render_template('index.html', data=json.dumps(root.as_dict()), groups=groups, vessels=vessels)


@app.route('/restore', methods=['GET', 'POST'])
def restore():
    global mysql_db, root, vessels
    mysql_db = MySQLConnector(db_name, db_user, db_pwd, db_server, db_port)
    mysql_db.restore_from_backup()

    create_tree()
    vessels = get_vascular_targets(vessel_map_all, branches)

    return render_template('index.html', data=json.dumps(root.as_dict()), groups=groups, vessels=vessels)


@app.route('/backup', methods=['GET', 'POST'])
def backup():
    global mysql_db, root, vessels
    mysql_db = MySQLConnector(db_name, db_user, db_pwd, db_server, db_port)
    mysql_db.create_backup()

    return render_template('index.html', data=json.dumps(root.as_dict()), groups=groups, vessels=vessels)


if __name__ == '__main__':
    app.run(debug=True)
