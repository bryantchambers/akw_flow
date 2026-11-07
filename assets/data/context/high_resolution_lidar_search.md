# Higher-resolution Angkor terrain: acquisition findings

Checked **6 November 2026**. Targeted primary-source/catalogue search, not an exhaustive systematic review. Scope: usable ground elevation for Angkor Wat and Greater Angkor, rather than rendered images or monument meshes. No external person was contacted and no restricted-access registration was submitted.

## Result

**The original 0.5–1 m archaeological LiDAR terrain remains the best target and has a documented institutional research-access route. No unrestricted, georeferenced KALC/CALI terrain download was verified.** A concrete intermediate-resolution alternative was located: the legacy NASA/JPL–ASF TOPSAR archive still publishes Angkor radar DEM products. One raw C-band DEM was downloaded and its actual header inspected. It is sampled at 5 m, but is not LiDAR, not a ready-to-use GeoTIFF, and is not yet suitable for replacing the viewer’s terrain without conversion and quality checks.

The useful distinction is now: **original LiDAR by research request; acquired 5 m-post radar DEM awaiting conversion/QC; 30 m modern DSM already operational.**

## Ranked options

| Priority | Product | Resolution / coverage | Verified access | Assessment |
|---|---|---|---|---|
| 1 | Original KALC 2012 bare-earth DTM and classified point cloud | Published examples include 0.5 m DTM; the 370 km² campaign includes separate Angkor, Phnom Kulen and Koh Ker blocks | APSARA Documentation Centre and University of Sydney archives are documented; request current access through APSARA/EFEO | Strongest route for archaeological canals/embankments; need georeferencing, absolute heights, metadata and permissions |
| 2 | Original CALI 2015 DTM/point cloud and archaeological vectors | High-resolution airborne survey across multiple Cambodian sites; do not assume the full surveyed area is Angkor | EFEO / Cambodian partner custodians; no unrestricted georeferenced download verified | Seek exact tile index and overlap with the pilot area rather than requesting “all CALI” |
| 3 | NASA/JPL–ASF TOPSAR C-band DEM, `ts1260` | **5 m posts**, nominal azimuth resolution about **10.8 m** in the processing log; a roughly 11.65 × 60.68 km strip crossing Angkor Wat | **Raw file downloaded from an independently public ASF endpoint**; packaged ZIP requires Earthdata login | Concrete fallback for comparison and historical landscape context, but radar surface effects, geocoding, vertical datum and invalid values require work |
| 4 | Monash SensiLab’s Greater Angkor visualization source repository | Almost 1,500 km² visualization combining LiDAR, DEM and GIS | Institutional page identifies University of Sydney + EFEO as repository maintainers; no downloadable raster project linked | Additional route to identify original terrain version, coverage and current custodians; do not extract elevation from rendered bitmaps |
| 5 | Open Heritage 3D Western Causeway / Banteay Kdei | Local terrestrial scans from 2004; Western Causeway download listed as 0.176 GB | Published data, download links emailed; **explicitly without georeferencing** | Useful monument-scale geometry, not a regional ground DTM or a georeferenced canal dataset |
| Exclude from direct geospatial integration | Archaeoscape released benchmark | 0.5 m nDTM/orthophotos and annotations, 888 km² | Credentialed files; **no georeferencing; licence prohibits attempts to locate the data** | May support permitted generic segmentation work. A separately authorized original georeferenced product is required for this project |
| Not an improvement | ODC Cambodia ASTER GDEM | Approximately 30 m global satellite elevation | Public Cambodia tile downloads | Different context source, not the high-resolution solution |

## 1. Best LiDAR access route: ask for the original research products

The [2017 ICC-Angkor technical report](https://icc-angkor.org/wp-content/uploads/2017/11/28-Technical-Committee-21-22-June-2017-English-final.pdf) states that KALC data were archived at the **University of Sydney and APSARA Documentation Centre**, with research use in GIS and other formats. It also explains that ownership is distributed among projects and partners. This is historical evidence of an access mechanism, not a promise that every product is currently available under one licence.

The [2013 acquisition paper](https://doi.org/10.1073/pnas.1306539110) demonstrates 0.5 m ground terrain and 1 m surface products around Angkor Wat. Those published figure resolutions do not establish access to the original rasters, current accuracy, submerged bathymetry or original medieval beds.

Use these current institutional routes:

- [APSARA contact page](https://apsaraauthority.gov.kh/contact-us/): `info@apsaraauthority.gov.kh`. Request routing to the Documentation Centre and the Department of Water, Forestry and Infrastructure Management.
- [EFEO Siem Reap centre](https://www.efeo.fr/centre/siem-reap/?lang=en): its institutional contact form and telephone **+855 768-235-453**. Ask for the present geospatial/KALC/CALI archive custodian. The site’s research text contains some historical staff information, so do not rely on the entire staff list as current.
- [Christophe Pottier’s EFEO profile](https://www.efeo.fr/membre/christophe-pottier/?lang=en): contact form; relevant archaeological mapping and landscape expertise. Ask for a custodian referral and interpretation rather than assuming personal ownership of every dataset.
- [Dan Penny’s current Sydney profile](https://profiles.sydney.edu.au/dan.penny/professional): `dan.penny@sydney.edu.au`; ask for the Greater Angkor/KALC archive route and identifiers linking the published graph to GIS features.

No original KALC/CALI vertical datum, ground-classification metadata or unrestricted redistribution licence was verified from a public raster header in this search. These must be requested explicitly.

## 2. Concrete acquisition: legacy TOPSAR `ts1260`

### Verified discovery and access

The [JPL Angkor TOPSAR search](https://airsar.jpl.nasa.gov/cgi-bin/search.plex?sitename=angkor&proc_type=ts%25&nav=SEARCH) returns **11 processed records**. Metadata for the first ten was retrieved into `lidar_search_evidence/`; the page’s result count and ten local records are deliberately distinguished.

The [ASF scene directory](https://airsar.asf.alaska.edu/data/ts/ts1260/) lists raw products and derived archives. The **ZIP** endpoint `ts1260_DEM.zip` redirects to `urs.earthdata.nasa.gov` OAuth and returned HTTP 401 without authentication. It was not acquired. This is distinct from the independently exposed [raw DEM endpoint](https://airsar.asf.alaska.edu/data/ts/ts1260/ts1260_c.demi2), which returned HTTP 200 without credentials. Its header was first checked with HTTP 206 byte-range access, then the bounded raw product was downloaded with parent authorization.

### Acquired files and exact header facts

Stored in `topsar/`:

- `ts1260_c.demi2`: **56,572,400 bytes**, SHA-256 `bff1b1b13d63d8f1a82121a67458b6d423ec321652d7ed841d55ca992b8f679f`.
- `ts1260_c.demi2.header.bin`: the first **18,640 bytes**, covering the source header records.
- `ts1260_meta.airsar`, `hd1260.log`: published scene and processor metadata.
- `ts1260_header_footprint.geojson`: WGS84 corner polygon, **not** a geocoded DEM.
- `acquisition.json`, `inspection.json`: acquisition provenance and unresolved processing issues.

Acquisition was **21 September 2000**. Raw dimensions are **12,136 rows × 2,330 columns**; signed integer samples occupy two bytes. The DEM header reports WGS84 ellipsoid, a UTM planimetric reference but zone **TBD**, 5 m post spacing, height increment **0.03765 m**, and offset **−161.3 m**. It also includes four latitude/longitude corners and peg-point/heading information. This is real geolocation metadata, not merely a place name, but it does not establish a standard GeoTIFF affine transform.

DEM-header footprint corners (longitude, latitude): `(103.97304, 13.73698)`, `(104.07427, 13.70117)`, `(103.88372, 13.18543)`, `(103.78268, 13.22116)`. The strip crosses Angkor Wat and covers only part of the broader study area.

### What must be resolved before using it

1. Convert the radar ground-range/peg representation using an AIRSAR-aware workflow; do not declare a UTM zone and attach an arbitrary affine transform. GDAL/Rasterio did not recognize this raw DEM directly in the available environment.
2. Confirm byte order and invalid-value conventions from the processor documentation. A big-endian inspection produces plausible digital values and frequent `−16384`, but that is not enough to silently declare a NoData mask.
3. Apply the documented increment/offset to decode metres; keep raw samples intact. [ASF’s AIRSAR format documentation](https://asf.alaska.edu/sar-information/data-formats-in-depth/) explains this conversion and the DEM header.
4. Verify the vertical reference. “WGS84 ellipsoid model” does **not** by itself establish that the output elevations are EGM2008 orthometric heights or that they can be mixed with Copernicus heights without correction.
5. Assess co-registration, radar artifacts, vegetation response and elevations against independent control. Grid spacing is neither effective spatial resolution nor vertical accuracy. Four-corner approximate placement may support an exploratory preview, but is not a validated hydraulic reference.

Do not substitute it for a bare-earth LiDAR DTM. The 2000 acquisition can also contain post-medieval structures and channel alterations.

Current ASF API searches using the study bounding box returned no AIRSAR DEM features, even though the legacy directories are live. Preserve the exact scene IDs and primary URLs instead of interpreting that empty modern search as evidence that no data exist.

## 3. Further repository lead: Monash / Sydney / EFEO

[Monash SensiLab’s institutional project page](https://sensilab.monash.edu/research/modelling-a-medieval-metropolis/) explicitly identifies a University of Sydney–EFEO geospatial repository as the source of its LiDAR, elevation and feature layers. The project’s listed general contact is **sensilab@monash.edu**. Ask which original raster versions and coordinate/height references were used, and who can authorize a bounded research extract. No public data archive or service endpoint was linked there during inspection.

## 4. Products that should not be mistaken for usable regional LiDAR

[Open Heritage 3D’s Western Causeway record](https://openheritage3d.org/project.php?id=vngf-1h12) is a terrestrial monument scan collected in March 2004. It explicitly scores the model as lacking georeferencing. Its CC BY-NC-SA licence and emailed download route do not turn approximate site bounds into surveyed reference coordinates. Banteay Kdei has the same georeferencing limitation.

[Archaeoscape’s official dataset record](https://zenodo.org/records/14409524) confirms restricted credentialed files and prohibits re-georeferencing and redistribution. Do not follow third-party claims that this release is freely relocatable onto an Angkor map. Seek a separately authorized original product instead.

The [ODC ASTER Cambodia catalogue](https://data.vietnam.opendevelopmentmekong.net/en/dataset/aster-global-digital-elevation-model-aster-gdem) exposes satellite elevation tiles; this is not LiDAR and does not improve the nominal 30 m sampling already in use. High-resolution images, hillshade figures, LiDAR intensity and normalized relative-height arrays also do not substitute for an absolute-elevation ground DTM.

## Suggested initial request (draft only; not sent)

**Subject:** Research access request: georeferenced KALC/CALI terrain and hydraulic GIS pilot near Angkor Wat

We are developing a provenance-controlled reconstruction of Angkor’s water distribution, initially testing a small pilot area before hydraulic and bacterial-transport scenarios. Could you identify the current custodian and access procedure for the original KALC/CALI ground-elevation data and associated archaeological hydraulic vectors?

Our first request is a coverage index and a roughly 5 × 5 km pilot clip centered near Angkor Wat (approximately 103.867° E, 13.412° N), to refine with your advice around supply canals and a receiving basin. Ideally the package would contain a 0.5–1 m bare-earth DTM with absolute elevations; classified LAS/LAZ if permitted; channel, embankment, reservoir, moat and structure vectors with original IDs; horizontal/vertical reference systems and transformation information; acquisition and processing dates; accuracy/ground-control information; and known restoration or historical-phase annotations.

Please advise the research licence, citation and publication conditions, permissible derived outputs, and any requirement for institutional collaboration or a formal proposal. We can supply affiliation, named investigators, a research plan and a map of the proposed pilot. We are requesting an authorized original georeferenced research product, not permission to relocate the degeoreferenced Archaeoscape benchmark.

## Immediate next steps

1. Request the original LiDAR pilot and archive coverage index through APSARA and EFEO; include the Sydney repository referral.
2. In parallel, convert and quality-check the acquired TOPSAR raw scene with explicit metadata handling. Keep its radar-derived interpretation separate from bare-earth LiDAR.
3. Only after reference/height checks, compare it with Copernicus and assess whether it provides meaningful additional channel/embankment information.
4. Acquire more TOPSAR strips only if the pilot’s reference, accuracy and coverage prove useful; do not build an unverified 5 m mosaic simply because files exist.

## Subsequent preview conversion — 6 November 2026

After the acquisition assessment above, `scripts/build_topsar_scenes.py` implemented metadata-based SCH conversion. The viewer now offers a native-spacing ~5 m Angkor Wat detail and an ~80 m full-strip overview. This resolves preview placement and mathematical height decoding; it does not establish independent ground accuracy, a fully verified NoData policy or suitability for hydraulic simulation. See [conversion notes](topsar/CONVERSION.md). Earlier raw-stage observations above are retained for provenance.
