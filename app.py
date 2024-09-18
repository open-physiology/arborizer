import json
from datetime import timedelta
from flask import Flask, render_template, request, redirect, session, url_for, flash
from scripts.mysql_connector import MySQLConnector
from scripts.node import Node
from flask_toastr import Toastr

app = Flask(__name__)
app.config['SESSION_PERMANENT'] = True
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=24)
app.secret_key = '***REMOVED***'
toastr = Toastr(app)

login = json.load(open('./credentials/api_mysql_db.json', 'r'))
db_name, db_user, db_pwd, db_server, db_port, user_access = (login.values())

mysql_db = None
vessel_map_all = {}
branches = []
groups = {}
root = {}
vessels = []
versions = []
included_options = []


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
    global mysql_db, vessel_map_all, branches, groups, root, vessels, included_options

    included_options = mysql_db.query_included()
    vessel_map_all = mysql_db.query_vascular_nodes_map()
    branches = mysql_db.query_vascular_edges()
    groups = {}
    node_map = {}
    include_set = set()
    for entry in included_options:
        if entry["included"]:
            include_set.add(entry["fmaID"])
    # print("Included:", include_set)

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
                "order": 0, "branch": branch["id"], 'disabled': branch["disabled"]
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
                "connector": 1, "order": order, "branch": branch["id"],
                "included": 1 if branch["source_fma"] in include_set else 0,
            }

            lyph_id = "lyph-" + branch["target"]

            lnk2_id = "lnk-" + m_id + "_" + t_id
            lnk2 = {
                "id": lnk2_id, "conveyingLyph": lyph_id, "source": m_id, "target": t_id, "fmaID": branch["target_fma"],
                "color": color, "group": group_id, "branch": branch["id"],
                "included": 1 if branch["target_fma"] in include_set else 0, 'disabled': branch["disabled"]
            }

            tree.append(lnk1)
            tree.append(lnk2)

            prev_m_id = m_id

        prev_s_id = s_id

    nodes = {}
    root_id = "all"
    root = Node(root_id, "All", None)
    nodes[root.id] = root
    loose_roots = {}
    root_parents = {}
    for edge in tree:
        if not edge["source"] in nodes:
            edge_copy = edge.copy()
            if "connector" in edge_copy:
                del edge_copy["connector"]
            parent = Node(edge["source"], node_map[edge["source"]]["name"], edge_copy)
            nodes[parent.id] = parent
            loose_roots[parent.id] = parent
        parent = nodes[edge["source"]]
        child = parent.child(edge["target"], node_map[edge["target"]]["name"], edge)
        nodes[child.id] = child
        if child.id in loose_roots:
            root_parents[child.id] = child
    for key in loose_roots:
        if key in root_parents:
            root_parents[key].children = loose_roots[key].children
        else:
            root.add_child(loose_roots[key])


def update_tree():
    global mysql_db, root, vessels, versions
    mysql_db = MySQLConnector(db_name, db_user, db_pwd, db_server, db_port)
    create_tree()
    vessels = get_vascular_targets(vessel_map_all, branches)
    versions = mysql_db.query_versions()
    authorized = session.get('logged_in')
    return render_template('index.html', data=json.dumps(root.as_dict()), groups=groups,
                           vessels=vessels, includedOptions=included_options, authorized=authorized, versions=versions)


@app.route('/')
def index():
    return update_tree()


@app.route('/login', methods=["GET", "POST"])
def login():
    user_pwd = request.form['password']
    if user_pwd == user_access:
        session['logged_in'] = True
        flash("Thanks, you can now edit the dataset! Do not forget to save your changes.", 'success')
    else:
        flash("Wrong password, please try again!", 'error')
    return redirect(url_for("index"))


@app.route('/logout', methods=["GET", "POST"])
def logout():
    session.pop('logged_in', None)
    return redirect(url_for("index"))


@app.route('/edit', methods=['GET', 'POST'])
def edit():
    if session.get('logged_in'):
        global mysql_db, root, vessels
        mysql_db = MySQLConnector(db_name, db_user, db_pwd, db_server, db_port)

        actions = json.loads(request.form['actions'])
        include = json.loads(request.form['include'])
        exclude = json.loads(request.form['exclude'])

        error_msg = mysql_db.execute_actions(actions, include, exclude)
        if not error_msg:
            flash("Changes saved!", 'success')
        else:
            flash(error_msg, 'error')
    else:
        flash("You are not authorized to alter the database! Please, login!", 'error')
    return redirect(url_for("index"))


@app.route('/restore', methods=['GET', 'POST'])
def restore():
    if session.get('logged_in'):
        try:
            global mysql_db, root, vessels
            mysql_db = MySQLConnector(db_name, db_user, db_pwd, db_server, db_port)
            version = request.form['version']
            # backup = request.form['backup']
            # if backup:
            #     mysql_db.create_backup("NK", "Auto before restore from " + version_id)
            if version:
                mysql_db.restore_from_backup(version)
                flash("Main table restored from the backup!", 'success')
            else:
                flash("No version identifier is provided!", 'error')
        except Exception as e:
            flash("Failed to restore the data!", 'error')
            print(e)
    else:
        flash("You are not authorized to alter the database! Please, login!", 'error')
    return redirect(url_for("index"))


@app.route('/backup', methods=['GET', 'POST'])
def backup():
    if session.get('logged_in'):
        try:
            global mysql_db, root, vessels
            mysql_db = MySQLConnector(db_name, db_user, db_pwd, db_server, db_port)
            user = request.form['user']
            comment = request.form['comment']
            timestamp = mysql_db.create_backup(user, comment)
            flash("Created backup with timestamp: " + timestamp, 'success')
        except Exception as e:
            flash("Backup failed: " + e, 'error')
    else:
        flash("You are not authorized to alter the database! Please, login!", 'error')
    return redirect(url_for("index"))


if __name__ == '__main__':
    app.run(debug=True)
    session.pop('logged_in', None)
