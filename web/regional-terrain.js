const $=s=>document.querySelector(s);
const map=L.map('map',{maxZoom:24,preferCanvas:true}).setView([13.43,103.83],12);
for(const [name,z] of [['nativeHeight',310],['nativeOutput',330],['nativeGrid',345],['referenceDepth',350],['nativeFeatures',420],['referenceFlow',440],['nativeReaches',430],['nativeNodes',460],['nativeArrows',450]]){map.createPane(name);map.getPane(name).style.zIndex=z;}
const imagery=L.tileLayer('https://services.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',{maxZoom:24,maxNativeZoom:17,attribution:'Esri, Vantor, Earthstar Geographics, GIS User Community'}).addTo(map);
let state,footprint,heightLayer,outputLayer,featureLayer,bankLayer,cellMarker,displayedSnapshot=null,fitDone=false,faceVersion=0,cellVersion=0,faceAbort,comparisonData,referenceData,lastFaceData;
const arrowGroup=L.layerGroup().addTo(map),gridGroup=L.layerGroup().addTo(map),referenceGroup=L.layerGroup().addTo(map);
const faceCanvas=L.canvas({pane:'nativeArrows'}),gridCanvas=L.canvas({pane:'nativeGrid'}),referenceCanvas=L.canvas({pane:'referenceFlow'}),referenceDepthCanvas=L.canvas({pane:'referenceDepth'});
let preflightQuality='';
const endpoint='/api/regional-native/';
function selectedCase(){return $('#rainfall-case').value;}
function withCase(url){const name=selectedCase();return name?url+(url.includes('?')?'&':'?')+'case='+encodeURIComponent(name):url;}
function updateDownloadLinks(){for(const a of document.querySelectorAll('a[href^="/api/water-network/download/"]'))a.href=withCase(a.getAttribute('href').split('?')[0]);}

async function request(path,signal){const r=await fetch(withCase(endpoint+path),{cache:'no-store',signal});if(!r.ok){let error;try{error=(await r.json()).error;}catch{}throw Error(error||'Regional data unavailable');}return r.json();}
function syncBaseLayers(){
 $('#native-imagery').checked?imagery.addTo(map):map.removeLayer(imagery);
 for(const [layer,id] of [[featureLayer,'native-water'],[bankLayer,'native-banks']])if(layer)$('#'+id).checked?layer.addTo(map):map.removeLayer(layer);
}
function rebuildLayers(){
 const key=$('#native-snapshot').value;
 if(displayedSnapshot!==key){cellVersion++;if(cellMarker)map.removeLayer(cellMarker);$('#native-cell').textContent='Click the map to inspect a native cell in the selected saved state.';displayedSnapshot=key;}
 if(heightLayer)map.removeLayer(heightLayer);if(outputLayer)map.removeLayer(outputLayer);
 if($('#native-height').checked)heightLayer=L.tileLayer(withCase(endpoint+'tiles/'+$('#native-terrain-style').value+'/'+key+'/{z}/{x}/{y}.png'),{pane:'nativeHeight',className:'native-layer',maxZoom:24,maxNativeZoom:22,opacity:Number($('#native-height-alpha').value)/100}).addTo(map);
 const metric=$('#native-metric').value;
 if(metric!=='none')outputLayer=L.tileLayer(withCase(endpoint+'tiles/'+metric+'/'+key+'/{z}/{x}/{y}.png'),{pane:'nativeOutput',className:'native-layer',maxZoom:24,maxNativeZoom:22,opacity:Number($('#native-output-alpha').value)/100}).addTo(map);
 $('#native-legend').textContent=metric==='tracer'?'Regional unit tracer: purple raster, 0–1, clipped. Numerical routing check only.':metric==='depth'?'Regional depth: blue, square-root colours 0–1 m; below 1 mm hidden. Mapped outlines remain visible even when dry. Click for exact values.':'Regional raster hidden. Mapped features and computed flow faces remain independently selectable.';
 syncBaseLayers();loadFaces();
}
async function refresh(){try{
 const requestedCase=selectedCase(),previousCase=state?.case,result=await request('status');if(requestedCase!==selectedCase())return;state=result;const m=state.manifest,p=state.progress;
 if(previousCase&&previousCase!==state.case){comparisonData=null;displayedSnapshot=null;rebuildLayers();loadComparison();refreshNetwork();}
 $('#native-progress').textContent=p?`Build: ${p.stage}${p.simulation?' · '+p.simulation.time_s.toFixed(2)+' / '+p.simulation.duration_s+' simulated seconds · '+p.simulation.steps+' steps':''}${p.error?' · '+p.error:''}`:'Build not started';
 if(!m)return;
 $('#native-summary').textContent=`${m.valid_cells.toLocaleString()} valid cells · ${m.valid_area_km2.toFixed(2)} km² · actual ${m.solver_spacing_m} m solver spacing and terrain. Full supplied survey footprint.${m.execution?' Backend: '+m.execution.backend+(m.execution.device?' · '+m.execution.device:''):''}`;
 $('#native-scenario').textContent=m.parameters.scenario_label;
 $('#native-config').textContent=JSON.stringify({parameters:m.parameters,scope:m.scope,source_state:m.source_state,friction_treatment:m.friction_treatment,velocity_depth_timing:m.velocity_depth_timing,assumptions:m.assumptions},null,2);
 const q=state.verification;
 $('#native-quality').textContent=q?`Native export checks passed. ${q.faces_with_froude_over_one_and_face_depth_at_least_1cm?.toLocaleString()??'Uncounted'} faces at least 1 cm deep exceed Froude 1 and require review. Very shallow films have additional limitations. This is not predictive hydraulic validation.`:(preflightQuality||'Export and hydraulic-regime checks pending.');
 $('#native-budget').textContent=m.budget?JSON.stringify({water:m.budget,tracer:m.tracer_budget},null,2):'Final result still computing.';
 if(!fitDone){map.fitBounds(m.bounds_lonlat,{animate:false});fitDone=true;footprint=L.rectangle(m.bounds_lonlat,{color:'#777',weight:2,fill:false,dashArray:'6 5'}).addTo(map);rebuildLayers();}
 const exportLink=$('#native-raster-export');exportLink.setAttribute('aria-disabled',m.status!=='complete');exportLink.style.opacity=m.status==='complete'?'1':'.45';exportLink.onclick=e=>{if(m.status!=='complete')e.preventDefault();};
 const hasFinal=m.status==='complete'&&m.snapshots.some(s=>s.key==='final');
 if(!hasFinal&&Array.from($('#native-snapshot').options).some(o=>o.value==='final')){for(const option of Array.from($('#native-snapshot').options))if(option.value==='final')option.remove();$('#native-snapshot').value='initial';rebuildLayers();}
 if(hasFinal&&!Array.from($('#native-snapshot').options).some(o=>o.value==='final')){$('#native-snapshot').add(new Option(`Water-present relaxation · ${m.parameters.duration_s} s`,'final'));$('#native-snapshot').value='final';rebuildLayers();}
 window.regionalNativeReady=true;
 }catch(e){$('#native-progress').textContent=e.message;}}
function arrow(aa,bb,colour,weight,tooltip,representative=false,group=arrowGroup,renderer=faceCanvas,pane='nativeArrows'){
 let a=L.latLng(aa[1],aa[0]),b=L.latLng(bb[1],bb[0]);
 let ap=map.project(a),bp=map.project(b),dx=bp.x-ap.x,dy=bp.y-ap.y,length=Math.hypot(dx,dy);
 if(!length)return;
 if(representative){const center=map.latLngToLayerPoint([(aa[1]+bb[1])/2,(aa[0]+bb[0])/2]);dx=12*dx/length;dy=12*dy/length;a=map.layerPointToLatLng([center.x-dx/2,center.y-dy/2]);b=map.layerPointToLatLng([center.x+dx/2,center.y+dy/2]);}
 ap=map.latLngToLayerPoint(a);bp=map.latLngToLayerPoint(b);dx=bp.x-ap.x;dy=bp.y-ap.y;
 const opts={renderer,pane,color:colour,weight,opacity:.9};
 L.polyline([a,b],opts).bindTooltip(tooltip).addTo(group);
 L.polyline([map.layerPointToLatLng([bp.x-dx*.35-dy*.22,bp.y-dy*.35+dx*.22]),b,map.layerPointToLatLng([bp.x-dx*.35+dy*.22,bp.y-dy*.35-dx*.22])],opts).addTo(group);
}
async function loadFaces(){
 window.regionalNativeFacesReady=false;lastFaceData=null;$('#native-focus-flow').disabled=true;
 const version=++faceVersion;faceAbort?.abort();faceAbort=new AbortController();arrowGroup.clearLayers();gridGroup.clearLayers();
 if(!$('#native-arrows').checked&&!$('#native-grid').checked){$('#native-face-status').textContent='Flow and grid layers hidden.';return;}
 const b=map.getBounds(),bounds=[b.getWest(),b.getSouth(),b.getEast(),b.getNorth()].join(',');
 const minimum=Number($('#native-minimum-q').value);$('#native-face-status').textContent='Loading native face display…';
 try{
  const data=await request(`faces?bounds=${encodeURIComponent(bounds)}&snapshot=${$('#native-snapshot').value}&minimum_q=${minimum}&include_idle=${$('#native-idle').checked}`,faceAbort.signal);
  if(version!==faceVersion)return;
  if($('#native-grid').checked)for(const coords of data.grid_lines)L.polyline(coords.map(p=>[p[1],p[0]]),{renderer:gridCanvas,pane:'nativeGrid',color:'#6b8090',weight:.6,opacity:.45,interactive:false}).addTo(gridGroup);
  let active=0;const maximum=Math.max(minimum,...data.faces.map(f=>Math.abs(f.discharge_m3_s)));
  const drawOverview=$('#native-overview-faces').checked;
  if($('#native-arrows').checked&&(data.mode==='native'||drawOverview))for(const f of data.faces){
   const q=f.discharge_m3_s,flowing=Math.abs(q)>Math.max(minimum,1e-15),tip=`Native ${f.id}: Q ${q.toExponential(3)} m³/s; positive ${f.orientation}. ${flowing?'Computed flow.':'Inactive or below the display threshold.'}`;
   if(data.mode==='native')L.polyline(f.face_coordinates.map(p=>[p[1],p[0]]),{renderer:faceCanvas,pane:'nativeArrows',color:flowing?'#ed791a':'#97a4ac',weight:flowing?1.3:.6,opacity:.8}).bindTooltip(tip).addTo(arrowGroup);
   if(!flowing)continue;active++;
   const a=q>=0?f.from_coordinates:f.to_coordinates,c=q>=0?f.to_coordinates:f.from_coordinates;
   arrow(a,c,'#d66500',1+1.5*Math.sqrt(Math.abs(q)/maximum),tip,data.mode!=='native');
  }
  $('#native-face-status').textContent=`${data.mode!=='native'&&!drawOverview?'Overview uses extracted reaches; face glyphs appear at cell zoom. ':''}${active.toLocaleString()} flowing faces displayed. ${data.message}${data.mode==='representative'?' Zoom to cells to inspect individual 0.5 m faces.':''}`;
  lastFaceData=data;$('#native-focus-flow').disabled=!data.faces.some(f=>Math.abs(f.discharge_m3_s)>Math.max(minimum,1e-15));
  window.regionalNativeFacesReady=true;window.regionalNativeFaceMode=data.mode;
 }catch(e){if(e.name!=='AbortError')$('#native-face-status').textContent=e.message;}
}
async function loadComparison(){if(selectedCase().startsWith('hydraulics_gpu_rain_')){$('#native-comparison').textContent='Rainfall cases use their matched zero-rain control.';return;}try{
 const requestedCase=selectedCase(),result=await request('comparison');if(requestedCase!==selectedCase())return;comparisonData=result;const c=comparisonData;
 if(!c.current){$('#native-comparison').textContent='Saved runs changed; rebuild the comparison before using these figures.';$('#native-reference').checked=false;$('#native-reference').disabled=true;referenceGroup.clearLayers();return;}
 $('#native-reference').disabled=false;$('#native-reference-label').textContent=`Original ${c.pilot.spacing_m} m pilot reference · purple · ${c.pilot.duration_s} s`;
 const nf=c.regional.pilot_footprint.final;
 $('#native-comparison').textContent=`Same ${c.extent_m} m pilot area: original ${c.pilot.spacing_m} m / ${c.pilot.duration_s} s run holds ${Math.round(c.pilot.final_water_volume_m3).toLocaleString()} m³; regional ${c.regional.spacing_m} m / ${c.regional.duration_s} s run holds ${Math.round(nf.water_volume_m3).toLocaleString()} m³. Original forcing: ${c.pilot.forcing}. Regional forcing: ${c.regional.forcing}. Starting levels differ. They are not equivalent scenarios.`;
 window.regionalComparisonReady=true;
 }catch(e){$('#native-comparison').textContent=e.message;}}
async function renderReference(){
 referenceGroup.clearLayers();if(!$('#native-reference').checked)return;
 try{
  if(!referenceData){const r=await fetch('/api/channel-inspector/terrain_flow.json');if(!r.ok)throw Error('Original 2D pilot unavailable');referenceData=await r.json();}
  if(!$('#native-reference').checked)return;
  const p=referenceData,f=p.frames[p.frames.length-1],lookup=new Map(p.nodes.map((n,i)=>[n.id,i]));
  p.nodes.forEach((node,i)=>{if(f.depth_m[i]<=.001)return;L.geoJSON(node.geometry,{renderer:referenceDepthCanvas,pane:'referenceDepth',style:{color:'#8648b5',weight:.5,fillColor:'#a36bd4',fillOpacity:.22},onEachFeature:(g,l)=>l.bindTooltip(`Original 10 m pilot at ${f.time_s} s: depth ${f.depth_m[i].toFixed(3)} m. Different scenario; not native regional output.`)}).addTo(referenceGroup);});
  const max=Math.max(1e-5,...f.flows_m3_s.map(Math.abs));
  p.edges.forEach((edge,i)=>{const q=f.flows_m3_s[i];if(Math.abs(q)<Math.max(1e-5,max*.01))return;
   const tip=`Original 10 m pilot reference at ${f.time_s} s: Q ${q.toExponential(3)} m³/s. Different forcing.`;
   L.polyline(edge.face_geometry.coordinates.map(p=>[p[1],p[0]]),{renderer:referenceCanvas,pane:'referenceFlow',color:'#8648b5',weight:1.5}).bindTooltip(tip).addTo(referenceGroup);
   const a=p.nodes[lookup.get(q>=0?edge.from:edge.to)].coordinates,b=p.nodes[lookup.get(q>=0?edge.to:edge.from)].coordinates;
   arrow(a,b,'#8648b5',1.2,tip,false,referenceGroup,referenceCanvas,'referenceFlow');
  });
 }catch(e){$('#native-comparison').textContent=e.message;}}
function displayScale(){const metres=156543.03392*Math.cos(map.getCenter().lat*Math.PI/180)/2**map.getZoom();$('#native-display').textContent=`Map ≈ ${metres.toFixed(2)} m per screen pixel at zoom ${map.getZoom()}; hydraulic cells remain 0.50 m. Native grid appears at cell zoom.`;}
map.on('moveend',()=>{displayScale();loadFaces();if($('#native-reference').checked)renderReference();});
map.on('click',async e=>{const version=++cellVersion;try{
 const p=await request(`point?lon=${e.latlng.lng}&lat=${e.latlng.lat}&snapshot=${$('#native-snapshot').value}`);if(version!==cellVersion)return;
 $('#native-cell').textContent=`Native r${p.row} c${p.col} · 0.50 m. Depth ${p.water_depth_m.toFixed(6)} m; bed ${p.terrain_elevation_m.toFixed(4)} m; stage ${p.water_stage_m.toFixed(4)} m. East-face Q ${p.east_face_discharge_m3_s.toExponential(3)} m³/s; south-face Q ${p.south_face_discharge_m3_s.toExponential(3)} m³/s. Unit tracer ${p.unit_tracer_concentration.toFixed(6)}.`;
 if(cellMarker)map.removeLayer(cellMarker);cellMarker=L.circleMarker([p.center_lonlat[1],p.center_lonlat[0]],{radius:5,color:'#ff277a',fillOpacity:0}).addTo(map);
 }catch(err){$('#native-cell').textContent=err.message;}});
for(const id of ['native-snapshot','native-height','native-terrain-style','native-metric'])$('#'+id).onchange=rebuildLayers;
for(const id of ['native-imagery','native-water','native-banks'])$('#'+id).onchange=syncBaseLayers;
$('#native-height-alpha').oninput=()=>heightLayer?.setOpacity(Number($('#native-height-alpha').value)/100);
$('#native-output-alpha').oninput=()=>outputLayer?.setOpacity(Number($('#native-output-alpha').value)/100);
for(const id of ['native-arrows','native-grid','native-idle','native-minimum-q','native-overview-faces'])$('#'+id).onchange=loadFaces;
$('#native-reference').onchange=renderReference;
$('#native-fit').onclick=()=>{if(state?.manifest)map.fitBounds(state.manifest.bounds_lonlat,{animate:false});};
$('#native-pilot-area').onclick=async()=>{if(!comparisonData)await loadComparison();if(comparisonData){map.fitBounds(comparisonData.pilot_bounds_lonlat,{animate:false});return;}try{const r=await fetch('/api/channel-inspector/terrain_flow.json'),p=await r.json();const points=p.nodes.flatMap(n=>n.geometry.coordinates[0].map(c=>[c[1],c[0]]));map.fitBounds(L.latLngBounds(points),{animate:false});}catch(e){$('#native-comparison').textContent=e.message;}};
$('#native-cell-zoom').onclick=()=>map.setZoom(23,{animate:false});
$('#native-focus-flow').onclick=()=>{
 const list=(lastFaceData?.faces||[]).filter(f=>Math.abs(f.discharge_m3_s)>Math.max(Number($('#native-minimum-q').value),1e-15));if(!list.length)return;
 const f=list.reduce((a,b)=>Math.abs(a.discharge_m3_s)>Math.abs(b.discharge_m3_s)?a:b);
 const center=[(f.from_coordinates[1]+f.to_coordinates[1])/2,(f.from_coordinates[0]+f.to_coordinates[0])/2];
 map.setView(center,23,{animate:false});$('#native-cell').textContent=`Selected native ${f.id}: Q ${f.discharge_m3_s.toExponential(3)} m³/s. Click an adjacent cell for depth and stage.`;
};
$('#native-network-view').onclick=()=>{$('#native-imagery').checked=false;$('#native-height').checked=false;$('#native-banks').checked=false;$('#native-water').checked=true;$('#native-arrows').checked=true;$('#native-view-label').textContent='EXTRACTED REACHES + 2D CELL FLOWS';$('#map').style.background='#f8fbfd';rebuildLayers();};
$('#native-layered-view').onclick=()=>{$('#native-imagery').checked=true;$('#native-height').checked=true;$('#native-view-label').textContent='CONTINUOUS 0.5 m HYDRAULIC GRID';rebuildLayers();};
$('#native-refresh').onclick=()=>{refresh();loadComparison();loadFaces();};
fetch('/api/channel-inspector/inspector.json').then(r=>{if(!r.ok)throw Error('Mapped feature layer unavailable');return r.json();}).then(data=>{
 const waterKinds=new Set(['Canal','Water','Temple Moat','Pond']),water=data.features.filter(f=>waterKinds.has(f.properties.kind)),banks=data.features.filter(f=>!waterKinds.has(f.properties.kind));
 const options={pane:'nativeFeatures',style:f=>({pane:'nativeFeatures',color:{Canal:'#00bac8',Water:'#ff941f','Temple Moat':'#a66be2',Pond:'#318eff','Pond Bank':'#c6b100','Raised Linear':'#dd559e'}[f.properties.kind]||'#777',weight:1.6,fillOpacity:0}),onEachFeature:(f,l)=>l.bindTooltip(`Mapped ${f.properties.kind} · ${f.properties.fid}; geometry is not proof of current flow.`)};
 featureLayer=L.geoJSON(water,options);bankLayer=L.geoJSON(banks,options);syncBaseLayers();$('#native-features-status').textContent=`${water.length.toLocaleString()} mapped water features. Dry channels keep their outlines; orange arrows require computed flow.`;
 }).catch(e=>{$('#native-features-status').textContent=e.message;});
refresh();loadComparison();setInterval(refresh,15000);displayScale();

const reachGroup=L.layerGroup().addTo(map),nodeGroup=L.layerGroup().addTo(map),portGroup=L.layerGroup().addTo(map);
const reachCanvas=L.canvas({pane:'nativeReaches'}),nodeCanvas=L.canvas({pane:'nativeNodes'});let networkVersion=0,networkStamp='';
async function loadNetwork(){
 const version=++networkVersion;reachGroup.clearLayers();nodeGroup.clearLayers();portGroup.clearLayers();
 try{
  const b=map.getBounds(),bounds=[b.getWest(),b.getSouth(),b.getEast(),b.getNorth()].join(',');
  const names=$('#network-reaches').checked?['reaches']:[];
  if(map.getZoom()>=18&&$('#network-nodes').checked)names.push('nodes');
  if(map.getZoom()>=18&&$('#network-ports').checked)names.push('ports');
  const results=await Promise.all(names.map(async name=>{const r=await fetch(withCase('/api/water-network/layers/'+name+'?bounds='+encodeURIComponent(bounds)));if(!r.ok)throw Error('Reach extraction is still being prepared');return [name,await r.json()];}));
  if(version!==networkVersion)return;
  for(const [name,data] of results){
   if(name==='reaches')for(const f of data.features){const p=f.properties,d=p.flow_direction||0;
    const changed=$('#rainfall-change-colours').checked&&p.rainfall_comparison,colour=changed&&p.rainfall_comparison==='newly directional'?'#008c62':changed&&p.rainfall_comparison==='reversed direction'?'#a82d99':changed&&p.rainfall_comparison==='lost consistent direction'?'#777':d?'#d66500':'#009eab';
    const tip=`${p.id} · ${p.kind} · ${p.length_m.toFixed(1)} m · ${p.flow_status}. ${p.discharge_m3_s==null?'No hydraulic flux result yet.':'Mid-section Q '+p.discharge_m3_s.toExponential(3)+' m³/s; positive from-node toward to-node.'}${p.delta_discharge_m3_s==null?'':' Control ΔQ '+p.delta_discharge_m3_s.toExponential(3)+' m³/s; '+p.rainfall_comparison+'.'}`;
    L.geoJSON(f,{renderer:reachCanvas,pane:'nativeReaches',style:{color:colour,weight:d?2.8:1.7,opacity:.9}}).bindTooltip(tip).addTo(reachGroup);
    if(d){const cs=f.geometry.coordinates,mid=Math.floor(cs.length/2),a=cs[Math.max(0,mid-1)],b=cs[Math.min(cs.length-1,mid+1)];arrow(d>0?a:b,d>0?b:a,colour,1.5,tip,true,reachGroup,reachCanvas,'nativeReaches');}
   }
   else L.geoJSON(data,{renderer:nodeCanvas,pane:'nativeNodes',pointToLayer:(f,ll)=>L.circleMarker(ll,{renderer:nodeCanvas,pane:'nativeNodes',radius:name==='ports'?4:f.properties.degree>2?3.5:2,color:name==='ports'?'#ed6fce':'#164759',weight:1,fillOpacity:.8}),onEachFeature:(f,l)=>l.bindTooltip(name==='ports'?`${f.properties.id}: contact with ${f.properties.storage_id}; crest unverified`:`${f.properties.id}: ${f.properties.role}; ${f.properties.degree} reaches; geometric connectivity only`)}).addTo(name==='ports'?portGroup:nodeGroup);
  }
  window.waterNetworkReady=true;
 }catch(e){$('#network-status').textContent=e.message;}
}
async function refreshNetwork(){try{
 const requestedCase=selectedCase(),r=await fetch(withCase('/api/water-network/status'));if(!r.ok)throw Error('Network unavailable');const data=await r.json();if(requestedCase!==selectedCase())return;const m=data.network_manifest;
 if(!m){$('#network-status').textContent='Native centerline extraction still computing.';return;}
 $('#network-status').textContent=`${m.reaches.toLocaleString()} reaches · ${m.nodes.toLocaleString()} nodes · ${m.components.toLocaleString()} geometric components · ${m.waterbodies.toLocaleString()} storage polygons · ${m.ports.toLocaleString()} mapped contacts. Extraction on the native ${m.extraction_resolution_m} m grid. Components are geometric candidates, not verified flow connectivity.`;
 $('#network-flow-status').textContent=data.coupling?`2D flux samples at ${data.coupling.time_s} s: `+Object.entries(data.coupling.flow_status_counts).map(([k,v])=>v.toLocaleString()+' '+k).join('; ')+'. Transient cross-section estimates, not steady 1D flows.':'Reach geometry ready. The corrected water-present 2D run is computing; directions will appear after flux integration.';
 $('#native-report-link').hidden=data.acceptance?.stage!=='complete'||!!data.scenario_summary;
 $('#pilot-comparison-section').hidden=!!data.scenario_summary;$('#rainfall-summary-link').hidden=!data.scenario_summary;updateDownloadLinks();
 if(data.scenario_summary){const s=data.scenario_summary,c=s.reach_comparison.directional_class_changes,area=s.raster_comparison.area_at_or_above_depth_m_m2;$('#rainfall-comparison').textContent=`${s.rainfall_mm_hr} mm/h × ${s.duration_s/60} min = ${s.total_rainfall_mm.toFixed(2)} mm. Same-duration zero-rain control: ${c.newly_directional} newly consistent reaches; ${c.reversed_direction} reversed. End-of-event area: ≥1 cm ${((area['0.01']||0)/10000).toFixed(2)} ha; ≥5 cm ${((area['0.05']||0)/10000).toFixed(2)} ha; ≥10 cm ${((area['0.1']||0)/10000).toFixed(2)} ha. ${s.raster_comparison.newly_flowing_faces.toLocaleString()} newly qualifying native faces (not a count of spillways).`;}else{$('#rainfall-comparison').textContent='Current reference: 60 s without rain. Rainfall comparisons use their separate, same-duration zero-rain control.';}
 if(data.preflight){const p=data.preflight;preflightQuality=`Native pilot-window preflight: conservation and finite-state checks passed; ${p.faces_froude_over_1_at_depth_at_least_1cm.toLocaleString()} of ${p.faces_depth_at_least_1cm.toLocaleString()} faces at least 1 cm deep exceed Froude 1. Regime review required; regional export checks remain pending.`;if(!state?.verification)$('#native-quality').textContent=preflightQuality;}
 const stamp=JSON.stringify([m.reaches,data.coupling]);if(stamp!==networkStamp){networkStamp=stamp;loadNetwork();}
 }catch(e){$('#network-status').textContent=e.message;}}
for(const id of ['network-reaches','network-nodes','network-ports'])$('#'+id).onchange=loadNetwork;
map.on('moveend',loadNetwork);
$('#native-export-cells').onclick=async()=>{const label=$('#native-export-status');label.textContent='Preparing native cell export…';try{const b=map.getBounds(),bounds=[b.getWest(),b.getSouth(),b.getEast(),b.getNorth()].join(',');const data=await request('cells?bounds='+encodeURIComponent(bounds)+'&snapshot='+$('#native-snapshot').value);const url=URL.createObjectURL(new Blob([JSON.stringify(data)],{type:'application/geo+json'})),a=document.createElement('a');a.href=url;a.download='native_cells_'+$('#native-snapshot').value+'.geojson';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);label.textContent=`Exported ${data.features.length.toLocaleString()} native cells.`;}catch(e){label.textContent=e.message;}};
refreshNetwork();setInterval(refreshNetwork,15000);loadNetwork();

async function refreshRainfall(){try{
 const r=await fetch('/api/rainfall-scenarios/status',{cache:'no-store'});if(!r.ok)throw Error('Rainfall catalog unavailable');const data=await r.json(),s=data.suite;
 if(!s){$('#rainfall-status').textContent='No rainfall sweep prepared.';return;}
 const completed=s.cases.filter(c=>c.status==='complete').length,p=s.current_progress,sim=p?.simulation,current=s.cases.find(c=>c.directory===s.current_case);
 $('#rainfall-status').textContent=`${completed}/${s.cases.length} cases verified · ${s.configuration.duration_s/60}-minute events · batch ${s.status} · Slurm ${s.slurm_job_id||'not submitted'}.${current?' Current: '+current.rainfall_mm_hr+' mm/h.':''}${sim?' '+sim.time_s.toFixed(1)+' / '+sim.duration_s+' simulated seconds.':''}${s.error?' '+s.error:''}`;
 const select=$('#rainfall-case');
 for(const c of s.cases){let option=Array.from(select.options).find(o=>o.value===c.directory);if(!option){option=new Option('',c.directory);select.add(option);}option.disabled=c.status!=='complete';option.textContent=`${c.rainfall_mm_hr} mm/h · ${c.duration_s/60} min · ${c.total_rainfall_mm.toFixed(2)} mm${c.status!=='complete'?' · '+c.status:''}`;}
 window.rainfallCatalogReady=true;
 }catch(e){$('#rainfall-status').textContent=e.message;}}
$('#rainfall-case').onchange=()=>{$('#native-reference').checked=false;referenceGroup.clearLayers();faceVersion++;cellVersion++;networkVersion++;networkStamp='';faceAbort?.abort();arrowGroup.clearLayers();gridGroup.clearLayers();reachGroup.clearLayers();nodeGroup.clearLayers();portGroup.clearLayers();comparisonData=null;displayedSnapshot=null;window.waterNetworkReady=false;window.regionalNativeReady=false;preflightQuality='';updateDownloadLinks();refresh();refreshNetwork();};
$('#rainfall-change-colours').onchange=loadNetwork;
refreshRainfall();setInterval(refreshRainfall,15000);
