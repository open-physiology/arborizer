const ActionType = {
    REMOVE: "Remove",
    MOVE_UP: "MoveUp",
    MOVE_DOWN: "MoveDown",
    MOVE_TO_GROUP: "MoveToGroup",
    ADD_TO_GROUP: "AddToGroup",
    ADD_ORDER: "AddOrder",
    REMOVE_ORDER: "RemoveOrder"
};

class Tree {
    constructor(root, groups, actions) {
        this.root = root;
        this.groups = groups;
        this.actions = actions;
        this.createTreeDiagram();
    }

    createTreeDiagram() {
        let numGroups = Object.keys(this.groups).length;
        let max_width = Math.max(numGroups * 100, 4000)

        let margin = {top: 10, right: 20, bottom: 10, left: 40},
            width = max_width - margin.right - margin.left,
            height = 4000 - margin.top - margin.bottom;

        this.tree = d3.layout.tree()
            .size([width, height]);

        this.svg = d3.select("#tree").append("svg")
            .attr("width", width + margin.right + margin.left)
            .attr("height", height + margin.top + margin.bottom)

        this.svg.append("rect")
            .attr("width", "100%")
            .attr("height", "100%")
            .attr("fill", "white")
            .on('click', this.hideMenu)
            .on('contextmenu', this.hideMenu);

        this.treeGroup = this.svg.append("g")
            .attr("transform", "translate(" + margin.left + "," + margin.top + ")");

        let zoom = d3.behavior.zoom()
            .translate([0,0])
            .scaleExtent([0.5, 2.0])
            .on("zoom", () => {
                this.treeGroup.attr("transform", ["translate(" + d3.event.translate + ")", "scale(" + d3.event.scale + ")"])
            });
        this.svg.call(zoom);

        this.root.x0 = 0;
        this.root.y0 = width / 2;

        this.update(this.root);
    }

    hideMenu() {
        let contextMenu = document.getElementById("treeContextMenu");
        contextMenu.style.display = "none";
    }

    saveAction(action, ...params) {
        let isChange = document.getElementById("isChange");
        isChange.style.display = 'inline';
        this.actions.push({"action": action, "params": params});
    }

    // Remove a node from the tree => delete edge from DB
    removeNode(d) {
        this.hideMenu();
        if (d.parent) {
            let n = d.parent.children?.length;
            if (d.children?.length > 1) {
                d.parent.children[n - 1] = d.children[1];
                if (d.data.order){
                    this.decreaseTailOrder(d.children[1]);
                }
            } else {
                d.parent.children.pop();
            }
            this.saveAction(ActionType.REMOVE, d.data);
            this.update(this.root);
        }
    }

    // Move a node up => swap sequences of two edges in the DB
    moveUp(d) {
        this.hideMenu();
        let pred = d.parent?.parent;
        if (pred) {
            if (d.parent.data.group === d.data.group) {
                d.data.order -= 1;
                d.parent.data.order += 1;
                d3.select("#node_"+d.id).remove();
                d3.select("#node_"+d.parent.id).remove();
                let x = d.parent.data;

                let n = pred.children.length;
                pred.children[n - 1] = d;
                if (d.children.length > 1) {
                    let next = d.children[1];
                    d.children[1] = d.parent;
                    d.parent.children[1] = next;
                } else {
                    d.parent.children.pop();
                    d.children.push(d.parent);
                }
                d.parent = pred;
                this.saveAction(ActionType.MOVE_UP, d.data, x);
                this.update(this.root);
            }
        }
    }

    // Move a node down => swap sequences of two edges in the DB
    moveDown(d) {
        this.hideMenu();
        if (d.parent && d.children?.length > 1) {
            d.data.order += 1;
            d.children[1].data.order -= 1;
            d3.select("#node_"+d.id).remove();
            d3.select("#node_"+d.children[1].id).remove();
            let x = d.children[1].data;

            let n = d.parent.children.length;
            d.parent.children[n-1] = d.children[1];
            d.children[1].parent = d.parent;

            if (d.children[1].children?.length > 1) {
                let next = d.children[1].children[1];
                d.children[1].children[1] = d;
                d.children[1] = next;
            } else {
                d.children[1].children.push(d);
                d.children.pop();
            }
            d.parent = d.children[1];
            this.saveAction(ActionType.MOVE_DOWN, d.data, x);
            this.update(this.root);
        }
    }

    // Move a node to another group => update an edge's MAIN (source) field in the DB, update sequences of the follow-up edges
    moveToGroup(d, group) {
        this.hideMenu();
        let groupRoot = this.findNode(group.id.substring(2));
        if (groupRoot?.children && d.parent) {
            let curr = groupRoot.children[0];
            while (curr.children?.length > 1 && curr.children[1].data.group === group.id) {
                curr = curr.children[1];
            }
            let n = d.parent.children.length;
            if (d.children?.length > 1) {
                d.parent.children[n-1] = d.children[1];
            } else {
                d.parent.children.pop();
            }
            let oldOrder = d.data.order;
            if (d.children?.length > 1) {
                let child = d.children.pop();
                child.parent = d.parent;
                if (oldOrder){
                    this.decreaseTailOrder(child);
                }
            }
            d.parent = curr;
            d.disabled = true;
            d.data.group = group.id;
            d.data.order = 0;
            if (curr.data.order) {
                d.data.order = curr.data.order + 1;
            }
            curr.children = curr.children || [];
            curr.children.push(d);

            d3.select("#node_"+d.id).remove();
            if (d.children?.length > 1){
                d3.select("#node_"+d.children[1].id).remove();
            }
            let source = {"nodeID": groupRoot.id, "name": groupRoot.name, "fmaID": groupRoot.data.fmaID}

            this.saveAction(ActionType.MOVE_TO_GROUP, d.data, source, oldOrder);
            this.update(this.root);
        }
    }

    // Add node to a group
    addToGroup(target, group){
        let groupRoot = this.findNode(group.id.substring(2));
        if (groupRoot?.children) {
            let curr = groupRoot.children[0];
            while (curr.children?.length > 1 && curr.children[1].data.group === group.id) {
                curr = curr.children[1];
            }

            let s_id = curr.id;
            let t_id = target.nodeID;
            let m_id = s_id + "_" + t_id;
            let color = curr.data.color;

            let lnk1_id = "lnk-" + s_id + "_" + m_id
            let order = curr.data.order? curr.data.order + 1: 0;
            let lnk1_name = curr.name + " to " + target.name
            let lnk1 = {
                "id": lnk1_id, "name": lnk1_name, "source": s_id, "target": m_id,
                "fmaID": curr.data.fmaID, "color": color, "group": group.id, "connector": 1, "order": order
            }

            let lyph_id = "lyph-" + target.fmaID;
            let lnk2_id = "lnk-" + m_id + "_" + t_id
            let lnk2 = {
                "id": lnk2_id, "name": target.name, "conveyingLyph": lyph_id, "source": m_id, "target": t_id,
                "fmaID": target.fmaID, "color": color, "group": group.id
            }

            let d = {
                "id": lnk1.target,
                "name": lnk1.name,
                "parent": curr,
                "children": [],
                "data": lnk1
            }
            let d2 = {
                "id": lnk2.target,
                "name": lnk2.name,
                "parent": d,
                "children": [],
                "data": lnk2
            }
            d.children.push(d2);
            curr.children = curr.children || [];
            curr.children.push(d);

            let source = {"nodeID": groupRoot.id, "name": groupRoot.name, "fmaID": groupRoot.data.fmaID}

            this.saveAction(ActionType.ADD_TO_GROUP, source, target, order);
            this.update(this.root);
            return true;
        }
    }

    addOrder(d){
        this.hideMenu();
        if (d.parent) {
            let order = 1;
            let curr = d.parent;
            while (curr && !curr.data.order) {
                curr = curr.parent;
            }
            order = curr.data.order + 1;
            let tmp = curr.children[1];
            if (tmp && tmp.id !== d.id) {
                if (d.children.length > 1) {
                    let n = d.parent.children.length;
                    d.parent.children[n - 1] = d.children[1];
                    d.children[1] = d.parent;
                } else {
                    d.parent.children.pop();
                }
                curr.children[1] = d;
                d.parent = curr;
                if (d.children.length > 1) {
                    d.children[1] = tmp;
                } else {
                    d.children.push(tmp);
                }
                tmp.parent = d;
            }
            d.data.order = order;
            d3.select("#node_" + d.id).remove();
            this.saveAction(ActionType.ADD_ORDER, d.data);
            this.update(this.root);
        }
    }

    removeOrder(d){
        this.hideMenu();
        if (d.data?.order) {
            let oldOrder = d.data.order;
            if (d.children?.length > 1) {
                this.decreaseTailOrder(d.children[1]);
            }
            d.data.order = 0;
            d3.select("#node_"+d.id).remove();
            let curr = d;
            while (curr.children?.length > 1){
                curr = curr.children[1];
            }
            if (curr.id !== d.id) {
                let n = d.parent.children.length;
                if (d.children?.length > 1) {
                    d.parent.children[n - 1] = d.children[1];
                    d.children[1].parent = d.parent;
                } else {
                    d.parent.children.pop();
                }
                d.children.pop();
                curr.children.push(d);
                d.parent = curr;
            }
            this.saveAction(ActionType.REMOVE_ORDER, d.data, oldOrder);
            this.update(this.root);
        }
    }

    // Decrease order of updated node ancestors
    decreaseTailOrder(d){
        let curr = d;
        while (curr?.data.order > 1){
            curr.data.order -= 1;
            d3.select("#node_"+curr.id).remove();
            curr = curr.children?.length > 1? curr.children[1]: null;
        }
    }

    include(d){
       this.hideMenu();
       toggleIncludeOption(d.data);
    }

    exclude(d){
        this.hideMenu();
        toggleIncludeOption(d.data);
    }

    findNode(nodeID){
        let nodes = this.tree.nodes(this.root);
        return nodes.find(e => e.id === nodeID);
    }

    getLabel(d){
        if (d.data?.connector) {
            return (d.data.order || '?');
        }
        return d.name.substring(0, 20);
    }

    clear(){
        this.treeGroup.selectAll("g").remove();
    }

    update(source) {
        // Compute the new tree layout.

        let nodes = this.tree.nodes(this.root),
            links = this.tree.links(nodes);

        // Normalize for fixed-depth.
        nodes.forEach(function (d) {
            d.y = d.depth * 30;
        });

        // Update the nodes…
        let node = this.treeGroup.selectAll("g.node")
            .data(nodes, function (d, i) {
                return d.id || (d.id = i);
            });

        // Enter any new nodes at the parent's previous position.
        let nodeEnter = node.enter().append("g")
            .attr("class", "node")
            .attr("id", d => "node_" + d.id)
            .attr("transform", function (d) {
                return "translate(" + source.x0 + "," + source.y0 + ")";
            });

        let tooltip = d3.select("body").append("div")
            .attr('id', 'tooltip').attr('class', 'tooltip')
            .style("visibility", "hidden");

        nodeEnter.append("circle")
            .attr("r", 1e-6)
            .on("mouseover", d => {
                tooltip.text((d.data?.fmaID ? "FMA: " + d.data.fmaID + ": " : "") + d.name);
                return tooltip.style("visibility", "visible");
            })
            .on("mousemove", d => tooltip.style("top", (d3.event.pageY - 10) + "px").style("left", (d3.event.pageX + 10) + "px"))
            .on("mouseout", d => tooltip.style("visibility", "hidden"))
            .on('contextmenu', d => onRightClick(d))
            .on('click', d => console.log(d));

        const onRightClick = d => {
            d3.event.preventDefault();

            let contextMenu = document.getElementById("treeContextMenu");
            contextMenu.style.display = 'block';
            contextMenu.style.left = d3.event.clientX + 'px';
            contextMenu.style.top = d3.event.clientY + 'px';

            let btnRemove = document.getElementById("btnRemove");
            let btnMoveUp = document.getElementById("btnMoveUp");
            let btnMoveDown = document.getElementById("btnMoveDown");
            let btnAddOrder = document.getElementById("btnAddOrder");
            let btnRemoveOrder = document.getElementById("btnRemoveOrder");
            let btnInclude = document.getElementById("btnInclude");
            let btnExclude = document.getElementById("btnExclude");

            btnRemove.style.display = "none";
            btnMoveUp.style.display = "none";
            btnMoveDown.style.display = "none";
            btnAddOrder.style.display = "none";
            btnRemoveOrder.style.display = "none";
            btnInclude.style.display = "none";
            btnExclude.style.display = "none";

            if (d.data && !d.data.connector){
                if (d.data.included){
                    btnExclude.style.display = "block";
                    btnExclude.onclick = e => this.exclude(d);
                } else {
                    btnInclude.style.display = "block";
                    btnInclude.onclick = e => this.include(d);
                }
            }

            // Actions are applied to connector nodes in a group
            // NK it is important not to allow actions on a newly added branch - no row ID exists
            if (d.data && d.data.connector && d.data.branch && d.data.group && d.children?.length >= 0){

                btnRemove.onclick = e => this.removeNode(d);
                btnMoveUp.onclick = e => this.moveUp(d);
                btnMoveDown.onclick = e => this.moveDown(d);
                btnAddOrder.onclick = e => this.addOrder(d);
                btnRemoveOrder.onclick = e => this.removeOrder(d);

                btnRemove.style.display = "block";
                // Can move up if not the first
                if (d.data.order > 1) {
                    btnMoveUp.style.display = "block";
                }
                // Can move down if not the last
                if (d.children?.length > 1 && d.children[1].data.order) {
                    btnMoveDown.style.display = "block";
                }
                if (!d.data?.order) {
                    // Can add order if there is no order
                    btnAddOrder.style.display = "block";
                } else {
                    btnRemoveOrder.style.display = "block";
                }

                let groupList = Object.values(this.groups);
                if (groupList.length > 0 && d.data.order > 1) {
                    let ul = document.getElementById('ulChange');
                    ul.innerHTML = '';

                    const renderGroupMenu = group => {
                        if (d.data?.group !== group.id) {
                            let li = document.createElement('li');
                            ul.appendChild(li);
                            let btn = document.createElement('button');
                            btn.onclick = e => this.moveToGroup(d, group);
                            btn.innerHTML = ">>" + group.name;
                            li.appendChild(btn);
                        }
                    }
                    groupList.forEach(renderGroupMenu);
                }
            }
        }

        nodeEnter.append("text")
            .attr("x", function (d) {
                return d.children || d._children ? 10 : -10;
            })
            .attr("dy", ".35em")
            .attr("text-anchor", function (d) {
                return d.children || d._children ? "start" : "end";
            })
            .text(d => this.getLabel(d))
            .style("fill-opacity", 1e-6);

        // Transition nodes to their new position.
        let duration = 750;

        let nodeUpdate = node.transition()
            .duration(duration)
            .attr("transform", function (d) {
                return "translate(" + d.x + "," + d.y + ")";
            });

        nodeUpdate.select("circle")
            .attr("r", function (d) {
                if (d.id.includes("(")) return 6
                return 4.5
            })
            .style("fill", function (d) {
                if (d.id.includes("(")) return "white";
                return d.data?.color || "lightsteelblue";
            });

        nodeUpdate.select("text")
            .style("fill-opacity", 1);

        // Transition exiting nodes to the parent's new position.
        let nodeExit = node.exit().transition()
            .duration(duration)
            .attr("transform", function (d) {
                return "translate(" + source.x + "," + source.y + ")";
            })
            .remove();

        nodeExit.select("circle")
            .attr("r", 1e-6);

        nodeExit.select("text")
            .style("fill-opacity", 1e-6);

        // Update the links…
        let link = this.treeGroup.selectAll("path.link")
            .data(links, function (d) {
                return d.target.id;
            });

        let diagonal = d3.svg.diagonal()
            .projection(function (d) {
                return [d.x, d.y];
            });

        // Enter any new links at the parent's previous position.
        link.enter().insert("path", "g")
            .attr("class", "link")
            .attr("d", function (d) {
                var o = {x: source.x0, y: source.y0};
                return diagonal({source: o, target: o});
            })
            .on("mouseover", d => {
                tooltip.text(d.target.data?.conveyingLyph + " (" + d.target.data?.fmaID + ")");
                return tooltip.style("visibility", "visible");
            })
            .on("mousemove", d => {
                return tooltip.style("top", (d3.event.pageY - 10) + "px").style("left", (d3.event.pageX + 10) + "px");
            })
            .on("mouseout", d => {
                return tooltip.style("visibility", "hidden");
            });


        // Transition links to their new position.
        link.transition()
            .duration(duration)
            .attr("d", diagonal)
            .style("stroke", function (d) {
                return d.target.data?.color || "#ccc";
            });

        // Transition exiting nodes to the parent's new position.
        link.exit().transition()
            .duration(duration)
            .attr("d", function (d) {
                let o = {x: source.x, y: source.y};
                return diagonal({source: o, target: o});
            })
            .remove();

        // Stash the old positions for transition.
        nodes.forEach(function (d) {
            d.x0 = d.x;
            d.y0 = d.y;
        });
    }
}
