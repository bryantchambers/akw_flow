const $=s=>document.querySelector(s);
const map=L.map('map',{maxZoom:22,preferCanvas:true}).setView([13.43,103.83],12);
map.createPane('nativeHeight');map.getPane('nativeHeight').style.zIndex=310;
map.createPane('nativeOutput');map.getPane('nativeOutput').style.zIndex=330;
map.createPane('nativeFeatures');map.getPane('nativeFeatures').style.zIndex=420;
map.createPane('nativeArrows');map.getPane('nativeArrows').style.zIndex=450;
const imagery=L.tileLayer('https://services.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',{maxZoom:22,maxNativeZoom:17,attribution:'Esri, Vantor, Earthstar Geographics, GIS User Community'}).addTo(map);
let state,footprint,heightLayer,outputLayer,featureLayer,arrowGroup=L.layerGroup().addTo(map),cellMarker,lastStatus=null,vectorVersion=0,cellVersion=0,fitDone=false,displayedSnapshot=null;
const endpoint='/api/regional-native/';
async function request(path){const r=await fetch(endpoint+path,{cache:'no-store'});if(!r.ok){let error;try{error=(await r.json()).error;}catch{}throw Error(error||'Regional data unavailable');}return r.json();}
function rebuildLayers(){
 const key=$('#native-snapshot').value;
 if(displayedSnapshot!==key){cellVersion++;if(cellMarker)map.removeLayer(cellMarker);$('#native-cell').textContent='Click the map to inspect a native cell in the selected saved state.';displayedSnapshot=key;}
 if(heightLayer)map.removeLayer(heightLayer);if(outputLayer)map.removeLayer(outputLayer);
 if($('#native-height').checked){heightLayer=L.tileLayer(endpoint+'tiles/'+$('#native-terrain-style').value+'/'+key+'/{z}/{x}/{y}.png',{pane:'nativeHeight',className:'native-layer',maxZoom:22,opacity:Number($('#native-height-alpha').value)/100}).addTo(map);}
 const metric=$('#native-metric').value;
 if(metric!=='none')outputLayer=L.tileLayer(endpoint+'tiles/'+metric+'/'+key+'/{z}/{x}/{y}.png',{pane:'nativeOutput',className:'native-layer',maxZoom:22,opacity:Number($('#native-output-alpha').value)/100}).addTo(map);
 $('#native-legend').textContent=metric==='tracer'?'Purple: conservative unit tracer, 0–1, clipped. Dry cells hidden. Numerical routing check only.':metric==='depth'?'Blue: water depth, square-root colours 0–1 m, clipped; values below 1 mm hidden. Click for native values.':($('#native-terrain-style').value==='hillshade'?'Model output hidden. Hillshade reveals relief; light from the northwest.':'Model output hidden. Terrain colours: 15–60 m, clipped; vertical datum unverified.');
 loadVectors();
}
async function refresh(){try{
 state=await request('status');const m=state.manifest,p=state.progress;
 $('#native-progress').textContent=p?`Build: ${p.stage}${p.simulation?' · '+p.simulation.time_s.toFixed(2)+' / '+p.simulation.duration_s+' simulated seconds · '+p.simulation.steps+' steps':''}${p.error?' · '+p.error:''}`:'Build not started';
 if(!m)return;
 $('#native-summary').textContent=`${m.valid_cells.toLocaleString()} valid cells · ${m.valid_area_km2.toFixed(2)} km² · actual ${m.solver_spacing_m} m solver spacing and terrain. Full supplied survey footprint.`;
 $('#native-scenario').textContent=m.parameters.scenario_label;
 $('#native-config').textContent=JSON.stringify({parameters:m.parameters,scope:m.scope,source_state:m.source_state,friction_treatment:m.friction_treatment,velocity_depth_timing:m.velocity_depth_timing,assumptions:m.assumptions},null,2);
 const q=state.verification;$('#native-quality').textContent=q?`Native export checks passed. ${q.faces_with_froude_over_one_and_face_depth_at_least_1cm?.toLocaleString()??'Uncounted'} faces with at least 1 cm face depth exceed Froude 1; these require review. Very shallow films have additional limitations. This is not predictive hydraulic validation.`:'Export and hydraulic-regime checks pending.';
 $('#native-budget').textContent=m.budget?JSON.stringify({water:m.budget,tracer:m.tracer_budget},null,2):'Initial model prepared; final result still computing.';
 if(!fitDone){map.fitBounds(m.bounds_lonlat);fitDone=true;footprint=L.rectangle(m.bounds_lonlat,{color:'#fff',weight:2,fill:false,dashArray:'6 5'}).addTo(map);rebuildLayers();}
 if(!(m.status==='complete'&&m.snapshots.some(s=>s.key==='final'))&&Array.from($('#native-snapshot').options).some(o=>o.value==='final')){for(const option of Array.from($('#native-snapshot').options))if(option.value==='final')option.remove();$('#native-snapshot').value='initial';rebuildLayers();}
 if(m.status==='complete'&&m.snapshots.some(s=>s.key==='final')&&!Array.from($('#native-snapshot').options).some(o=>o.value==='final')){
  $('#native-snapshot').add(new Option(`Final startup check · ${m.parameters.duration_s} s`,'final'));$('#native-snapshot').value='final';rebuildLayers();
 }
 lastStatus=m.status;window.regionalNativeReady=true;
 }catch(e){$('#native-progress').textContent=e.message;}}
async function loadVectors(){
 const version=++vectorVersion;arrowGroup.clearLayers();if(!$('#native-arrows').checked||$('#native-snapshot').value!=='final')return;
 const b=map.getBounds(),bounds=[b.getWest(),b.getSouth(),b.getEast(),b.getNorth()].join(',');
 try{const v=await request('vectors?bounds='+encodeURIComponent(bounds)+'&snapshot=final');if(version!==vectorVersion)return;
 for(const item of v){const p=map.latLngToLayerPoint([item.lonlat[1],item.lonlat[0]]),u=item.east_m_s,w=item.north_m_s,speed=Math.hypot(u,w),length=14;
 const dx=length*u/speed,dy=-length*w/speed;
 const a=map.layerPointToLatLng([p.x-dx*.5,p.y-dy*.5]),b=map.layerPointToLatLng([p.x+dx*.5,p.y+dy*.5]);
 L.polyline([a,b],{pane:'nativeArrows',color:'#ff8b18',weight:1.5}).bindTooltip(`Sampled face velocity ${speed.toFixed(4)} m/s; depth ${item.depth_m.toFixed(4)} m`).addTo(arrowGroup);
 L.polyline([map.layerPointToLatLng([p.x+dx*.15-dy*.2,p.y+dy*.15+dx*.2]),b,map.layerPointToLatLng([p.x+dx*.15+dy*.2,p.y+dy*.15-dx*.2])],{pane:'nativeArrows',color:'#ff8b18',weight:1.5}).addTo(arrowGroup);
 }}catch(e){$('#native-progress').textContent=e.message;}
}
function displayScale(){const metres=156543.03392*Math.cos(map.getCenter().lat*Math.PI/180)/2**map.getZoom();$('#native-display').textContent=`Map display ≈ ${metres.toFixed(2)} m per screen pixel at zoom ${map.getZoom()}; hydraulic cells remain 0.50 m.`;}
map.on('moveend',()=>{displayScale();loadVectors();});
map.on('click',async e=>{const version=++cellVersion;try{const p=await request(`point?lon=${e.latlng.lng}&lat=${e.latlng.lat}&snapshot=${$('#native-snapshot').value}`);if(version!==cellVersion)return;
 $('#native-cell').textContent=`Cell r${p.row} c${p.col} · 0.50 m. Terrain ${p.terrain_elevation_m.toFixed(4)} m; water depth ${p.water_depth_m.toFixed(6)} m; stage ${p.water_stage_m.toFixed(4)} m. East-face Q ${p.east_face_discharge_m3_s.toExponential(3)} m³/s; south-face Q ${p.south_face_discharge_m3_s.toExponential(3)} m³/s. Unit tracer ${p.unit_tracer_concentration.toFixed(6)}.`;
 if(cellMarker)map.removeLayer(cellMarker);cellMarker=L.circleMarker([p.center_lonlat[1],p.center_lonlat[0]],{radius:5,color:'#ff277a',fillOpacity:0}).addTo(map);
 }catch(err){$('#native-cell').textContent=err.message;}});
for(const id of ['native-snapshot','native-height','native-terrain-style','native-metric'])$('#'+id).onchange=rebuildLayers;
$('#native-imagery').onchange=()=>{$('#native-imagery').checked?imagery.addTo(map):map.removeLayer(imagery);};
$('#native-height-alpha').oninput=()=>heightLayer?.setOpacity(Number($('#native-height-alpha').value)/100);
$('#native-output-alpha').oninput=()=>outputLayer?.setOpacity(Number($('#native-output-alpha').value)/100);
$('#native-arrows').onchange=loadVectors;
$('#native-water').onchange=()=>{if(featureLayer)$('#native-water').checked?featureLayer.addTo(map):map.removeLayer(featureLayer);};
$('#native-fit').onclick=()=>{if(state?.manifest)map.fitBounds(state.manifest.bounds_lonlat);};
$('#native-refresh').onclick=refresh;
fetch('/api/channel-inspector/inspector.json').then(r=>r.json()).then(data=>{featureLayer=L.geoJSON(data.features,{pane:'nativeFeatures',style:f=>({pane:'nativeFeatures',color:{Canal:'#00e6e8',Water:'#ff941f','Temple Moat':'#be76ff',Pond:'#318eff','Pond Bank':'#ffff4f','Raised Linear':'#ff70a8'}[f.properties.kind]||'#fff',weight:1.4,fillOpacity:0}),onEachFeature:(f,l)=>l.bindTooltip(f.properties.kind+' · '+f.properties.fid)});if($('#native-water').checked)featureLayer.addTo(map);}).catch(()=>{});
refresh();setInterval(refresh,15000);displayScale();
