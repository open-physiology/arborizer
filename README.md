# Arborizer: Documentation

Arborizer is a specialized web-based tool designed for the visualization, manipulation, and export of anatomical tree structures, specifically tailored for vascular systems and anatomical models (such as ApiNATOMY and FMA). It provides an interactive interface for researchers to build and refine complex branching structures.

### 1. Technology Stack
The application is built using a modern full-stack architecture:
- **Backend**: Python-based **Flask** web framework.
- **Frontend**: **D3.js** (Data-Driven Documents) for high-performance interactive tree visualization.
- **Database**: **MySQL** for persistent storage of nodes, edges (vessels), and anatomical metadata.
- **Authentication**: Simple session-based login system for collaborative editing.

### 2. Core Functionality
Arborizer translates flat relational database records of anatomical connections into a hierarchical tree representation.

#### Interactive Tree Visualization
The central component is a dynamic tree diagram that supports:
- **Zoom and Pan**: Effortless navigation through large, complex anatomical networks.
- **Tooltips**: Instant access to anatomical identifiers (e.g., FMA IDs) and node names.
- **Contextual Actions**: A right-click context menu provides a suite of tree manipulation tools based on the selected node's type.
- **Starting the tree from a chosen node**: Right-click a node and select *Make a root*, or use the 🌳 toolbar button to enter an FMA ID or select a vessel name. *Show full tree* returns to the whole tree. This only changes the view and is kept for the browser tab across page reloads. The downloads export the displayed part (the *Export part of a chain* dialog still offers all chains). If the tree starts from a connector node, the editing actions on the rest of that chain are hidden, because its head is out of view.

#### Tree Construction Algorithm
The tool constructs the hierarchy from a list of edges (vessels). It handles complex branching by:
1. **Node Mapping**: Resolving source and target identifiers from the database.
2. **Connector Generation**: Automatically creating intermediate "connector" nodes for multi-segmented vessels, ensuring a continuous hierarchical flow.
3. **Branch Grouping**: Categorizing vessels into logical anatomical groups to simplify the visualization.

### 3. Tree Manipulation Operations
Arborizer implements sophisticated algorithms for real-time tree editing:

*   **Node Movement (`moveUp`/`moveDown`)**: Reorders nodes within the same anatomical group. This involves swapping sequence identifiers and updating the parent-child pointers in the D3 hierarchy.
*   **Tree Restructuring (`moveToGroup`)**: Relocates an entire branch to a different anatomical parent. The algorithm handles the detachment from the current parent, recalculation of sequence orders, and reattachment to the new target group.
*   **Cloning and Copy-Paste**: Supports duplicating anatomical structures. Cloned nodes are assigned unique identifiers to prevent ID collisions while maintaining the original anatomical context.
*   **Order Management**: Dynamic adjustment of vessel sequences (orders). When a node's position changes, a "tail-update" algorithm recursively adjusts the orders of all subsequent sibling nodes.
*   **State Management (`Enable`/`Disable`/`Include`/`Exclude`)**: Allows researchers to toggle the visibility or inclusion of specific anatomical branches without deleting them from the underlying database.

### 4. Data Export
Arborizer supports multiple export formats suitable for scientific reporting and downstream simulation:

#### ApiNATOMY Model Export
This is a specialized export that converts the tree into a structured JSON format compatible with ApiNATOMY modeling standards:
- **Lyphs**: Tree nodes are converted into "lyphs" (functional units) with associated anatomical properties.
- **Links**: Connections are modeled as links between source and target points.
- **Chains**: Sequential segments are aggregated into "chains," representing continuous anatomical paths.
- **Branching Templates**: Capture the complexity of bifurcations and anatomical patterns.

#### Flat JSON Export
A simplified, flattened JSON representation of the tree structure, preserving the hierarchy via child references, ideal for general-purpose data analysis.

### 5. Scientific Application
In a scientific context, Arborizer serves as a bridge between raw anatomical databases and structured topological models. By providing a visual and interactive way to manipulate these hierarchies, it enables researchers to:
- Verify and correct anatomical connections.
- Model complex branching patterns in vascular systems.
- Export standardized data for physiological simulations.

### 6. Database Model and Queries
All database access goes through `scripts/mysql_connector.py` (class `MySQLConnector`). This section describes the underlying data, how the displayed tree is derived from it, and what each query does conceptually.

#### 6.1 The raw FMA-based vascular database
The vascular network is stored as a flat list of pairwise parent–child relations between vessels, originally extracted from the Foundational Model of Anatomy (FMA). Vessels are identified by their FMA IDs; vessels added manually through the UI carry a user-supplied *external* ID in the same column.

| Table | Role | Key columns |
|---|---|---|
| `master_vascular` | The network itself: one row per branching relation "vessel `BRANCH` is a branch of vessel `MAIN`". | `ID` (row key), `MAIN` / `BRANCH` (internal node IDs of parent and child), `vl1originalID` / `vl2originalID` (FMA IDs of parent and child), `vl1originalvesselname` / `vl2originalvesselname` (their names), `sequence` (position of the branch along the parent; `0` = unordered), `vessel_type`, `disabled` |
| `master_vascular_vessels` | Catalogue of all known vessels, whether or not they are connected. | `node_id` (internal ID used in `MAIN`/`BRANCH`), `fma_id`, `name`, `vessel_type`, `external` (1 = added manually, not from FMA) |
| `master_vascular_lyph_templates` | Per-vessel annotations, keyed by FMA ID. | `VESSEL_FMA_ID`, `lyph_template_ID` (ApiNATOMY lyph template, exported with the `wbkg:` prefix), `node_colour`, `include` (1 = show the vessel's branches in the tree) |
| `master_vascular_logs` | Registry of back-up versions. | `id` (timestamp label `YYYYMMDDHHMMSS`), `user`, `date`, `description` |
| `master_vascular_<label>`, `master_vascular_lyph_templates_<label>` | Snapshot copies of the two editable tables, one pair per back-up. | same as the originals |
| `lyphs` | Local copy of lyph definitions (read by `query_lyphs`, currently unused — the app loads lyph templates from the `wbrcm.json` model on GitHub instead). | `ID`, `label`, `ontologyTerm`, `isTemplate` |

Only `master_vascular` and `master_vascular_lyph_templates` are modified by tree editing; they are also the two tables included in back-ups.

#### 6.2 How the structured tree is constructed
The tree shown in the UI is rebuilt from the database on every page load (`create_tree()` in `app.py`):

1. **Select visible relations** (`query_vascular_edges`). Only rows of `master_vascular` whose parent vessel is marked `include` in `master_vascular_lyph_templates` are taken, so the researcher controls which vessels are expanded. Each row is joined (left outer join) with the template table twice, to obtain the lyph template and colour of both the parent and the child vessel. Unordered rows (`sequence = 0`) are treated as `1000` so that they sort after the ordered ones. Rows are sorted by parent and sequence, and for every parent the number of its branches (`total`) is counted.
   *Note:* the include flag is matched to the parent's node ID through rows in which the vessel appears as a child (`BRANCH`), so a vessel that never occurs as a branch of another vessel cannot be expanded this way.
2. **Load vessel names** (`query_vascular_nodes_map`). All vessels from `master_vascular_vessels`, keyed by node ID, supply names and FMA IDs for tree nodes. Vessels that take part in no selected relation are listed separately as candidates that can be added to the tree.
3. **Turn relations into links.**
   - A parent with a single branch yields one link *parent → child*.
   - A parent with several branches is modelled as a **chain of connector nodes**, one per branch point, in `sequence` order. For each branch a connector `<parent>_<child>` (labelled "Parent -> Child") is created, with a link *previous connector (or parent) → connector* conveyed by the parent's lyph template, and a link *connector → child* conveyed by the child's lyph template (or a generated `lyph-<id>` if none is assigned). The parent vessel thus becomes a sequence of segments, each ending at the point where one branch leaves it. The branch order (`sequence` between 1 and 999) is kept on the connector link.
   - Each parent defines a **group** `g_<parent>`, which the UI offers as a target when moving or adding branches.
4. **Assemble the hierarchy** (`scripts/node.py`). Links are folded into a nested `Node` tree under an artificial root "All". Sub-trees whose top vessel later turns out to be a child of another vessel are grafted under it; the remaining ones are attached to "All". When a vessel would appear a second time (the FMA graph is not strictly a tree), a **clone** node is created with ID suffix `_XXX_<n>` and the name suffix " (clone)", so that every tree node has a unique ID.

The resulting nested dictionary is passed to the D3.js front-end (`static/tree.js`) as JSON.

#### 6.3 Queries used by the application
**Reading data (page load, route `/`)**

| Method | What it does |
|---|---|
| `query_vascular_edges` | Fetches the visible parent–child relations with lyph templates, colours, order and enable/disable state, and counts branches per parent (step 1 above). |
| `query_vascular_nodes_map` | Fetches all vessels from the catalogue (step 2 above). |
| `query_included` | Lists all vessels that have an annotation record, with their `include` flag and lyph template; shown in the "included" side panel where branches can be switched on and off. |
| `query_versions` | Lists the available back-ups, newest first. |

**Editing the tree (route `/edit`)**

Edits made in the browser are not written immediately. They are recorded as a list of actions and sent together when the user saves. `execute_actions` first applies the include/exclude toggles and lyph template changes (`update_include`, `update_template`), then executes the actions in the order they were performed, and commits once at the end. An action that fails is reported to the user; the others are still saved.

| Action | Method | Effect on `master_vascular` |
|---|---|---|
| Include / Exclude | `update_include` | Sets `include` to 1 or NULL for the given vessels in `master_vascular_lyph_templates`, so their branches appear in or disappear from the tree. |
| Assign lyph template | `update_template` | Sets `lyph_template_ID` for a vessel. |
| `Remove` | `remove_edge` | Deletes the relation; if it was ordered, the following branches of the same parent move one position up (`decrease_order`). |
| `MoveUp` / `MoveDown` | `move_up_or_down` | Swaps the `sequence` values of two neighbouring branches of the same parent. |
| `SetOrder` | `update_order` | Moves a branch to a given position and shifts the branches in between by one (`decrease_order` / `increase_order`). |
| `AddOrder` | `add_order` | Gives a position to a previously unordered branch. |
| `RemoveOrder` | `remove_order` | Makes a branch unordered (`sequence = 0`) and closes the gap in the order of its siblings. |
| `RemoveOrderAll` | `remove_order_all` | Makes all branches of a parent unordered. |
| `FixOrderAll` | `fix_order_all` | Renumbers the given branches 1…n (in ascending row `ID` order) in a single statement, removing gaps and duplicates. |
| `MoveToGroup` | `move_to_group` | Re-attaches a branch to a different parent vessel (updates `MAIN`, parent FMA ID and name, and `sequence`) and closes the gap in the old parent's order. |
| `AddToGroup` | `add_to_group` | Inserts a new relation between a parent and a child vessel with the given order (new `ID` = current maximum + 1). |
| `Disable` / `Enable` | `disable_enable` | Sets the `disabled` flag, keeping the relation in the database: it is drawn in grey and skipped in the ApiNATOMY export. |

**Managing the vessel catalogue (routes `/create`, `/delete`)**

| Method | What it does |
|---|---|
| `create_vessel` | Adds a vessel with a new external ID (rejected if the ID already exists) to `master_vascular_vessels` with `external = 1`, and creates its annotation record in `master_vascular_lyph_templates`. |
| `can_delete_vessel` | Checks whether the vessel is referenced, as parent or child, in the current network or in any back-up table (`master_vascular_20…`); the check builds a `UNION ALL` query over all these tables. |
| `delete_vessel` | Removes the vessel and its annotation record; only called when `can_delete_vessel` allows it. |

**Versioning (routes `/backup`, `/restore`, `/delete_version`)**

| Method | What it does |
|---|---|
| `create_backup` | Copies `master_vascular` and `master_vascular_lyph_templates` into new tables suffixed with a timestamp and records the version in `master_vascular_logs`. |
| `restore_from_backup` | Copies the chosen back-up tables and swaps them in place of the current ones with a single `RENAME TABLE`. The replaced tables are either kept as an automatic back-up (logged as "Auto-backup before restore …") or dropped. |
| `delete_backup` | Drops the back-up tables of a version and removes its log entry. |

### 7. Configuration and Deployment
The application reads its settings from environment variables (see `.env.example`):

| Variable | Description |
|---|---|
| `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT` | MySQL connection parameters |
| `EDITOR_PASSWORD` | Password that unlocks editing in the web UI |
| `SECRET_KEY` | Flask session signing key |

**Local run:** copy `.env.example` to `.env`, fill in the values, then run `./run.sh` (serves on http://127.0.0.1:5050). The `.env` file is git-ignored and must never be committed.

**Render:** build command `pip install -r requirements.txt`, start command `gunicorn app:app` (as in `Procfile`). Set the variables above under the service's *Environment* settings (or upload `.env` as a Secret File).
