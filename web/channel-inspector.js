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

let flowData,flowGroup=L.layerGroup().addTo(map);
const fixedTerrainFiles={terrain:'terrain_flow.json',terrain10:'terrain_review_10m.json',terrain5:'terrain_review_5m.json'};
function renderFlow(){if(flowData)renderTerrainFlow();}
function setFlow(result){
 if(result.version!==2)throw Error('This workspace accepts fixed-terrain 2D results only.');
 flowData=result;
 for(const id of ['flow-time','flow-alpha','flow-visible'])$('#'+id).disabled=false;
 $('#run-flow').disabled=$('#model-scope').value!=='terrain';
 $('#flow-config').value=JSON.stringify(result.parameters,null,2);
 $('#flow-time').max=result.frames.length-1;$('#flow-time').value=result.frames.length-1;
 renderFlow();window.channelFlowReady=true;
}
async function loadFlow(){
 if(typeof clearTerrainReview==='function')clearTerrainReview();
 try{
  const scope=$('#model-scope').value;$('#quick-model-scope').value=scope;
  const file=fixedTerrainFiles[scope];if(!file)throw Error('Select a fixed-terrain 2D model');
  $('#flow-status').textContent='Loading fixed-terrain 2D results…';
  const response=await fetch('/api/channel-inspector/'+file);if(!response.ok)throw Error('Selected model unavailable');
  setFlow(await response.json());fitFlow();
 }catch(e){$('#flow-status').textContent=e.message;}
}
function fitFlow(){if(flowData)map.fitBounds(L.latLngBounds(flowData.nodes.map(n=>[n.coordinates[1],n.coordinates[0]])).pad(.1));}
$('#load-flow').onclick=loadFlow;$('#focus-flow').onclick=loadFlow;
$('#network-view').onclick=async()=>{
 if(!flowData)await loadFlow();if(!flowData)return;
 networkMode=true;for(const s of Object.values(specs))if(s.layer)map.removeLayer(s.layer);
 $('#flow-visible').checked=true;renderFlow();fitFlow();$('#view-label').textContent='FLOW FACES · fixed-terrain 2D';
};
$('#layered-view').onclick=()=>{networkMode=false;for(const s of Object.values(specs))if(s.enabled&&s.layer)s.layer.addTo(map);renderFlow();$('#view-label').textContent='LAYERED VIEW · fixed-terrain 2D';};
for(const id of ['flow-time','flow-alpha','flow-visible'])$('#'+id).addEventListener('input',renderFlow);
$('#model-scope').onchange=loadFlow;
$('#quick-model-scope').onchange=()=>{$('#model-scope').value=$('#quick-model-scope').value;loadFlow();};
$('#run-flow').onclick=async()=>{
 const button=$('#run-flow');button.disabled=true;
 try{
  if($('#model-scope').value!=='terrain')throw Error('Matched studies are saved reference runs.');
  const config=JSON.parse($('#flow-config').value);$('#flow-status').textContent='Solving fixed-terrain pilot…';
  const response=await fetch('/api/terrain-flow/simulate',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(config)});
  const result=await response.json();if(!response.ok)throw Error(result.error||'Run failed');setFlow(result);
 }catch(e){$('#flow-status').textContent=e.message;}
 finally{button.disabled=$('#model-scope').value!=='terrain';}
};

const terrainDepthCanvas=L.canvas({pane:'flowDepth'}),terrainFaceCanvas=L.canvas({pane:'flowNetwork'});
function renderTerrainFlow(){
 flowGroup.clearLayers();if(!flowData||!$('#flow-visible').checked)return;
 const f=flowData.frames[Number($('#flow-time').value)],alpha=Number($('#flow-alpha').value)/100;
 $('#flow-time-label').textContent=(f.time_s/60).toFixed(1)+' min';
 const metric=$('#terrain-metric').value;
 const values=metric==='tracer'?f.tracer_concentration:metric==='maximum'?flowData.maximum_depth_m:metric==='stage'?f.stage_m:f.depth_m;
 const visible=values.filter((v,i)=>metric==='maximum'?v>.001:f.depth_m[i]>.001);
 const low=metric==='stage'&&visible.length?Math.min(...visible):0;
 const high=metric==='tracer'?1:metric==='stage'&&visible.length?Math.max(...visible):Math.max(1,...visible);
 $('#terrain-legend').textContent=metric==='tracer'?'Purple: dimensionless conservative unit tracer, 0–1; not bacterial concentration.':metric==='stage'?`Water level colours ${low.toFixed(2)}–${high.toFixed(2)} m (unverified datum).`:`Blue: ${metric==='maximum'?'maximum':'current'} volume / whole cell area, 0–${high.toFixed(2)} m. Dry cells hidden. Local depth varies within each cell.`;
 const indices=new Map(flowData.nodes.map((n,i)=>[n.id,i]));
 flowData.nodes.forEach((n,i)=>{
  if((metric==='maximum'?values[i]:f.depth_m[i])<=.001)return;
  const v=Math.max(0,Math.min(1,(values[i]-low)/Math.max(1e-9,high-low)));
  const fill=metric==='tracer'?`rgb(${Math.round(245-130*v)},${Math.round(235-205*v)},${Math.round(250-70*v)})`:`rgb(${Math.round(225-210*v)},${Math.round(245-160*v)},${Math.round(255-100*v)})`;
  L.geoJSON(n.geometry,{renderer:terrainDepthCanvas,pane:'flowDepth',style:{weight:.2,color:'#305a7a',fillColor:fill,fillOpacity:alpha,opacity:alpha},onEachFeature:(g,l)=>l.on('click',()=>{$('#selection').textContent=`${n.id}: mean depth ${f.depth_m[i].toFixed(3)} m; stage ${f.stage_m[i].toFixed(3)} m; mapped-water fraction ${(100*n.water_fraction).toFixed(0)}%; unit tracer ${f.tracer_concentration[i].toFixed(4)}. Fixed present-terrain scenario; bathymetry unverified.`;})}).addTo(flowGroup);
 });
 const maximum=Math.max(1e-8,...f.flows_m3_s.map(Math.abs)),displayThreshold=Math.max(1e-5,maximum*.01);const active=f.flows_m3_s.filter(q=>Math.abs(q)>=1e-5).length;
 flowData.edges.forEach((e,i)=>{
  const q=f.flows_m3_s[i],wet=f.active_width_m[i],showAll=$('#terrain-faces').checked;
  if(Math.abs(q)<displayThreshold&&!showAll)return;
  const coords=e.face_geometry.coordinates.map(p=>[p[1],p[0]]);
  L.polyline(coords,{renderer:terrainFaceCanvas,pane:'flowNetwork',color:Math.abs(q)>=1e-5?'#ed791a':'#777',weight:Math.abs(q)>=1e-5?1+3*Math.abs(q)/maximum:.6,opacity:Math.abs(q)>=1e-5?alpha:.35}).bindTooltip(`${e.id}: signed Q ${q.toExponential(3)} m³/s; crest ${e.crest_min_m.toFixed(2)}–${e.crest_max_m.toFixed(2)} m; wetted face width ${wet.toFixed(1)} m. A wet face need not carry net flow.`).addTo(flowGroup);
  if(Math.abs(q)<Math.max(1e-5,maximum*.02))return;
  const aa=flowData.nodes[indices.get(q>=0?e.from:e.to)].coordinates,bb=flowData.nodes[indices.get(q>=0?e.to:e.from)].coordinates;
  const x=(aa[0]+bb[0])/2,y=(aa[1]+bb[1])/2,dx=(bb[0]-aa[0])*.3,dy=(bb[1]-aa[1])*.3;
  L.polyline([[y-dy,x-dx],[y+dy,x+dx]],{renderer:terrainFaceCanvas,pane:'flowNetwork',color:'#be4d00',weight:1.5,opacity:alpha}).addTo(flowGroup);
  L.polyline([[y+dy*.3+dx*.35,x+dx*.3-dy*.35],[y+dy,x+dx],[y+dy*.3-dx*.35,x+dx*.3+dy*.35]],{renderer:terrainFaceCanvas,pane:'flowNetwork',color:'#be4d00',weight:1.5,opacity:alpha}).addTo(flowGroup);
 });
 $('#graph-stats').textContent=`Fixed-terrain 2D pilot · ${flowData.nodes.length} cells at ${flowData.parameters.grid_spacing_m} m · ${flowData.edges.length} actual shared faces · ${active} flowing at this time. 0.5 m source terrain.`;
 $('#flow-budget').textContent=JSON.stringify({water:flowData.budget,unit_tracer:flowData.tracer_budget},null,2);
 if(typeof renderTerrainReview==='function')renderTerrainReview();
 $('#flow-status').textContent=`${flowData.parameters.duration_s}-second hypothetical rise and recession. No erosion. ${['terrain10','terrain5'].includes($('#model-scope').value)?'Saved comparison run; rebuild with scripts/build_terrain_refinement.py.':'Edit the configuration below and run, or use configs/terrain_flow.json.'} Local-inertial research prototype; not calibrated.`;
}
$('#terrain-metric').onchange=renderFlow;
$('#terrain-faces').onchange=renderFlow;
