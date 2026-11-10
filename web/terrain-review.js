/* Private pilot mesh sensitivity and native-terrain inspection. */
let terrainStudy=null;
map.createPane('terrainReview');map.getPane('terrainReview').style.zIndex=465;
const terrainReviewCanvas=L.canvas({pane:'terrainReview'});
const terrainReviewOverlay=L.layerGroup().addTo(map);
function clearTerrainReview(){terrainReviewOverlay.clearLayers();}
function terrainStudyChart(title,x,series,unit){
 const ns='http://www.w3.org/2000/svg',svg=document.createElementNS(ns,'svg');svg.setAttribute('viewBox','0 0 300 185');svg.style.width='100%';svg.setAttribute('role','img');svg.setAttribute('aria-label',title);
 const values=series.flatMap(s=>s.values),lo=Math.min(...values),hi=Math.max(...values),xmin=Math.min(...x),xmax=Math.max(...x);
 const xx=v=>40+245*(v-xmin)/Math.max(1e-9,xmax-xmin),yy=v=>135-90*(v-lo)/Math.max(1e-9,hi-lo);
 function text(x,y,str,color='#234'){const el=document.createElementNS(ns,'text');el.setAttribute('x',x);el.setAttribute('y',y);el.setAttribute('font-size','9');el.setAttribute('fill',color);el.textContent=str;svg.append(el);}
 text(5,14,title);text(2,35,hi.toFixed(2));text(2,138,lo.toFixed(2));text(45,151,xmin.toFixed(1));text(250,151,xmax.toFixed(1));text(5,173,unit);
 series.forEach((s,i)=>{const path=document.createElementNS(ns,'path');path.setAttribute('d',s.values.map((v,j)=>(j?'L':'M')+xx(x[j])+','+yy(v)).join(' '));path.setAttribute('stroke',s.color);path.setAttribute('stroke-width','1.5');path.setAttribute('fill','none');svg.append(path);text(110+i*80,173,s.name,s.color);});return svg;
}
function activeTerrainAudit(){return terrainStudy?.audits[$('#model-scope').value==='terrain5'?'5m':'10m'];}
function populateTerrainQueue(){
 const queue=activeTerrainAudit()?.review_queue||[],select=$('#terrain-review-cell'),old=select.value;select.replaceChildren();
 queue.forEach((item,i)=>select.add(new Option(`${i+1}. ${item.id} · ${item.simulated_wet?'wet · ':'dry in run · '}${item.mapped_bank_or_raised_overlap?'bank + ':''}split pools`,String(i))));
 if(!queue.length)select.add(new Option('No flagged cells',''));
 if(queue[Number(old)])select.value=old;
}
function inspectTerrainCell(fit=true){
 const audit=activeTerrainAudit(),item=audit?.review_queue[Number($('#terrain-review-cell').value)];if(!item)return;
 $('#terrain-review-detail').textContent=`${item.id}: separate native wet patches at screening levels ${item.stages_m.map(x=>x.toFixed(2)).join(', ')} m: ${item.pools.map(x=>x.pool_count).join(', ')} pools. ${item.mapped_bank_or_raised_overlap?'Intersects a mapped bank or raised feature.':'No mapped bank overlap; inspect terrain and imagery.'} ${item.simulated_wet?'This cell becomes wet during the run.':'This cell stays dry in the run; flag applies to other water-level scenarios.'} These levels are uniform diagnostic tests, not simulated local stages.`;
 const profile=item.native_cross_sections;
 $('#terrain-review-profile').replaceChildren(terrainStudyChart('Native terrain through cell centre',profile.distance_m,[{name:'W→E',values:profile.west_to_east_m,color:'#147f82'},{name:'N→S',values:profile.north_to_south_m,color:'#a94b35'}],'Distance m; elevation m (datum unverified)'));
 renderTerrainReview();
 if(fit){const layer=L.geoJSON(item.geometry);map.fitBounds(layer.getBounds().pad(3));}
}
function renderTerrainReview(){
 clearTerrainReview();const scope=$('#model-scope').value;
 if(!terrainStudy||!['terrain10','terrain5'].includes(scope)||!flowData||flowData.version!==2)return;
 if($('#terrain-review-difference').checked){
  const time=flowData.frames[Number($('#flow-time').value)].time_s,frame=terrainStudy.frames.find(f=>Math.abs(f.time_s-time)<1e-6);
  if(frame){const maximum=Math.max(.01,...frame.depth_difference_m.map(Math.abs));
   terrainStudy.coarse_nodes.forEach((node,i)=>{const d=frame.depth_difference_m[i];if(Math.abs(d)<.001)return;
    L.geoJSON(node.geometry,{renderer:terrainReviewCanvas,pane:'terrainReview',style:{weight:0,fillColor:d>0?'#bd155e':'#087fbb',fillOpacity:.15+.6*Math.min(1,Math.abs(d)/maximum)},onEachFeature:(f,l)=>l.bindTooltip(`5 m minus 10 m mean depth: ${d.toFixed(4)} m at ${(time/60).toFixed(1)} min. Fine volumes aggregated to 10 m cells.`)}).addTo(terrainReviewOverlay);
   });
  }
 }
 const audit=activeTerrainAudit();
 if($('#terrain-review-flags').checked)for(const item of audit.review_queue){
  L.geoJSON(item.geometry,{renderer:terrainReviewCanvas,pane:'terrainReview',style:{color:item.mapped_bank_or_raised_overlap?'#d72430':'#ffb000',weight:1.3,fillOpacity:.05},onEachFeature:(f,l)=>l.on('click',()=>{$('#terrain-review-cell').value=String(audit.review_queue.indexOf(item));inspectTerrainCell(false);})}).addTo(terrainReviewOverlay);
 }
 const selected=audit.review_queue[Number($('#terrain-review-cell').value)];
 if(selected&&$('#terrain-review-flags').checked)L.geoJSON(selected.geometry,{renderer:terrainReviewCanvas,pane:'terrainReview',style:{color:'#ff14b8',weight:3,fillOpacity:0}}).addTo(terrainReviewOverlay);
}
$('#load-terrain-study').onclick=async()=>{
 const button=$('#load-terrain-study');button.disabled=true;
 try{
  const response=await fetch('/api/channel-inspector/terrain_review.json',{cache:'no-store'});if(!response.ok)throw Error('Comparison not built yet');terrainStudy=await response.json();
  const s=terrainStudy.summary;
  $('#terrain-study-status').textContent='Matched comparison ready. Both runs use the same domain, native initial water volume, and one 10 m inlet band. Initialisation and inlet differ from the original pilot.';
  $('#terrain-study-summary').textContent=`Final depth difference: wet-area RMSE ${(s.final_depth_rmse_wet_union_m*1000).toFixed(1)} mm; maximum ${(s.final_depth_max_absolute_difference_m*1000).toFixed(1)} mm. Native split-pool flags: ${terrainStudy.audits['10m'].flagged_cells} at 10 m and ${terrainStudy.audits['5m'].flagged_cells} at 5 m. Counts have different cell areas. This two-resolution comparison does not establish convergence. Difference overlay: pink = deeper at 5 m; blue = shallower.`;
  const gauge10=terrainStudy.gauges['10m'],gauge5=terrainStudy.gauges['5m'];
  $('#terrain-review-gauge').replaceChildren(terrainStudyChart('Canal diagnostic transect · flow',gauge10.series.map(p=>p.time_s/60),[{name:'10 m',values:gauge10.series.map(p=>p.flow_m3_s),color:'#147f82'},{name:'5 m',values:gauge5.series.map(p=>p.flow_m3_s),color:'#a94b35'}],'Time min; discharge m³/s; south positive'));
  $('#model-scope').value='terrain10';await loadFlow();populateTerrainQueue();inspectTerrainCell(false);
 }catch(e){$('#terrain-study-status').textContent=e.message;}finally{button.disabled=false;}
};
$('#terrain-review-cell').onchange=()=>inspectTerrainCell();
$('#terrain-review-flags').onchange=()=>{renderTerrainReview();};
$('#terrain-review-difference').onchange=renderTerrainReview;
for(const id of ['model-scope','quick-model-scope'])$('#'+id).addEventListener('change',()=>{clearTerrainReview();if(terrainStudy){populateTerrainQueue();inspectTerrainCell(false);}});
