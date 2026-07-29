let network = null;
let nodesDataset = new vis.DataSet();
let edgesDataset = new vis.DataSet();

// 1. 初始化 Vis.js 畫布與物理力學設定 (超級推力拉開節點)
function initNetwork() {
    const container = document.getElementById('network');
    const data = { nodes: nodesDataset, edges: edgesDataset };

    const options = {
        nodes: {
            font: { size: 14, color: '#2c3e50' },
            borderWidth: 1.5,
            shadow: true
        },
        edges: {
            smooth: { type: 'continuous' },
            arrows: { to: { enabled: true, scaleFactor: 0.6 } }
        },
        interaction: { hover: true, dragNodes: true, zoomView: true },
        physics: {
            enabled: true,
            barnesHut: {
                gravitationalConstant: -30000, // 💥 超強推力！把節點徹底推開不重疊
                centralGravity: 0.05,
                springLength: 250,            // ↔️ 彈簧線條拉長，留出文字空間
                springConstant: 0.02,
                damping: 0.09
            },
            stabilization: { enabled: true, iterations: 1000 }
        }
    };

    network = new vis.Network(container, data, options);

    // 點擊事件：點選某個體時高亮關聯親屬，其他變半透明
    network.on("click", function (params) {
        if (params.nodes.length > 0) {
            const selectedNode = params.nodes[0];
            const connectedNodes = network.getConnectedNodes(selectedNode);
            connectedNodes.push(selectedNode);

            const allNodes = nodesDataset.get();
            nodesDataset.update(allNodes.map(node => ({
                id: node.id,
                opacity: connectedNodes.includes(node.id) ? 1.0 : 0.12
            })));
        } else {
            const allNodes = nodesDataset.get();
            nodesDataset.update(allNodes.map(n => ({ id: n.id, opacity: 1.0 })));
        }
    });
}

// 2. 讀取 Python 產出的固定圖檔數據 data.json
async function loadGraphData() {
    try {
        // 加時間戳記避免瀏覽器讀到舊快取
        const response = await fetch('data.json?t=' + new Date().getTime());
        const graphData = await response.json();

        nodesDataset.clear();
        edgesDataset.clear();

        graphData.nodes.forEach(node => {
            nodesDataset.add({
                id: node.id,
                label: node.label,
                shape: node.shape,
                size: node.size,
                color: { background: node.color, border: '#ffffff' },
                title: node.title
            });
        });

        if (graphData.edges) {
            edgesDataset.add(graphData.edges);
        }
    } catch (err) {
        console.error("載入 data.json 失敗，請確認 generate_tree.py 是否已執行並產生 data.json。", err);
    }
}

// 3. 搜尋耳號功能
function searchPig() {
    const query = document.getElementById('searchInput').value.trim();
    if (query && nodesDataset.get(query)) {
        network.focus(query, { scale: 1.4, animation: true });
        network.selectNodes([query]);
    } else if (query) {
        alert("找不到該個體或耳號！");
    }
}

function handleSearchKeyPress(event) {
    if (event.key === 'Enter') {
        searchPig();
    }
}

// 4. 網頁開啟後自動啟動
window.onload = () => {
    initNetwork();
    loadGraphData();
};
