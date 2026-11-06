# Angkor waterways: archaeological reconstruction and hydraulic model review

Search date: 19 October 2026. Targeted literature and institutional-source review; not an exhaustive systematic review. Scope: Angkor Wat's local waterways and moat, the Greater Angkor network, and evidence useful for volumetric reconstruction and eventual bacterial transport. No authors or institutions were contacted.

## Finding

**Substantial archaeologically grounded reconstructions exist, and an actual detailed modern hydraulic model of Angkor is documented. I did not identify a publicly downloadable, independently validated, period-specific volumetric hydraulic model of the complete medieval Greater Angkor network or Angkor Wat moat.** These statements are compatible: mapping, estimated storage, modern operational hydraulics, and a historical flow reconstruction are different products.

The most consequential lead is APSARA/SIAVB/Hydratec's **Hydra model**. An institutional brochure explicitly describes topographic surveys, monitoring data, calibration, and simulated hydrological and gate-operation scenarios. This should be investigated before assuming a hydraulic model must be built from scratch. Its historical applicability and availability remain unverified.

## Annotated sources

### 1. Archaeological network foundation

**Evans et al. (2007), “A comprehensive archaeological map of the world's largest preindustrial settlement complex at Angkor, Cambodia.”** [DOI: 10.1073/pnas.0702525104](https://doi.org/10.1073/pnas.0702525104); [open article](https://pmc.ncbi.nlm.nih.gov/articles/PMC1964867/).

Integrates remote sensing, aerial/radar information, earlier maps, and field survey into Greater Angkor archaeological mapping. Provides the spatial foundation for waterways and barriers; it is not a transient water-level/velocity model. Public article and map figures exist. An openly downloadable complete hydraulic GIS or geometry package was not verified. Surface remains combine different construction phases, so spatial fidelity does not guarantee a single historical configuration.

**Fletcher, Pottier, Evans & Kummu (2008), “The development of the water management system of Angkor: a provisional model.”** [DOI: 10.7152/bippa.v28i0.12016](https://doi.org/10.7152/bippa.v28i0.12016); [publisher PDF](https://journals.lib.washington.edu/index.php/BIPPA/article/view/12016/10641).

Reconstructs successive development of the approximately 1,000 km² network from the eighth/ninth to fourteenth centuries, using mapped channels, embankments, reservoirs and diversions. Here “model” means an archaeological interpretation of development and function. Useful for selecting historical phases and assessing proposed connections; not a calibrated volumetric flow simulation. Open paper; executable model/GIS release not verified.

### 2. LiDAR terrain and Angkor Wat-specific reconstruction

**Evans et al. (2013), “Uncovering archaeological landscapes at Angkor using lidar.”** [DOI: 10.1073/pnas.1306539110](https://doi.org/10.1073/pnas.1306539110); [open article](https://pmc.ncbi.nlm.nih.gov/articles/PMC3732978/).

Ground-surface elevation models reveal features obscured by vegetation, including the urban context of Angkor Wat. This supports extraction of channels, embankments, and depressions. LiDAR is an observation of surviving topography, not a measurement of all original beds or submerged bathymetry. Article availability does not establish access to the original georeferenced terrain/point cloud. Need acquisition metadata, vertical datum, uncertainty, coverage, and permissions before hydraulic use.

**Evans & Fletcher (2015), “The landscape of Angkor Wat redefined.”** [DOI: 10.15184/aqy.2015.157](https://doi.org/10.15184/aqy.2015.157).

The strongest directly relevant local archaeological source located: combines LiDAR, archival research, and targeted ground investigations to reinterpret Angkor Wat and its surroundings. Crucially, the “Vicinity of Angkor Wat” section identifies the present northeastern moat inlet as constructed in **1916**. It cannot automatically be imposed on a medieval simulation. The study also stresses chronological ambiguity and multiple phases of landscape development. It supplies archaeological constraints rather than a calibrated moat circulation model; downloadable hydraulic project files were not identified.

**Hanus & Evans (online 2015; issue 2016), “Imaging the Waters of Angkor: A Method for Semi-Automated Pond Extraction from LiDAR Data.”** [DOI: 10.1002/arp.1530](https://doi.org/10.1002/arp.1530).

Direct methodological precedent for extracting numerous household/community ponds in the urban core. Relevant because bacterial retention may depend on small, poorly exchanged waters absent from a coarse distribution graph. This is feature detection and archaeological mapping, not proof that every extracted depression was contemporaneous, connected, or water-filled. Software/data download was not verified in this review.

### 3. Existing volumetric estimates: an important partial answer

**Klassen, Ortman, Lobo & Evans (online 2021; issue 2022), “Provisioning an Early City: Spatial Equilibrium in the Agricultural Economy at Angkor, Cambodia.”** [DOI: 10.1007/s10816-021-09535-5](https://doi.org/10.1007/s10816-021-09535-5).

Explicitly estimates reservoir/moat volumes from LiDAR; therefore it would be incorrect to say volumetric reconstructions do not exist. In “Estimating Temple Platform, Reservoir, and Moat Volumes,” the authors use within-polygon elevation range as a depth/height estimate, and area–depth regressions outside LiDAR coverage. They assume surviving extrema approximate original form. These are storage proxies for agricultural analysis, not measured historical bathymetry, stage–storage curves, or validated operating water volumes. The principal analysis excludes the civic-ceremonial core, so it is not an Angkor Wat-specific model. Data Availability points to [tDAR's Social Reactors project](https://core.tdar.org/project/392021/social-reactors-project-datasets), but the actual downloadable records were not inspected successfully. The DTM is credited to KALC rather than released there as an accessible terrain package.

### 4. Penny's failure model and an earlier channel-evolution model

**Penny et al. (2018), “The demise of Angkor: Systemic vulnerability of urban infrastructure to climatic variations.”** [DOI: 10.1126/sciadv.aau4029](https://doi.org/10.1126/sciadv.aau4029); [open article](https://pmc.ncbi.nlm.nih.gov/articles/PMC6192684/). Both PDFs supplied in `resources/` were text-extracted and checked.

The 617-node, 1,013-edge directed network is an archaeological abstraction with phenomenological erosion/sedimentation and flow redistribution. Capacity substitutes for channel cross-section; it does not supply surveyed reach geometry, reservoir storage, or calibrated travel times. Main article describes the topology as thirteenth-century; supplement Fig. S1 calls its source maps fourteenth-century—resolve this labeling before choosing an exact simulation date. Supplement Fig. S1 documents GIS-to-graph conversion. Data statement: paper/supplement contain data needed for conclusions; additional data may be requested. No downloadable graph/code/geometry package was verified. Useful failure hypotheses, not ready-made bacterial hydraulics.

**Kummu (2009), “Water management in Angkor: Human impacts on hydrology and sediment transportation.”** [DOI: 10.1016/j.jenvman.2008.08.007](https://doi.org/10.1016/j.jenvman.2008.08.007); [Aalto full PDF](https://aaltodoc.aalto.fi/server/api/core/bitstreams/5c04c4ad-ac51-4f0f-b75e-f78cb6929431/content).

Contains more than descriptive hydrology: pp. 1418–1419 and Fig. 6 summarize a mathematical Siem Reap channel-incision model, attributed to Lustig et al. (2008), compared with measured bed elevations. Original bed depth is assumed approximately 2 m below ground; topography uses 50 m DEM/TOPSAR information. Authors acknowledge sparse validation and construction in multiple phases. This is useful for alternative historical bed profiles, not a complete network storage/transport model. No runnable model or input release was identified.

### 5. Actual Angkor hydraulic model: modern operating system

**SIAVB, “SDGERA: Système d’Aide à la Décision pour la Gestion des Eaux de la Région d’Angkor,” institutional brochure, undated in inspected text.** [Primary PDF](https://www.siavb.fr/download00010002.aspx?f=.%2Fiso_album%2F8_pages_angkor-version_definitive-27oct-4.pdf).

PDF **p. 6** explicitly reports surveys at dykes, sills, bridges, roads, gates, and storage basins; these and monitoring data supported a detailed Angkor hydraulic model calibrated with **Hydra (Hydratec)**. Hydrological and gate-management scenarios were simulated. This is evidence that a real geometry-based hydraulic model exists, rather than merely aspirational language. Calibration performance, event dates, mesh resolution, full equations/configuration, geometry files, and public download were not supplied in the inspected brochure. It addresses modern/restored operation, not archaeological validation of medieval conditions.

**Hang Peou, “Angkor Hydraulic City and its Water Management,” in Sophia University's *The Hydraulic City of the Angkor Empire and Construction of Angkor Wat*, special issue 33.** [Primary institutional volume](https://dept.sophia.ac.jp/is/angkor/publication/pdf/bunka/bunka33_special.pdf).

Printed **pp. 122–124** identify APSARA's French partners and Hydratec/SETEC, introduce SDGERA's December 2022 MoU, and show model/network layouts in Figs. 7.1–7.3. They discuss hydraulic/hydrologic forecasts and gate optimization. Confirms model context, but does not independently validate model accuracy. Bibliographic publication date should be confirmed from repository metadata before formal citation.

**Peou Hang (2014), “Sacred water: rediscovering the ancient hydraulic system of Angkor and traditional knowledge of water management and engineering systems.”** [IJIH article](https://ijih.org/volumes/article/461).

Describes rehabilitation and dimensions/storage, useful for identifying surveys and operational knowledge. Modern restorations depart from ancient arrangements: the North Baray inlet was relocated, and a canal was dredged narrower to protect cultivated land. Consequently, restored geometry needs explicit historical editing. The introductory modelling claim alone does not establish software, calibration or access; the SIAVB brochure provides stronger technical evidence.

### 6. A real archaeological hydraulic modelling precedent—outside Angkor Wat

**Lustig, Klassen, Evans, French & Moffat (2018), “Evidence for the breakdown of an Angkorian hydraulic system, and its historical implications for understanding the Khmer Empire.”** [DOI: 10.1016/j.jasrep.2017.11.014](https://doi.org/10.1016/j.jasrep.2017.11.014); [institutional full PDF](https://researchnow-admin.flinders.edu.au/ws/files/35851711/1_s2.0_S2352409X17303619_main.pdf).

Reconstructs the tenth-century Koh Ker reservoir/embankment and evaluates hydraulic failure with HEC-RAS/HEC-GeoRAS, hydrological and wave modelling, archaeological survey and terrain evidence. Uses local observations of recent high-water marks to constrain river modelling; historical rainfall and original geometry remain uncertain. A strong methodological precedent, **not a model of Greater Angkor or Angkor Wat**. A public runnable project release was not verified.

### 7. Accessible LiDAR-derived data with a crucial limitation

**Perron et al. (2024), “Archaeoscape: Bringing Aerial Laser Scanning Archaeology to the Deep Learning Era.”** [Paper](https://arxiv.org/abs/2412.05203); [official dataset and licence](https://archaeoscape.ai/data/2024/).

Official page specifies 888 km², 0.5 m orthophotos and normalized DTMs, and expert hydrology annotations from 2012/2015 surveys and long-term mapping. Access requires credentials and licence acceptance. **Released data have no georeferencing, and licence terms prohibit attempts to locate the data.** Consequently, this release cannot legitimately be aligned to Penny's georeferenced network. It may support generic feature-extraction research within its licence. Seek a separately authorized georeferenced terrain/GIS product from custodians for this project; do not attempt to recover locations from the benchmark.

## Recommended acquisition order

1. Establish the study area and historical window: Angkor Wat moat alone, its supply catchment, or Greater Angkor, and which century/failure sequence.
2. Investigate access to APSARA/SIAVB/Hydratec model geometry, topographic surveys, storage representations, boundary conditions and calibration report. These may be more valuable than reconstructing everything from papers, but modern controls must be distinguished from historical ones.
3. Obtain authorized georeferenced archaeological GIS and original KALC/CALI terrain with datum and uncertainty metadata. Obtain Penny's graph with feature IDs if available, allowing its simplifications to be audited against the GIS.
4. Reuse published volume estimates as checks/priors, not final bathymetry. Constrain original beds and control elevations using excavation, cores, archive surveys and phased archaeological interpretation.
5. Build a small prototype with explicit uncertain geometry and conservative-tracer mass balance before bacterial processes. Compare intact, blockage, diversion/incision and altered-storage scenarios. Historical hotspot predictions would be scenario-dependent rather than validated observations of past bacterial concentrations.

## Outstanding verification

No full public historical hydraulic package was found in this targeted search; this is not evidence none exists privately or in technical archives. Most important unresolved questions are access to the Hydra project, actual coverage and calibration skill, availability of georeferenced GIS/DTM, and historical configuration of Angkor Wat's supply/outlet structures. Archaeological accuracy should be assessed feature-by-feature and period-by-period, rather than assigned to an entire model as a binary property.
