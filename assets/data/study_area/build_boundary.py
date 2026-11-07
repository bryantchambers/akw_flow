"""Rebuild provisional Angkor Wat study domain and regional Angkor/baray search domain from existing context bounds."""
import hashlib
import json
from pathlib import Path
import math

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
BBOX = [103.8594, 13.4062, 103.8738, 13.4185]
w, s, e, n = BBOX
ring = [[w,s],[e,s],[e,n],[w,n],[w,s]]
source = ROOT / 'assets/data/context/osm_water_context.geojson'
scene_path = ROOT / 'assets/data/context/topsar/viewer_topsar_detail.json'
source_data = json.loads(source.read_text())
selected = [f for f in source_data['features'] if f['properties'].get('osm_id') in (160675481,39842237,39842238)]
refs = [
 {'id':'apsara_angkor_wat','url':'https://apsaraauthority.gov.kh/2021/06/14/angkor-wat/', 'title':'Angkor Wat — APSARA National Authority','evidence':'Moated temple complex approximately 1500 by 1300 metres with 190 m wide moat; search index read 2026-11-06, direct page returned HTTP403. General extent evidence only.'},
 {'id':'evans_fletcher_2015','url':'https://doi.org/10.15184/aqy.2015.157','title':'The landscape of Angkor Wat redefined','evidence':'Archaeological study distinguishes moated precinct, internal pond/mound grid, and external eastern enclosure. Article consulted 2026-11-06. No coordinates digitized from figures.'},
 {'id':'osm','url':'https://www.openstreetmap.org/copyright','title':'OpenStreetMap contributors','evidence':'Modern mapped water footprints provide spatial context, not archaeological dating, bathymetry, or validated connections.'}]
feature = {'type':'Feature','id':'angkor_wat_core_provisional','properties':{'name':'Angkor Wat temple, moat and internal ponds — provisional study area','boundary_role':'study_clip_only','status':'approximate_rectangle_pending_archaeological_review','reservoir_interpretation':'surrounding moat and internal reflecting ponds; excludes regional barays','hydraulic_boundary_conditions_defined':False,'source_ids':['apsara_angkor_wat','evans_fletcher_2015','osm']},'geometry':{'type':'Polygon','coordinates':[ring]}}
boundary = {'type':'FeatureCollection','name':'Angkor Wat provisional core study domain','bbox':BBOX,'features':[feature]}
scene=json.loads(scene_path.read_text()); gw,gs,ge,gn=scene['grid_bbox_wsen']; nx,ny=scene['width'],scene['height']
heights=scene['elevation_m']; heights=[x for row in heights for x in row] if isinstance(heights[0],list) else heights
idx=[r*nx+c for r in range(ny) for c in range(nx) if w<=gw+c*(ge-gw)/(nx-1)<=e and s<=gn-r*(gn-gs)/(ny-1)<=n]
valid=sum(heights[i] is not None and math.isfinite(heights[i]) for i in idx)
config={'schema_version':1,'id':'angkor_wat_core_provisional','name':feature['properties']['name'],'bbox_wsen':BBOX,'horizontal_crs':'EPSG:4326','working_projected_crs':'EPSG:32648','boundary_geojson':'assets/data/study_area/boundary.geojson','water_reference_geojson':'assets/data/study_area/water_references.geojson','terrain_scene':'assets/data/context/topsar/viewer_topsar_detail.json','clip_policy':'retain only geometry inside boundary; trim crossing reaches; preserve crossing points as external boundary candidates','reservoir_assumption':feature['properties']['reservoir_interpretation'],'excluded_features':['West Baray','East Baray','Srah Srang','Trapeang Seh west of the temple','external eastern enclosure'],'boundary_conditions':{'status':'unset','inflow':None,'downstream_stage':None,'rainfall':None,'evaporation':None,'seepage':None},'horizontal_boundary_accuracy_m':None,'waterbody_depths_m':None,'validation_status':'provisional study footprint, not survey boundary or delineated catchment'}
provenance={'generated_by':'assets/data/study_area/build_boundary.py','sources':refs,'source_osm_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'source_scene_sha256':hashlib.sha256(scene_path.read_bytes()).hexdigest(),'method':'Explicit conservative rectangular selection around the moated temple precinct, checked against north moat and internal pond footprints. Southern extent is approximate; no complete moat polygon is available in the current extract. No snapping to noisy radar elevations.','bbox_wsen':BBOX,'approx_dimensions_m':[111320*math.cos(math.radians((s+n)/2))*(e-w),111320*(n-s)],'terrain_coverage':{'cells_in_boundary':len(idx),'valid_cells':valid,'valid_fraction':valid/len(idx),'missing_cells':len(idx)-valid},'limitations':['Boundary is a study clip, not a closed hydraulic system. External connections need surveyed or explicitly scenario-defined boundary conditions.','Only the northern moat OSM polygon is available in the current water extract. Full moat water geometry is unresolved.','Study rectangle includes a narrow margin beyond the nominal moat and does not claim surveyed precision.','TOPSAR missing cells remain missing; it cannot establish underwater invert elevations or cross sections.','Reservoir scope requires confirmation if the intended reservoir is a named regional baray.']}
water={'type':'FeatureCollection','name':'Modern water references in Angkor Wat core','attribution':'© OpenStreetMap contributors, ODbL 1.0','features':selected}
# Preserve the prior core selection and its measured detail-grid coverage. The
# regional search rectangle is reused from the existing context scene, not a
# digitized archaeological reservoir outline.
regional_path = ROOT / 'assets/data/context/viewer_scene.json'
regional_scene = json.loads(regional_path.read_text())
regional_bbox = regional_scene['bbox_wsen']
rw, rs, re, rn = regional_bbox
regional_ring = [[rw,rs],[re,rs],[re,rn],[rw,rn],[rw,rs]]
config.update(id='angkor_wat_west_east_baray_provisional',
    name='Angkor Wat, West Baray and East Baray — provisional regional search domain',
    bbox_wsen=regional_bbox, extraction_bbox_wsen=BBOX,
    included_features=['Angkor Wat temple, moat and internal ponds', 'West Baray', 'East Baray'],
    terrain_scene='assets/data/context/viewer_scene.json',
    extraction_terrain_scene='assets/data/context/topsar/viewer_topsar_detail.json',
    reservoir_assumption='West Baray and East Baray are in study scope; geometry, bathymetry and connections unresolved',
    excluded_features=[],
    validation_status='provisional regional search rectangle; not surveyed reservoir outlines or a catchment')
boundary['name'] = config['name']
boundary['bbox'] = regional_bbox
boundary['features'] = [{'type':'Feature', 'id':config['id'],
    'properties':{'name':config['name'], 'boundary_role':'regional_search_clip_only',
    'status':'provisional_context_bounds_pending_archaeological_review',
    'included_features':config['included_features'], 'hydraulic_boundary_conditions_defined':False},
    'geometry':{'type':'Polygon','coordinates':[regional_ring]}}]
provenance['core_bbox_wsen'] = BBOX
provenance['core_terrain_coverage'] = provenance.pop('terrain_coverage')
provenance['bbox_wsen'] = regional_bbox
provenance.pop('approx_dimensions_m')
provenance['regional_context_sha256'] = hashlib.sha256(regional_path.read_bytes()).hexdigest()
provenance['method'] = 'Regional search bounds reused from existing Copernicus viewer scene to include Angkor Wat and both barays. Prior core clip retained separately for current TOPSAR extraction. No reservoir outlines or underwater elevations inferred.'
provenance['limitations'] = [
    'Regional rectangle is deliberately broad and is not a watershed or surveyed archaeological boundary.',
    'West and East Baray water polygons are absent from the current OSM water extract; both remain explicit study targets.',
    'TOPSAR detail coverage is limited to the Angkor Wat core. The overview is a sampled survey strip with masked holes, not complete regional coverage.',
    'TOPSAR surface heights cannot supply reservoir bathymetry or establish hydraulic connections.',
    'Current candidate/flow artifacts cover the prior Angkor Wat core only; they do not simulate either baray.',
    'External discharge, stage, rainfall, evaporation and seepage boundary conditions remain unset.']
# Count valid overview grid centres in the regional domain; do not extrapolate
# this sampled-grid statistic into native survey coverage or reservoir depths.
overview_path = ROOT / 'assets/data/context/topsar/viewer_topsar_overview.json'
overview = json.loads(overview_path.read_text())
ow, os, oe, on = overview['grid_bbox_wsen']
ox, oy = overview['width'], overview['height']
overview_idx = [r*ox+c for r in range(oy) for c in range(ox)
    if rw <= ow+c*(oe-ow)/(ox-1) <= re and rs <= on-r*(on-os)/(oy-1) <= rn]
ovalid = sum(overview['elevation_m'][i] is not None and math.isfinite(overview['elevation_m'][i]) for i in overview_idx)
provenance['regional_topsar_overview_coverage'] = {
    'source_sha256': hashlib.sha256(overview_path.read_bytes()).hexdigest(),
    'sampled_grid_centres_in_region':len(overview_idx), 'valid_centres':ovalid,
    'masked_centres':len(overview_idx)-ovalid,
    'valid_fraction_within_available_grid':ovalid/len(overview_idx) if overview_idx else None,
    'region_fully_within_available_grid':rw>=ow and rs>=os and re<=oe and rn<=on,
    'warning':'Fraction excludes regional area outside the available strip; no bathymetric interpretation.'}
for name,data in [('boundary.geojson',boundary),('config.json',config),('provenance.json',provenance),('water_references.geojson',water)]:
 (HERE/name).write_text(json.dumps(data,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
assert all(w<=x<=e and s<=y<=n for f in selected for x,y,*_ in f['geometry']['coordinates'][0])
assert all(math.isfinite(v) for p in ring for v in p)
assert ring[0]==ring[-1]
print(json.dumps({'core':provenance['core_terrain_coverage'], 'regional_overview':provenance['regional_topsar_overview_coverage']}))
