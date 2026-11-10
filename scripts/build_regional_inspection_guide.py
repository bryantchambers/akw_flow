#!/usr/bin/env python3
"""Build the illustrated methods review from supplied captures and local model data.
Report-only: does not edit source rasters, topology, reviews or solver results.
Requires GIS requirements plus requirements-reports.txt.
"""
import json,math,hashlib,sys
from pathlib import Path
from datetime import datetime,timezone
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle,Ellipse,FancyArrowPatch
from PIL import Image as PILImage
import pymupdf
from reportlab.platypus import SimpleDocTemplate,Paragraph,Spacer,Image,Table,TableStyle,PageBreak,KeepTogether
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet,ParagraphStyle
from reportlab.lib.enums import TA_LEFT
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.pagesizes import A4
from xml.sax.saxutils import escape
ROOT=Path(__file__).resolve().parents[1];FOLDER=ROOT/'knowledge/RegionalModelInspections';WORK=ROOT/'.runtime/regional-guide';WORK.mkdir(parents=True,exist_ok=True)
PDF=FOLDER/'Regional_Model_Review_and_Inspection_Guide.pdf'
TEAL='#155b61';RED='#c44a38';BLUE='#2677a0';GREEN='#15985a';PURPLE='#8453b5';ORANGE='#e89a32'
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10,'axes.spines.top':False,'axes.spines.right':False})

def savefig(fig,name):
    fig.savefig(WORK/name,dpi=180,bbox_inches='tight',facecolor='white');plt.close(fig);return WORK/name

def annotate_capture(filename,name,marks):
    img=PILImage.open(FOLDER/filename);w,h=img.size;fig,ax=plt.subplots(figsize=(w/150,h/150));ax.imshow(img);ax.set_axis_off()
    for number,target,label in marks:
        ax.annotate(str(number),xy=target,xytext=label,color='white',fontsize=18,fontweight='bold',ha='center',va='center',bbox={'boxstyle':'circle,pad=.3','fc':RED,'ec':'white','lw':2},arrowprops={'arrowstyle':'->','color':RED,'lw':2.5})
    return savefig(fig,name)

def figures():
    annotate_capture('feature graph nodes connectivity.png','green_annotated.png',[(1,(150,545),(75,620)),(2,(535,320),(430,215)),(3,(855,155),(1010,85))])
    annotate_capture('hydraulic cell up close.png','orange_annotated.png',[(1,(153,305),(105,170)),(2,(545,225),(570,100)),(3,(1045,310),(1005,525))])
    annotate_capture('hydrualic cell up close w: features.png','mesh_annotated.png',[(1,(500,160),(420,65)),(2,(475,630),(630,700)),(3,(90,310),(200,370))])
    doc=pymupdf.open(ROOT/'assets/manuscripts/penny_2018_demise_angkor_supplement.pdf');doc[4].get_pixmap(matrix=pymupdf.Matrix(2,2),clip=pymupdf.Rect(65,65,550,455)).save(WORK/'penny_s1_panels.png');doc.close()
    # Illustrative geometry: these drawings are not reconstructed Angkor features.
    fig,axes=plt.subplots(1,2,figsize=(10,3.1))
    x=np.array([0,1,2,3,4,5]);y=np.array([1.1,1.1,1.6,1.6,1.1,1.1])
    for ax in axes:
        ax.plot(x,y,color='#bee2e2',lw=26,solid_capstyle='round');ax.add_patch(Ellipse((5.7,1.1),1.1,1.4,color='#d7eaf7'));ax.set(xlim=(-.5,6.5),ylim=(-.2,3));ax.axis('off')
    for xx,yy in [(1,1.1),(3,1.6),(5.7,1.1),(4,2.6)]:axes[0].plot([2.6,xx],[.4,yy],color=GREEN,lw=1.8)
    axes[0].scatter([2.6],[.4],c=PURPLE,s=70);axes[0].set_title('Current feature-anchor schematic',color=RED)
    axes[1].plot(x,y,color=TEAL,lw=2.4);axes[1].plot([3,3,4],[1.6,2.4,2.4],color=TEAL,lw=2.4)
    axes[1].scatter([0,3,4,5],[1.1,1.6,2.4,1.1],s=55,facecolors='white',edgecolors=TEAL,zorder=5)
    axes[1].plot([5,5.25],[1.1,1.1],color=TEAL,lw=2.4);axes[1].scatter([5.25],[1.1],marker='s',color=ORANGE,s=60,zorder=6)
    axes[1].text(3,2.8,'junction / branch',ha='center',fontsize=9);axes[1].text(5.65,.12,'storage + outlet port',ha='center',fontsize=9);axes[1].set_title('Target reach-junction + storage graph',color=TEAL)
    savefig(fig,'graph_target.png')
    # Actual multipart source feature, anonymous to the diagram except original ID.
    import shapefile
    from shapely.geometry import shape
    from shapely import make_valid
    reader=shapefile.Reader(str(ROOT/'assets/private/humanum_danish_edna/angkor_center_features'))
    rec=next(r for r in reader.iterShapeRecords() if str(r.record['FID'])=='ANG_F_12248');g=make_valid(shape(rec.shape.__geo_interface__))
    fig,ax=plt.subplots(figsize=(9,2.7));xmin,ymin,xmax,ymax=g.bounds
    for i,part in enumerate(g.geoms):
        xy=np.array(part.exterior.coords);ax.fill((xy[:,0]-xmin)/1000,(xy[:,1]-ymin)/1000,alpha=.55,color=plt.cm.tab10(i%10));p=part.representative_point();ax.text((p.x-xmin)/1000,(p.y-ymin)/1000,str(i+1),fontsize=10,fontweight='bold')
    p=g.representative_point();ax.scatter([(p.x-xmin)/1000],[(p.y-ymin)/1000],marker='*',s=160,color=RED,zorder=4)
    ax.set_aspect('equal');ax.set_xlabel('Easting offset (km)');ax.set_ylabel('Northing offset (km)');ax.set_title('Actual ANG_F_12248: seven polygon parts, one current feature node',fontsize=11)
    savefig(fig,'multipart.png')
    # Alternative reservoir representation.
    fig,axes=plt.subplots(1,3,figsize=(10,3.4))
    for ax in axes:ax.add_patch(Rectangle((.12,.2),.7,.65,facecolor='#dceef7',edgecolor=TEAL,lw=2));ax.set(xlim=(0,1),ylim=(0,1));ax.axis('off')
    for y in np.linspace(.25,.8,9):axes[0].plot([.45,.9],[.52,y],color=ORANGE,lw=1)
    axes[0].scatter([.45],[.52],c=RED,s=40);axes[0].set_title('Current lumped-cell spokes',fontsize=10);axes[0].text(.45,.05,'Not streamlines; ports unreviewed',ha='center',fontsize=8)
    axes[1].text(.47,.54,'Shared stage\nV(stage) storage',ha='center',va='center',fontsize=10)
    for yy in [.35,.72]:axes[1].plot([.82,.97],[yy,yy],color=TEAL,lw=3);axes[1].scatter([.82],[yy],marker='s',c=ORANGE,s=60,zorder=3)
    axes[1].set_title('Option A: 0D storage + real ports',fontsize=10);axes[1].text(.48,.05,'Gate / culvert / spillway laws',ha='center',fontsize=8)
    for xx in np.linspace(.12,.82,7):axes[2].plot([xx,xx],[.2,.85],color='#6c9eae',lw=.7)
    for yy in np.linspace(.2,.85,6):axes[2].plot([.12,.82],[yy,yy],color='#6c9eae',lw=.7)
    axes[2].plot([.82,.82],[.2,.85],color=PURPLE,lw=4)
    for yy in [.35,.72]:axes[2].scatter([.82],[yy],marker='s',c=ORANGE,s=60,zorder=3)
    axes[2].set_title('Option B: resolved 2D waterbody',fontsize=10);axes[2].text(.48,.05,'Explicit bank/crest and outlet faces',ha='center',fontsize=8)
    savefig(fig,'storage_options.png')
    # Four connection situations.
    fig,axes=plt.subplots(1,4,figsize=(10,2.5))
    for ax in axes:ax.set(xlim=(0,2),ylim=(0,1.6));ax.axis('off')
    for ax in [axes[0],axes[2]]:
        ax.add_patch(Rectangle((.1,.3),.8,.9,fc='#d4eaf0',ec=TEAL));ax.add_patch(Rectangle((.9,.3),.8,.9,fc='#d4eaf0',ec=TEAL))
    axes[0].plot([.9,.9],[.3,1.2],color=GREEN,lw=4);axes[0].set_title('Shared open face',fontsize=10);axes[0].text(.9,.05,'Potential exchange, if physically open',ha='center',fontsize=7)
    axes[1].add_patch(Rectangle((.1,.1),.7,.65,fc='#d4eaf0',ec=TEAL));axes[1].add_patch(Rectangle((.8,.75),.7,.65,fc='#d4eaf0',ec=TEAL));axes[1].scatter([.8],[.75],c=RED,s=40);axes[1].set_title('Point touch',fontsize=10);axes[1].text(.9,.01,'No finite opening width',ha='center',fontsize=8)
    axes[2].plot([.9,.9],[.3,1.2],color=PURPLE,lw=5);axes[2].set_title('Shared face + bank',fontsize=10);axes[2].text(.9,.05,'Blocked below crest unless an opening',ha='center',fontsize=7)
    axes[3].add_patch(Rectangle((.1,.3),.65,.9,fc='#d4eaf0',ec=TEAL));axes[3].add_patch(Rectangle((1.15,.3),.65,.9,fc='#d4eaf0',ec=TEAL));axes[3].plot([.75,1.15],[.75,.75],color=RED,ls='--',lw=2);axes[3].set_title('Gap / crossing',fontsize=10);axes[3].text(.95,.05,'Evidence + explicit connector required',ha='center',fontsize=7)
    savefig(fig,'connection_cases.png')
    # Coupled conceptual process layers.
    fig,ax=plt.subplots(figsize=(10,4));ax.set(xlim=(0,10),ylim=(0,5));ax.axis('off')
    boxes=[(.1,4.1,9.7,.65,'Atmospheric forcing: rainfall, evaporation, upstream/downstream boundary data','#edf2f2'),(.1,2.85,4.5,.8,'Catchments / overland flow\n1D/2D routing over dry and flooded land','#e4f0df'),(5.1,2.85,4.7,.8,'Channels + ponds/moats/reservoirs\nreaches, junctions, storage, control structures','#d9edf5'),(.1,1.55,9.7,.7,'Soil / unsaturated zone: infiltration, soil moisture, recharge, evapotranspiration','#eee3d0'),(.1,.25,9.7,.7,'Groundwater: aquifer storage, heads and geologic flow paths beneath land and water','#dddff3')]
    for x,y,w,h,t,c in boxes:ax.add_patch(Rectangle((x,y),w,h,fc=c,ec=TEAL));ax.text(x+w/2,y+h/2,t,ha='center',va='center',fontsize=9)
    for a,b in [((2,4.1),(2,3.65)),((7,4.1),(7,3.65)),((4.6,3.25),(5.1,3.25)),((2,2.85),(2,2.25)),((3,1.55),(3,.95)),((8,1.55),(8,.95))]:ax.add_patch(FancyArrowPatch(a,b,arrowstyle='<->' if a[0] in [4.6,8] else '->',mutation_scale=12,color=TEAL))
    ax.text(5,0,'Water quality/sediment use the water fluxes; archaeological phase is a scenario, not a water compartment.',ha='center',fontsize=8)
    savefig(fig,'process_layers.png')
    # Real terrain evidence, no assertion of measured bathymetry.
    evidence=json.loads((ROOT/'assets/private/channel_review/prepared_evidence.json').read_text());p=evidence['profiles'][0]
    fig,axes=plt.subplots(1,2,figsize=(10,3.3))
    l=p['longitudinal'];axes[0].plot(l['station_m'],l['elevation_m'],color=TEAL,lw=1);axes[0].set_title('Actual guide terrain profile (direction arbitrary)',fontsize=10);axes[0].set_xlabel('Distance along provisional guide (m)');axes[0].set_ylabel('Elevation (m provisionally assumed)')
    c=p['cross_sections'][1];x=np.array(c['station_m']);z=np.array([np.nan if q is None else q for q in c['elevation_m']]);axes[1].plot(x,z,color=TEAL,label='Present terrain')
    inside=np.zeros(x.shape,bool)
    for a,b in c['mapped_water_intervals_m']:inside|=(x>=a)&(x<=b)
    for incision,ls in [(.2,':'),(.5,'--'),(1.,'-.')]:axes[1].plot(x,z-incision*inside,ls=ls,lw=1,label=f'Assumed incision {incision:g} m')
    axes[1].set_title('Cross-section: scenarios, not measured beds',fontsize=10);axes[1].set_xlabel('Offset across guide (m)');axes[1].legend(fontsize=7);fig.tight_layout();savefig(fig,'real_profiles.png')

fonts=Path(matplotlib.get_data_path())/'fonts/ttf'
for name,file in [('Guide','DejaVuSans.ttf'),('GuideBold','DejaVuSans-Bold.ttf'),('GuideMono','DejaVuSansMono.ttf')]:pdfmetrics.registerFont(TTFont(name,str(fonts/file)))
styles=getSampleStyleSheet();styles.add(ParagraphStyle('GuideBody',fontName='Guide',fontSize=9.5,leading=14,spaceAfter=7,textColor=colors.HexColor('#263d43')));styles.add(ParagraphStyle('GuideH1',fontName='GuideBold',fontSize=20,leading=25,spaceAfter=14,textColor=colors.HexColor(TEAL)));styles.add(ParagraphStyle('GuideH2',fontName='GuideBold',fontSize=11,leading=15,spaceBefore=8,spaceAfter=6,textColor=colors.HexColor(TEAL)));styles.add(ParagraphStyle('GuideCaption',fontName='Guide',fontSize=8,leading=11,spaceAfter=9,textColor=colors.HexColor('#53676c')));styles.add(ParagraphStyle('GuideSmall',parent=styles['GuideBody'],fontSize=8.2,leading=11));styles.add(ParagraphStyle('GuideCode',fontName='GuideMono',fontSize=8,leading=11,spaceAfter=5));styles.add(ParagraphStyle('GuideTitle',parent=styles['GuideH1'],fontSize=29,leading=36))
W=A4[0]-84;story=[];page_titles=[]
def P(text,style='GuideBody'):return Paragraph(text,styles[style])
def para(text):story.append(P(text))
def h2(text):story.append(P(text,'GuideH2'))
def bullet(text):story.append(P('• '+text))
def pic(path,maxh=240,width=W):
    path=Path(path);im=PILImage.open(path);iw,ih=im.size;scale=min(width/iw,maxh/ih);return Image(str(path),width=iw*scale,height=ih*scale)
def caption(text):story.append(P(text,'GuideCaption'))
def page(title):
    if story:story.append(PageBreak())
    page_titles.append(title);story.append(P(title,'GuideH1'))
def table(rows,widths=None,header=True):
    data=[[P(str(x),'GuideSmall') for x in row] for row in rows];t=Table(data,colWidths=widths or [W/len(rows[0])]*len(rows[0]),hAlign='LEFT');commands=[('VALIGN',(0,0),(-1,-1),'TOP'),('LEFTPADDING',(0,0),(-1,-1),7),('RIGHTPADDING',(0,0),(-1,-1),7),('TOPPADDING',(0,0),(-1,-1),6),('BOTTOMPADDING',(0,0),(-1,-1),6),('LINEBELOW',(0,0),(-1,-1),.4,colors.HexColor('#ccd8dc'))]
    if header:commands+=[('BACKGROUND',(0,0),(-1,0),colors.HexColor('#e3eff0'))]
    t.setStyle(TableStyle(commands));story.append(t);story.append(Spacer(1,7))
def callout(title,text):
    t=Table([[P(title,'GuideH2')],[P(text)]],colWidths=[W]);t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,-1),colors.HexColor('#fff0df')),('BOX',(0,0),(-1,-1),.8,colors.HexColor('#cf9f69')),('LEFTPADDING',(0,0),(-1,-1),10),('RIGHTPADDING',(0,0),(-1,-1),10)]));story.append(t);story.append(Spacer(1,10))
def footer(canvas,doc):
    canvas.saveState();canvas.setStrokeColor(colors.HexColor('#cfdbde'));canvas.line(42,35,A4[0]-42,35);canvas.setFont('Guide',8);canvas.setFillColor(colors.HexColor('#61757b'));canvas.drawString(42,23,'ANGKOR · METHODS REVIEW · 10 NOVEMBER 2026');canvas.drawRightString(A4[0]-42,23,str(doc.page));canvas.restoreState()

def content(audit):
    page('What you are seeing—and what needs to change')
    story.append(P('Regional model inspection guide','GuideTitle'))
    para('Prepared for the Angkor archaeological water-system project · 10 November 2026. Based on all seven captures in this folder, the current construction/rendering code, live regional artifacts, and Penny et al. (2018) with its supplement.')
    callout('Verdict: useful evidence scaffold; not yet a defensible conveyance model', 'Your expectation of a channel-following network is reasonable. The current green layer is a <b>whole-feature adjacency schematic</b>, not a reach–junction network. Parts of the cell system also use unverified shoreline openings and crude resistance lengths. These require targeted redesign before interpreting discharge, flood depth or transport hotspots. Passing conservation tests does not resolve those problems.')
    story.append(pic(FOLDER/'whole feature network.png',180))
    caption('Your regional feature capture. The long green stars are not evidence of long straight canals. The model-generated anchor drawing is a major source of this appearance.')
    table([['Keep','Correct before predictive simulation'],['0.5 m terrain, source mapping/IDs, private provenance, review ledger and diagnostic profiles.','Reach/junction topology, disconnected feature parts, reservoir outlets, bank/structure controls and hydraulic face geometry.']],widths=[W*.45,W*.55])
    para('<b>Read first:</b> pages 3–7 explain the strange lines and the connection rules. Page 8 compares Penny. Pages 11–14 give an inspection and rebuilding sequence. Page 16 is a worksheet you can use beside the dashboard.')
    caption('Scope: this is a methods audit and review guide. It does not silently change source mapping, accept connections, replace the mesh or recalibrate hydraulic results. Captures and terrain are research material; this PDF has not been published to GitHub.')

    page('1 · Four different representations—not one map')
    table([['Representation','Meaning / what it should look like'],['Source evidence map','Canal/moat/pond footprints, banks, raised features, terrain and imagery. Shows surviving mapped evidence; not all features belong to the same period.'],['Current feature graph','One anchor per source feature. Green lines show enabled geometric contacts via anchors; dashed links are candidate gaps. This is an adjacency audit, not a channel trace.'],['Desired reach–junction graph','Nodes at actual junctions, terminals and storage ports; edges follow the mapped/reconstructed channel path. Crossings connect only where a physical exchange is supported.'],['Hydraulic discretization','Storage volumes and reach/2D cells used for numerical flow. A cell node is not automatically a junction. Solver links are mathematical interfaces, not necessarily visible waterways.']],widths=[W*.29,W*.71])
    t=Table([[pic(FOLDER/'whole feature network.png',130,W*.48),pic(FOLDER/'whole hydrualic cell.png',130,W*.48)]],colWidths=[W/2,W/2]);story.append(t)
    caption('Left: your feature graph. Right: your cell graph. Comparing line count alone confuses source objects with numerical degrees of freedom.')
    h2('Read the colours by mode')
    para('<b>Mapped evidence:</b> cyan canal outlines; orange water traces; purple moats; blue ponds; yellow pond banks; pink raised linear features. These are source classes, not model validation labels.')
    para('<b>Feature graph:</b> teal conveyance-feature anchors and purple storage/moat anchors; green enabled contacts; muted dashed gap proposals when shown. Green does not mean field-verified.')
    para('<b>Cell graph:</b> hollow markers are numerical cell locations; orange links are interfaces. Line thickness scales with absolute discharge in the saved frame; direction/sign is in the tooltip. In layered mode blue fill shows simulated depth, clipped to the display scale—not observed depth. The separate depression overlay is not water depth either.')

    page('2 · Why the green lines look random')
    story.append(pic(WORK/'green_annotated.png',345))
    caption('Annotated version of “feature graph nodes connectivity.png”. Numbered callouts identify display artifacts and missing physical interpretation, not newly verified channels.')
    para('<b>1 · Feature anchor.</b> A representative point stands for an entire source polygon. It is not necessarily a junction, an outlet, the polygon centroid or a point on the channel centreline.')
    para('<b>2 · Anchor-to-contact arms.</b> The renderer draws: anchor A → nearest contact on A → nearest contact on B → anchor B. Even when A and B touch, the two anchor arms can traverse kilometres and cut across land. Their crossings do not create physical junctions.')
    para('<b>3 · Mapped water versus graph ink.</b> The cyan/purple/blue outlines retain the source footprints. Green lines that ignore those paths should not be accepted as canals merely because they are green.')
    callout('Measured audit of the current drawing',f"{audit['active_drawn_anchor_links_over_1km']} of {audit['active_feature_links']} enabled feature links draw more than 1 km. The longest draws {audit['longest_active_drawn_anchor_link_m']/1000:.2f} km, while its actual polygon gap is 0 m. This is anchor geometry, not an 8 km unmapped channel.")
    caption('Code: web/channel-inspector.js, renderFeatureGraph(); scripts/build_regional_network.py, feature_contacts(). Do not spend your review time trying to repair every long green chord manually.')

    page('3 · One source ID can conceal multiple physical pieces')
    story.append(pic(WORK/'multipart.png',185))
    caption('Actual source geometry, plotted in projected metric coordinates. The star marks the representative point used for the whole feature; coloured numbered parts are disconnected polygon pieces. This is a diagnosis of the existing source record, not a new network reconstruction.')
    para('<b>Concrete case:</b> source canal <font face="GuideMono">ANG_F_12248</font> contains seven polygon parts. The feature graph gives all seven one node. That can make contacts on separate pieces appear connected through a single abstract object, even when no within-feature route exists.')
    para('The audit found three multipart water-feature records: ANG_F_12248 (7 canal parts), ANG_F_09009 (3 canal parts), and ANG_F_00017 (2 moat parts). The cell builder keeps disconnected polygon pieces separate, so the feature graph and cell graph need not describe the same connectivity.')
    story.append(pic(WORK/'graph_target.png',195))
    caption('Schematic comparison—not recovered Angkor geometry. Right: junctions and storage ports lie on channel-following paths; left: feature-anchor lines obscure that structure.')
    para('<b>Required correction:</b> retain the parent source ID, create stable child IDs for connected geometry components, then subdivide conveyance at real branches, confluences, structures and terminals. A disconnected component must not acquire an internal hydraulic connection solely because it shares an FID. A long connected canal feature also needs intermediate junctions, not one infinite-capacity hub.')

    page('4 · Why orange fans appear around large water bodies')
    story.append(pic(WORK/'orange_annotated.png',330))
    caption('Annotated version of “hydraulic cell up close.png”. The screenshot does not label source IDs, so identify the selected feature in the inspector rather than inferring its identity from this image alone.')
    para('<b>1 · One lumped storage node.</b> A large polygon classified as Pond is represented by one uniform-stage storage cell. A lumped reservoir can be a valid abstraction, but its plotting point is not a place through which all water physically travels.')
    para('<b>2 · Spokes.</b> The orange lines join that storage node to adjacent numerical cells. They are not channel centrelines or simulated streamlines. A fan of valid <i>schematic</i> outlet links can be drawn around a storage node; the critical question is whether each link represents a real opening.')
    para('<b>3 · Shoreline does not equal opening.</b> The present builder can treat shared water-polygon boundaries as open exchange interfaces. It does not enforce bank crest, gates or culverts at those faces.')
    callout('This also affects the calculation', 'The largest retained storage polygon is about <b>14.31 km²</b> and has <b>225 interfaces</b>. Some solver lengths involving it are about <b>3.83 km</b>, computed from polygon centroids. Shared-boundary widths are used as rectangular conveyance widths. Those are not 225 verified outlets or surveyed channel lengths.')
    caption('Large source cell: angkor_center_features:ANG_F_11406|storage0. The fan cannot be corrected reliably by merely hiding lines or increasing mesh resolution.')

    page('5 · What a reservoir connection should look like')
    story.append(pic(WORK/'storage_options.png',230))
    caption('Conceptual alternatives, not a replacement model. Either storage abstraction can be appropriate; outlet physics and the study question decide which.')
    h2('Option A · Lumped storage with explicit ports')
    para('Keep a reservoir or small pond as one storage element when a shared water level is an acceptable approximation. Describe its volume versus stage, locate real inflow/outflow ports on the boundary, and connect those ports to channel reaches or structures. Draw the waterbody as an area and the ports as explicit symbols. Do not depict centroid spokes as paths through the water.')
    para('A shoreline bank is closed below its crest unless an opening is supported. A culvert, gate, weir or spillway needs its own location and flow relationship. This is consistent with HEC-RAS storage-connection concepts [4], but the required Angkor structures and parameters still need evidence.')
    h2('Option B · Resolved two-dimensional waterbody')
    para('Use internal cells if lateral water-level gradients, flood propagation or circulation matter. Represent banks and roads with appropriate mesh/face controls and resolve important openings. The mesh is not justified simply because it looks detailed. Compare results under refinement and provide terrain/bathymetric evidence.')
    table([['Do not use as an outlet law','Use instead'],['Distance from a large storage centroid to every bank-adjacent cell.','Port/channel/structure geometry, stage differences and an appropriate rating or hydraulic equation.'],['Every common polygon boundary automatically open.','Explicit opening, continuous open water, or conditional overtopping—with a documented scenario.']],widths=[W/2,W/2])
    caption('HEC guidance describes storage/2D links using structure or routing options [4]. This guide does not assert that a particular gate or culvert exists at any shown location.')

    page('6 · Exactly when the current code connects cells')
    table([['Stage','Current rule'],['Feature candidates','Nearest source geometries within 50 m are queued. Zero-gap contacts are enabled by the baseline; positive gaps are disabled unless explicitly accepted.'],['Saved decisions','Accepted enables a scenario connection. Rejected or explicitly unresolved disables it. Unreviewed contacts retain the unverified baseline.'],['Cell creation','Ponds: one cell per retained connected polygon part. Canals/moats/traces: polygon-clipped 100 m grid pieces. Overlap ownership: Water → Canal → Moat → Pond.'],['Ordinary cell interface','Both cells retained; boundaries share more than 10⁻⁵ m of line length. Point-only touch gives no interface. Across source IDs, the feature-pair scenario must also be enabled.'],['Explicit accepted gap','The builder links the nearest retained cells using a hypothetical 2 m width and a representative-distance proxy. It does not reconstruct the missing channel or a structure.'],['Actual water flux','An enabled interface still needs an effective wet opening and a stage difference. Flow may reverse. A graph connection is not necessarily flowing in a given frame.']],widths=[W*.25,W*.75])
    story.append(pic(WORK/'connection_cases.png',155))
    para('<b>What is missing from the rule:</b> a shared face is not proof of an open channel. Pond banks, raised roads, levees, sill elevations, culvert inverts and gates are not automatically applied by the regional flux calculation. The review screen flags some mapped barriers; it does not close their faces in the solver.')
    caption('NoData is not an invitation to bridge. The code filters small/poorly sampled cells, but a usable elevation sample is not proof of channel-bed accuracy. Exact functions: partition(), shared_interfaces(), connection_enabled(), then hydraulics/model.py::flux().')

    page('7 · What Penny et al. actually built')
    pics=Table([[pic(WORK/'penny_s1_panels.png',240,W*.66),pic(FOLDER/'penny et all.png',235,W*.29)]],colWidths=[W*.69,W*.31]);story.append(pics)
    caption('Left: Penny et al. supplementary Fig. S1, reproduced from the supplied supplement (PDF page 5). Right: your supplied crop of Fig. 5. These are two different stages/products of their analysis [1–2].')
    para('S1 goes from archaeological GIS evidence to delineated water-distribution features, then <b>nodes at intersections/terminations and edges along feature lengths</b>. The model has 617 nodes and 1,013 edges, including a supersource and supersink. Its coding reflects interpreted functional connectivity and a late historical time slice, not every water polygon collapsed to an anchor [1–2].')
    para('The supplement specifies a directed acyclic topology, relative initial weights of 1, 0.1 and 0.01 based on approximate mapped widths, proportional capacity-based splitting, and phenomenological erosion/sedimentation rules. It does not solve a calibrated channel-depth field, Saint-Venant hydraulics, groundwater or sediment mass redistribution [2, pp. 2–5].')
    callout('The colour in your Penny image is not discharge', 'Fig. 5 maps average <b>damage Q</b> over 3,000 stochastic runs (γ=1, α=β=0.9). Their damage measures redistribution relative to the initial flow pattern. It is not m³/s, water depth or contaminant concentration. Our orange links do not depict that quantity.')
    para('<b>Adopt the reach/junction discipline, not all their simplifying assumptions.</b> A physical moat/reservoir system may contain loops, backwater or reversible flow. Do not delete real loops merely to force a DAG or match Penny’s edge count. Our central source coverage and all-pond inventory also differ from their watershed-scale interpreted system.')
    caption('The authors explicitly discuss the network as a diachronic palimpsest. Present surviving terrain is not automatically the functioning network of any earlier century [1, Methods].')

    page('8 · Physical process layers and present implementation')
    story.append(pic(WORK/'process_layers.png',220))
    caption('Recommended coupled process architecture. Arrows are exchanges that must conserve water; these are not just opacity layers in the map.')
    table([['Compartment / data layer','Current status'],['Imagery, terrain, archaeological phase','Evidence/scenario layers. They provide geometry and context, not separate stores of water.'],['Catchment runoff / floodplain','Not implemented regionally. Cells occupy mapped water footprints, omitting most dry land, storm runoff and floodplain spill paths.'],['Channel + storage flow','Prototype storage-network closure. No validated ports, full face property curves or regional forcing.'],['Controls / embankments','Displayed or flagged as evidence, not resolved regional gates/weirs/culverts/crest controls.'],['Unsaturated soil / infiltration','No soil-moisture or Richards/Green-Ampt model. Pilot bed leakage is an effective saturated Darcy connection.'],['Groundwater','Optional pilot columns only; regional groundwater disabled. Pilot lateral links follow surface-grid edges, not a defensible regional aquifer mesh.'],['Sediment and water quality','Surface fate/transport modules exist; regional transport capacity and groundwater solute coupling remain limited. No Penny-style morphodynamic feedback is coupled.']],widths=[W*.32,W*.68])
    para('Groundwater should extend beneath land and water according to geology and head gradients. A pond may exchange through groundwater without any surface channel; do not encode that as a green surface edge. Porosity, specific yield and hydraulic conductivity have distinct roles. Evaporation, recharge, seepage and boundary flows belong in compartment budgets when added.')

    page('9 · Methods review: what passes, what does not')
    table([['Finding','Assessment and required action'],['Source and numerical bookkeeping','Retain provenance, source IDs, immutable terrain, logged exclusions, review history and conservation checks. These are useful foundations.'],['Whole-feature anchors + multipart collapse','Blocking for reach-network interpretation. Split connected components and build junctions/ports and channel-following reaches. Rendering cleanup alone is insufficient.'],['Reservoir shoreline interfaces','Blocking for predictive hydraulics. Review openings and barriers; represent structure/port physics rather than every shared boundary as an open passage.'],['Centroid-distance resistance','High priority. Replace crude lengths/sections where they do not represent actual conveyance. Storage-centroid distance is not a channel survey.'],['Percentile bed minus incision','Scenario proxy only. No demonstrated bathymetry, vertical datum or elevation uncertainty. Preserve the raw surface and label alternatives.'],['100 m slices and lumped ponds','May be useful locally, but not validated by nominal cell size. Protect junctions, curved reaches, structures, narrow passages and storage geometry.'],['0.5-second closed run','Software/conservation demonstration only. It provides no evidence of an actual storm, long-term circulation, equilibrium, flood routing or historical failure.']],widths=[W*.31,W*.69])
    h2('The current discharge closure')
    para('Each cell uses stage η = bed proxy + V/plan area. Each interface uses a rectangular Manning-type relation driven by |Δη|/L; its width is the summed shared-boundary length and L is a centroid-distance proxy. The higher cell-bed proxy controls an effective opening. Inertia, surveyed face elevation/conveyance curves and explicit crest/structure laws are absent. This is not a full shallow-water solution.')
    para('A zero global water residual is expected when internal fluxes are added to one cell and subtracted from another. It verifies bookkeeping, not whether an interface is real, its capacity is correct, or the stored water represents the chosen historical period.')
    caption('Code inspected: scripts/build_regional_network.py; hydraulics/model.py; hydraulics/groundwater.py; hydraulics/channel_review.py; web/channel-inspector.js. No underlying network was changed for this report.')

    page('10 · Example A: inspect one real canal, not the whole city')
    story.append(pic(WORK/'real_profiles.png',210))
    caption('Real prepared evidence for ANG_F_09042. Left: terrain along a provisional straight guide (~449 m). Right: the middle cross-section with illustrative incision alternatives. The 0.2/0.5/1.0 m curves are hypotheses, not inferred ancient beds. Units/datum remain unconfirmed.')
    for text in [
        '<b>1. Isolate evidence.</b> In Channel inspector choose Review workspace. Reduce feature and terrain opacity until the canal footprint, banks and imagery can be read together. Remember that the regional terrain preview is ~15 m display spacing; the pilot preview and profile sampling use finer source data.',
        '<b>2. Identify the feature.</b> Record the original ID and distinguish canal footprint, pond bank and raised road. A source class is evidence of interpretation, not proof of present or historical operation.',
        '<b>3. Check the guide.</b> Generate the provisional profile. If the guide cuts a bend, crosses a bank or covers only one segment of a complex feature, draw an along-channel guide instead. Do not use its straight chord as a reach length.',
        '<b>4. Inspect several sections.</b> View the three transects and add/adjust the guide where needed. Check bank crests, low points, possible road embankments, abrupt interpolation steps, NoData and whether the section reaches beyond both banks.',
        '<b>5. Separate observation and scenario.</b> Record measured/mapped evidence in notes. Only then propose incision and roughness values/ranges, with the reason for each. Current topography is not an ancient excavation-depth measurement.',
        '<b>6. Scope the assumption.</b> A saved per-feature incision applies to all retained cells from that source ID, potentially beyond the plotted guide. If one FID spans several physical reaches, split its geometry before assigning different reach parameters.'
    ]:para(text)
    caption('Perpendicular transects are an initial inspection aid. HEC-RAS guidance also uses bank/flow-path information and carefully oriented overbank sections; the automatic two-endpoint transects are not a finished surveyed 1D geometry [3].')

    page('11 · Example B: a gap, crossing or reservoir opening')
    story.append(pic(WORK/'connection_cases.png',175))
    h2('Walk through the actual connection segment')
    para('Use the queue and red highlight to find the two source features. Inspect the nearest gap/contact location—not the long anchor arms. Screen terrain and mapped barriers. Check a transect across the suspected opening and a profile along its intended route. Look for a bank, a road crossing, a low saddle, an inlet/outlet, or an unmapped continuation. Optical imagery can hide a ditch under vegetation; a DEM may retain a road above a culvert [5].')
    table([['Decision example','What to record—not a decision already made'],['Accepted scenario connection','“A continuous ditch is mapped and terrain/imagery support a route at this location. Treat it as open in scenario X; width/invert remain uncertain.” Give the source ID, evidence, period and bounds.'],['Rejected for this surface scenario','“A continuous embankment separates these units; no opening is supported for scenario X. Keep surface exchange closed below its reviewed crest.” Do not claim that groundwater exchange is absent.'],['Unresolved','“Canopy, water, interpolated terrain or missing structure metadata prevents an opening/invert decision. Keep competing blocked/open hypotheses separate.” Do not label missing evidence as a surveyed obstruction.']],widths=[W*.28,W*.72])
    callout('Do not adjudicate 13,103 proximity proposals one by one yet', 'First correct multipart identity, reach/junction structure and reservoir-port semantics. Then review candidates near supported alignments and plausible outlets. Raising the gap threshold until everything connects would create a convenient graph, not archaeological evidence.')
    caption('First prepared workspace: 24 links, including 5 mapped barrier-intersection flags. An intersection can be a bank edge, not a definite impermeable obstruction. Conversely, no intersection does not prove a culvert or channel.')

    page('12 · Retune the whole system—or rebuild selected parts?')
    callout('Yes to targeted reconstruction; no to starting from zero', 'Keep the source terrain/mapping, IDs, provenance, review ledger and useful numerical tests. Replace the reach-graph abstraction and the critical cell/port rules. Pure threshold adjustment cannot repair these structural issues.')
    table([['Order','Work to do'],['1 · Correct identity and topology','Split disconnected polygon components; retain parent IDs. Trace channel paths, split at genuine junctions, terminals and structures. Keep an uncertain crossing separate until reviewed.'],['2 · Classify storage and ports','Identify reservoir/pond/moat function by scale and purpose, not the generic Pond label alone. Choose lumped storage or resolved waterbody; enumerate candidate inlet/outlet/overflow ports.'],['3 · Add barrier/structure semantics','Place reviewed bank/road/levee controls at faces. Specify crest/invert and gate/culvert/weir behavior where evidence exists; use explicit alternative scenarios where it does not.'],['4 · Build hydraulic cells from the reviewed graph','Use reach-following 1D cells where appropriate and terrain-aware 2D cells for overland flow or complex water bodies. Do not let a cell straddle an important control or merge disconnected openings.'],['5 · Assess missing channels','Use terrain relief, bank geometry, imagery and archaeology to propose extra reaches. Compare conservative/sensitive extraction variants against positive examples and negative controls; do not burn every old feature into the DEM or fill every pond.'],['6 · Force and test the water system','Only after geometry review: specify initial levels, inflow/outlet conditions and rainfall; add catchment runoff and eventually soil/groundwater as required by the scientific question.']],widths=[W*.27,W*.73])
    para('<b>Your contribution:</b> identify phase-specific interpretations, true openings/structures, plausible missing alignments and data provenance. <b>Software/model contribution:</b> component-safe geometry, centreline/reach topology, explicit ports/controls, face hydraulics and reproducible uncertainty experiments. You should not be asked to rescue a misdrawn schematic by clicking thousands of green lines.')
    caption('Breaklines, terrain-informed face properties and explicit storage connections are established hydraulic modelling concepts [4,6]. That does not make the present prototype equivalent to HEC-RAS.')

    page('13 · Acceptance tests before interpreting results')
    table([['Check','Pass condition / review question'],['Topology','No connection exists merely because two pieces share an FID or two drawn lines cross. Genuine junctions and storage ports have IDs and evidence. Isolated storage is allowed.'],['Path geometry','Reach edges follow intended conveyance. Lengths reflect flow paths; a lumped reservoir has port physics rather than an arbitrary long centroid-resistance path.'],['Barriers and openings','A levee/road is closed below its reviewed crest unless a documented or explicit scenario opening exists. Test an isolated-bank case and an overtopping/culvert case.'],['Storage','No double-counted area. Stage–area/volume assumptions are documented; uniform-stage lumping is defensible for the question and timescale.'],['Terrain','Units/datum, coverage, processing, possible flattened/interpolated water surfaces and vertical uncertainty are documented. Do not derive a precise ancient bed from grid spacing.'],['Hydraulics','Test a known channel/rating case, no-gradient equilibrium, reversed head and wet/dry exchange. Check local and total balances as well as magnitudes.'],['Resolution and time','Refine geometry/timestep around bends, controls and steep changes. Compare stage, port flux, travel time and budget, not just visual similarity.'],['Forcing and period','Specify watershed/external inputs and outlet levels. Separate modern-terrain, reconstructed historical and failure scenarios; use independent observations where possible.']],widths=[W*.23,W*.77])
    h2('Tune parameters only after fixing representation')
    para('Candidate gap distance changes the review search, not physical opening width. Cell size changes resolution, not the existence of a buried channel. Manning n cannot compensate reliably for an incorrect bank opening or a kilometre-scale resistance shortcut. Incision changes a hypothetical bed; it is not a substitute for bathymetry. Groundwater conductivity cannot repair a missing surface-channel route.')
    para('<b>Do not use a larger connected component as the sole success criterion.</b> A valid dry-season system may contain closed ponds and seasonal spill connections. Earlier periods may have a different functioning subnetwork. A robust result should survive plausible geometry/parameter alternatives, not just one visually appealing graph.')

    page('14 · Source map, evidence and limitations')
    table([['Reference','How it was used'],['[1] Penny et al. (2018), Science Advances 4, eaau4029. DOI: 10.1126/sciadv.aau4029.','Local supplied original: assets/manuscripts/penny_2018_demise_angkor.pdf. Main text pp. 2, 5–6: topology, coding, scope, capacities and interpretation of Fig. 5.'],['[2] Penny et al. (2018), Supplementary Materials.','Local supplied supplement: assets/manuscripts/penny_2018_demise_angkor_supplement.pdf. PDF pp. 2–5: graph assumptions, initialization, perturbation, damage equations and Fig. S1.'],['[3] USACE HEC-RAS Mapper, Cross Sections.','Perpendicular placement, bank/terrain context, editing and updated geometry. Official page checked 10 Nov 2026; local HTML already in library.'],['[4] USACE HEC-RAS 6.6, Storage Area and 2D Flow Area Connections.','Connection/structure concepts, not evidence for an Angkor structure. Official documentation checked 10 Nov 2026.'],['[5] USGS Lidar Base Specification, Appendix 2: Hydro-Flattening Reference.','Distinguishes topographic treatment from hydrologic conditioning/enforcement. Does not establish processing of our Huma-Num DTM.'],['[6] USACE HEC-RAS 6.5, Development of the 2D Computational Mesh.','Cell/face geometry, mesh refinement and breakline concepts; not a claim that our code implements that solver.']],widths=[W*.46,W*.54])
    for label,url in [('Penny original DOI','https://doi.org/10.1126/sciadv.aau4029'),('HEC cross-sections','https://www.hec.usace.army.mil/confluence/rasdocs/rmum/latest/geometry-data/cross-sections'),('HEC storage connections','https://www.hec.usace.army.mil/confluence/rasdocs/rasum/6.6/entering-and-editing-geometric-data/storage-area-and-2d-flow-area-connections'),('USGS hydro-flattening','https://www.usgs.gov/ngp-standards-and-specifications/lidar-base-specification-appendix-2-hydro-flattening-reference'),('HEC computational mesh','https://www.hec.usace.army.mil/confluence/rasdocs/r2dum/6.5/development-of-a-2d-or-combined-1d-2d-model/development-of-the-2d-computational-mesh')]:story.append(P(f'<link href="{escape(url)}" color="#155b61">{label} ↗</link>','GuideSmall'))
    h2('Audit versus interpretation')
    para('All seven source captures were inspected. Counts, multipart identities, anchor lengths and cell-interface examples were recomputed from local artifacts/source geometry. Diagrammed replacements are schematic recommendations, not a generated corrected network. No field visits, bathymetric surveys, metadata confirmation or predictive calibration were performed. The generic solver and review tests are useful software checks; they do not constitute scientific acceptance.')
    caption('Primary code pointers: scripts/build_regional_network.py::{feature_contacts,partition,shared_interfaces,sample_bed,build}; web/channel-inspector.js::{renderFeatureGraph,renderFlow}; hydraulics/model.py::{discharge,simulate}; hydraulics/groundwater.py::Groundwater; hydraulics/channel_review.py::{profile,screen,connection_enabled}.')

    page('15 · A review sheet to use beside the dashboard')
    para('<b>Start with one channel reach, one actual junction or crossing, and one receiving storage outlet.</b> Do not try to certify the city-wide network from the overview. Keep current terrain and each proposed historical reconstruction separate.')
    table([['Record','Fill in / attach evidence'],['Feature/reach/port IDs; scenario and period','_________________________________________________\n_________________________________________________'],['Geometry observed versus inferred','Source footprint / field measurement / imagery / terrain profile / hypothetical continuation\n_________________________________________________'],['Actual contact/opening location','Inspect the gap/port, not the long anchor arms.\n_________________________________________________'],['Barriers and structure evidence','Bank/road crest, culvert invert, gate, breach, spill path, or unknown\n_________________________________________________'],['Bed, banks, width and uncertainty','Datum/units; observed cross-section versus assumed incision; missing submerged bed\n_________________________________________________'],['Water levels and possible direction','Stage/head evidence; perennial/seasonal/reversible/unknown\n_________________________________________________'],['Decision and alternatives','Accept scenario / reject / unresolved, with rationale and a contrasting case\n_________________________________________________'],['Change category','Display only / geometry split / reach-junction change / storage-port law / parameter / external forcing\n_________________________________________________']],widths=[W*.34,W*.66])
    callout('What “good” should look like at the next milestone', 'A readable map of source-aligned reaches, explicit junctions and storage ports, with uncertain alternatives clearly separated. A companion hydraulic mesh respects banks and structures. Its fluxes respond to documented heads and boundaries, not to incidental polygon adjacency. Sparse disconnected ponds are acceptable; unexplained long chords and unreviewed shoreline outlets are not.')
    para('The immediate priority is to correct graph/port construction and review a small pilot against these criteria. Then expand regionally, test numerical and parameter sensitivity, and only afterward interpret historical damage or biological/chemical transport.')


def main():
    import shapefile
    from shapely import make_valid
    from shapely.geometry import shape,LineString
    from pyproj import Transformer
    # Recompute the audit so report figures are tied to the actual current artifacts.
    import runpy
    runpy.run_path(str(ROOT/'scripts/audit_regional_model.py'),run_name='__main__')
    audit=json.loads((WORK/'audit.json').read_text());figures();content(audit)
    doc=SimpleDocTemplate(str(PDF),pagesize=A4,rightMargin=42,leftMargin=42,topMargin=40,bottomMargin=46,title='Angkor regional model: inspection guide and methods review',author='QModel research workspace',pageCompression=1)
    doc.build(story,onFirstPage=footer,onLaterPages=footer)
    provenance={'built_utc':datetime.now(timezone.utc).isoformat(),'pdf':str(PDF.relative_to(ROOT)),'intended_pages':len(page_titles),'page_titles':page_titles,'inputs':{}}
    for path in [*FOLDER.glob('*.png'),ROOT/'assets/manuscripts/penny_2018_demise_angkor.pdf',ROOT/'assets/manuscripts/penny_2018_demise_angkor_supplement.pdf',ROOT/'scripts/build_regional_network.py',ROOT/'hydraulics/model.py',ROOT/'web/channel-inspector.js',ROOT/'assets/private/regional_network/feature_graph.json',ROOT/'assets/private/regional_network/cell_network.json']:
        provenance['inputs'][str(path.relative_to(ROOT))]=hashlib.sha256(path.read_bytes()).hexdigest()
    provenance['pdf_sha256']=hashlib.sha256(PDF.read_bytes()).hexdigest();(WORK/'guide_provenance.json').write_text(json.dumps(provenance,indent=2))
    print('PDF created:',PDF)
if __name__=='__main__':main()
