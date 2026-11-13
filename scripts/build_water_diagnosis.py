#!/usr/bin/env python3
"""Private review PDF: distinguish geometry, scenario changes and validation."""
import json,sys,textwrap
from pathlib import Path
import numpy as np,rasterio
from rasterio.windows import from_bounds
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'assets/private/water_system';FOLDER=ROOT/'knowledge/Fixed-terrain model'


def page_text(pdf,title,paragraphs):
    fig=plt.figure(figsize=(11.7,8.3));fig.text(.06,.92,title,size=20,weight='bold');y=.83
    for text in paragraphs:
        lines=textwrap.wrap(text,115);fig.text(.06,y,'\n'.join(lines),size=11,va='top',linespacing=1.5);y-=.0275*len(lines)+.025
    pdf.savefig(fig);plt.close(fig)


def build(model_directory=None):
    model=Path(model_directory).resolve() if model_directory is not None else OUT/'hydraulics'
    FOLDER.mkdir(exist_ok=True,parents=True);n=json.loads((OUT/'network_manifest.json').read_text());m=json.loads((model/'manifest.json').read_text())
    v=json.loads((model/'verification.json').read_text());c=json.loads((model/'view_comparison.json').read_text());q=json.loads((OUT/'coupling.json').read_text())
    target=FOLDER/'Fixed-terrain rebuild diagnosis.pdf'
    with PdfPages(target) as pdf:
        page_text(pdf,'What was wrong, and what was rebuilt',[
            'The previous regional image was not the original pilot extended over the survey. It combined a nearly dry, minimum-level initialization with 30 seconds of rain on the terrain and a closed perimeter. The pilot instead had locally initialized water and a 900-second imposed stage hydrograph. Sparse regional face arrows were also presented without a real reach export.',
            f"The rebuilt geometry uses the native 0.5 m source grid: {n['reaches']:,} reaches, {n['nodes']:,} nodes, {n['waterbodies']:,} storage polygons and {n['ports']:,} mapped channel/storage contacts. There are {n['components']} separate geometric components. Gaps are retained; no centroid spokes, proximity merging or hidden terrain burn-in is used.",
            f"The new native 2D experiment covers {m['valid_area_km2']:.2f} square kilometres and {m['valid_cells']:,} valid 0.25-square-metre cells. Storage polygons start at their own terrain 25th percentile plus 0.15 m. Conduit stages outside storage are estimated from cross-section terrain percentiles plus 0.15 m; banks above that surface remain dry. Rainfall is zero. The duration is {m['parameters']['duration_s']:g} seconds, with no external inflows.",
            'This is an explicit exploratory water-present relaxation case. It does not reproduce the pilot hydrograph, establish ancient water levels or validate contaminant hotspots. More visible water is a consequence of changed initial conditions, not evidence that an ancient channel has been proven.'
        ])
        images=[FOLDER/'pilot.png',FOLDER/'full model.png']
        if all(p.exists() for p in images):
            fig,axs=plt.subplots(1,2,figsize=(11.7,8.3))
            for ax,p,title in zip(axs,images,['Original pilot (user capture)','Former regional startup (user capture)']):ax.imshow(plt.imread(p));ax.set_title(title);ax.axis('off')
            fig.suptitle('The reported mismatch: different model scenarios and representations',size=16);fig.tight_layout();pdf.savefig(fig);plt.close(fig)
        x,y=c['center_utm_m'];half=c['extent_m']/2;bounds=(x-half,y-half,x+half,y+half)
        fig,axs=plt.subplots(1,3,figsize=(11.7,7.5),sharex=True,sharey=True)
        cases=[('regional_native','initial','Old regional initial'),(str(model.relative_to(ROOT/'assets/private')),'initial','Rebuilt initial'),(str(model.relative_to(ROOT/'assets/private')),'final',f"Rebuilt {m['parameters']['duration_s']:g} s")]
        for ax,(directory,key,label) in zip(axs,cases):
            with rasterio.open(ROOT/'assets/private'/directory/(key+'.tif')) as src:
                window=from_bounds(*bounds,src.transform);h=src.read(1,window=window);valid=h>=0
                shown=np.ma.masked_where((h<=.001)|~valid,h)
                ax.imshow(shown,extent=(bounds[0],bounds[2],bounds[1],bounds[3]),origin='upper',cmap='Blues',vmin=0,vmax=1,interpolation='none')
                ax.set_title(label+f"\n{h[valid].sum(dtype=float)*.25:,.0f} m³; {(valid&(h>.001)).sum()*.25:,.0f} m² wet",fontsize=11)
                ax.set_xlabel('Easting (m)');ax.ticklabel_format(useOffset=False,style='plain');ax.set_facecolor('#eee')
        axs[0].set_ylabel('Northing (m)');fig.suptitle('Same 640 m footprint, actual native depth rasters (blue; 0-1 m colour range)',size=15)
        fig.text(.05,.035,'Different starting water and forcing: this diagnoses initialization, not grid convergence. The original 10 m pilot initially holds approximately 14,942 m³.',size=10)
        fig.tight_layout(rect=(0,.06,1,.91));pdf.savefig(fig);plt.close(fig)
        page_text(pdf,'How to inspect the rebuilt model',[
            'Open /regional-terrain. At regional scale, cyan reach lines give a readable conduit overview. Ponds and reservoirs remain 2D storage polygons; a tree of arbitrary lines across a lake is not a suitable representation. Orange directed reaches have matching flux signs at three sampled cross-sections. Other statuses identify dry, mixed-direction and unresolved cases.',
            'Use Inspect original pilot area, then Zoom to 0.5 m cells. Click a cell for its native bed, water depth, stage and east/south face discharges. The cell-grid overlay and optional idle faces show actual resolved cells. Export visible 0.5 m cells creates GIS polygons with those same values. The GeoPackage supplies the whole reach/node/storage/contact network and inspection cross-sections.',
            'Two cells connect hydraulically through a shared face if water overtops the higher adjacent bed. More bank faces and multiple outlets can activate as stages rise. A geometric contact does not prove an open spillway or culvert. Diagonal-only mapped contacts, missing terrain and unverified structures do not become invented connections.',
            'Review missing mapped waterways, apparent crossings over high banks, local interruptions at crests, and sensitivity to assumed water levels. Check high-flow areas against hillshade and actual cell stages. Store proposed changes as explicit evidence-labeled terrain or water-level scenarios, keeping the source DTM untouched.'
        ])
        page_text(pdf,'Checks passed, and what remains unvalidated',[
            f"Native export and conservation checks: {v['status']}. Water-budget residual: {m['budget']['residual_m3']:.6g} m³. Source-alignment checks, GIS readback, native node coordinates, endpoint references, component IDs and node degrees are verified. These checks establish implementation consistency, not historical accuracy.",
            f"Hydraulic regime flag: {v['faces_with_froude_over_one_and_face_depth_at_least_1cm']:,} exported faces with at least 1 cm face depth exceed Froude 1. The local-inertial model omits advective momentum; those faces need regime/solver review. Thin films have further limitations. Maximum exported face velocity is {v['maximum_exported_face_velocity_m_s']:.4g} m/s; this is distinct from the internal end-depth speed proxy.",
            'The modern source DTM does not establish submerged bathymetry, historical channel shape, a verified vertical datum, observed inflows, roughness or permeability. The source footprint is not all Greater Angkor. Native spacing is 0.5 m; elevation accuracy is not thereby 0.5 m. Groundwater coupling and sustained regional stage boundaries remain unsupported in this native engine.',
            'Before hotspot interpretation: select a dated archaeological scenario, verify bed/crest/structure geometry, supply plausible stage or inflow boundary data, calibrate/validate water levels and travel times, and review the appropriate momentum formulation. The conservative unit tracer is only a routing diagnostic. Geometry and hydraulic snapshots should not be labeled a validated bacterial prediction.'
        ])
        page_text(pdf,'Method and reproducibility references',[
            'Detailed methods, configuration fields, limitations and exact reproduction commands: docs/water_system_rebuild.md. Executed solver/source snapshots, source file states, per-storage initial levels, exported budgets and cross-section coupling metadata are retained alongside the private outputs.',
            'scikit-image skeletonization documentation: https://scikit-image.org/docs/stable/auto_examples/edges/plot_skeleton.html . Shape thinning provides candidate topology, not bathymetric thalwegs or proven hydraulic connections.',
            'HEC-RAS 2D mesh-development guidance: https://www.hec.usace.army.mil/confluence/rasdocs/r2dum/6.5/development-of-a-2d-or-combined-1d-2d-model/development-of-the-2d-computational-mesh . Terrain controls and waterbody geometry matter; the custom solver is not HEC-RAS and is not validated by analogy.',
            'Penny et al. (2018), local paper and supplement in assets/manuscripts: the abstracted archaeological infrastructure network is a comparison, not a visual target that justifies adding unsupported hydraulic edges. Private source captures and derived spatial review material remain excluded from Git.'
        ])
    print(target);return target

if __name__=='__main__':build()
