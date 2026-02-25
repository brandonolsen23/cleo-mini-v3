# Ontario Municipalities Reference

Generated: 2026-02-25
Source: [AMO - Ontario Municipalities](https://www.amo.on.ca/about-us/municipal-101/ontario-municipalities)

Ontario has 444 municipalities organized into single-tier, upper-tier (regions/counties/districts), and lower-tier structures.

---

## How Ontario Municipal Government Works

- **Single-tier**: One level of municipal government (e.g., Toronto, Hamilton, Ottawa)
- **Upper-tier**: Counties, Regions, or Districts that provide services across multiple lower-tier municipalities
- **Lower-tier**: Cities, towns, townships, villages within an upper-tier municipality
- **Separated**: Cities/towns geographically within a county but governed independently (e.g., London is "separated" from Middlesex County)

For GIS/parcel data, upper-tier municipalities (regions, counties) often host the ArcGIS services that cover all their lower-tier members.

---

## Cleo Property Counts by Municipality

Based on `properties.json` (19,741 properties). Counts are approximate due to city field normalization issues (case variants, abbreviations, typos).

### Your Core Markets (Secondary/Tertiary)

| Municipality | ~Properties | Upper Tier | ArcGIS Status |
|---|---|---|---|
| London | 640 | Middlesex (separated) | READY - `maps.london.ca` |
| Hamilton | 510 | Single-tier | HUB ONLY - need endpoint discovery |
| Brampton | 450 | Peel Region | HUB ONLY - `geohub.brampton.ca` |
| Windsor | 365 | Essex (separated) | HUB ONLY - `opendata.citywindsor.ca` |
| Kitchener | 340 | Waterloo Region | RESTRICTED - 403 on directory |
| Barrie | 283 | Simcoe (separated) | READY - `gispublic.barrie.ca` |
| Kingston | 265 | Frontenac (separated) | HUB ONLY - `maps-cityofkingston.hub.arcgis.com` |
| Cambridge | 189 | Waterloo Region | RESTRICTED - via Waterloo Region |
| Waterloo | 170 | Waterloo Region | RESTRICTED - via Waterloo Region |
| Oshawa | 184 | Durham Region | PARTIAL - `maps.durham.ca` |
| Niagara Falls | 195 | Niagara Region | NEEDS TESTING - `maps.niagararegion.ca` |
| St. Catharines | 225 | Niagara Region | NEEDS TESTING - via Niagara Region |
| Welland | 82 | Niagara Region | NEEDS TESTING - via Niagara Region |
| Brantford | 166 | Single-tier | READY - `maps.brant.ca` |
| Peterborough | 157 | Peterborough (separated) | HUB ONLY - `data-ptbo.opendata.arcgis.com` |
| Guelph | 207 | Wellington (separated) | UNKNOWN - needs research |
| Greater Sudbury | 147 | Single-tier | HUB ONLY - `opendata.greatersudbury.ca` |
| Orillia | 93 | Simcoe (separated) | UNKNOWN - check Simcoe County |
| Belleville | 85 | Hastings (separated) | UNKNOWN - needs research |
| Woodstock | 79 | Oxford County | READY - `public.oxfordcounty.ca` |
| Orangeville | 75 | Dufferin County | RESTRICTED - 403 on directory |
| Cornwall | 68 | SDG (separated) | HUB ONLY - `data-cornwallcity.opendata.arcgis.com` |
| Collingwood | 70 | Simcoe County | UNKNOWN - needs research |
| Sarnia | 106 | Lambton County | UNKNOWN - needs research |
| Stratford | 76 | Perth (separated) | UNKNOWN - needs research |
| Owen Sound | ~40 | Grey County | READY - `gis.grey.ca` |
| St. Thomas | ~30 | Elgin (separated) | READY - `gisdata.elginmapping.ca` |
| North Bay | ~25 | Nipissing District | HUB ONLY - `data-northbaygis.hub.arcgis.com` |
| Kingsville | ~15 | Essex County | PARTIAL - `gisservices.countyofessex.ca` |

### GTA (Lower Priority for You)

| Municipality | ~Properties | Upper Tier |
|---|---|---|
| Toronto (all old boroughs) | 4,514 | Single-tier |
| Mississauga | 688 | Peel Region |
| Markham | 263 | York Region |
| Vaughan | 220 | York Region |
| Oakville | 314 | Halton Region |
| Burlington | 231 | Halton Region |
| Richmond Hill | 177 | York Region |
| Whitby | 143 | Durham Region |
| Milton | 118 | Halton Region |
| Newmarket | 110 | York Region |
| Ajax | 95 | Durham Region |
| Aurora | 73 | York Region |
| Pickering | 77 | Durham Region |

### Ottawa Region (Lower Priority)

| Municipality | ~Properties |
|---|---|
| Ottawa + Nepean + Gloucester + Kanata | ~1,123 |

---

## ArcGIS Service Registry

### Tier 1: Production-Ready REST Endpoints (Verified Parcels + Zoning)

#### London (Middlesex County)
- **REST:** `https://maps.london.ca/arcgisa/rest/services/`
- **Parcels:** `https://maps.london.ca/arcgisa/rest/services/Parcels/MapServer` (Layer 1)
- **Zoning:** `https://maps.london.ca/arcgisa/rest/services/Zoning/MapServer` (Layer 0)
- **Also:** Zoning_Public, Buildings, Addresses, PlanningDistricts, LondonPlan
- **Server:** ArcGIS v11.3, no auth
- **Coverage:** ~640 properties

#### Barrie (Simcoe County)
- **REST:** `https://gispublic.barrie.ca/arcgis/rest/services/`
- **Parcels:** `.../Public/OperationalLayers_Dynamic/MapServer` (Layer 2: Assessment Parcels)
- **Zoning:** Same service (Layer 55: Zoning By-Law, Layer 120: Official Plan Land Use)
- **Also:** 138 total layers, Heritage Properties, Rezoning Applications
- **Server:** ArcGIS v10.91, no auth
- **Coverage:** ~283 properties

#### Brantford / Brant County
- **REST:** `https://maps.brant.ca/arcgis/rest/services/`
- **Parcels:** `.../PublicData/Zoning/MapServer` (Layer 2: Assessment Parcel)
- **Zoning:** Same service (Layer 1: Active Zoning)
- **Also:** OfficialPlan, DevelopmentApplications
- **Server:** ArcGIS v11.5, no auth, max 2000 records/query
- **Coverage:** ~166 properties

#### Oxford County (Woodstock, Ingersoll, Tillsonburg)
- **REST:** `https://public.oxfordcounty.ca/gis/rest/services/`
- **Parcels:** `.../GIS/Parcels/MapServer` (Layer 0: Parcel Lines, Layer 1: Parcel)
- **Zoning:** `.../CommunityPlanning/Zoning/MapServer` (Layers 2/3/4)
- **Also:** Official_Plan, Development_Constraints
- **Server:** ArcGIS v11.4, no auth
- **Coverage:** ~79 properties

#### Grey County (Owen Sound, Blue Mountains, Hanover, Meaford)
- **REST:** `https://gis.grey.ca/server/rest/services/`
- **Parcels:** `.../Public/Service_ParcelLabels/MapServer`
- **Zoning:** `.../Public/Service_GreyCountyZoning/MapServer` (12+ layers, per-municipality)
- **Also:** FeatureServers per municipality, Official Plan, Active Planning Applications
- **Server:** ArcGIS v11.5, no auth
- **Coverage:** ~40+ properties

#### Elgin County (St. Thomas, Aylmer, Bayham)
- **REST:** `https://gisdata.elginmapping.ca/arcgis/rest/services/`
- **Parcels:** `.../Elgin_parcels_2021/MapServer` (Layer 0)
- **Zoning:** `.../EEMS_Planning/MapServer` (per-municipality zoning layers)
- **Also:** EEMS_Property_Layers, EEMS_BNDRY
- **Server:** ArcGIS v10.41, no auth
- **Coverage:** ~30 properties

### Tier 2: ArcGIS Hub (Data Available, Need FeatureServer URL Extraction)

| Municipality | Hub URL | Parcels | Zoning | ~Properties |
|---|---|---|---|---|
| Hamilton | `data-spatialsolutions.opendata.arcgis.com` | Via interactive map | YES | 510 |
| Windsor | `opendata.citywindsor.ca` | YES (incl. zoning field) | YES | 365 |
| Kingston | `maps-cityofkingston.hub.arcgis.com` | Likely (150+ layers) | YES | 265 |
| Brampton | `geohub.brampton.ca` | YES | YES | 450 |
| Peterborough | `data-ptbo.opendata.arcgis.com` | YES | YES | 157 |
| Sudbury | `opendata.greatersudbury.ca` | YES (incl. zoning) | YES | 147 |
| Cornwall | `data-cornwallcity.opendata.arcgis.com` | YES | YES | 68 |
| North Bay | `data-northbaygis.hub.arcgis.com` | YES | YES | ~25 |

For ArcGIS Hub datasets, the underlying FeatureServer URL follows:
`https://services*.arcgis.com/[org-id]/arcgis/rest/services/[service-name]/FeatureServer/[layer-id]`
These can be found by clicking "API" or "I want to use this" on each dataset page.

### Tier 3: Server Exists but Restricted or Needs Investigation

| Municipality | Endpoint | Issue | ~Properties |
|---|---|---|---|
| Waterloo Region | `taps.regionofwaterloo.ca/arcgis/rest/services/` | 403 on directory, MPAC parcels confirmed | 700 |
| Niagara Region | `maps.niagararegion.ca/arcgis/rest/services/` | v10.31, connection issues | 500 |
| Durham Region | `maps.durham.ca/arcgis/rest/services/` | No parcels in public service | 560 |
| Orangeville | `gis.orangeville.ca/arcgis/rest/services/` | 403 on directory | 75 |
| Essex County | `gisservices.countyofessex.ca/arcgis/rest/services/` | Lots only, municipal folders | ~15 |

### Tier 4: Unknown / Not Yet Researched

| Municipality | ~Properties | Upper Tier |
|---|---|---|
| Guelph | 207 | Wellington (separated) |
| Sarnia | 106 | Lambton County |
| Orillia | 93 | Simcoe (separated) |
| Belleville | 85 | Hastings (separated) |
| Stratford | 76 | Perth (separated) |
| Collingwood | 70 | Simcoe County |
| Thunder Bay | 106 | Thunder Bay District |
| Bradford West Gwillimbury | ~50 | Simcoe County |
| Innisfil | ~30 | Simcoe County |
| New Tecumseth (Alliston) | ~40 | Simcoe County |
| Wasaga Beach | ~20 | Simcoe County |
| Cobourg | ~40 | Northumberland County |
| Brighton | ~20 | Northumberland County |

---

## Complete Ontario Municipal Structure

### Single-Tier Municipalities (11)

| Municipality | Type |
|---|---|
| County of Brant | County |
| City of Brantford | City |
| City of Chatham-Kent | City |
| City of Greater Sudbury | City |
| Haldimand County | County |
| City of Hamilton | City |
| City of Kawartha Lakes | City |
| Norfolk County | County |
| City of Ottawa | City |
| Prince Edward County | County |
| City of Toronto | City |

### Regional Municipalities (7 upper-tier)

#### Durham Region
- Oshawa, Pickering, Clarington, Ajax, Whitby, Brock Twp, Scugog Twp, Uxbridge Twp

#### Halton Region
- Burlington, Halton Hills, Milton, Oakville

#### Muskoka District
- Bracebridge, Gravenhurst, Huntsville, Georgian Bay Twp, Lake of Bays Twp, Muskoka Lakes Twp

#### Niagara Region
- Niagara Falls, Port Colborne, St. Catharines, Thorold, Welland, Fort Erie, Grimsby, Lincoln, Niagara-on-the-Lake, Pelham, Wainfleet Twp, West Lincoln Twp

#### Peel Region
- Brampton, Mississauga, Caledon

#### Waterloo Region
- Cambridge, Kitchener, Waterloo, North Dumfries Twp, Wellesley Twp, Wilmot Twp, Woolwich Twp

#### York Region
- Markham, Richmond Hill, Vaughan, Aurora, East Gwillimbury, Georgina, Newmarket, Whitchurch-Stouffville, King Twp

### Counties (23 upper-tier)

#### Bruce County
- Arran Elderslie, Brockton, Kincardine, Northern Bruce Peninsula, South Bruce, Saugeen Shores, South Bruce Peninsula, Huron-Kinloss Twp

#### Dufferin County
- Grand Valley, Mono, Orangeville, Shelburne, Amaranth Twp, East Garafraxa Twp, Melancthon Twp, Mulmur Twp

#### Elgin County
- **St. Thomas (separated)**, Bayham, Central Elgin, Dutton/Dunwich, West Elgin, Aylmer, Malahide Twp, Southwold Twp

#### Essex County
- **Windsor (separated)**, Leamington, Amherstburg, Essex, Kingsville, Lakeshore, LaSalle, Tecumseh, Pelee Twp (separated)

#### Frontenac County
- **Kingston (separated)**, Central Frontenac Twp, Frontenac Islands Twp, North Frontenac Twp, South Frontenac Twp

#### Grey County
- Owen Sound, Blue Mountains, Hanover, Meaford, Chatsworth Twp, Georgian Bluffs Twp, Grey Highlands, Southgate Twp, West Grey

#### Haliburton County
- Algonquin Highlands Twp, Dysart et al, Highlands East, Minden Hills Twp

#### Hastings County
- **Belleville (separated)**, **Quinte West (separated)**, Centre Hastings, Hastings Highlands, Marmora and Lake, Tweed, Bancroft, Deseronto, Carlow/Mayo Twp, Faraday Twp, Limerick Twp, Madoc Twp, Stirling-Rawdon Twp, Tudor & Cashel Twp, Tyendinaga Twp, Wollaston Twp

#### Huron County
- Bluewater, Central Huron, Huron East, Morris-Turnberry, South Huron, Goderich, Ashfield-Colborne-Wawanosh Twp, Howick Twp, North Huron Twp

#### Lambton County
- Sarnia, Lambton Shores, Petrolia, Brooke-Alvinston, Dawn-Euphemia Twp, Enniskillen Twp, Plympton-Wyoming, St. Clair Twp, Warwick Twp, Oil Springs, Point Edward

#### Lanark County
- **Smiths Falls (separated)**, Mississippi Mills, Carleton Place, Perth, Beckwith Twp, Drummond-North Elmsley Twp, Lanark Highlands Twp, Montague Twp, Tay Valley Twp

#### Leeds & Grenville (United Counties)
- **Brockville (separated)**, **Gananoque (separated)**, **Prescott (separated)**, North Grenville, Athens Twp, Augusta Twp, Edwardsburgh/Cardinal Twp, Elizabethtown-Kitley Twp, Leeds & Thousand Islands Twp, Front of Yonge Twp, Rideau Lakes Twp, Merrickville-Wolford, Westport

#### Lennox & Addington County
- Greater Napanee, Addington Highlands Twp, Loyalist Twp, Stone Mills Twp

#### Middlesex County
- **London (separated)**, North Middlesex, Southwest Middlesex, Thames Centre, Adelaide Metcalfe Twp, Lucan Biddulph Twp, Middlesex Centre Twp, Strathroy-Caradoc Twp, Newbury

#### Northumberland County
- Brighton, Cobourg, Port Hope, Trent Hills, Alnwick/Haldimand Twp, Cramahe Twp, Hamilton Twp

#### Oxford County
- Woodstock, Ingersoll, Tillsonburg, Blandford Blenheim Twp, East Zorra-Tavistock Twp, Norwich Twp, South-West Oxford Twp, Zorra Twp

#### Perth County
- **Stratford (separated)**, North Perth, **St. Marys (separated)**, Perth East Twp, Perth South Twp, West Perth

#### Peterborough County
- **Peterborough (separated)**, Asphodel-Norwood Twp, Cavan Monaghan Twp, Douro-Dummer Twp, Havelock-Belmont-Methuen Twp, North Kawartha Twp, Otonabee-South Monaghan Twp, Selwyn Twp, Trent Lakes

#### Prescott & Russell (United Counties)
- Clarence-Rockland, Casselman, The Nation, Hawkesbury, Alfred & Plantagenet Twp, Champlain Twp, East Hawkesbury Twp, Russell Twp

#### Renfrew County
- **Pembroke (separated)**, Arnprior, Deep River, Laurentian Hills, Petawawa, Renfrew, Admaston-Bromley Twp, Bonnechere Valley Twp, Brudenell/Lyndoch/Raglan Twp, Greater Madawaska Twp, Horton Twp, Killaloe/Hagarty/Richards Twp, Laurentian Valley Twp, Madawaska Valley Twp, McNab-Braeside Twp, North Algona-Wilberforce Twp, Whitewater Region Twp, Head/Clara/Maria Twps

#### Simcoe County
- **Barrie (separated)**, **Orillia (separated)**, Bradford West Gwillimbury, Collingwood, Innisfil, Midland, New Tecumseth, Penetanguishene, Wasaga Beach, Adjala-Tosorontio Twp, Clearview Twp, Essa Twp, Oro-Medonte Twp, Ramara Twp, Severn Twp, Springwater Twp, Tay Twp, Tiny Twp

#### Stormont, Dundas & Glengarry (United Counties)
- **Cornwall (separated)**, South Dundas, North Dundas Twp, North Glengarry Twp, North Stormont Twp, South Glengarry Twp, South Stormont Twp

#### Wellington County
- **Guelph (separated)**, Erin, Minto, Centre Wellington Twp, Guelph-Eramosa Twp, Mapleton Twp, Puslinch Twp, Wellington North Twp

### Districts (10 -- Northern Ontario)

#### Algoma District
- Elliot Lake, Sault Ste Marie, Huron Shores, Blind River, Bruce Mines, Thessalon, + 16 townships

#### Cochrane District
- Timmins, Cochrane, Hearst, Iroquois Falls, Kapuskasing, Moosonee, Smooth Rock Falls, + 6 townships

#### Kenora District
- Dryden, Kenora, Red Lake, Sioux Lookout, + 5 townships

#### Manitoulin District
- Gore Bay, Northeastern Manitoulin, + 7 townships/municipalities

#### Nipissing District
- North Bay, Temagami, West Nipissing, Mattawa, + 7 townships

#### Parry Sound District
- Callander, Magnetawan, Powassan, Whitestone, Kearney, Parry Sound, + 16 townships/villages

#### Rainy River District
- Fort Frances, Rainy River, + 8 townships

#### Sudbury District (not Greater Sudbury)
- Espanola, French River, Killarney, Markstay-Warren, St. Charles, + 4 townships

#### Timiskaming District
- Temiskaming Shores, Kirkland Lake, Cobalt, Englehart, Latchford, + 18 townships

#### Thunder Bay District
- Thunder Bay, Greenstone, Neebing, Oliver Paipoonge, Marathon, + 10 townships

---

## Coverage Strategy for Parcel Data

### Phase 1: Tier 1 ArcGIS endpoints (~1,200 properties)
London, Barrie, Brantford, Oxford County, Grey County, Elgin County.
These are ready to query today with spatial point-in-polygon lookups.

### Phase 2: ArcGIS Hub endpoint discovery (~1,900 properties)
Hamilton, Windsor, Kingston, Brampton, Peterborough, Sudbury, Cornwall, North Bay.
Need to extract underlying FeatureServer URLs from Hub dataset API tabs.

### Phase 3: Restricted/investigation (~1,300 properties)
Waterloo Region (Kitchener/Cambridge/Waterloo), Niagara Region, Durham Region, Orangeville.
May need to try individual layer URLs even if directory is blocked, or find alternative access.

### Phase 4: Research remaining markets (~800 properties)
Guelph, Sarnia, Orillia, Belleville, Stratford, Collingwood, Simcoe County towns, Northumberland County.

### Regrid API as fallback
For municipalities without public ArcGIS services, [Regrid](https://regrid.com/canada) provides Ontario-wide parcel data. Free tier: 25 lookups/day. Paid API for bulk. Schema includes parcel boundary polygon, address, parcel ID.

---

## City Name Normalization Issues (from properties.json)

The following inconsistencies exist in the `city` field and should be addressed:

### Case variants
- "Ajax" (93) vs "AJAX" (2)
- "Barrie" (279) vs "BARRIE" (4)
- "Toronto" (2865) vs "TORONTO" (31)
- (pattern repeats for most cities)

### Abbreviation variants
- "N. York" (456) vs "North York" (51) vs "NORTH YORK" (25)
- "N. Bay" vs "North Bay"
- "E. York" vs "East York"
- "St. Catharines" (170) vs "St Catharines" (52) vs "ST CATHARINES" (5)

### Compound city names (old borough + city)
- "Toronto-Etobicoke" (12), "Toronto-North York" (17), "Ottawa-Nepean" (5)

### Garbage in city field
- Full addresses: "100 Queens Quay East", "114 Ellesmere Rd Scarborough"
- Unit numbers: "Unit 1", "Unit 2", "Unit 501"
- Province: "Ontario", "ON L6E0E5"

### Typos
- "Orilla" (should be Orillia)
- "Glouester" (Gloucester)
- "oronto" (Toronto)
- "Hunstville" (Huntsville)

### Merged municipalities
- "Stoney Creek" (70) is now part of Hamilton
- "Sudbury" (66) vs "Greater Sudbury" (81) -- same municipality
- "Nepean" (136), "Gloucester" (119), "Kanata" (70) -- all now Ottawa
- "Scarborough" (554), "N. York" (456), "Etobicoke" (385), "York" (168), "E. York" (86) -- all now Toronto
