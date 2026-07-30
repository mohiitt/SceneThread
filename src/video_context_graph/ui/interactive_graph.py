"""Self-contained interactive graph rendering for the Streamlit iframe."""

from __future__ import annotations

import html
import json
import math
from collections.abc import Mapping
from typing import Any

from pyvis.network import Network  # type: ignore[import-untyped]

JsonRecord = dict[str, Any]

NODE_STYLES: dict[str, dict[str, str]] = {
    "Video": {"background": "#fb7185", "border": "#fecdd3"},
    "Scene": {"background": "#38bdf8", "border": "#bae6fd"},
    "Entity": {"background": "#a78bfa", "border": "#ddd6fe"},
    "Event": {"background": "#f59e0b", "border": "#fde68a"},
    "Tag": {"background": "#34d399", "border": "#a7f3d0"},
}


def build_interactive_graph_html(
    graph: Mapping[str, Any],
    *,
    root_id: str,
    height: int = 720,
) -> str:
    """Render a bounded graph that expands already-authorized neighbors on click."""

    rows = list(graph.get("nodes", []))
    edges = list(graph.get("edges", []))
    node_ids = {str(row["id"]) for row in rows}
    if root_id not in node_ids and rows:
        root_id = str(rows[0]["id"])
    initial_ids = {root_id}
    for edge in edges:
        source = str(edge.get("source", ""))
        target = str(edge.get("target", ""))
        if source == root_id and target in node_ids:
            initial_ids.add(target)
        elif target == root_id and source in node_ids:
            initial_ids.add(source)

    network = Network(
        height=f"{height}px",
        width="100%",
        directed=True,
        bgcolor="#07111f",
        font_color="#e5eef8",
        cdn_resources="in_line",
        select_menu=False,
        filter_menu=False,
    )
    network.set_options(
        """
        {
          "interaction": {
            "hover": true,
            "navigationButtons": true,
            "keyboard": true,
            "multiselect": false
          },
          "physics": {
            "enabled": false,
            "barnesHut": {
              "gravitationalConstant": -5200,
              "centralGravity": 0.24,
              "springLength": 155,
              "springConstant": 0.035,
              "damping": 0.18,
              "avoidOverlap": 0.55
            },
            "stabilization": {"iterations": 180}
          },
          "nodes": {
            "shape": "dot",
            "size": 22,
            "borderWidth": 2,
            "font": {"size": 14, "face": "Inter, Arial", "color": "#e5eef8"}
          },
          "edges": {
            "arrows": {"to": {"enabled": true, "scaleFactor": 0.55}},
            "color": {"color": "#52647a", "highlight": "#e2e8f0", "hover": "#94a3b8"},
            "font": {"size": 10, "color": "#9fb0c3", "strokeWidth": 0},
            "smooth": {"enabled": true, "type": "dynamic"}
          }
        }
        """
    )

    details: dict[str, JsonRecord] = {}
    initial_scene_ids = [
        str(row["id"])
        for row in rows
        if str(row["id"]) in initial_ids and str(row.get("type")) == "Scene"
    ]
    scene_positions = {
        node_id: {
            "x": round(
                math.cos((2 * math.pi * index / max(len(initial_scene_ids), 1)) - math.pi / 2)
                * 230
            ),
            "y": round(
                math.sin((2 * math.pi * index / max(len(initial_scene_ids), 1)) - math.pi / 2)
                * 230
            ),
        }
        for index, node_id in enumerate(initial_scene_ids)
    }
    for row in rows:
        node_id = str(row["id"])
        node_type = str(row.get("type", "Unknown"))
        properties = dict(row.get("properties") or {})
        label = _safe_label(_node_label(node_type, node_id, properties))
        style = NODE_STYLES.get(
            node_type,
            {"background": "#64748b", "border": "#cbd5e1"},
        )
        position: dict[str, Any] = {}
        if node_id == root_id:
            position = {"x": 0, "y": 0, "fixed": {"x": True, "y": True}}
        elif node_id in scene_positions:
            position = {
                **scene_positions[node_id],
                "fixed": {"x": True, "y": True},
            }
        network.add_node(
            node_id,
            label=label,
            title=html.escape(_node_tooltip(node_type, properties)),
            color=style,
            hidden=node_id not in initial_ids,
            size=30 if node_type == "Video" else 22,
            **position,
        )
        details[node_id] = {
            "id": node_id,
            "type": node_type,
            "label": label.replace("\n", " "),
            "properties": properties,
        }

    relationship_details: list[JsonRecord] = []
    for index, row in enumerate(edges):
        source = str(row["source"])
        target = str(row["target"])
        if source not in node_ids or target not in node_ids:
            continue
        relationship_type = str(row.get("type", "RELATED"))
        properties = dict(row.get("properties") or {})
        edge_id = f"edge_{index}"
        network.add_edge(
            source,
            target,
            id=edge_id,
            label=relationship_type,
            title=html.escape(_relationship_tooltip(relationship_type, properties)),
        )
        relationship_details.append(
            {
                "id": edge_id,
                "source": source,
                "target": target,
                "type": relationship_type,
                "properties": properties,
            }
        )

    generated = network.generate_html()
    generated = generated.replace(
        "</head>",
        _graph_css() + "\n</head>",
        1,
    )
    generated = generated.replace(
        "<body>",
        "<body>" + _graph_controls(),
        1,
    )
    generated = generated.replace(
        "</body>",
        _graph_script(
            root_id=root_id,
            initial_ids=sorted(initial_ids),
            details=details,
            relationships=relationship_details,
        )
        + "\n</body>",
        1,
    )
    return generated


def _node_label(node_type: str, node_id: str, properties: Mapping[str, Any]) -> str:
    if node_type == "Video":
        return str(properties.get("title") or node_id)
    if node_type == "Scene":
        ordinal = properties.get("ordinal")
        prefix = f"Scene {ordinal}" if ordinal is not None else "Scene"
        return f"{prefix}\n{_time_range(properties)}"
    if node_type == "Entity":
        return str(properties.get("canonical_name") or node_id)
    if node_type == "Event":
        return str(properties.get("event_type") or properties.get("description") or node_id)
    if node_type == "Tag":
        return f"#{properties.get('name') or node_id}"
    return node_id


def _safe_label(value: str) -> str:
    return value.replace("<", "‹").replace(">", "›")


def _time_range(properties: Mapping[str, Any]) -> str:
    start = properties.get("start_sec")
    end = properties.get("end_sec")
    if not isinstance(start, (int, float)) or not isinstance(end, (int, float)):
        return ""
    return f"{_clock(float(start))}–{_clock(float(end))}"


def _clock(seconds: float) -> str:
    rounded = max(0, round(seconds))
    minutes, remaining = divmod(rounded, 60)
    return f"{minutes:02d}:{remaining:02d}"


def _node_tooltip(node_type: str, properties: Mapping[str, Any]) -> str:
    summary = (
        properties.get("summary")
        or properties.get("description")
        or properties.get("canonical_name")
        or ""
    )
    return f"{node_type}: {summary}".strip()


def _relationship_tooltip(
    relationship_type: str, properties: Mapping[str, Any]
) -> str:
    description = properties.get("description") or properties.get("role") or ""
    return f"{relationship_type}: {description}".strip()


def _json_for_script(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":")).replace(
        "</", "<\\/"
    )


def _graph_controls() -> str:
    legend = "".join(
        (
            f'<span class="st-legend-item"><i style="background:{style["background"]}"></i>'
            f"{node_type}</span>"
        )
        for node_type, style in NODE_STYLES.items()
    )
    return f"""
    <div id="st-toolbar">
      <div class="st-brand">SceneThread Graph</div>
      <button onclick="expandAll()">Expand all</button>
      <button onclick="resetGraph()">Reset</button>
      <button onclick="fitVisibleGraph()">Fit</button>
      <span id="st-count"></span>
    </div>
    <div id="st-legend">{legend}</div>
    <aside id="st-details">
      <div class="st-details-empty">
        <strong>Click a node</strong>
        <span>Its direct neighbors will appear here and on the graph.</span>
      </div>
    </aside>
    """


def _graph_css() -> str:
    return """
    <style>
      html, body {
        margin: 0; background: #07111f !important; color: #dce7f3; overflow: hidden;
      }
      .card { width: 62% !important; border: 0 !important; background: transparent !important; }
      #mynetwork {
        width: 100% !important;
        border: 1px solid #24364b !important;
        border-radius: 16px !important;
        background:
          radial-gradient(circle at 25% 20%, rgba(29,78,216,.16), transparent 30%),
          radial-gradient(circle at 75% 75%, rgba(124,58,237,.12), transparent 34%),
          #07111f !important;
      }
      #st-toolbar {
        position: absolute; z-index: 20; top: 12px; left: 14px;
        display: flex; gap: 8px; align-items: center; padding: 8px;
        border: 1px solid #2b4058; border-radius: 12px;
        background: rgba(8,20,34,.92); backdrop-filter: blur(10px);
        font: 12px Inter, Arial, sans-serif;
      }
      .st-brand { font-weight: 750; color: #f8fafc; margin: 0 5px; }
      #st-toolbar button {
        border: 1px solid #3b526c; border-radius: 8px; padding: 6px 10px;
        background: #14253a; color: #dce7f3; cursor: pointer;
      }
      #st-toolbar button:hover { background: #203852; border-color: #5b7898; }
      #st-count { color: #8fa6bf; margin: 0 5px; }
      #st-legend {
        position: absolute; z-index: 20; left: 14px; bottom: 14px;
        display: flex; flex-wrap: wrap; gap: 9px; max-width: 58%;
        padding: 8px 10px; border: 1px solid #2b4058; border-radius: 10px;
        background: rgba(8,20,34,.9); font: 11px Inter, Arial, sans-serif;
      }
      .st-legend-item { display: inline-flex; gap: 5px; align-items: center; }
      .st-legend-item i { width: 9px; height: 9px; border-radius: 50%; }
      #st-details {
        position: absolute; z-index: 20; top: 70px; right: 14px;
        width: calc(38% - 20px); max-height: calc(100% - 100px); overflow: auto;
        padding: 14px; box-sizing: border-box;
        border: 1px solid #2b4058; border-radius: 14px;
        background: rgba(8,20,34,.94); backdrop-filter: blur(12px);
        font: 12px/1.45 Inter, Arial, sans-serif;
        box-shadow: 0 15px 45px rgba(0,0,0,.3);
      }
      #st-details h3 { margin: 0 0 3px; color: #f8fafc; font-size: 16px; }
      #st-details .st-type { color: #67e8f9; text-transform: uppercase; letter-spacing: .08em; }
      #st-details table { width: 100%; border-collapse: collapse; margin-top: 12px; }
      #st-details td { border-top: 1px solid #1e3349; padding: 6px 3px; vertical-align: top; }
      #st-details td:first-child { width: 37%; color: #8fa6bf; overflow-wrap: anywhere; }
      #st-details td:last-child { color: #dce7f3; overflow-wrap: anywhere; }
      .st-connections { margin-top: 13px; color: #9fb0c3; }
      .st-connection { margin-top: 5px; padding: 6px; background: #102238; border-radius: 7px; }
      .st-details-empty { display: flex; flex-direction: column; gap: 5px; color: #8fa6bf; }
      .st-details-empty strong { color: #e5eef8; }
      @media (max-width: 720px) {
        .card { width: 58% !important; }
        #st-details { width: calc(42% - 20px); }
        #st-toolbar { right: 12px; flex-wrap: wrap; }
        .st-brand, #st-count { display: none; }
      }
    </style>
    """


def _graph_script(
    *,
    root_id: str,
    initial_ids: list[str],
    details: Mapping[str, Any],
    relationships: list[JsonRecord],
) -> str:
    return f"""
    <script>
      const stRootId = {_json_for_script(root_id)};
      const stInitialIds = new Set({_json_for_script(initial_ids)});
      const stDetails = {_json_for_script(details)};
      const stRelationships = {_json_for_script(relationships)};

      function visibleNodeIds() {{
        return nodes.get({{filter: n => !n.hidden}}).map(n => n.id);
      }}

      function updateCount() {{
        document.getElementById("st-count").textContent =
          visibleNodeIds().length + " / " + nodes.length + " nodes";
      }}

      function fitWithBreathingRoom(nodeIds) {{
        network.fit({{
          nodes: nodeIds,
          animation: {{duration: 300}},
          maxZoomLevel: 0.85
        }});
      }}

      function fitVisibleGraph() {{
        fitWithBreathingRoom(visibleNodeIds());
      }}

      function revealNeighbors(nodeId) {{
        const neighbors = network.getConnectedNodes(nodeId);
        nodes.update(neighbors.map(id => ({{id: id, hidden: false}})));
        nodes.update({{id: nodeId, borderWidth: 4}});
        network.setOptions({{physics: {{enabled: true}}}});
        network.stabilize(80);
        updateCount();
        setTimeout(() => {{
          network.setOptions({{physics: {{enabled: false}}}});
          fitWithBreathingRoom([nodeId, ...neighbors]);
        }}, 120);
      }}

      function renderDetails(nodeId) {{
        const record = stDetails[nodeId];
        if (!record) return;
        const panel = document.getElementById("st-details");
        panel.replaceChildren();
        const type = document.createElement("div");
        type.className = "st-type";
        type.textContent = record.type;
        const heading = document.createElement("h3");
        heading.textContent = record.label;
        panel.append(type, heading);

        const table = document.createElement("table");
        Object.entries(record.properties || {{}})
          .filter(([key, value]) => value !== null && value !== "" &&
                  ![
                    "normalized_aliases", "normalized_name", "created_at", "updated_at",
                    "twelvelabs_asset_id", "twelvelabs_index_id",
                    "twelvelabs_indexed_asset_id", "segmentation_task_id"
                  ].includes(key))
          .forEach(([key, value]) => {{
            const row = table.insertRow();
            const name = row.insertCell();
            const content = row.insertCell();
            name.textContent = key.replaceAll("_", " ");
            content.textContent = Array.isArray(value) ? value.join(", ") :
              (typeof value === "object" ? JSON.stringify(value) : String(value));
          }});
        panel.appendChild(table);

        const connected = stRelationships.filter(
          edge => edge.source === nodeId || edge.target === nodeId
        );
        if (connected.length) {{
          const label = document.createElement("div");
          label.className = "st-connections";
          label.textContent = "Relationships (" + connected.length + ")";
          panel.appendChild(label);
          connected.forEach(edge => {{
            const row = document.createElement("div");
            row.className = "st-connection";
            const otherId = edge.source === nodeId ? edge.target : edge.source;
            const direction = edge.source === nodeId ? "→" : "←";
            row.textContent = edge.type + " " + direction + " " +
              (stDetails[otherId]?.label || otherId);
            panel.appendChild(row);
          }});
        }}
      }}

      function expandAll() {{
        nodes.update(nodes.get().map(node => ({{id: node.id, hidden: false}})));
        network.setOptions({{physics: {{enabled: true}}}});
        network.stabilize(140);
        updateCount();
        setTimeout(() => {{
          network.setOptions({{physics: {{enabled: false}}}});
          fitWithBreathingRoom(nodes.getIds());
        }}, 180);
      }}

      function resetGraph() {{
        nodes.update(nodes.get().map(node => ({{
          id: node.id,
          hidden: !stInitialIds.has(node.id),
          borderWidth: node.id === stRootId ? 4 : 2
        }})));
        updateCount();
        setTimeout(() => {{
          fitWithBreathingRoom([...stInitialIds]);
        }}, 80);
        renderDetails(stRootId);
      }}

      network.on("click", params => {{
        if (!params.nodes.length) return;
        const nodeId = params.nodes[0];
        revealNeighbors(nodeId);
        renderDetails(nodeId);
      }});
      network.on("doubleClick", params => {{
        if (params.nodes.length) network.focus(params.nodes[0], {{scale: 1.25, animation: true}});
      }});
      renderDetails(stRootId);
      updateCount();
      window.addEventListener("load", () => setTimeout(resetGraph, 180));
      setTimeout(resetGraph, 700);
      setTimeout(resetGraph, 2500);
    </script>
    """
