function convertToApiNATOMY(data) {
    let model = buildApiNATOMY(data);
    downloadModel(model, `vascular-model${getDateTime()}.json`);
}

function downloadModel(model, filename) {
    let modelStr = JSON.stringify(model, null, 2);
    const blob = new Blob([modelStr], {type: 'application/json'});
    saveAs(blob, filename);
}

function buildApiNATOMY(data) {
    let lyphs = [];
    let lyphMap = {};
    let links = [];
    let chains = [];

    function generateLyphs(target, source) {
        let curr = target;
        while (curr.children?.length > 0 && (!curr.data || curr.data.order > 0) && curr.children[0].data?.disabled) {
            curr = curr.children[curr.children.length - 1];
        }
        if (source?.data && curr.data && !curr.data.disabled) {
            if (curr.data.order > 0 || curr.data.included) {
                let lyph = {
                    "id": curr.data.id.replace("lnk-", "lyph_"),
                    "name": curr.name,
                    "_next": [],
                    "_branch": curr.children?.length > 1
                };
                if (curr.children?.length > 0) {
                    if (lyph._branch && curr.children[0].data?.conveyingLyph) {
                        lyph._branchTemplate = curr.children[0].data?.conveyingLyph;
                    }
                }
                if (curr.data.conveyingLyph) {
                    lyph.supertype = curr.data.conveyingLyph;
                }
                if (!(lyph.id in lyphMap)) {
                    lyphMap[lyph.id] = lyph;
                    lyphs.push(lyph);
                }
                if ((source?.data.id !== curr.data.id)) {
                    lyph._prev = source.data.id.replace("lnk-", "lyph_");
                    if (lyph._prev in lyphMap) {
                        lyphMap[lyph._prev]._next.push(lyph.id);
                    } else {
                        console.error("Undefined lyph._prev: ", lyph._prev);
                    }
                }
            }
        }
        curr.children?.forEach(child => generateLyphs(child, curr));
    }

    function generateLinks() {
        lyphs.forEach(lyph => {
            if (lyph._branch) {
                //Branching point
                let link = {
                    "id": lyph.id.replace("lyph_", "lnk_"),
                    "name": "Level of branch " + lyph.name,
                    "target": lyph.id.replace("lyph_", "t_"),
                    "length": 20
                }
                if (lyph._prev) {
                    link.source = lyph._prev.replace("lyph_", "t_");
                } else {
                    link.source = "root_" + lyph.id.replace("lyph_", "chain_");
                }
                links.push(link);
                lyph.conveys = link.id;

                let branch_chain = {
                    "id": lyph.id.replace("lyph_", "chain_branch_"),
                    "name": "Branch " + lyph.name,
                    "root": link.target,
                    "length": 20,
                    "fixed": true
                }
                if (lyph._branchTemplate.startsWith("wbkg")) {
                    branch_chain.lyphTemplate = lyph._branchTemplate;
                    branch_chain.numLevels = 1
                } else {
                    branch_chain.lyphs = [lyph._branchTemplate]
                }

                chains.push(branch_chain);
            }
        });
    }

    generateLyphs(data);

    generateLinks();

    let chainFinalLevels = lyphs.filter(lyph => lyph._next.length === 0);
    chainFinalLevels.forEach(lyph => {
        let chain = {
            "id": lyph.id.replace("lyph_", "chain_"),
            "name": "Chain " + lyph.name,
            "lyphs": [lyph.id]
        }
        let prev = lyph;
        while (prev?._prev) {
            let prevID = prev._prev;
            chain.lyphs.unshift(prevID);
            prev = lyphMap[prevID];
        }
        chains.push(chain);
    });
    lyphs.forEach(lyph => {
        delete lyph._prev;
        delete lyph._next;
        delete lyph._branch;
        delete lyph._branchTemplate;
    });

    let model = {
        "id": "vascular",
        "name": "vascular",
        "imports": ["https://raw.githubusercontent.com/albatros13/apinatomy-models/main/wbrcm.json"],
        "lyphs": lyphs,
        "links": links,
        "chains": chains
    }
    return model;
}

// If treeDiagram is given, each node also gets its layout coordinates (x, y) and displayed color
function convertToJSON(data, treeDiagram) {
    let dataStr = "";
    try {
        let dataFlat = [];
        let used = new Set();

        const CLONE_SUFFIX_ID = "_XXX";

        function getOriginalId(id) {
            // Escape special regex characters in CLONE_SUFFIX_ID
            const escapedSuffix = CLONE_SUFFIX_ID.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
            // Match pattern: [id] + CLONE_SUFFIX_ID or [id] + CLONE_SUFFIX_ID + _1, _2, etc.
            const clonePattern = new RegExp(escapedSuffix + '(?:_\\d+)?$');
            return id.replace(clonePattern, "");
        }

        function toJSON(root) {
            if (root.data?.clone) {
                return;
            }

            if (used.has(root.id)) {
                return;
            }

            let curr = root;
            while (curr.children?.length > 0 && curr.children[0].data?.disabled) {
                curr = curr.children[curr.children.length - 1];
            }

            if (!curr.data || !curr.data.disabled) {
                // Skip d3 layout internals (parent is a circular reference)
                let {parent, depth, x0, y0, ...rootCopy} = curr;
                if (treeDiagram) {
                    if (curr.x !== undefined) {
                        rootCopy.x = Math.round(curr.x);
                        rootCopy.y = Math.round(curr.y);
                    }
                    rootCopy.color = treeDiagram.getNodeColor(curr);
                }

                // Replace clone IDs in children references
                rootCopy.children = curr.children?.map(child => getOriginalId(child.id)) || [];

                // Mark as processed
                used.add(root.id);
                dataFlat.push(rootCopy);
            }

            if (curr.children) {
                curr.children.forEach(child => toJSON(child));
            }
        }

        toJSON(data);
        dataStr = JSON.stringify(dataFlat, null, 2);
    } catch (error) {
        console.log("Unable to prepare JSON output!");
        console.log(error);
    }
    return dataStr;
}

// --- Export part of a single chain (level range) --------------------------

// A chain (e.g. "Aorta") is a linear spine of connector nodes descending from
// its group root. Each connector's data.order is the level shown in the tree
// (the node label). Its children[0] is the vessel branching off at that level,
// children[1] the next connector on the spine. This collects the ordered spine.
function collectChainSpine(groupRoot, groupId) {
    let spine = [];
    let curr = (groupRoot.children || []).find(c => c.data?.connector && c.data?.group === groupId);
    while (curr) {
        spine.push(curr);
        let next = curr.children && curr.children[1];
        curr = (next && next.data?.connector && next.data?.group === groupId) ? next : null;
    }
    return spine;
}

// Plain-object copies decoupled from the live d3 nodes (which carry circular
// .parent references). data is shared by reference - the converters only read it.
function cloneNodeShallow(n) {
    return {id: n.id, name: n.name, data: n.data, children: []};
}

function cloneSubtree(n) {
    let copy = cloneNodeShallow(n);
    copy.children = (n.children || []).map(cloneSubtree);
    return copy;
}

// Build a tree containing only the selected chain, restricted to connectors
// whose level (order) is within [fromLevel, toLevel] inclusive, keeping the
// vessel that branches off at each of those levels. Returns null if empty.
function pruneChainSegment(groupRoot, groupId, fromLevel, toLevel) {
    let spine = collectChainSpine(groupRoot, groupId);
    let selected = spine.filter(c => {
        let order = c.data?.order || 0;
        return order >= fromLevel && order <= toLevel;
    });
    if (selected.length === 0) {
        return null;
    }
    let connectors = selected.map(c => {
        let copy = cloneNodeShallow(c);
        // children[0] is the vessel branching off at this level (kept whole)
        copy.branch = (c.children && c.children[0]) ? cloneSubtree(c.children[0]) : null;
        return copy;
    });
    connectors.forEach((copy, i) => {
        copy.children = [];
        if (copy.branch) {
            copy.children.push(copy.branch);
        }
        if (i + 1 < connectors.length) {
            copy.children.push(connectors[i + 1]);
        }
        delete copy.branch;
    });
    let root = cloneNodeShallow(groupRoot);
    root.children = [connectors[0]];
    return root;
}

function sanitizeName(name) {
    return (name || "chain").replace(/[^A-Za-z0-9]+/g, "_").replace(/^_+|_+$/g, "");
}

// Export the ApiNATOMY sub-model for one chain between two levels.
function exportChainSegment(groupRoot, groupId, chainName, fromLevel, toLevel) {
    let pruned = pruneChainSegment(groupRoot, groupId, fromLevel, toLevel);
    if (!pruned) {
        window.alert(`No levels found in range ${fromLevel}-${toLevel} for chain "${chainName}".`);
        return;
    }
    let model = buildApiNATOMY(pruned);
    let tag = sanitizeName(chainName);
    model.id = `vascular_${tag}_${fromLevel}_${toLevel}`;
    model.name = `${chainName} [${fromLevel}-${toLevel}]`;
    downloadModel(model, `vascular-${tag}-${fromLevel}-${toLevel}-${getDateTime()}.json`);
}