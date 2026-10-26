import json
import os
from datetime import timedelta
from dotenv import load_dotenv
from flask import Flask, render_template, request, redirect, session, url_for, flash, g, current_app
from scripts.mysql_connector import MySQLConnector
from scripts.node import Node
from flask_toastr import Toastr
import requests

# Configuration is read from environment variables. Locally they can be placed in a .env file
# (see .env.example); on Render they are set in the service's Environment settings.
load_dotenv()

app = Flask(__name__)
app.config['SESSION_PERMANENT'] = True
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=24)
app.secret_key = os.environ.get('SECRET_KEY') or os.urandom(24)
toastr = Toastr(app)

db_name = os.environ['DB_NAME']
db_user = os.environ['DB_USER']
db_pwd = os.environ['DB_PASSWORD']
db_server = os.environ['DB_HOST']
db_port = os.environ.get('DB_PORT', '3306')
user_access = os.environ['EDITOR_PASSWORD']


def load_lyph_templates():
    try:
        lyphs = []
        url = "https://raw.githubusercontent.com/albatros13/apinatomy-models/main/wbrcm.json"
        response = requests.get(url)
        if response.status_code == 200:
            data = response.json()  # Parse JSON response
            for obj in data["lyphs"]:
                if "isTemplate" in obj and obj["isTemplate"] and "id" in obj:
                    lyphs.append({
                        "id": obj["id"],
                        "name": obj["name"] if "name" in obj else obj["id"],
                        "ontologyTerms": obj["ontologyTerms"] if "ontologyTerms" in obj else []
                    })
            return lyphs
        else:
            flash("Failed to load lyph templates!")
            print(f"Error: {response.status_code}")
    except Exception as e:
        flash("Failed to load lyph templates!")
        print(e)
    return []


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
    CLONE_SUFFIX_ID = "_XXX"
    CLONE_SUFFIX_NAME = " (clone)"

    g.included_options = g.mysql_db.query_included()
    g.groups = {}

    vessel_map_all = g.mysql_db.query_vascular_nodes_map()
    branches = g.mysql_db.query_vascular_edges()

    node_map = {}
    include_set = set()
    for entry in g.included_options:
        if entry["included"]:
            include_set.add(entry["fmaID"])
    g.vessels = get_vascular_targets(vessel_map_all, branches)

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

    def revise_id(id):
        test = id
        count = 2
        while test in node_map:
            test = id + CLONE_SUFFIX_ID + "_{0}".format(count)
            count += 1
        if count > 2:
            return test
        return id

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
            g.groups[group_id] = {"id": group_id, "name": source_name}

        t = node_map[t_id]

        # Create links
        if total == 1:
            lnk_id = "lnk-" + s["id"] + "_" + t_id
            lnk = {
                "id": lnk_id, "conveyingLyph": lyph_template, "source": s["id"], "target": t_id,
                "fmaID": t["fmaID"], "color": color, "group": group_id,
                "order": 0, "branch": branch["id"], "disabled": branch["disabled"], "vesselType": branch["vessel_type"]
            }
            tree.append(lnk)
            group_id = None
        else:
            m_id = s_id + "_" + t_id
            # To ensure unique ID
            m_id = revise_id(m_id)

            m_label = source_name + " -> " + t["name"]

            # Create connector nodes
            node_map[m_id] = {"id": m_id, "name": m_label, "fmaID": ""}

            lnk1_id = "lnk-" + s["id"] + "_" + m_id
            lnk1 = {
                "id": lnk1_id, "conveyingLyph": lyph_template, "source": s["id"], "target": m_id,
                "fmaID": branch['source_fma'], "color": color, "group": group_id,
                "connector": 1, "order": order, "branch": branch["id"],
                "included": 1 if branch["source_fma"] in include_set else 0, "vesselType": branch["vessel_type"]
            }

            lyph_template2 = "wbkg:" + branch["target_lyph_template"] if branch["target_lyph_template"] else "lyph-" + branch["target"]

            lnk2_id = "lnk-" + m_id + "_" + t_id
            lnk2 = {
                "id": lnk2_id, "conveyingLyph": lyph_template2, "source": m_id, "target": t_id, "fmaID": branch["target_fma"],
                "color": color, "group": group_id, "branch": branch["id"],
                "included": 1 if branch["target_fma"] in include_set else 0, 'disabled': branch["disabled"],
                "vesselType": branch["vessel_type"]
            }

            tree.append(lnk1)
            tree.append(lnk2)

            prev_m_id = m_id

        prev_s_id = s_id

    nodes = {}
    root_id = "all"
    g.root = Node(root_id, "All", None)
    nodes[g.root.id] = g.root
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

        # Create node clones for loops
        x = edge["target"]
        if x in nodes and x not in loose_roots:
            edge_copy = edge.copy()
            edge_copy["clone"] = True
            clone_id = revise_id(edge["target"])
            clone_name =  node_map[x]["name"] + CLONE_SUFFIX_NAME
            node_map[clone_id] = {"id": clone_id, "name": clone_name, "fmaID": node_map[x]["fmaID"]}
            child = parent.child(clone_id, clone_name, edge_copy)
        else:
            child = parent.child(edge["target"], node_map[x]["name"], edge)
        nodes[child.id] = child
        if child.id in loose_roots:
            root_parents[child.id] = child
    for key in loose_roots:
        if key in root_parents:
            root_parents[key].children = loose_roots[key].children
        else:
            g.root.add_child(loose_roots[key])


@app.route('/')
def index():
    if 'mysql_db' not in g or not g.mysql_db.is_connected():
        g.mysql_db = MySQLConnector(db_name, db_user, db_pwd, db_server, db_port)
    create_tree()
    lyph_templates = load_lyph_templates()
    versions = g.mysql_db.query_versions()
    authorized = session.get('logged_in')
    return render_template('index.html', data=json.dumps(g.root.as_dict()), groups=g.groups,
                           vessels=g.vessels, includedOptions=g.included_options,
                           authorized=authorized, versions=versions,
                           lyphTemplates=lyph_templates)


@app.route('/login', methods=["GET", "POST"])
def login():
    user_pwd = request.form['password']
    if user_pwd == user_access:
        session['logged_in'] = True
        flash("Thanks, you can now edit the dataset! Do not forget to save your changes.", 'success')
    else:
        flash("Wrong password, please try again!", 'error')
    return redirect(url_for("index"))


@app.route('/commit_api', methods=["GET", "POST"])
def commit_api():
    if session.get('logged_in'):
        flash("You are allowed to commit the generated model...", 'success')
    else:
        flash("You are not authorized to commit to the ApiNATOMY repository! Please, login!", 'error')
    return redirect(url_for("index"))


@app.route('/logout', methods=["GET", "POST"])
def logout():
    session.pop('logged_in', None)
    return redirect(url_for("index"))


@app.route('/edit', methods=['GET', 'POST'])
def edit():
    if session.get('logged_in'):
        if 'mysql_db' not in g or not g.mysql_db.is_connected():
            g.mysql_db = MySQLConnector(db_name, db_user, db_pwd, db_server, db_port)

        actions = json.loads(request.form['actions'])
        include = json.loads(request.form['include'])
        exclude = json.loads(request.form['exclude'])
        update = json.loads(request.form['update'])

        error_msg = g.mysql_db.execute_actions(actions, include, exclude, update)
        if not error_msg:
            flash("Changes saved!", 'success')
        else:
            flash(error_msg, 'error')
    else:
        flash("You are not authorized to alter the database! Please, login!", 'error')
    return redirect(url_for("index"))


@app.route('/create', methods=['GET', 'POST'])
def create():
    if session.get('logged_in'):
        try:
            if 'mysql_db' not in g or not g.mysql_db.is_connected():
                g.mysql_db = MySQLConnector(db_name, db_user, db_pwd, db_server, db_port)
            external = request.form['externalID'].strip()
            name = request.form['createName'].strip()
            vessel_type = request.form['bloodType']
            if len(external) == 0 or len(name) == 0 or not vessel_type:
                flash("Cannot add the vessel: not all parameters are specified", 'error')
            vessel_id = g.mysql_db.create_vessel(external, name, vessel_type)
            if vessel_id is None:
                flash("Failed to add the vessel: a vessel with such external ID ({0}) already exists!".format(external), 'error')
            else:
                flash("Vessel created: " + str(vessel_id), 'success')
        except Exception as e:
            flash("Failed to add the vessel!", 'error')
            print(e)
    else:
        flash("You are not authorized to alter the database! Please, login!", 'error')
    return redirect(url_for("index"))


@app.route('/delete', methods=['GET', 'POST'])
def delete():
    if session.get('logged_in'):
        try:
            if 'mysql_db' not in g or not g.mysql_db.is_connected():
                g.mysql_db = MySQLConnector(db_name, db_user, db_pwd, db_server, db_port)
            # external_id = request.args.get('externalID')
            external = request.form['externalID']
            ok_to_delete = g.mysql_db.can_delete_vessel(external)
            if ok_to_delete:
                is_deleted = g.mysql_db.delete_vessel(external)
                if is_deleted:
                    flash("Vessel deleted: " + external, 'success')
                else:
                    flash("Something went wrong: no such vessel is in the DB!", 'warning')
            else:
                flash("Cannot delete vessel " + external + ". Please remove it from the network or back-ups." )
        except Exception as e:
            flash("Failed to delete the vessel!", 'error')
            print(e)
    else:
        flash("You are not authorized to alter the database! Please, login!", 'error')
    return redirect(url_for("index"))


@app.route('/delete_version', methods=['GET', 'POST'])
def delete_version():
    if session.get('logged_in'):
        if 'mysql_db' not in g or not g.mysql_db.is_connected():
            g.mysql_db = MySQLConnector(db_name, db_user, db_pwd, db_server, db_port)
        version = request.form['versionID']
        try:
            g.mysql_db.delete_backup(version)
            flash("Backup deleted: " + version, 'success')
        except Exception as e:
            flash("Failed to delete the backup: " + version, 'error')
    else:
        flash("You are not authorized to alter the database! Please, login!", 'error')
    return redirect(url_for("index"))


@app.route('/restore', methods=['GET', 'POST'])
def restore():
    if session.get('logged_in'):
        try:
            if 'mysql_db' not in g or not g.mysql_db.is_connected():
                g.mysql_db = MySQLConnector(db_name, db_user, db_pwd, db_server, db_port)
            version = request.form['version']
            backup_current = request.form.get('current') != None
            if version:
                g.mysql_db.restore_from_backup(version, backup_current)
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
            if 'mysql_db' not in g or not g.mysql_db.is_connected():
                g.mysql_db = MySQLConnector(db_name, db_user, db_pwd, db_server, db_port)
            user = request.form['user']
            comment = request.form['comment']
            timestamp = g.mysql_db.create_backup(user, comment)
            flash("Created backup with timestamp: " + timestamp, 'success')
        except Exception as e:
            flash("Backup failed!", 'error')
    else:
        flash("You are not authorized to alter the database! Please, login!", 'error')
    return redirect(url_for("index"))


def close_mysql_db():
    mysql_db = g.pop('mysql_db', None)

    if mysql_db is not None and mysql_db.is_connected():
        mysql_db.close()


if __name__ == '__main__':
    app.run(host='127.0.0.1', port='5050')
    app.app_context().push()
    session.pop('logged_in', None)
    current_app.teardown_appcontext(close_mysql_db)
