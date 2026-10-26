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

### 6. Configuration and Deployment
The application reads its settings from environment variables (see `.env.example`):

| Variable | Description |
|---|---|
| `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT` | MySQL connection parameters |
| `EDITOR_PASSWORD` | Password that unlocks editing in the web UI |
| `SECRET_KEY` | Flask session signing key |

**Local run:** copy `.env.example` to `.env`, fill in the values, then run `./run.sh` (serves on http://127.0.0.1:5050). The `.env` file is git-ignored and must never be committed.

**Render:** build command `pip install -r requirements.txt`, start command `gunicorn app:app` (as in `Procfile`). Set the variables above under the service's *Environment* settings (or upload `.env` as a Secret File).
