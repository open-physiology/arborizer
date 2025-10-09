function convertToApiNATOMY(data) {
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
    let modelStr = JSON.stringify(model, null, 2);
    const blob = new Blob([modelStr], {type: 'application/json'});
    saveAs(blob, `vascular-model${getDateTime()}.json`);
}

function convertToJSON(data) {
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
                let rootCopy = {...curr};

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