import json
import csv
from flask import Flask, render_template, request
from scripts.mysql_connector import MySQLConnector
from scripts.node import Node

app = Flask(__name__)

login = json.load(open('./credentials/api_mysql_db.json', 'r'))
db_name, db_user, db_pwd, db_server, db_port = (login.values())
mysql_db = MySQLConnector(db_name, db_user, db_pwd, db_server, db_port)


@app.route('/')
def index():
    db_node_map = mysql_db.query_master_vascular_nodes_map()
    branches = mysql_db.query_master_vascular_edges()

    def get_label(source_name, target_name, order):
        return order + ": " + source_name + " to " + target_name

    tree = []

    # Create end nodes
    node_map = {}
    for branch in branches:
        s_id = branch["source"]
        t_id = branch["target"]

        def create_node(x_id):
            if x_id not in node_map:
                x = db_node_map[x_id]
                node_map[x["nodeID"]] = {
                    "id": x["nodeID"], "name": x["name"], "ontologyTerms": "FMA:" + x["fmaID"]}

        create_node(s_id)
        create_node(t_id)

    # Create links
    prev_s_id = None
    prev_m_id = None
    source_name = "origin"
    lyph_template = None

    group = None

    for branch in branches:
        s_id = branch["source"]
        t_id = branch["target"]
        order = str(branch["order"])
        total = branch["total"] if "total" in branch else 1
        color = branch["color"]

        if prev_s_id == s_id:
            s = node_map[prev_m_id]
        else:
            s = node_map[s_id]
            source_name = s["name"]
            lyph_template = "wbkg:" + branch["lyph_template"] if branch["lyph_template"] else ""
            group = "g_" + s_id

        t = node_map[t_id]

        # Create links
        if total == 1:
            lnk_id = "lnk-" + s["id"] + "_" + t_id
            lnk = {
                "id": lnk_id, "conveyingLyph": lyph_template, "source": s["id"], "target": t_id, "ontologyTerms": "FMA:" + t["ontologyTerms"], "color": color, "group": group
            }
            tree.append(lnk)
            group = None
        else:
            m_id = s_id + "_" + t_id
            m_label = get_label(source_name, t["name"], order)

            # Create connector nodes
            node_map[m_id] = {"id": m_id, "name": m_label, "ontologyTerms": ""}

            lnk1_id = "lnk-" + s["id"] + "_" + m_id
            lnk1 = {
                "id": lnk1_id, "conveyingLyph": lyph_template, "source": s["id"], "target": m_id,
                "ontologyTerms": "FMA:" + branch['source_fma'], "color": color, "group": group, "order": order, "connector": 1
            }

            lyph_id = "lyph-" + branch["target_fma"]

            lnk2_id = "lnk-" + m_id + "_" + t_id
            lnk2 = {
                "id": lnk2_id, "conveyingLyph": lyph_id, "source": m_id, "target": t_id,
                "ontologyTerms": "FMA:" + branch["target_fma"], "color": color, "group": group, "order": order
            }

            tree.append(lnk1)
            tree.append(lnk2)

            prev_m_id = m_id

        prev_s_id = s_id

    nodes = {}
    root_id = tree[0]["source"]
    root = Node(root_id, node_map[root_id]["name"], tree[0])
    nodes[root.id] = root
    for edge in tree:
        parent = nodes[edge["source"]]
        child = parent.child(edge["target"], node_map[edge["target"]]["name"], edge)
        nodes[child.id] = child

    return render_template('index.html', data=json.dumps(root.as_dict()))


if __name__ == '__main__':
    app.run(debug=True)
