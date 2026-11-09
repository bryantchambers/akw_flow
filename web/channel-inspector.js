const $=s=>document.querySelector(s);let data,heightLayer,depressionLayer;let networkMode=false;
const map=L.map('map',{preferCanvas:true}).setView([13.41247,103.86699],14);
for(const [name,z] of [['terrainHeight',300],['terrainDepression',310],['mappedFeatures',400],['flowDepth',450],['flowNetwork',460]]){map.createPane(name);map.getPane(name).style.zIndex=z;}
const imagery=L.tileLayer('https://services.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',{maxZoom:20,maxNativeZoom:17,attribution:'Esri, Vantor, Earthstar Geographics, GIS User Community'}).addTo(map);
let tileErrors=0;imagery.on('tileerror',()=>{$('#status').textContent='Some imagery tiles could not load. Terrain and mapped features remain available.';tileErrors++;});
const specs={imagery:{name:'Satellite imagery',opacity:1,layer:imagery},height:{name:'Terrain elevation',opacity:.45},depression:{name:'Local depression · depth proxy',opacity:0},canals:{name:'Mapped canals',opacity:1},water:{name:'Mapped water traces',opacity:1},moats:{name:'Mapped temple moats',opacity:1},ponds:{name:'Mapped ponds',opacity:.8},banks:{name:'Mapped pond banks',opacity:.8},raised:{name:'Raised linear features · not assumed ditches',opacity:.8}};
for(const [key,s] of Object.entries(specs)){
 const div=document.createElement('div');div.className='layer';const label=document.createElement('label'),check=document.createElement('input');check.type='checkbox';check.checked=!['depression','raised'].includes(key);check.id=key+'-visible';s.enabled=check.checked;label.append(check,document.createTextNode(s.name));
 const slider=document.createElement('input');slider.type='range';slider.min=0;slider.max=100;slider.value=s.opacity*100;slider.id=key+'-opacity';slider.setAttribute('aria-label',s.name+' opacity');const output=document.createElement('output');output.textContent=slider.value+'%';
 const apply=()=>{s.opacity=Number(slider.value)/100;s.enabled=check.checked;output.textContent=slider.value+'%';if(!s.layer)return;if(s.enabled&&!networkMode&&!map.hasLayer(s.layer))map.addLayer(s.layer);if(!s.enabled&&map.hasLayer(s.layer))map.removeLayer(s.layer);if(s.layer.setOpacity)s.layer.setOpacity(s.opacity);else s.layer.setStyle({opacity:s.opacity});};check.onchange=apply;slider.oninput=()=>{if(Number(slider.value)>0)check.checked=true;apply();};div.append(label,slider,output);$('#layers').append(div);
}
function terrain(fit=true){
 const name=$('#extent').value,t=data.terrains[name];
 for(const [key,suffix] of [['height','height'],['depression','depression']]){
  const s=specs[key];if(s.layer)map.removeLayer(s.layer);s.layer=L.imageOverlay('/api/channel-inspector/'+name+'_'+suffix+'.png',t.bounds,{opacity:s.opacity,pane:key==='height'?'terrainHeight':'terrainDepression',interactive:false});if(s.enabled&&!networkMode)s.layer.addTo(map);
 }
 // Mapped geometry remains above both raster overlays.
 for(const key of ['canals','water','moats','ponds','banks','raised'])specs[key].layer?.bringToFront();
 $('#resolution').textContent=`0.5 m source · ~${t.display_pixel_m.toFixed(2)} m display. ${t.note}`;
 $('#ranges').textContent=`Elevation colours: ${t.height_range.map(v=>v.toFixed(2)).join(' to ')} m. Depression colours: 0 to ${t.depression_range[1].toFixed(2)} m.`;
 $('#relief').textContent=`Local depression uses a ~${t.relief_neighbourhood_m.toFixed(1)} m neighbourhood; this changes with display resolution. Coarse overview and fine pilot relief are not directly comparable.`;
 if(fit)map.fitBounds(t.bounds);window.channelInspectorReady=true;
}
fetch('/api/channel-inspector/inspector.json').then(r=>{if(!r.ok)throw Error('Inspection data unavailable');return r.json();}).then(d=>{
 data=d;
 for(const [key,kind,color] of [['canals','Canal','#00eced'],['water','Water','#ff941f'],['moats','Temple Moat','#c67bff'],['ponds','Pond','#318eff'],['banks','Pond Bank','#ffff4f'],['raised','Raised Linear','#ff70a8']]){
  const features=data.features.filter(f=>f.properties.kind===kind);const s=specs[key];s.layer=L.geoJSON(features,{pane:'mappedFeatures',style:{pane:'mappedFeatures',color,weight:3,opacity:s.opacity},onEachFeature:(f,l)=>{l.bindTooltip(kind+' · '+f.properties.fid);l.on('click',()=>{$('#selection').textContent=`${f.properties.kind} · original ID ${f.properties.id}. Source mapped geometry; no measured depth or dated hydraulic connection.`;});}});if(s.enabled&&!networkMode)s.layer.addTo(map);
  s.count=features.length;
 }
 terrain();$('#status').textContent=`${specs.canals.count} canals · ${specs.water.count} water traces · ${specs.moats.count} moats · ${specs.ponds.count} ponds · ${specs.banks.count} pond banks · ${specs.raised.count} raised linear features. Toggle layers to compare.`;
 $('#extent').onchange=()=>terrain();$('#fit').onclick=()=>map.fitBounds(data.terrains[$('#extent').value].bounds);
}).catch(e=>{$('#status').textContent=e.message;});

let featureGraph=null;let flowData,flowGroup=L.layerGroup().addTo(map);
function renderFlow(){
 if(featureGraph){renderFeatureGraph();return;}
 if(!flowData)return;flowGroup.clearLayers();
 const frame=flowData.frames[Number($('#flow-time').value)],alpha=Number($('#flow-alpha').value)/100;
 $('#flow-time-label').textContent=frame.time_s.toFixed(1)+' s';
 const nodes=new Map(flowData.nodes.map((n,i)=>[n.id,{...n,index:i}]));
 if(!$('#flow-visible').checked)return;
 if(!networkMode)flowData.nodes.forEach((n,i)=>{const depth=frame.depth_m[i],v=Math.min(1,Math.max(0,depth));
  const feature={type:'Feature',geometry:n.geometry,properties:{}};
  L.geoJSON(feature,{pane:'flowDepth',style:{pane:'flowDepth',color:'#2464ad',weight:.3,opacity:alpha,fillOpacity:alpha,fillColor:`rgb(${Math.round(225-205*v)},${Math.round(245-160*v)},${Math.round(255-100*v)})`},onEachFeature:(f,l)=>l.on('click',()=>{$('#selection').textContent=`Cell ${n.id}: simulated depth ${depth.toFixed(4)} m; assumed bed ${n.bed_elevation_m.toFixed(3)} m. ${frame.groundwater_head_m?'Groundwater head '+frame.groundwater_head_m[i].toFixed(3)+' m; surface→groundwater '+frame.surface_to_groundwater_m3_s[i].toExponential(3)+' m³/s.':''}`;})}).addTo(flowGroup);
 });
 const max=Math.max(1e-9,...frame.flows_m3_s.map(Math.abs));
 flowData.edges.forEach((edge,i)=>{const a=nodes.get(edge.from).coordinates,b=nodes.get(edge.to).coordinates,q=frame.flows_m3_s[i];
  L.polyline([[a[1],a[0]],[b[1],b[0]]],{pane:'flowNetwork',color:'#ff941f',opacity:networkMode?1:alpha,weight:1+3*Math.abs(q)/max}).bindTooltip(`${edge.from} → ${edge.to}: ${q.toExponential(3)} m³/s; negative reverses direction`).addTo(flowGroup);
 });
 if(networkMode)flowData.nodes.forEach((n,i)=>L.circleMarker([n.coordinates[1],n.coordinates[0]],{pane:'flowNetwork',radius:3,color:'#194f73',weight:1,fillColor:'#fff',fillOpacity:1}).bindTooltip(`Cell ${n.id}: depth ${frame.depth_m[i].toFixed(3)} m`).addTo(flowGroup));
}
function setFlow(data){featureGraph=null;flowData=data;for(const id of ['flow-time','flow-alpha','flow-visible'])$('#'+id).disabled=false;$('#run-flow').disabled=$('#model-scope').value!=='pilot';$('#graph-stats').textContent=data.summary?`${data.summary.feature_nodes} source features → ${data.nodes.length} terrain-supported cells. ${data.summary.excluded.length} excluded fragments totalling ${data.summary.excluded_area_m2.toFixed(1)} m² (see manifest). ${data.summary.cell_components.length} disconnected cell components.`:'';$('#flow-config').value=JSON.stringify(data.parameters,null,2);$('#flow-time').max=data.frames.length-1;$('#flow-time').value=data.frames.length-1;$('#flow-budget').textContent=JSON.stringify({surface:data.budget,groundwater:data.groundwater_budget},null,2);renderFlow();$('#flow-status').textContent=`${data.nodes.length} wet cells, ${data.edges.length} links. ${data.status}.`;window.channelFlowReady=true;}
async function loadFlow(){try{const scope=$('#model-scope').value;$('#quick-model-scope').value=scope;const file=scope==='features'?'feature_graph.json':scope==='regional'?'regional_flow.json':'flow_model.json';$('#flow-status').textContent='Loading '+scope+' model…';const r=await fetch('/api/channel-inspector/'+file);if(!r.ok)throw Error('Selected model unavailable');const result=await r.json();if(scope==='features'){featureGraph=result;flowData=null;$('#flow-visible').checked=true;$('#flow-time-label').textContent='topology only';$('#flow-budget').textContent='No hydraulic result in feature-graph mode. Dashed proposals do not change the solver.';$('#flow-config').value='Regional parameters: configs/regional_network.json; explicit link review before rebuilding cells.';$('#run-flow').disabled=true;$('#flow-time').disabled=true;$('#flow-alpha').disabled=true;renderFeatureGraph();window.channelFlowReady=true;}else setFlow(result);fitFlow();}catch(e){$('#flow-status').textContent=e.message;}};
$('#load-flow').onclick=loadFlow;
function fitFlow(){const active=featureGraph||flowData;if(active)map.fitBounds(L.latLngBounds(active.nodes.map(n=>[n.coordinates[1],n.coordinates[0]])).pad(.1));}
$('#focus-flow').onclick=async()=>{await loadFlow();};
$('#network-view').onclick=async()=>{if(!flowData&&!featureGraph)await loadFlow();if(!flowData&&!featureGraph)return;networkMode=true;for(const s of Object.values(specs))if(s.layer)map.removeLayer(s.layer);$('#flow-visible').checked=true;renderFlow();fitFlow();$('#view-label').textContent='NETWORK VIEW · selected model';};
$('#layered-view').onclick=()=>{networkMode=false;for(const s of Object.values(specs))if(s.enabled&&s.layer)s.layer.addTo(map);renderFlow();$('#view-label').textContent='LAYERED VIEW';};
for(const id of ['flow-time','flow-alpha','flow-visible'])$('#'+id).addEventListener('input',renderFlow);
$('#run-flow').onclick=async()=>{const button=$('#run-flow');button.disabled=true;$('#flow-status').textContent='Solving edited pilot…';try{const config=JSON.parse($('#flow-config').value);const r=await fetch('/api/channel-flow/simulate',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(config)});const data=await r.json();if(!r.ok)throw Error(data.error||'Run failed');setFlow(data);}catch(e){$('#flow-status').textContent=e.message;}finally{button.disabled=false;}};

function renderFeatureGraph(){
 if(!featureGraph)return;flowGroup.clearLayers();if(!$('#flow-visible').checked)return;
 const nodes=new Map(featureGraph.nodes.map(n=>[n.id,n]));const gap=Number($('#gap-distance').value);$('#gap-label').textContent=gap+' m';let proposals=0,enabled=0;
 for(const edge of featureGraph.edges){if(edge.scenario_enabled)enabled++;else if(!$('#show-proposals').checked||edge.gap_m>gap)continue;else proposals++;
  const a=nodes.get(edge.from).coordinates,b=nodes.get(edge.to).coordinates;
  const coords=[a,...edge.connection_coordinates,b].map(x=>[x[1],x[0]]);
  L.polyline(coords,{pane:'flowNetwork',color:edge.scenario_enabled?'#00a96b':'#9b6574',weight:edge.scenario_enabled?2:1,dashArray:edge.scenario_enabled?null:'5 5',opacity:.8}).bindTooltip(`${edge.id}: ${edge.status}; gap ${edge.gap_m.toFixed(2)} m. Schematic link through feature anchors, not a surveyed centreline.`).addTo(flowGroup);
 }
 for(const node of featureGraph.nodes)L.circleMarker([node.coordinates[1],node.coordinates[0]],{pane:'flowNetwork',radius:node.kind==='Pond'?2:4,color:node.kind==='Canal'||node.kind==='Water'?'#087e8b':'#6947a5',weight:1,fillOpacity:.8}).bindTooltip(`${node.kind} · ${node.id}; source feature anchor`).addTo(flowGroup);
 $('#graph-stats').textContent=`${featureGraph.nodes.length} source-feature nodes · ${enabled} enabled geometric-contact links · ${proposals} displayed proposals. Proposed connections remain disabled until reviewed in the configuration.`;
 $('#flow-status').textContent='Regional source-feature graph. Anchors and links are schematic; proximity is not proof of hydraulic or historical connectivity.';
}
for(const id of ['show-proposals','gap-distance'])$('#'+id).oninput=()=>{if(featureGraph)renderFeatureGraph();};
$('#model-scope').onchange=()=>loadFlow();

$('#quick-model-scope').onchange=()=>{$('#model-scope').value=$('#quick-model-scope').value;loadFlow();};
