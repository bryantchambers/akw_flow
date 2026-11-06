import * as THREE from 'three';
import { OrbitControls } from '/vendor/OrbitControls.js';
const $ = s => document.querySelector(s);
let data, imported = null, renderer, scene, camera, controls, terrain, root, waters, points, fence, importedLines;
let currentPoints = [], selected = -1, renderPending = true;
const raycaster = new THREE.Raycaster(), pointer = new THREE.Vector2();
const container = $('#canvas-container');
const ramp = ['#608a65','#d2c16a','#e6a45b','#bf5b43','#902f30'].map(s => new THREE.Color(s));
const labels = [];
function color(value) {
  const t = Math.max(0, Math.min(.999999, value)) * (ramp.length - 1), i = Math.floor(t);
  return ramp[i].clone().lerp(ramp[i + 1], t - i);
}
function inside(lon, lat) { const [w,s,e,n] = data.bbox_wsen; return lon>=w && lon<=e && lat>=s && lat<=n; }
function position(lon, lat, offset = 0) {
  const [w,s,e,n] = data.bbox_wsen;
  const col = Math.max(0,Math.min(data.width-1,(lon-w)/(e-w)*(data.width-1)));
  const row = Math.max(0,Math.min(data.height-1,(n-lat)/(n-s)*(data.height-1)));
  const r0=Math.floor(row), c0=Math.floor(col), r1=Math.min(r0+1,data.height-1), c1=Math.min(c0+1,data.width-1);
  const fx=col-c0, fy=row-r0, z=data.elevation_m;
  const elevation=(z[r0*data.width+c0]*(1-fx)+z[r0*data.width+c1]*fx)*(1-fy)+(z[r1*data.width+c0]*(1-fx)+z[r1*data.width+c1]*fx)*fy;
  return new THREE.Vector3((lon-(w+e)/2)*111.32*Math.cos((n+s)/2*Math.PI/180),(elevation-data.terrain.min_m)/1000+offset,((n+s)/2-lat)*111.32);
}
function dispose(object) {
  if (!object) return;
  root.remove(object); object.traverse(child=>{child.geometry?.dispose(); if(child.material) for(const m of (Array.isArray(child.material)?child.material:[child.material])) m.dispose();});
}
function lineSegments(features, valueColor = null) {
  const verts=[], colors=[];
  for (const f of features) {
    let paths=[];
    if (f.geometry.type==='LineString') paths=[f.geometry.coordinates];
    if (f.geometry.type==='Polygon') paths=f.geometry.coordinates;
    const c=valueColor?valueColor(f.properties.value):new THREE.Color(f.properties.waterway==='canal'?'#147c9c':f.geometry.type==='Polygon'?'#54a8ac':'#2499a5');
    for (const path of paths) for(let i=1;i<path.length;i++) {
      const a=path[i-1],b=path[i]; if(!inside(a[0],a[1])||!inside(b[0],b[1]))continue;
      const pa=position(a[0],a[1],.003),pb=position(b[0],b[1],.003);
      verts.push(...pa.toArray(),...pb.toArray());colors.push(c.r,c.g,c.b,c.r,c.g,c.b);
    }
  }
  const geo=new THREE.BufferGeometry();geo.setAttribute('position',new THREE.Float32BufferAttribute(verts,3));geo.setAttribute('color',new THREE.Float32BufferAttribute(colors,3));
  return new THREE.LineSegments(geo,new THREE.LineBasicMaterial({vertexColors:true,transparent:true,opacity:.95,depthTest:false}));
}
function currentMode() {return $('#output-mode').value;}
function updateTerrain() {
  const field = data.screening_area_km2;
  const max = Math.max(...field), span=data.terrain.max_m-data.terrain.min_m;
  const colors=new Float32Array(field.length*3);
  for(let i=0;i<field.length;i++) {
    const base=new THREE.Color('#b9cba1').lerp(new THREE.Color('#859866'),(data.elevation_m[i]-data.terrain.min_m)/Math.max(1,span));
    let c=base;
    if(currentMode()==='screening') {
      const t=Math.log1p(field[i])/Math.log1p(max);
      c=base.clone().lerp(color(t), Math.min(.9,t*1.4));
    }
    colors[i*3]=c.r;colors[i*3+1]=c.g;colors[i*3+2]=c.b;
  }
  terrain.geometry.setAttribute('color',new THREE.BufferAttribute(colors,3));
  renderPending=true;
}
function setLegend() {
  const mode=currentMode();
  if(mode==='screening') {
    $('#legend-title').textContent='Upstream contributing area';$('#legend-unit').textContent='km² · logarithmic colour scale';
    $('#legend-min').textContent='0';$('#legend-max').textContent=Math.max(...data.screening_area_km2).toFixed(1)+' km²';
    $('#result-label').textContent='TERRAIN SCREENING';$('#output-status').textContent='D8 contributing area · not calibrated flow or bacterial concentration.';
    $('#hotspot-heading').textContent='Highest contributing-area locations';
    $('#results-note').textContent='Drainage-screening candidates, not validated bacterial hotspots. Boundary points and local sinks depend on the extent and routing assumptions.';
    $('#scene-title').textContent='Terrain drainage screening';$('#ramp-colors').style.background='linear-gradient(90deg,#608a65,#d2c16a,#e6a45b,#bf5b43,#902f30)';
  } else if(mode==='elevation') {
    $('#legend-title').textContent='Surface elevation';$('#legend-unit').textContent='metres · EGM2008';$('#legend-min').textContent=data.terrain.min_m.toFixed(0)+' m';$('#legend-max').textContent=data.terrain.max_m.toFixed(0)+' m';
    $('#result-label').textContent='MODERN DSM';$('#output-status').textContent='Modern surface elevations include vegetation and structures. This is not historical canal bathymetry.';
    $('#hotspot-heading').textContent='Output locations';$('#results-note').textContent='Select drainage screening or import spatial model output to inspect candidate locations.';$('#scene-title').textContent='Surface elevation';
    $('#ramp-colors').style.background='linear-gradient(90deg,#b9cba1,#859866)';
  } else {
    const {metric,unit,name,scenario}=imported.model;
    const values=imported.visibleFeatures.map(f=>f.properties.value), min=Math.min(...values),max=Math.max(...values);
    $('#legend-title').textContent=metric;$('#legend-unit').textContent=unit+' · linear colour scale';$('#legend-min').textContent=min.toLocaleString();$('#legend-max').textContent=max.toLocaleString();
    $('#result-label').textContent='IMPORTED / UNVERIFIED';$('#output-status').textContent=`${name} / ${scenario}. User-supplied output; not independently validated.`;
    $('#hotspot-heading').textContent='Highest imported values';$('#results-note').textContent='Ranking uses the declared metric and unit. High values are not automatically bacterial hotspots.';$('#scene-title').textContent=metric+' · '+scenario;
    $('#ramp-colors').style.background='linear-gradient(90deg,#608a65,#d2c16a,#e6a45b,#bf5b43,#902f30)';
  }
}
function makeHotspots() {
  dispose(points);dispose(importedLines);selected=-1;
  if(currentMode()==='screening')currentPoints=data.hotspots.map(p=>({...p,name:'Screening location '+p.id,unit:'km²'}));
  else if(currentMode()==='imported') {
    const f=imported.visibleFeatures;
    const vals=f.map(x=>x.properties.value),min=Math.min(...vals),max=Math.max(...vals);
    importedLines=new THREE.Group();
    importedLines.add(lineSegments(f,v=>color((v-min)/Math.max(1e-12,max-min))));
    const allPoints=f.filter(x=>x.geometry.type==='Point');
    if(allPoints.length){
      const g=new THREE.BufferGeometry();g.setFromPoints(allPoints.map(x=>position(x.geometry.coordinates[0],x.geometry.coordinates[1],.004)));
      const cs=allPoints.flatMap(x=>color((x.properties.value-min)/Math.max(1e-12,max-min)).toArray());
      g.setAttribute('color',new THREE.Float32BufferAttribute(cs,3));
      importedLines.add(new THREE.Points(g,new THREE.PointsMaterial({vertexColors:true,size:8,sizeAttenuation:false,depthTest:false})));
    }
    root.add(importedLines);
    currentPoints=[...f].sort((a,b)=>b.properties.value-a.properties.value).slice(0,10).map((feature,i)=>{
      const coords=feature.geometry.type==='Point'?feature.geometry.coordinates:feature.geometry.coordinates[Math.floor(feature.geometry.coordinates.length/2)];
      return {id:i+1,lon:coords[0],lat:coords[1],value:feature.properties.value,name:feature.properties.name||'Output feature '+(i+1),unit:imported.model.unit};
    });
  } else currentPoints=[];
  const geo=new THREE.BufferGeometry();geo.setFromPoints(currentPoints.map(p=>position(p.lon,p.lat,.006)));
  points=new THREE.Points(geo,new THREE.PointsMaterial({color:'#be633e',size:11,sizeAttenuation:false,depthTest:false}));points.renderOrder=10;root.add(points);points.visible=$('#hotspots-toggle').checked;
  $('#hotspot-list').replaceChildren(...currentPoints.map((p,i)=>{
    const b=document.createElement('button');b.className='hotspot';b.type='button';
    const rank=document.createElement('span');rank.className='rank';rank.textContent='#'+(i+1);
    const v=document.createElement('strong');v.textContent=p.value.toLocaleString(undefined,{maximumFractionDigits:2});
    const small=document.createElement('small');small.textContent=p.unit+' · '+p.lat.toFixed(4)+', '+p.lon.toFixed(4);
    b.append(rank,v,small);
    if(p.domain_boundary){const edge=document.createElement('span');edge.className='edge';edge.textContent='Domain boundary';b.append(edge);}
    b.addEventListener('click',()=>selectPoint(i,true));return b;
  }));
  $('#tooltip').hidden=true;renderPending=true;
}
function selectPoint(index,focus=false) {
  selected=index;const p=currentPoints[index];if(!p)return;
  document.querySelectorAll('.hotspot').forEach((b,i)=>b.classList.toggle('active',i===index));
  if(focus) {
    const target=position(p.lon,p.lat,.006);target.y*=root.scale.y;
    const delta=target.clone().sub(controls.target);camera.position.add(delta);controls.target.copy(target);controls.update();
  }
  const box=$('#tooltip');box.replaceChildren();
  const title=document.createElement('b');title.textContent=p.name;
  const value=document.createElement('span');value.textContent=p.value.toLocaleString()+' '+p.unit;
  const coordinate=document.createElement('span');coordinate.textContent=p.lat.toFixed(5)+' N, '+p.lon.toFixed(5)+' E';
  box.append(title,value,coordinate);box.hidden=false;renderPending=true;
}
function reset(top=false) {
  const [w,s,e,n]=data.bbox_wsen, width=(e-w)*111.32*Math.cos((s+n)/2*Math.PI/180),height=(n-s)*111.32;
  camera.up.set(0,1,0);
  controls.target.set(0,(data.terrain.max_m-data.terrain.min_m)/1000*root.scale.y*.18,0);
  if(top){camera.position.set(0,Math.max(width,height)*1.25,.001);camera.up.set(0,0,-1);}
  else camera.position.set(width*.60,Math.max(width,height)*.65,height*.74);
  camera.lookAt(controls.target);controls.update();renderPending=true;
}
function addFence() {
  const [w,s,e,n]=data.bbox_wsen, coords=[[w,s],[e,s],[e,n],[w,n],[w,s]];const vertices=[];
  for(let i=1;i<coords.length;i++) {
    const a=coords[i-1],b=coords[i];let last=null;
    for(let t=0;t<=80;t++){const u=t/80,p=position(a[0]+(b[0]-a[0])*u,a[1]+(b[1]-a[1])*u,.002);if(last)vertices.push(...last.toArray(),...p.toArray());last=p;}
  }
  const geo=new THREE.BufferGeometry();geo.setAttribute('position',new THREE.Float32BufferAttribute(vertices,3));
  fence=new THREE.LineSegments(geo,new THREE.LineDashedMaterial({color:'#a68142',dashSize:.5,gapSize:.25,depthTest:false}));fence.computeLineDistances();root.add(fence);
}
function validateImport(document) {
  if(document.type!=='FeatureCollection'||!document.model||!Array.isArray(document.features)||!document.features.length||document.features.length>10000)throw new Error('Use a FeatureCollection with 1–10,000 features and a model declaration.');
  for(const key of ['name','scenario','metric','unit'])if(typeof document.model[key]!=='string'||!document.model[key].trim()||document.model[key].length>200)throw new Error('Declare model '+key+' as a non-empty string (max 200 characters).');
  let totalCoordinates=0;
  for(const feature of document.features) {
    if(feature.type!=='Feature'||!feature.properties||typeof feature.properties.value!=='number'||!Number.isFinite(feature.properties.value))throw new Error('Every feature needs a finite numeric properties.value.');
    const g=feature.geometry;if(!g||!['Point','LineString'].includes(g.type))throw new Error('Only Point or LineString output is supported.');
    const coords=g.type==='Point'?[g.coordinates]:g.coordinates;
    if(!Array.isArray(coords)||coords.length<(g.type==='Point'?1:2)||coords.length>20000)throw new Error('Invalid geometry coordinates.');
    totalCoordinates+=coords.length;if(totalCoordinates>200000)throw new Error('Maximum 200,000 coordinate pairs per output file.');
    for(const c of coords)if(!Array.isArray(c)||c.length<2||!Number.isFinite(c[0])||!Number.isFinite(c[1])||Math.abs(c[0])>180||Math.abs(c[1])>90)throw new Error('Coordinates must be finite WGS84 longitude/latitude.');
  }
  document.visibleFeatures=document.features.filter(f=>f.geometry.type==='Point'?inside(...f.geometry.coordinates):f.geometry.coordinates.every(c=>inside(...c)));
  if(!document.visibleFeatures.length)throw new Error('No complete output features lie inside the study fence.');
  return document;
}
async function init() {
  try {
    const response=await fetch('/assets/data/context/viewer_scene.json');if(!response.ok)throw new Error('Terrain scene is unavailable.');data=await response.json();
    scene=new THREE.Scene();scene.background=new THREE.Color('#e6ede2');
    renderer=new THREE.WebGLRenderer({antialias:true,alpha:false});renderer.setPixelRatio(Math.min(window.devicePixelRatio,2));renderer.outputColorSpace=THREE.SRGBColorSpace;container.prepend(renderer.domElement);
    camera=new THREE.PerspectiveCamera(42,1,.01,1500);controls=new OrbitControls(camera,renderer.domElement);controls.enableDamping=false;controls.minDistance=1;controls.maxDistance=350;controls.maxPolarAngle=Math.PI*.49;controls.addEventListener('change',()=>renderPending=true);
    root=new THREE.Group();root.scale.y=Number($('#exaggeration').value);scene.add(root);
    scene.add(new THREE.AmbientLight('#ffffff',2));const sun=new THREE.DirectionalLight('#fffbe8',2.3);sun.position.set(-30,70,20);scene.add(sun);
    const [w,s,e,n]=data.bbox_wsen, width=(e-w)*111.32*Math.cos((s+n)/2*Math.PI/180),height=(n-s)*111.32;
    const geo=new THREE.PlaneGeometry(width,height,data.width-1,data.height-1);geo.rotateX(-Math.PI/2);
    for(let i=0;i<data.elevation_m.length;i++)geo.attributes.position.setY(i,(data.elevation_m[i]-data.terrain.min_m)/1000);
    geo.computeVertexNormals();terrain=new THREE.Mesh(geo,new THREE.MeshStandardMaterial({vertexColors:true,roughness:1,side:THREE.DoubleSide}));root.add(terrain);
    const grid=new THREE.GridHelper(100,20,'#c6d5bd','#d6dfcd');grid.position.y=-.05;scene.add(grid);
    waters=lineSegments(data.waterways.features);waters.renderOrder=5;root.add(waters);addFence();
    for(const landmark of data.landmarks){
      const node=document.createElement('div');node.textContent=landmark.name;node.style.cssText='position:absolute;font-size:10px;color:#365a4b;background:#f4f6e9c9;padding:2px 5px;border-radius:3px;pointer-events:none;';container.append(node);labels.push({node,landmark});
    }
    $('#water-count').textContent=data.waterways.features.length.toLocaleString()+' ways';
    $('#fence-bounds').textContent=`${w.toFixed(2)}–${e.toFixed(2)}° E / ${s.toFixed(2)}–${n.toFixed(2)}° N`;
    $('#mesh-info').textContent=`~30 m source · ~${Math.round(data.terrain.display_pixel_metres_approx[0])} m display`;
    $('#source-info').textContent=`${data.terrain.source}. Heights: EGM2008 metres; horizontal coordinates: WGS84. Native routing uses ${data.screening.native_cells.toLocaleString()} cells. Display terrain is aggregated.`;
    $('#snapshot-date').textContent='Scene prepared '+new Date(data.generated_utc).toLocaleDateString('en-GB');
    $('#loading').hidden=true;updateTerrain();setLegend();makeHotspots();reset();
    const resize=()=>{const rect=container.getBoundingClientRect();renderer.setSize(rect.width,rect.height);camera.aspect=rect.width/rect.height;camera.updateProjectionMatrix();renderPending=true;};new ResizeObserver(resize).observe(container);resize();
    $('#output-mode').addEventListener('change',()=>{updateTerrain();setLegend();makeHotspots();});
    $('#exaggeration').addEventListener('input',e=>{root.scale.y=Number(e.target.value);$('#exaggeration-label').textContent=e.target.value+'×';renderPending=true;});
    $('#waterways-toggle').addEventListener('change',e=>{waters.visible=e.target.checked;renderPending=true;});
    $('#hotspots-toggle').addEventListener('change',e=>{points.visible=e.target.checked;$('#hotspot-list').hidden=!e.target.checked;$('#tooltip').hidden=true;renderPending=true;});
    $('#fence-toggle').addEventListener('change',e=>{fence.visible=e.target.checked;renderPending=true;});
    $('#landmarks-toggle').addEventListener('change',()=>renderPending=true);
    $('#reset-view').addEventListener('click',()=>reset());$('#top-view').addEventListener('click',()=>reset(true));
    let down=null;renderer.domElement.addEventListener('pointerdown',e=>down=[e.clientX,e.clientY]);
    renderer.domElement.addEventListener('pointerup',e=>{
      if(!down||Math.hypot(e.clientX-down[0],e.clientY-down[1])>5||!points.visible)return;
      const rect=renderer.domElement.getBoundingClientRect();pointer.set((e.clientX-rect.left)/rect.width*2-1,-(e.clientY-rect.top)/rect.height*2+1);raycaster.setFromCamera(pointer,camera);raycaster.params.Points.threshold=.45;const hits=raycaster.intersectObject(points);if(hits.length)selectPoint(hits[0].index);
    });
    $('#model-file').addEventListener('change',async e=>{
      const file=e.target.files[0];if(!file)return;
      try {
        if(file.size>10*1024*1024)throw new Error('Maximum file size is 10 MB.');
        imported=validateImport(JSON.parse(await file.text()));
        let option=$('#output-mode option[value=imported]');if(!option){option=document.createElement('option');option.value='imported';$('#output-mode').append(option);}option.textContent='Imported: '+imported.model.scenario;$('#output-mode').value='imported';
        $('#import-message').textContent=`${imported.visibleFeatures.length} of ${imported.features.length} features inside the fence. Loaded in this browser only.`;updateTerrain();setLegend();makeHotspots();
      } catch(error){$('#import-message').textContent=error.message;}finally{e.target.value='';}
    });
    function animate(){requestAnimationFrame(animate);if(!renderPending)return;scene.updateMatrixWorld(true);renderer.render(scene,camera);
      const nd=new THREE.Vector3(0,0,-1).transformDirection(camera.matrixWorldInverse);
      $('#north-arrow').style.transform='rotate('+Math.atan2(nd.x,nd.y)*180/Math.PI+'deg)';
      for(const {node,landmark} of labels){const p=position(landmark.lon,landmark.lat,.005).applyMatrix4(root.matrixWorld).project(camera);node.hidden=!$('#landmarks-toggle').checked||p.z>1||p.z< -1||Math.abs(p.x)>1||Math.abs(p.y)>1;node.style.left=((p.x+1)/2*container.clientWidth)+'px';node.style.top=((-p.y+1)/2*container.clientHeight)+'px';}
      if(selected>=0&&!$('#tooltip').hidden){const p=currentPoints[selected],world=position(p.lon,p.lat,.006).applyMatrix4(root.matrixWorld).project(camera);$('#tooltip').style.left=Math.max(5,Math.min(container.clientWidth-235,(world.x+1)/2*container.clientWidth+12))+'px';$('#tooltip').style.top=Math.max(5,Math.min(container.clientHeight-90,(-world.y+1)/2*container.clientHeight-75))+'px';}
      renderPending=false;
    }animate();
    window.viewerReady=true;
  }catch(error){console.error(error);$('#loading').textContent='The 3D viewer could not start: '+error.message+' Check that WebGL is enabled, then reload.';window.viewerError=error.message;}
}
init();
