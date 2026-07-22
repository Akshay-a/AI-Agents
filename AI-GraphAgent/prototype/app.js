const $ = (selector) => document.querySelector(selector);
const $$ = (selector) => [...document.querySelectorAll(selector)];
const appShell = $('#appShell');
const opsScreen = $('#opsScreen');
const launchScreen = $('#launchScreen');
const graphPanel = $('#graphPanel');
const inspectorContent = $('#inspectorContent');
const liveRegion = $('#liveRegion');
const ui = { org: null, health: null, run: null, events: [], stream: null, selectedNode: null, tab: 'live', mode: 'run', filter: 'all', cursor: 100, graphZoom: 1, approvalDecisionPending: false };

const graphZoomLimits = { min: 0.45, max: 1.6, step: 0.1 };

const escapeHTML = (value = '') => String(value).replace(/[&<>"]/g, (char) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' })[char]);
const titleCase = (value = '') => String(value).replaceAll('_', ' ').replace(/\b\w/g, (char) => char.toUpperCase());
const compact = (value) => Array.isArray(value) ? value.map((item) => typeof item === 'object' ? JSON.stringify(item) : item).join(' · ') || 'None' : value && typeof value === 'object' ? JSON.stringify(value, null, 2) : value || 'None';
const truncate = (value, length = 29) => String(value || '—').length > length ? `${String(value).slice(0, length - 1)}…` : String(value || '—');
const nodeMap = () => Object.fromEntries((ui.run?.nodes || ui.org?.nodes || []).map((node) => [node.id, node]));
const pendingApproval = () => ui.run?.queues?.approvals?.find((approval) => approval.status === 'pending');
const approvalSource = (approval) => approval?.source_node_id || approval?.node_id;
const terminalStates = new Set(['completed', 'failed', 'blocked', 'cancelled']);

async function requestJSON(url, options) {
  const response = await fetch(url, options);
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : data.detail?.message || `Request failed (${response.status})`);
  return data;
}

function showScreen(screen) {
  const showOps = screen === 'ops' && ui.run;
  opsScreen.hidden = !showOps;
  launchScreen.hidden = showOps;
  (showOps ? $('#newRunButton') : $('#objectiveInput')).focus({ preventScroll: true });
}

function statusLabel(state) {
  return ({ idle: 'Idle', ready: 'Ready', running: 'Running', waiting_for_approval: 'Approval wait', reviewing: 'Reviewing', completed: 'Completed', blocked: 'Blocked', failed: 'Failed', cancelled: 'Cancelled' })[state] || titleCase(state);
}

function markFor(state) {
  if (state === 'completed') return ['✓', ''];
  if (['blocked', 'failed', 'cancelled'].includes(state)) return ['×', 'state-mark--attention'];
  if (state === 'waiting_for_approval') return ['∥', 'state-mark--attention'];
  if (['running', 'reviewing'].includes(state)) return ['•', 'state-mark--attention'];
  return ['', 'state-mark--pending'];
}

function graphItems(org) {
  const items = org.nodes.map((node) => ({ ...node, kind: 'node' }));
  const ids = new Set(items.map((item) => item.id));
  org.edges.forEach((edge) => [edge.from, edge.to].forEach((id) => {
    if (!ids.has(id)) {
      items.push({ id, name: id === 'END' ? 'End' : titleCase(id), role: id === 'END' ? 'terminal state' : 'runtime gate', description: id === 'END' ? 'Run terminates by route' : 'Human decision boundary', kind: id === 'END' ? 'terminal' : 'gate' });
      ids.add(id);
    }
  }));
  return items;
}

function topology(org) {
  const items = graphItems(org);
  const levels = Object.fromEntries(items.map((item) => [item.id, item.id === org.entry_node ? 0 : 0]));
  for (let pass = 0; pass < items.length; pass += 1) {
    org.edges.forEach((edge) => { levels[edge.to] = Math.max(levels[edge.to] || 0, (levels[edge.from] || 0) + 1); });
  }
  const layers = [];
  items.forEach((item) => (layers[levels[item.id]] ||= []).push(item));
  return { items, levels, layers };
}

function edgeState(edge, showRun) {
  if (!showRun) return { active: false, traversed: false };
  const projected = ui.run?.edges?.find((item) => item.id === edge.id);
  return { active: Boolean(projected?.active), traversed: Boolean(projected?.last_activation) };
}

function graphDescription(org, showRun) {
  const nodes = showRun ? nodeMap() : {};
  return org.nodes.map((node) => `${node.name}: ${showRun ? statusLabel(nodes[node.id]?.state || 'idle') : node.role}`).join('. ');
}

function renderGraphSVG(svg, org, orientation, prefix, interactive = true) {
  if (!svg) return;
  const showRun = Boolean(interactive && ui.run && ui.mode === 'run');
  const { items, levels, layers } = topology(org);
  const itemsById = Object.fromEntries(items.map((item) => [item.id, item]));
  const horizontal = orientation === 'horizontal';
  const nodeWidth = horizontal ? 180 : 240;
  const nodeHeight = horizontal ? 116 : 106;
  const levelGap = horizontal ? 64 : 52;
  const crossGap = 24;
  const padding = 34;
  const maxLayer = Math.max(1, ...layers.map((layer) => layer?.length || 0));
  const width = horizontal ? padding * 2 + layers.length * nodeWidth + Math.max(0, layers.length - 1) * levelGap : padding * 2 + maxLayer * nodeWidth + Math.max(0, maxLayer - 1) * crossGap;
  const height = horizontal ? Math.max(260, padding * 2 + maxLayer * nodeHeight + Math.max(0, maxLayer - 1) * crossGap) : padding * 2 + layers.length * nodeHeight + Math.max(0, layers.length - 1) * levelGap;
  const positions = {};
  layers.forEach((layer, level) => layer?.forEach((item, index) => {
    const layerCrossSize = layer.length * (horizontal ? nodeHeight : nodeWidth) + Math.max(0, layer.length - 1) * crossGap;
    positions[item.id] = horizontal
      ? { x: padding + level * (nodeWidth + levelGap), y: (height - layerCrossSize) / 2 + index * (nodeHeight + crossGap) }
      : { x: (width - layerCrossSize) / 2 + index * (nodeWidth + crossGap), y: padding + level * (nodeHeight + levelGap) };
  }));
  const markerNeutral = `${prefix}ArrowNeutral`;
  const markerActive = `${prefix}ArrowActive`;
  const cardSize = (item) => item.kind === 'node' ? { width: nodeWidth, height: nodeHeight } : item.kind === 'gate' ? { width: horizontal ? 92 : 130, height: 64 } : { width: 86, height: 44 };
  const cardPosition = (item) => {
    const base = positions[item.id];
    const size = cardSize(item);
    return { x: base.x + (nodeWidth - size.width) / 2, y: base.y + (nodeHeight - size.height) / 2, ...size };
  };
  const edges = org.edges.map((edge) => {
    const sourceItem = itemsById[edge.from];
    const targetItem = itemsById[edge.to];
    if (!sourceItem || !targetItem) return '';
    const source = cardPosition(sourceItem);
    const target = cardPosition(targetItem);
    const state = edgeState(edge, showRun);
    const parallels = org.edges.filter((item) => item.from === edge.from && item.to === edge.to);
    const parallelOffset = (parallels.findIndex((item) => item.id === edge.id) - (parallels.length - 1) / 2) * 20;
    const skippedLevels = Math.max(0, levels[edge.to] - levels[edge.from] - 1);
    const routeOffset = parallelOffset + (skippedLevels ? (horizontal ? -76 : 92) - skippedLevels * 8 : 0);
    const start = horizontal ? { x: source.x + source.width, y: source.y + source.height / 2 } : { x: source.x + source.width / 2, y: source.y + source.height };
    const end = horizontal ? { x: target.x, y: target.y + target.height / 2 } : { x: target.x + target.width / 2, y: target.y };
    const curve = horizontal
      ? `M${start.x} ${start.y}C${(start.x + end.x) / 2} ${start.y + routeOffset} ${(start.x + end.x) / 2} ${end.y + routeOffset} ${end.x} ${end.y}`
      : `M${start.x} ${start.y}C${start.x + routeOffset} ${(start.y + end.y) / 2} ${end.x + routeOffset} ${(start.y + end.y) / 2} ${end.x} ${end.y}`;
    const labelX = (start.x + end.x) / 2 + (horizontal ? 0 : routeOffset * 0.75 + 8);
    const labelY = (start.y + end.y) / 2 + (horizontal ? routeOffset * 0.75 - 8 : 0);
    const classes = `graph-edge${state.active ? ' graph-edge--active' : ''}${state.traversed ? ' graph-edge--traversed' : ' graph-edge--pending'}`;
    return `<g data-edge="${escapeHTML(edge.id)}"><path class="${classes}" d="${curve}" marker-end="url(#${state.active ? markerActive : markerNeutral})"/><text class="node-code edge-label" x="${labelX}" y="${labelY}" text-anchor="middle">${escapeHTML(truncate(edge.when, 18))}</text></g>`;
  }).join('');
  const projected = nodeMap();
  const pending = pendingApproval();
  const cards = items.map((item) => {
    const pos = cardPosition(item);
    if (item.kind === 'gate') {
      const state = showRun ? pending ? 'pending' : ui.run?.queues?.approvals?.at(-1)?.status || 'idle' : item.role;
      return `<g class="approval-gate" data-gate="${escapeHTML(item.id)}" ${interactive ? 'tabindex="0" role="button"' : ''} aria-label="Open ${escapeHTML(item.name)}" transform="translate(${pos.x} ${pos.y})"><rect class="gate-shell" width="${pos.width}" height="${pos.height}" rx="4"/><rect class="gate-bar" x="${pos.width / 2 - 7}" y="16" width="4" height="24"/><rect class="gate-bar" x="${pos.width / 2 + 3}" y="16" width="4" height="24"/><text class="gate-label" x="${pos.width / 2}" y="${pos.height - 9}" text-anchor="middle">${escapeHTML(truncate(state, 16))}</text></g>`;
    }
    if (item.kind === 'terminal') return `<g class="graph-terminal" transform="translate(${pos.x} ${pos.y})"><rect class="terminal-shell" width="${pos.width}" height="${pos.height}" rx="22"/><text class="gate-label" x="${pos.width / 2}" y="${pos.height / 2 + 4}" text-anchor="middle">END</text></g>`;
    const node = showRun ? projected[item.id] || item : item;
    const [mark] = markFor(node.state);
    const state = showRun ? statusLabel(node.state) : node.role;
    let detail = showRun ? node.activity || node.state_reason : node.description;
    if (showRun && node.artifact_type === 'implementation' && ui.run.build_contract?.status) detail = `Contract ${ui.run.build_contract.status} · ${detail}`;
    const ringClass = node.state === 'completed' ? 'node-ring--complete' : ['running', 'reviewing', 'waiting_for_approval'].includes(node.state) ? 'node-ring--attention' : 'node-ring--pending';
    const verdictClass = node.artifact_type === 'verdict' ? ' graph-node--verdict' : '';
    return `<g class="graph-node${verdictClass}" data-node="${escapeHTML(item.id)}" data-selected="${item.id === ui.selectedNode}" ${interactive ? 'tabindex="0" role="button"' : ''} aria-label="Select ${escapeHTML(item.name)} node" transform="translate(${pos.x} ${pos.y})"><rect class="node-body" width="${pos.width}" height="${pos.height}" rx="4"/><circle class="node-ring ${ringClass}" cx="20" cy="22" r="8"/>${mark ? `<text class="node-mark" x="20" y="26" text-anchor="middle">${escapeHTML(mark)}</text>` : ''}<text class="node-role" x="40" y="28">${escapeHTML(truncate(node.name, horizontal ? 20 : 29))}</text><text class="node-state" x="20" y="50">${escapeHTML(truncate(state, 28))}</text><line class="node-divider" x1="20" y1="61" x2="${pos.width - 20}" y2="61"/><text class="node-value" x="20" y="81">${escapeHTML(truncate(detail, horizontal ? 27 : 37))}</text><text class="node-code" x="20" y="101">${showRun ? `try ${node.attempt || 0}/${node.max_attempts} · tools ${(node.tools_allowed || []).length}` : escapeHTML(titleCase(node.artifact_type || 'artifact'))}</text></g>`;
  }).join('');
  const baseWidth = horizontal ? Math.max(width, 720) : width;
  const zoom = prefix === 'desktop' ? ui.graphZoom : 1;
  svg.setAttribute('viewBox', `0 0 ${width} ${height}`);
  svg.dataset.baseWidth = String(baseWidth);
  svg.style.width = horizontal ? `${Math.round(baseWidth * zoom)}px` : '100%';
  svg.style.maxWidth = horizontal ? 'none' : '30rem';
  svg.innerHTML = `<title>${escapeHTML(org.name)} graph</title><desc>${escapeHTML(graphDescription(org, showRun))}</desc><defs><marker id="${markerNeutral}" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto"><path class="edge-arrow--neutral" d="M0 0 8 4 0 8z"/></marker><marker id="${markerActive}" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto"><path class="edge-arrow--active" d="M0 0 8 4 0 8z"/></marker></defs>${edges}${cards}`;
}

function renderLaunchGraph() {
  const svg = $('#launchGraph');
  if (svg && ui.org) renderGraphSVG(svg, ui.org, 'horizontal', 'launch', false);
}

function renderNodeList() {
  const nodes = ui.run?.nodes || ui.org?.nodes || [];
  const nodeList = $('#nodeList');
  if (!nodeList) return;
  nodeList.innerHTML = nodes.map((node) => {
    const [mark, className] = markFor(node.state);
    return `<li><button class="node-list__button" type="button" data-node="${escapeHTML(node.id)}" aria-current="${node.id === ui.selectedNode}"><span class="state-mark ${className}">${escapeHTML(mark)}</span><span class="node-list__name">${escapeHTML(node.name)}</span><span class="node-list__state">${ui.run ? escapeHTML(statusLabel(node.state)) : escapeHTML(titleCase(node.artifact_type || node.role))}</span></button></li>`;
  }).join('');
}

function renderProgressPath() {
  const progressPath = $('#progressPath');
  if (!progressPath || !ui.run) return;
  progressPath.innerHTML = ui.run.nodes.map((node) => {
    const [mark, className] = markFor(node.state);
    return `<li class="progress-step" data-state="${escapeHTML(node.state)}"><button class="progress-step__button" type="button" data-node="${escapeHTML(node.id)}" aria-current="${node.id === ui.selectedNode}"><span class="state-mark ${className}">${escapeHTML(mark)}</span><span class="progress-step__name">${escapeHTML(node.name)}</span><span class="progress-step__state">${escapeHTML(statusLabel(node.state))}</span></button></li>`;
  }).join('');
}

function renderAgentTable() {
  const tableBody = $('#agentTableBody');
  if (!tableBody || !ui.run) return;
  tableBody.innerHTML = ui.run.nodes.map((node) => {
    const artifact = node.artifacts?.at(-1);
    const currentWork = node.activity || node.state_reason || '—';
    const deliverable = artifact?.summary || titleCase(artifact?.type || node.artifact_type || '—');
    return `<tr data-node="${escapeHTML(node.id)}" data-selected="${node.id === ui.selectedNode}"><th scope="row"><button class="agent-table__select" type="button" data-node="${escapeHTML(node.id)}" aria-current="${node.id === ui.selectedNode}">${escapeHTML(node.name)}</button></th><td>${escapeHTML(statusLabel(node.state))}</td><td>${escapeHTML(currentWork)}</td><td>${escapeHTML(`${node.attempt || 0}/${node.max_attempts}`)}</td><td>${escapeHTML(deliverable)}</td><td>${escapeHTML(node.sandbox || '—')}</td></tr>`;
  }).join('');
}

function renderRunSurfaces() {
  renderProgressPath();
  renderAgentTable();
}

function queueCount(key, items) {
  if (key === 'approvals') return items.filter((item) => item.status === 'pending').length;
  if (key === 'questions') return items.filter((item) => item.status === 'open').length;
  return items.length;
}

function renderQueues() {
  const queues = ui.run?.queues || {};
  const icons = { approvals: 'inbox', questions: 'question', assumptions: 'assumption', artifacts: 'artifact' };
  const queueList = $('#queueList');
  if (!queueList) return;
  queueList.innerHTML = Object.entries(queues).map(([key, items]) => `<li><button class="queue-button" type="button" data-queue="${escapeHTML(key)}"><svg class="icon" aria-hidden="true"><use href="#icon-${icons[key] || 'artifact'}"/></svg><span class="queue-button__label">${escapeHTML(titleCase(key))}</span><span class="queue-button__count">${queueCount(key, items)}</span></button></li>`).join('');
}

function renderOrg(org) {
  ui.org = org;
  const entry = org.nodes.find((node) => node.id === org.entry_node);
  $('#orgNodeCount').textContent = `${org.nodes.length} nodes`;
  $('#orgEntryNode').textContent = `Entry: ${entry?.name || '—'}`;
  $('#orgValidation').textContent = `Validation: ${org.validation.errors.length ? 'failed' : 'pass'}`;
  $('#orgContractsStatus').textContent = org.validation.errors.length ? org.validation.errors.join(' · ') : `All ${org.nodes.length} Markdown node contracts compiled.`;
  $('#orgApprovalPolicy').textContent = org.policies?.approval || 'No approval policy configured.';
  $('#orgMemoryPolicy').textContent = org.policies?.memory || 'No memory policy configured.';
  $('#startRunButton').disabled = Boolean(org.validation.errors.length);
  renderNodeList();
  renderLaunchGraph();
}

function acceptRun(run, event, centerSelection = false) {
  ui.run = run;
  if (run.events) ui.events = run.events;
  if (event && !ui.events.some((item) => item.seq === event.seq)) ui.events.push(event);
  const selectionMissing = !ui.selectedNode || !nodeMap()[ui.selectedNode];
  if (selectionMissing) {
    ui.selectedNode = run.nodes.find((node) => ['running', 'reviewing', 'waiting_for_approval'].includes(node.state))?.id || run.org.entry_node;
  }
  localStorage.setItem('graphroomRun', run.run.id);
  localStorage.setItem('graphroomData', ui.health?.data_namespace || '');
  render(centerSelection || selectionMissing);
}

function renderSummary() {
  const run = ui.run.run;
  const approval = pendingApproval();
  const approvals = ui.run.queues.approvals || [];
  appShell.dataset.runState = approval ? 'waiting' : run.status === 'blocked' ? 'rejected' : approvals.some((item) => item.status === 'approved') ? 'approved' : 'waiting';
  $('#runtimeLabel').textContent = run.mode === 'simulate' ? 'Deterministic simulation' : `Codex · ${run.mode}`;
  $('#runIdLabel').textContent = `Run ${run.id}`;
  $('#objectiveLabel').textContent = run.mode === 'simulate' ? 'Simulated objective' : 'Live objective';
  $('#runObjective').textContent = run.objective;
  $('#runStateValue').textContent = statusLabel(run.status);
  $('#activeValue').textContent = run.active_count;
  $('#approvalValue').textContent = approvals.filter((item) => item.status === 'pending').length;
  $('#questionValue').textContent = (ui.run.queues.questions || []).filter((item) => item.status === 'open').length;
  $('#blockedValue').textContent = run.blocked_count;
  const tokens = run.tokens.input + run.tokens.output;
  $('#tokenValue').textContent = tokens ? `${tokens.toLocaleString()} tok` : '—';
  $('#riskValue').textContent = titleCase(run.risk);
  $('#latestEvent').textContent = run.latest_event;
  $('#nextHandoff').textContent = run.next_handoff;
  $('#timelineMode').textContent = `Graphroom · ${run.mode} · ${statusLabel(run.status)}`;
  $('#stopRunButton').hidden = terminalStates.has(run.status);
  const approvalJumpButton = $('#approvalJumpButton');
  if (approvalJumpButton) {
    approvalJumpButton.hidden = !approval;
    approvalJumpButton.disabled = !approval;
  }
  renderQueues();
  renderNodeList();
  renderRunSurfaces();
}

function renderGraph() {
  renderGraphSVG($('#desktopGraph'), ui.run.org, 'horizontal', 'desktop');
  renderGraphSVG($('#mobileGraph'), ui.run.org, 'vertical', 'mobile');
  const graphZoomValue = $('#graphZoomValue');
  if (graphZoomValue) graphZoomValue.textContent = `${Math.round(ui.graphZoom * 100)}%`;
  const zoomOutButton = $('#zoomOutButton');
  const zoomInButton = $('#zoomInButton');
  if (zoomOutButton) zoomOutButton.disabled = ui.graphZoom <= graphZoomLimits.min;
  if (zoomInButton) zoomInButton.disabled = ui.graphZoom >= graphZoomLimits.max;
}

function factList(rows) {
  return `<dl class="fact-list">${rows.map(([label, value]) => `<div class="fact-row"><dt>${escapeHTML(label)}</dt><dd>${escapeHTML(compact(value))}</dd></div>`).join('')}</dl>`;
}

function approvalMarkup() {
  const approval = pendingApproval();
  if (!approval || ui.selectedNode !== approvalSource(approval) || ui.tab !== 'live') return '';
  return `<article class="approval-docket" aria-labelledby="approvalDocketTitle"><header class="approval-docket__header"><div><p class="meta-label">${escapeHTML(titleCase(approval.status))} approval</p><h3 id="approvalDocketTitle">${escapeHTML(approval.title)}</h3></div><span class="approval-docket__risk">${escapeHTML(approval.risk)}</span></header><p class="approval-docket__summary"><strong>Policy</strong> · ${escapeHTML(approval.policy)}<br><strong>Impact</strong> · ${escapeHTML(approval.impact)}</p><div class="approval-actions"><button class="button button--primary" type="button" data-approval-action="approve"><span class="button__label">Approve and resume</span></button><button class="button button--quiet" type="button" data-approval-action="reject"><span class="button__label">Reject</span></button></div></article>`;
}

function latestEvent(types, nodeId) {
  return [...ui.events].reverse().find((event) => types.includes(event.type) && (!nodeId || event.node_id === nodeId));
}

function operationalRows(node) {
  const rows = [['State', statusLabel(node.state)], ['Reason', node.state_reason], ['Artifact type', titleCase(node.artifact_type)], ['Attempt', `${node.attempt}/${node.max_attempts}`], ['Current activity', node.activity], ['Codex thread', node.thread_id || 'Not started']];
  if (node.artifact_type === 'build_contract') rows.push(['Contract status', ui.run.build_contract?.status || 'Waiting'], ['Contract errors', ui.run.build_contract?.errors || 'None'], ['Required checks', ui.run.build_contract?.content?.required_checks || 'Not validated']);
  if (node.artifact_type === 'implementation') {
    const contract = ui.run.build_contract;
    const contractEvent = latestEvent(['contract.validated', 'contract.invalid']);
    const violation = latestEvent(['policy.violation'], node.id);
    rows.push(
      ['Build contract', contract?.status ? `${titleCase(contract.status)}${contract.errors?.length ? ` · ${contract.errors.join(' · ')}` : ''}` : contractEvent ? `${contractEvent.type} · ${eventSummary(contractEvent)}` : 'Waiting for validated contract'],
      ['Policy boundary', violation ? `Violation · ${eventSummary(violation)}` : 'No violation recorded'],
      ['Workspace diff', node.workspace_diff || contract?.last_diff || node.artifacts?.at(-1)?.evidence || 'Not produced'],
    );
  }
  if (node.artifact_type === 'test_report') rows.push(['Test result', node.artifacts?.at(-1)?.summary || statusLabel(node.state)], ['Required checks', ui.run.build_contract?.content?.required_checks || node.context?.build_contract?.required_checks || node.context?.required_checks || 'Waiting for build contract']);
  if (node.artifact_type === 'verdict') rows.push(['Reviewer verdict', node.artifacts?.at(-1)?.summary || statusLabel(node.state)], ['Approval history', node.context?.approval_history || ui.run.queues.approvals]);
  return rows;
}

function renderInspector() {
  const node = nodeMap()[ui.selectedNode];
  if (!node) return;
  const [mark, className] = markFor(node.state);
  $('#inspectorTitle').textContent = node.name;
  $('#inspectorSubtitle').textContent = `Selected node · ${node.file}`;
  $('#inspectorStatus').innerHTML = `<span class="state-mark ${className}">${mark}</span> ${escapeHTML(statusLabel(node.state))}`;
  $('#selectedTrace').textContent = node.name;
  let selectedTabButton;
  $$('.tab-button').forEach((button) => {
    const selected = button.dataset.tab === ui.tab;
    button.setAttribute('aria-selected', String(selected));
    button.tabIndex = selected ? 0 : -1;
    if (selected) selectedTabButton = button;
  });
  if (selectedTabButton) inspectorContent.setAttribute('aria-labelledby', selectedTabButton.id);
  const rows = {
    live: operationalRows(node),
    tools: [['Sandbox', node.sandbox], ['Declared tools', node.tools_allowed], ['MCP allow-list', node.mcp_allowed], ['Enforcement', 'Codex sandbox plus graph-owned handoff policy']],
    memory: [['Reads', node.memory_reads], ['Write proposals', node.memory_proposals], ['Provider', `${ui.run.memory.provider} · ${ui.run.memory.configured ? 'configured' : 'not configured'}`], ['Operational state', 'state.json'], ['Audit history', 'events.jsonl']],
    artifacts: [['Produced', node.artifacts.map((item) => `${item.id} · ${item.type}`)], ['Latest summary', node.artifacts.at(-1)?.summary], ['Evidence', node.artifacts.at(-1)?.evidence], ['Status', node.artifacts.at(-1)?.status]],
  };
  let content;
  if (ui.tab === 'contract') content = `<pre class="code-block contract-source">${escapeHTML(node.contract)}</pre>`;
  else if (ui.tab === 'context') content = `<pre class="code-block contract-source">${escapeHTML(JSON.stringify(node.context, null, 2) || '{}')}</pre>`;
  else content = factList(rows[ui.tab] || rows.live);
  inspectorContent.innerHTML = `${approvalMarkup()}${content}`;
}

function eventCategory(event) {
  if (event.type.startsWith('approval.')) return 'approval';
  return event.node_id ? 'node' : 'run';
}

function eventSummary(event) {
  return event.data?.summary || event.data?.reason || event.data?.title || event.data?.decision || event.data?.item_type || event.data?.paths || event.data?.offending_paths || (event.node_id ? nodeMap()[event.node_id]?.name : 'Graph state changed');
}

function renderTimeline() {
  const count = Math.ceil(ui.events.length * ui.cursor / 100);
  const events = ui.events.slice(0, count);
  const started = new Date(ui.run.run.created_at).getTime();
  $('#timelineList').innerHTML = events.map((event) => {
    const seconds = Math.max(0, Math.round((new Date(event.timestamp).getTime() - started) / 1000));
    const elapsed = `${String(Math.floor(seconds / 60)).padStart(2, '0')}:${String(seconds % 60).padStart(2, '0')}`;
    const attention = /(invalid|violation|failed|blocked|cancelled|rejected)/.test(event.type);
    return `<li class="timeline-event${attention ? ' timeline-event--attention' : ''}" data-category="${eventCategory(event)}" ${event.node_id ? `data-node="${escapeHTML(event.node_id)}"` : ''}><time class="timeline__time">${elapsed}</time><span><code class="event-code">${escapeHTML(event.type)}</code> · ${escapeHTML(eventSummary(event))}</span></li>`;
  }).join('');
  const lanes = [{ id: 'run', name: 'Run' }, ...ui.run.nodes.map((node) => ({ id: node.id, name: node.name }))];
  $('#timelineLanes').innerHTML = lanes.map((lane) => `<span class="lane-label">${escapeHTML(lane.name)}</span><div class="lane-track" data-lane="${escapeHTML(lane.id)}"></div>`).join('');
  events.filter((event) => !event.type.startsWith('worker.') && !['tool.completed', 'tool.requested'].includes(event.type)).forEach((event, index) => {
    const lane = $(`[data-lane="${event.node_id || 'run'}"]`);
    if (!lane) return;
    const position = events.length === 1 ? 50 : 5 + (index / (events.length - 1)) * 90;
    const attention = eventCategory(event) === 'approval' || /(invalid|violation|failed|blocked|cancelled|rejected)/.test(event.type);
    lane.insertAdjacentHTML('beforeend', `<button class="event-chip${attention ? ' event-chip--attention' : ''} timeline-event" type="button" data-category="${eventCategory(event)}" ${event.node_id ? `data-node="${escapeHTML(event.node_id)}"` : ''} style="--event-x:${position}%">${escapeHTML(event.type)}</button>`);
  });
  applyTimelineFilter(ui.filter);
  $('#replayCursor').value = ui.cursor;
  $('#replayOutput').textContent = `${ui.cursor}%`;
  $('#cursorFoot').textContent = `${ui.cursor}%`;
}

function applyTimelineFilter(filter) {
  ui.filter = filter;
  $$('.filter-button').forEach((button) => button.setAttribute('aria-pressed', String(button.dataset.filter === filter)));
  $$('.timeline-event').forEach((event) => { event.hidden = filter !== 'all' && event.dataset.category !== filter; });
}

function prefersReducedMotion() {
  return window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;
}

function selectedDesktopGraphNode() {
  return [...$$('#desktopGraph [data-node]')].find((node) => node.dataset.node === ui.selectedNode);
}

function centerSelectedGraphNode(behavior = 'auto') {
  const viewport = $('#graphViewport');
  const svg = $('#desktopGraph');
  const selected = selectedDesktopGraphNode();
  if (!viewport || !svg || !selected) return true;
  if (getComputedStyle(svg).display === 'none') return true;
  const viewportRect = viewport.getBoundingClientRect();
  const nodeRect = selected.getBoundingClientRect();
  if (!viewportRect.width || !nodeRect.width) return false;
  const left = viewport.scrollLeft + nodeRect.left - viewportRect.left + nodeRect.width / 2 - viewport.clientWidth / 2;
  viewport.scrollTo({ left: Math.max(0, left), behavior: prefersReducedMotion() ? 'auto' : behavior });
  return true;
}

function scheduleGraphCenter(behavior = 'auto') {
  let attempts = 0;
  const center = () => {
    attempts += 1;
    if (!centerSelectedGraphNode(behavior) && attempts < 4) requestAnimationFrame(center);
  };
  requestAnimationFrame(center);
}

function activeSelectionSurface() {
  const active = document.activeElement;
  return ['#nodeList', '#progressPath', '#agentTableBody', '#desktopGraph', '#mobileGraph'].find((selector) => active?.closest?.(selector)) || null;
}

function restoreSelectionFocus(surface, nodeId) {
  if (!surface) return;
  requestAnimationFrame(() => {
    const root = $(surface);
    const control = [...(root?.querySelectorAll('button[data-node], [data-node][tabindex]') || [])].find((item) => item.dataset.node === nodeId);
    control?.focus({ preventScroll: true });
  });
}

function setGraphZoom(value) {
  const viewport = $('#graphViewport');
  const svg = $('#desktopGraph');
  const previousWidth = svg?.getBoundingClientRect().width || 0;
  const previousCenter = viewport && previousWidth ? (viewport.scrollLeft + viewport.clientWidth / 2) / previousWidth : null;
  ui.graphZoom = Math.max(graphZoomLimits.min, Math.min(graphZoomLimits.max, Math.round(value * 100) / 100));
  renderGraph();
  if (previousCenter === null) return;
  requestAnimationFrame(() => {
    const nextWidth = svg.getBoundingClientRect().width;
    if (nextWidth) viewport.scrollLeft = Math.max(0, previousCenter * nextWidth - viewport.clientWidth / 2);
  });
}

function fitGraphToViewport() {
  const viewport = $('#graphViewport');
  const svg = $('#desktopGraph');
  const baseWidth = Number(svg?.dataset.baseWidth);
  if (!viewport?.clientWidth || !baseWidth) return;
  setGraphZoom(Math.min(1, Math.max(1, viewport.clientWidth - 48) / baseWidth));
}

function revealInspector(focusTitle = false) {
  requestAnimationFrame(() => {
    const target = $('.inspector');
    target?.scrollIntoView({ behavior: prefersReducedMotion() ? 'auto' : 'smooth', block: 'start' });
    if (focusTitle) $('#inspectorTitle')?.focus({ preventScroll: true });
  });
}

function setGraphMode(mode) {
  ui.mode = mode;
  graphPanel.classList.toggle('mode-run', mode === 'run');
  graphPanel.classList.toggle('mode-org', mode === 'org');
  $('#graphTitle').textContent = mode === 'run' ? 'Live run graph' : 'Org definition';
  $('#graphSubtitle').textContent = mode === 'run' ? 'Current state projection with an append-only event audit trail.' : `Stable roles and handoffs compiled from ORG.md · ${ui.run?.org.config_hash || ui.org?.config_hash}`;
  $$('.rail__mode').forEach((button) => button.setAttribute('aria-pressed', String(button.dataset.mode === mode)));
  ui.tab = mode === 'org' ? 'contract' : ui.tab === 'contract' ? 'live' : ui.tab;
  renderGraph();
  renderInspector();
}

function selectNode(nodeId, tab = ui.tab, options = {}) {
  if (!nodeMap()[nodeId]) return;
  const { centerGraph = true, showInspector = false } = options;
  const focusSurface = showInspector ? null : activeSelectionSurface();
  ui.selectedNode = nodeId;
  ui.tab = tab;
  renderSummary();
  renderGraph();
  renderInspector();
  if (centerGraph) scheduleGraphCenter('smooth');
  if (showInspector) revealInspector(true);
  else restoreSelectionFocus(focusSurface, nodeId);
}

function render(centerGraph = false) {
  if (!ui.run) return;
  renderSummary();
  renderGraph();
  renderInspector();
  renderTimeline();
  if (centerGraph) scheduleGraphCenter();
}

function openStream(runId, after = 0) {
  ui.stream?.close();
  const stream = new EventSource(`/api/runs/${runId}/events?after=${after}`);
  ui.stream = stream;
  stream.addEventListener('run_event', (message) => {
    const payload = JSON.parse(message.data);
    acceptRun(payload.projection, payload.event);
    if (['run.completed', 'run.failed', 'run.blocked', 'run.cancelled'].includes(payload.event.type)) stream.close();
  });
  stream.onerror = () => { if (!terminalStates.has(ui.run?.run.status)) liveRegion.textContent = 'Live event connection interrupted; reconnecting.'; };
}

async function refreshRun() {
  if (!ui.run) return;
  try {
    const run = await requestJSON(`/api/runs/${ui.run.run.id}`);
    acceptRun(run);
    openStream(run.run.id, run.run.last_seq);
  } catch (error) { liveRegion.textContent = error.message; }
}

async function decide(decision) {
  const approval = pendingApproval();
  if (!approval || ui.approvalDecisionPending) return;
  ui.approvalDecisionPending = true;
  $$('[data-approval-action]').forEach((button) => {
    button.disabled = true;
    button.setAttribute('aria-busy', 'true');
  });
  try {
    const run = await requestJSON(`/api/runs/${ui.run.run.id}/approvals/${approval.id}`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ decision }) });
    acceptRun(run);
    openStream(run.run.id, run.run.last_seq);
    liveRegion.textContent = decision === 'reject' ? 'Approval rejected. The graph is stopping.' : 'Approval resolved. The graph is resuming.';
  } catch (error) { liveRegion.textContent = error.message; }
  finally {
    ui.approvalDecisionPending = false;
    $$('[data-approval-action]').forEach((button) => {
      button.disabled = false;
      button.removeAttribute('aria-busy');
    });
  }
}

$('#runForm').addEventListener('submit', async (event) => {
  event.preventDefault();
  const objective = $('#objectiveInput');
  const status = $('#formStatus');
  const button = $('#startRunButton');
  if (!objective.value.trim()) {
    objective.setAttribute('aria-invalid', 'true');
    status.textContent = 'Objective is required.';
    objective.focus();
    return;
  }
  button.dataset.state = 'loading';
  status.textContent = 'Compiling ORG.md and starting the graph…';
  try {
    const run = await requestJSON('/api/runs', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ objective: objective.value.trim(), mode: $('input[name="mode"]:checked').value, memory_mode: $('#memorySelect').value }) });
    ui.events = run.events || [];
    ui.selectedNode = run.org.entry_node;
    ui.tab = 'live';
    ui.cursor = 100;
    acceptRun(run, null, true);
    showScreen('ops');
    openStream(run.run.id, run.run.last_seq);
    status.textContent = `Run ${run.run.id} started.`;
  } catch (error) { status.textContent = error.message; }
  finally { delete button.dataset.state; }
});

function selectFromTarget(target) {
  const nodeId = target.closest('[data-node]')?.dataset.node;
  if (nodeId) selectNode(nodeId);
}

$('#nodeList').addEventListener('click', (event) => selectFromTarget(event.target));
$('#progressPath')?.addEventListener('click', (event) => {
  const nodeId = event.target.closest('[data-node]')?.dataset.node;
  if (nodeId) selectNode(nodeId, 'live', { showInspector: true });
});
$('#agentTableBody')?.addEventListener('click', (event) => {
  const nodeId = event.target.closest('[data-node]')?.dataset.node;
  if (nodeId) selectNode(nodeId, 'live', { showInspector: true });
});
$('#graphCanvas').addEventListener('click', (event) => {
  const gate = event.target.closest('[data-gate]');
  if (gate) return pendingApproval() ? selectNode(approvalSource(pendingApproval()), 'live') : liveRegion.textContent = 'No approval is pending.';
  selectFromTarget(event.target);
});
$('#graphCanvas').addEventListener('keydown', (event) => {
  if (!['Enter', ' '].includes(event.key)) return;
  const target = event.target.closest('[data-node], [data-gate]');
  if (!target) return;
  event.preventDefault();
  target.dataset.node ? selectNode(target.dataset.node) : pendingApproval() ? selectNode(approvalSource(pendingApproval()), 'live') : liveRegion.textContent = 'No approval is pending.';
});
$$('.rail__mode').forEach((button) => button.addEventListener('click', () => setGraphMode(button.dataset.mode)));
$$('.tab-button').forEach((button) => button.addEventListener('click', () => selectNode(ui.selectedNode, button.dataset.tab, { centerGraph: false })));
$('.inspector__tabs').addEventListener('keydown', (event) => {
  if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return;
  const tabs = $$('.tab-button');
  const current = tabs.indexOf(event.target.closest('[role="tab"]'));
  if (current < 0) return;
  event.preventDefault();
  const next = event.key === 'Home' ? 0 : event.key === 'End' ? tabs.length - 1 : (current + (event.key === 'ArrowRight' ? 1 : -1) + tabs.length) % tabs.length;
  const target = tabs[next];
  selectNode(ui.selectedNode, target.dataset.tab, { centerGraph: false });
  target.focus();
});
$$('.filter-button').forEach((button) => button.addEventListener('click', () => applyTimelineFilter(button.dataset.filter)));
$('#zoomOutButton')?.addEventListener('click', () => setGraphZoom(ui.graphZoom - graphZoomLimits.step));
$('#zoomInButton')?.addEventListener('click', () => setGraphZoom(ui.graphZoom + graphZoomLimits.step));
$('#fitGraphButton')?.addEventListener('click', fitGraphToViewport);
$('#approvalJumpButton')?.addEventListener('click', () => {
  const approval = pendingApproval();
  const nodeId = approvalSource(approval);
  if (approval && nodeId) selectNode(nodeId, 'live', { showInspector: true });
});
$('#queueList').addEventListener('click', (event) => {
  const key = event.target.closest('[data-queue]')?.dataset.queue;
  const items = ui.run?.queues?.[key] || [];
  if (key === 'approvals' && pendingApproval()) selectNode(approvalSource(pendingApproval()), 'live');
  else if (key === 'questions' && items.find((item) => item.status === 'open')) selectNode(items.find((item) => item.status === 'open').node_id, 'live');
  else if (key === 'artifacts') selectNode(items.at(-1)?.node_id || ui.selectedNode, 'artifacts');
  else if (key) liveRegion.textContent = items.length ? `${items.length} ${titleCase(key).toLowerCase()} in the run projection.` : `No ${titleCase(key).toLowerCase()} recorded.`;
});
inspectorContent.addEventListener('click', (event) => {
  const action = event.target.closest('[data-approval-action]')?.dataset.approvalAction;
  if (action === 'approve' || action === 'reject') decide(action);
});
$('.timeline').addEventListener('click', (event) => { const nodeId = event.target.closest('[data-node]')?.dataset.node; if (nodeId) selectNode(nodeId, 'live'); });
$('#replayCursor').addEventListener('input', (event) => { ui.cursor = Number(event.target.value); renderTimeline(); });
$('#replayButton').addEventListener('click', () => { ui.cursor = 100; $('#replayCursor').value = 100; refreshRun(); });
$('#newRunButton').addEventListener('click', () => showScreen('launch'));
$('#stopRunButton').addEventListener('click', async () => {
  const button = $('#stopRunButton');
  button.disabled = true;
  try {
    const run = await requestJSON(`/api/runs/${ui.run.run.id}/cancel`, { method: 'POST' });
    ui.stream?.close();
    acceptRun(run);
    liveRegion.textContent = 'Run cancelled.';
  } catch (error) { liveRegion.textContent = error.message; }
  finally { button.disabled = false; }
});
$('#backToOpsButton').addEventListener('click', () => showScreen('ops'));
$('#homeLink').addEventListener('click', (event) => { event.preventDefault(); showScreen(ui.run ? 'ops' : 'launch'); });
$('#objectiveInput').addEventListener('input', (event) => { if (event.target.value.trim()) { event.target.removeAttribute('aria-invalid'); $('#formStatus').textContent = ''; } });

async function init() {
  try {
    const [org, health] = await Promise.all([requestJSON('/api/org'), requestJSON('/api/health')]);
    ui.health = health;
    renderOrg(org);
    $$('input[name="mode"]').filter((input) => input.value !== 'simulate').forEach((input) => { input.disabled = !health.codex; });
    const savedRun = localStorage.getItem('graphroomData') === health.data_namespace && localStorage.getItem('graphroomRun');
    if (!savedRun) localStorage.removeItem('graphroomRun');
    if (savedRun) {
      try {
        const run = await requestJSON(`/api/runs/${savedRun}`);
        ui.events = run.events || [];
        acceptRun(run, null, true);
        showScreen('ops');
        if (!terminalStates.has(run.run.status)) openStream(run.run.id, run.run.last_seq);
        return;
      } catch (_) { localStorage.removeItem('graphroomRun'); }
    }
    showScreen('launch');
  } catch (error) {
    $('#formStatus').textContent = `Server unavailable: ${error.message}`;
    $('#startRunButton').disabled = true;
    showScreen('launch');
  }
}

init();
