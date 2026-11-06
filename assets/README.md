# Angkor waterways source collection

Acquired 19 October 2026 from the sources in the literature review. Original files in `../resources/` are preserved.

## Downloaded material

| Source | Local file |
|---|---|
| Evans et al. 2007 — comprehensive archaeological map | [PDF](manuscripts/evans_2007_comprehensive_archaeological_map.pdf) |
| Fletcher et al. 2008 — development of the water management system | [PDF](manuscripts/fletcher_2008_water_management_provisional_model.pdf) |
| Evans et al. 2013 — archaeological landscapes using LiDAR | [PDF](manuscripts/evans_2013_uncovering_archaeological_landscapes_lidar.pdf) |
| Evans & Fletcher 2015 — landscape of Angkor Wat | [PDF](manuscripts/evans_fletcher_2015_landscape_angkor_wat_redefined.pdf) |
| Klassen et al. 2021/2022 — Provisioning an Early City | [PDF](manuscripts/klassen_2022_provisioning_early_city.pdf), [publisher supplement](manuscripts/klassen_2022_provisioning_supplement.docx) |
| Penny et al. 2018 — demise of Angkor | [PDF](manuscripts/penny_2018_demise_angkor.pdf), [supplement](manuscripts/penny_2018_demise_angkor_supplement.pdf) |
| Kummu 2009 — hydrology and sediment transportation | [PDF](manuscripts/kummu_2009_water_management_angkor.pdf) |
| SIAVB — SDGERA / Hydra model documentation | [Brochure PDF](documentation/siavb_sdgera_angkor_hydra_brochure.pdf), especially p. 6 |
| Sophia University special issue 33 — hydraulic city and construction of Angkor Wat | [Complete volume PDF](manuscripts/sophia_special33_hydraulic_city_angkor.pdf), including Hang Peou chapter |
| Peou Hang 2014 — Sacred water | [Scanned PDF](manuscripts/peou_2014_sacred_water.pdf), [article HTML](metadata/peou_2014_article.html) |
| Lustig et al. 2018 — breakdown of an Angkorian hydraulic system at Koh Ker | [PDF](manuscripts/lustig_2018_breakdown_angkorian_hydraulic_system.pdf) |
| Perron et al. 2024 — Archaeoscape | [arXiv manuscript](manuscripts/perron_2024_archaeoscape.pdf), [source archive](models/archaeoscape_source_main.zip), [extracted code](models/archaeoscape/README.md) |

The collection contains 13 PDFs (including Penny's supplement and the SIAVB brochure), one DOCX supplement, and one source-code archive. The full Sophia volume preserves the context of its individual chapters.

## Model and dataset status

**The downloaded Archaeoscape code is an archaeological feature-segmentation research framework, not a hydraulic model.** Its references to Hydra concern the Python configuration library, not Hydratec's hydraulic software. The source is pinned to commit `459b087f3753037490f3927d9db4120727840d9e`. Its README lists trained Archaeoscape models as “Coming soon”; the included download script fetches generic pretrained backbones, which are not Angkor hydraulic models and were not downloaded. Code is collected but has not been installed or executed.

| Requested item | Acquisition status / next access route |
|---|---|
| Angkor APSARA/SIAVB/Hydratec Hydra project, geometry, calibration report | Public project-file download not located. Documentation downloaded; project access would require its custodians. |
| Penny graph, original GIS and simulation code | No public downloadable package verified in the paper/supplement. Original data may be requested from the authors. |
| Kummu/Lustig channel-incision model inputs and code | Description and results downloaded within Kummu's manuscript; runnable package not located. |
| Koh Ker HEC-RAS/HEC-GeoRAS project | Manuscript downloaded; runnable project files not located. |
| Georeferenced KALC/CALI LiDAR and archaeological GIS | No unrestricted download verified. Original terrain and GIS require access through custodians. |
| Archaeoscape terrain/annotations | [Dataset access and licence page saved](metadata/archaeoscape_dataset_access.html). Credentialed registration and agreement required; data are degeoreferenced and prohibit attempts to locate them. No registration submitted or dataset downloaded. |
| Klassen / Social Reactors underlying tables | tDAR project endpoint blocked automated access (HTTP 403; browser tool also failed). Publisher supplement downloaded, but it does not substitute for the tDAR datasets. |
| Hanus & Evans 2016 — Imaging the Waters of Angkor | Publisher and author-upload download endpoints returned HTTP 403. [Citation metadata](metadata/hanus_evans_2016_crossref.json) saved; PDF not obtained. [DOI](https://doi.org/10.1002/arp.1530), [author upload landing page](https://www.researchgate.net/publication/284226603_Imaging_the_Waters_of_Angkor_A_Method_for_Semi-Automated_Pond_Extraction_from_LiDAR_Data). |

No authors or institutions were contacted, accounts created, or restricted-data access agreements submitted. Unavailable files have not been replaced with reconstructed or placeholder models.

## Provenance and verification

- [Acquisition manifest](metadata/acquisition_manifest.json): source and resolved URLs, retrieval timestamps, file sizes, SHA-256 values, and failed attempts.
- [PDF verification](metadata/pdf_validation.json): structural readability, page counts, and first-page excerpts. The Peou scanned PDF was also visually checked.
- [Unavailable model/data inventory](metadata/unavailable_assets.json): remaining access gaps.
- [Repository metadata](metadata/archaeoscape_repository.json) and [commit metadata](metadata/archaeoscape_commit.json): exact code snapshot.
- [Literature review](documentation/angkor_waterways_literature_review.md): archaeological interpretation, scope, and limitations.
- `SHA256SUMS`: checksums for all collected and extracted files, excluding the checksum file itself. Verify from this directory with `sha256sum -c SHA256SUMS`.

PDF signatures and structure were checked; ZIP and DOCX archives passed integrity checks. These checks establish file integrity and identity, not archaeological or hydraulic validation. Source-specific copyrights and licences remain applicable.
