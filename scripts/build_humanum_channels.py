#!/usr/bin/env python3
"""Build source-labelled water-feature inventory and tunable terrain pilot.

Huma-Num data are independently georeferenced; never use this to locate
Archaeoscape parcels. All derivatives stay in blocked private assets.
"""
import argparse, collections, hashlib, json, sys, zipfile
import xml.etree.ElementTree as ET
from pathlib import Path
import numpy as np
import rasterio
from rasterio.windows import Window
from pyproj import CRS, Transformer
import shapefile
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from scripts.extract_archaeoscape_network import extract
ROOT=Path(__file__).resolve().parents[1]


def categories(qgz):
    with zipfile.ZipFile(qgz) as z:
        xml=ET.fromstring(z.read(next(n for n in z.namelist() if n.endswith('.qgs'))))
    result={}
    for layer in xml.findall('.//projectlayers/maplayer'):
        result[layer.findtext('layername')]={int(c.attrib['value']):c.attrib['label']
            for c in layer.findall('.//categories/category') if c.attrib.get('value','').isdigit()}
    return result


def digest(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda:f.read(8*1024*1024),b''):h.update(chunk)
    return h.hexdigest()


def build(config):
    source=ROOT/config['input_directory'];out=(ROOT/config['output_directory']).resolve()
    if not out.is_relative_to((ROOT/'assets/private').resolve()):raise ValueError('Private output directory required')
    out.mkdir(parents=True,exist_ok=True)
    qgz=next(source.glob('*.qgz'));labels=categories(qgz);counts={};features=[];canals=[];unknown=[]
    for name in ('angkor_center_features','angkor_center_lineartraces'):
        crs=CRS.from_wkt((source/(name+'.prj')).read_text());transform=Transformer.from_crs(crs,32648,always_xy=True)
        reader=shapefile.Reader(str(source/name));counts[name]=dict(collections.Counter(str(r['TYPE']) for r in reader.iterRecords()))
        for row in reader.iterShapeRecords():
            props=row.record.as_dict();code=int(props['TYPE']);label=labels[name].get(code)
            if label is None:unknown.append({'layer':name,'fid':props['FID'],'type_code':code})
            if label not in ('Canal','Water','Pond','Pond Bank','Temple Moat','Raised Linear'):continue
            # Retain source parts without guessing polygon-ring topology.
            shape=row.shape;parts=list(shape.parts)+[len(shape.points)]
            xy=[list(map(float,transform.transform(x,y))) for x,y in shape.points]
            record={'id':name+':'+str(props['FID']),'source_layer':name,'source_fid':props['FID'],
                    'source_properties':props,'classification':label,'crs':'EPSG:32648',
                    'shape_type':shape.shapeType,'parts_xy_m':[xy[a:b] for a,b in zip(parts,parts[1:])],
                    'hydraulic_role_candidate':{'Canal':'conveyance','Water':'conveyance','Pond':'storage','Temple Moat':'storage_and_conveyance','Pond Bank':'storage_boundary_or_barrier','Raised Linear':'possible_barrier_requires_review'}[label],
                    'hydraulic_review':{'connectivity':'unassigned','historical_period':'unknown','bed_depth_m':None,'water_level_m':None,'cross_section':'unmeasured'},
                    'status':'Source-mapped feature; chronology and hydraulic connectivity unverified'}
            features.append(record)
            if label=='Canal':canals.append(record)
    with rasterio.open(source/'dtm_angkor_center.tif') as raster:
        if raster.count!=1 or raster.crs!=CRS.from_epsg(32648):raise ValueError('Unexpected DTM layout or CRS')
        if raster.transform.b or raster.transform.d or not np.allclose(raster.res,[config['pixel_size_m']]*2):raise ValueError('Unexpected DTM grid')
        target=Transformer.from_crs(4326,raster.crs,always_xy=True).transform(*config['target_lon_lat'])
        # Pick nearest canal vertex-centroid within terrain coverage; this is a pilot anchor, not a centroid survey.
        anchors=[]
        for feature in canals:
            points=np.array([p for part in feature['parts_xy_m'] for p in part]);cx,cy=points.mean(axis=0)
            if raster.bounds.left<cx<raster.bounds.right and raster.bounds.bottom<cy<raster.bounds.top:
                anchors.append(((cx-target[0])**2+(cy-target[1])**2,feature['id'],cx,cy))
        if not anchors:raise ValueError('No mapped canal anchors within DTM')
        _,anchor,cx,cy=min(anchors);r,c=raster.index(cx,cy);n=config['pilot_window_pixels']
        if type(n) is not int or n<3 or n>512:raise ValueError('Pilot window must be 3..512 pixels')
        window=Window(max(0,min(raster.width-n,c-n//2)),max(0,min(raster.height-n,r-n//2)),n,n)
        z=raster.read(1,window=window,masked=True).astype(float).filled(np.nan)*config['elevation_scale_to_m']
        transform=raster.window_transform(window)
    inventory={'coordinate_system':'EPSG:32648','features':features,'source_type_counts':counts,
               'qgis_category_labels':labels,'unmapped_type_records':unknown}
    (out/'mapped_water_features.json').write_text(json.dumps(inventory,indent=2,allow_nan=False)+'\n')
    results={};membership={};preview_networks={};source_provenance=[]
    for path in sorted(source.iterdir()):
        if path.suffix.lower() in ('.qgz','.shp','.shx','.dbf','.prj'):
            source_provenance.append({'filename':path.name,'sha256':digest(path)})
    # Reuse acquired TIFF checksum; separately hash actual processed window.
    acquisition=json.loads((source/'acquisition_manifest.json').read_text())
    dtm_record=next(x for x in acquisition['records'] if x['filename']=='dtm_angkor_center.tif')
    provenance={'source_files':source_provenance,'dtm_acquisition_record':dtm_record,
                'window_row_col':[int(window.row_off),int(window.col_off)],'window_shape':list(z.shape),
                'window_sha256':hashlib.sha256(np.asarray(z,dtype='<f8').tobytes()).hexdigest(),
                'elevation_units_status':config['elevation_units_status'],'pilot_anchor_feature_id':anchor}
    for name,profile in config['profiles'].items():
        if not name.replace('_','').isalnum():raise ValueError('Invalid profile name')
        settings={**config,**profile,'max_window_cells':512**2}
        net=extract(z,settings)
        net['coordinate_system']='EPSG:32648';net['provenance']=provenance;net['parameters']=settings
        for node in net['nodes']:
            row,col=node['row_col'];node['xy_m']=list(map(float,transform*(col+.5,row+.5)))
        for edge in net['edges']:
            membership.setdefault(edge['id'],[]).append(name)
        (out/(name+'_network.json')).write_text(json.dumps(net,indent=2,allow_nan=False)+'\n')
        results[name]=net['qc'];preview_networks[name]=net
    summary={'mapped_feature_counts':dict(collections.Counter(f['classification'] for f in features)),
             'profiles':results,'edge_profile_membership':membership,'provenance':provenance,
             'status':'Preliminary dataset; terrain traces are not dated channels or calibrated hydraulics',
             'limits':['Pilot only; not full raster or either baray','No pit filling, breaching or inferred connections across gaps',
                       'Grid resolution is not elevation accuracy; metres provisionally assumed',
                       'Widths and channel bed depths remain unset','Profile agreement is sensitivity persistence, not archaeological age']}
    (out/'channel_dataset_manifest.json').write_text(json.dumps(summary,indent=2)+'\n')
    # Standalone private SVG compares source mapping with parameter-sensitive links.
    import html
    span=float(config['pilot_window_pixels']*config['pixel_size_m'])
    left,top=transform*(0,0)
    panels=[]
    for index,(name,net) in enumerate(preview_networks.items()):
        nodes={node['id']:node for node in net['nodes']}
        shapes=[]
        for f in features:
            if f['classification'] not in ('Canal','Water','Temple Moat'):continue
            for part in f['parts_xy_m']:
                if not part:continue
                xs=[p[0] for p in part];ys=[p[1] for p in part]
                if max(xs)<left or min(xs)>left+span or max(ys)<top-span or min(ys)>top:continue
                points=' '.join(f'{(x-left)/span*360:.2f},{(top-y)/span*360:.2f}' for x,y in part)
                shapes.append(f'<polyline points="{points}" fill="none" stroke="#146c94" stroke-width="1.5"/>')
        for edge in net['edges']:
            a,b=nodes[edge['from']]['xy_m'],nodes[edge['to']]['xy_m']
            shapes.append(f'<line x1="{(a[0]-left)/span*360:.2f}" y1="{(top-a[1])/span*360:.2f}" x2="{(b[0]-left)/span*360:.2f}" y2="{(top-b[1])/span*360:.2f}" stroke="#ba4839" stroke-width="1"/>')
        panels.append(f'<g transform="translate({20+index*390},70)"><text y="-15" font-size="16">{html.escape(name)}: {len(net["edges"])} cell links</text><svg width="360" height="360" viewBox="0 0 360 360"><rect width="360" height="360" fill="#f2f3ed"/>'+''.join(shapes)+'</svg></g>')
    (out/'pilot_comparison.svg').write_text('<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="480"><rect width="100%" height="100%" fill="white"/><text x="20" y="28" font-size="18">Preliminary channel candidates: source mapping (blue), terrain links (red)</text>'+''.join(panels)+'<text x="20" y="465" font-size="13">Each panel: '+str(span)+' m square; north up. No inferred chronology, channel width or hydraulic calibration.</text></svg>')
    return summary

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--config',type=Path,default=ROOT/'configs/humanum_channels.json');a=p.parse_args()
    summary=build(json.loads(a.config.read_text()));print(json.dumps({k:summary[k] for k in ('mapped_feature_counts','profiles','status')}))
