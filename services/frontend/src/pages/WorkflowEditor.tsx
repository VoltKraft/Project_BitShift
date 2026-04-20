import { useCallback, useEffect, useState } from "react";
import {
  Background,
  Controls,
  MiniMap,
  ReactFlow,
  addEdge,
  applyEdgeChanges,
  applyNodeChanges,
  type Connection,
  type Edge,
  type EdgeChange,
  type Node,
  type NodeChange,
} from "@xyflow/react";

import "@xyflow/react/dist/style.css";

import { api, type Workflow } from "../api/client";

const initialNodes: Node[] = [
  { id: "start", type: "input", position: { x: 0, y: 0 }, data: { label: "Leave request submitted" } },
  { id: "delegate", position: { x: 240, y: 0 }, data: { label: "Delegate review" } },
  { id: "lead", position: { x: 480, y: 0 }, data: { label: "Team lead review" } },
  { id: "hr", position: { x: 720, y: 0 }, data: { label: "HR review" } },
  { id: "end", type: "output", position: { x: 960, y: 0 }, data: { label: "Approved" } },
];

const initialEdges: Edge[] = [
  { id: "e1", source: "start", target: "delegate" },
  { id: "e2", source: "delegate", target: "lead" },
  { id: "e3", source: "lead", target: "hr" },
  { id: "e4", source: "hr", target: "end" },
];

export default function WorkflowEditor() {
  const [nodes, setNodes] = useState<Node[]>(initialNodes);
  const [edges, setEdges] = useState<Edge[]>(initialEdges);
  const [workflows, setWorkflows] = useState<Workflow[]>([]);
  const [currentId, setCurrentId] = useState<string | null>(null);
  const [name, setName] = useState("Untitled workflow");
  const [status, setStatus] = useState<string | null>(null);

  const refreshList = useCallback(async () => {
    try {
      setWorkflows(await api.listWorkflows());
    } catch (err) {
      setStatus(`load failed: ${(err as Error).message}`);
    }
  }, []);

  useEffect(() => {
    refreshList();
  }, [refreshList]);

  const onNodesChange = useCallback((changes: NodeChange[]) => setNodes((ns) => applyNodeChanges(changes, ns)), []);
  const onEdgesChange = useCallback((changes: EdgeChange[]) => setEdges((es) => applyEdgeChanges(changes, es)), []);
  const onConnect = useCallback((c: Connection) => setEdges((es) => addEdge(c, es)), []);

  const loadWorkflow = async (id: string) => {
    try {
      const wf = await api.getWorkflow(id);
      setCurrentId(wf.id);
      setName(wf.name);
      setNodes((wf.definition.nodes as Node[]) ?? []);
      setEdges((wf.definition.edges as Edge[]) ?? []);
      setStatus(`loaded "${wf.name}" (v${wf.version})`);
    } catch (err) {
      setStatus(`load failed: ${(err as Error).message}`);
    }
  };

  const saveWorkflow = async () => {
    try {
      const definition = { nodes, edges };
      if (currentId) {
        const wf = await api.updateWorkflow(currentId, { name, definition });
        setStatus(`saved v${wf.version}`);
      } else {
        const wf = await api.createWorkflow({ name, definition });
        setCurrentId(wf.id);
        setStatus(`created ${wf.id}`);
      }
      await refreshList();
    } catch (err) {
      setStatus(`save failed: ${(err as Error).message}`);
    }
  };

  const newWorkflow = () => {
    setCurrentId(null);
    setName("Untitled workflow");
    setNodes(initialNodes);
    setEdges(initialEdges);
    setStatus(null);
  };

  return (
    <div>
      <h1>Workflow editor</h1>
      <div style={{ display: "flex", gap: 12, alignItems: "center", marginBottom: 12, flexWrap: "wrap" }}>
        <input
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="Workflow name"
          style={{ padding: 6, minWidth: 240 }}
        />
        <button onClick={saveWorkflow}>{currentId ? "Save" : "Save as new"}</button>
        <button onClick={newWorkflow}>New</button>
        <select
          value={currentId ?? ""}
          onChange={(e) => e.target.value && loadWorkflow(e.target.value)}
          style={{ padding: 6 }}
        >
          <option value="">— load existing —</option>
          {workflows.map((wf) => (
            <option key={wf.id} value={wf.id}>
              {wf.name} (v{wf.version})
            </option>
          ))}
        </select>
        {status && <span style={{ color: "#666" }}>{status}</span>}
      </div>
      <div style={{ height: 500, border: "1px solid #ddd" }}>
        <ReactFlow
          nodes={nodes}
          edges={edges}
          onNodesChange={onNodesChange}
          onEdgesChange={onEdgesChange}
          onConnect={onConnect}
          fitView
        >
          <Background />
          <MiniMap />
          <Controls />
        </ReactFlow>
      </div>
    </div>
  );
}
