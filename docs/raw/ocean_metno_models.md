Close search

Search

# Ocean and Sea Ice modeling systems

An overview of ocean and sea ice models at MET Norway is given below. The operational archive of the model is freely available on [THREDDS](https://thredds.met.no/thredds/catalog/fou-hi/fou-hi.html).

## Operational models

### Barents Sea

**Barents-2.5** is a coupled ocean and sea ice ensemble prediction model. It is MET Norway’s main forecasting model for ocean currents and sea ice in the Barents Sea and around Svalbard. Previous analysis as well as the latest forecast are available on [THREDDS](https://thredds.met.no/thredds/catalog/fou-hi/barents_eps.html). The model is based on the METROMS ( [GitHub](https://github.com/metno/metroms)) framework which implements the coupling between the ocean component (ROMS) and the sea ice component (CICE).

![barents](https://ocean.met.no/sites/ocean.met.no/files/inline-images/image_barents.png)

The model employs a regular grid in the horizontal with 2.5km resolution, and an irregular topography-following vertical coordinate system for the ocean consisting of 42 layers, while the ice is modeled in 5 thickness categories, each with 7 vertical layers and a single snow layer on top. The ocean and sea ice is forced by atmospheric fields from MET Norway’s 2.5km AROME-Arctic model that is setup on the same grid. Additional ensemble members use atmospheric forcing fields from ECMWF’s IFS-ENS forecasts providing perturbed atmospheric forcing. Boundary conditions come from TOPAZ, tides from TPXO tidal model, river runoff climatology from NVE data (mainland Norway) and AHYPE hydrological model (Svalbard+Russia) and the bottom topography is taken from the IBCAO v3 dataset. Daily model analysis is performed using an Ensemble Kalman Filter that assimilates sea ice concentration from passive microwave imagery (https://cryo.met.no/en/sirano), IR sea surface temperature, and in-situ hydrography. The model uncertainty is estimated from 24 ensemble members, of which 6 members are updated with new atmospheric forcing every 6 hours.

Daily updated validation results are available here:

- [Sea ice concentration (SIC)](https://ocean.met.no/sea-ice-concentration)
- [Sea surface temperature (SST)](https://ocean.met.no/sea-surface-temperature)
- [Temperature/Salinity profiles (Floats)](https://ocean.met.no/floats)

**Reference:**

Röhrs, J., Gusdal, Y., Rikardsen, E. S. U., Durán Moro, M., Brændshøi, J., Kristensen, N. M., Fritzner, S., Wang, K., Sperrevik, A. K., Idžanović, M., Lavergne, T., Debernard, J. B., and Christensen, K. H, 2023. Barents-2.5km v2.0: an operational data-assimilative coupled ocean and sea ice ensemble prediction model for the Barents Sea and Svalbard. Geosci. Model Dev., 16, 5401–5426. [https://doi.org/10.5194/gmd-16-5401-2023](https://doi.org/10.5194/gmd-16-5401-2023)

Duarte, P., Brændshøi, J., Shcherbin, D., Barras, P., Albretsen, J., Gusdal, Y., Szapiro, N., Martinsen, A., Samuelsen, A., Wang, K., Debernard, J.B, 2022. Implementation and evaluation of open boundary conditions for sea ice in a regional coupled ocean (ROMS) and sea ice (CICE) modeling system. Geosci. Model Dev., 15, 4373–4392. [https://doi.org/10.5194/gmd-15-4373-2022](https://doi.org/10.5194/gmd-15-4373-2022)

Fritzner, S.M., Graversen, R.G., Wang, K., Christensen, K.H., 2018. Comparison between a multi-variate nudging method and the ensemble Kalman filter for sea-ice data assimilation. Journal of Glaciology 64, 387–396. [https://doi.org/10.1017/jog.2018.33](https://doi.org/10.1017/jog.2018.33)

Fritzner, S.M., Graversen, R., Christensen, K.H., Rostosky, P., Wang, K., 2019. Impact of assimilating sea ice concentration, sea ice thickness and snow depth in a coupled ocean-sea ice modelling system. Ocean Sci. 13, 491–509. [https://doi.org/10.5194/tc-13-491-2019](https://doi.org/10.5194/tc-13-491-2019)

### Norwegian Coast

The **Norkyst** system is the primary tool for ocean forecasting along the Norwegian coast. It supports a wide range of applications, including forecasting sea surface temperatures and ocean currents for oil spill preparedness modeling, Search-and-Rescue preparedness and plankton dispersion modeling. All analysis runs are made available through the [THREDDS data server](https://thredds.met.no/thredds/catalog/fou-hi/norkystv3.html).

![norkyst](https://ocean.met.no/sites/ocean.met.no/files/inline-images/image10_0.png)

The Norkyst model is a collaboration project between the Institute of Marine Research (IMR) and the Norwegian Meteorological Institute. It is built upon the Regional Ocean Modeling System (ROMS), with a sub-kilometric horizontal resolution of 800m. This resolution is specifically designed to capture mesoscale oceanic features. The model incorporates 40 vertical layers, with enhanced resolution near the surface to improve the accuracy of near-surface flow predictions, which are critical for operational services. While the Norwegian coastline features numerous fjords and islands, Norkyst resolves the dominant coastal features, including all major fjords. However, the smallest islands and bays are generally excluded. Although some Norwegian fjords experience partial sea ice coverage during winter, the model does not include a sea ice component.

Key forcings and boundary conditions for the system:

- Atmospheric forcing: Hourly surface fields from [AROME-MetCoOP](https://journals.ametsoc.org/view/journals/wefo/32/2/waf-d-16-0099_1.xml).
- Tidal forcing: Provided by [TPXO](https://journals.ametsoc.org/view/journals/atot/19/2/1520-0426_2002_019_0183_eimobo_2_0_co_2.xml).
- Lateral boundary conditions: Temperature and salinity inputs from [Topaz](https://os.copernicus.org/articles/13/123/2017/) and the [CMEMS Baltic sea model](https://data.marine.copernicus.eu/product/BALTICSEA_ANALYSISFORECAST_PHY_003_006/description) in the Kattegat area.
- River runoff: Volume fluxes for Norwegian rivers are estimated using daily measurements from the Norwegian Water Resources and Energy Directorate (NVE). Runoff data for Swedish and Danish rivers are also included (source TBD).

**Norkyst-DA** (data assimilation) is a specialized setup of the Norkyst domain, designed for data assimilation. This configuration employs a horizontal resolution of 2.4km with 42 vertical layers, optimized to balance the resolution of ocean dynamics with the limitations of the 4D-variational (4D-Var) data assimilation scheme. To improve forecasting accuracy, the Norkyst model is nudged toward the Norkyst-DA analyses before running the 5-day forecast.

Norkyst-DA assimilates:

- Satellite-derived sea surface temperatures.
- In-situ data from ARGOS drifters.
- CTD sections.
- Ferry boxes.
- Surface currents from HF-radar systems.

**The Norkyst Historical Free Run** is a hindcast simulation covering the period from 2012 to the present, with frequent updates. It has proven the capability of an unconstrained forecasting system to accurately represent the dynamics of the Norwegian coastal ocean. The hindcast is available on [THREDDS](https://thredds.met.no/thredds/catalog/romshindcast/norkyst_v3/catalog.html).

**Norkyst Nested Models:** The system includes two high-resolution, two-way nested models for Oslofjorden and Sulafjorden, which operate at a horizontal resolution of 160m. These nested models are also accessible via [THREDDS](https://thredds.met.no/thredds/catalog/fou-hi/norkystv3.html).

**Reference:**

Albretsen, J., Sperrevik, A.K., Staalstrøm, A., Sandvik, A.D., Vikebø, F., Asplin, L., 2011. NorKyst-800 Rapport nr. 1 : Brukermanual og tekniske beskrivelser. NorKyst-800 Report No. 1 : User Manual and technical descriptions.

Röhrs, J., Christensen, K.H., Vikebø, F.B., Sundby, S., Saetra, O., Broström, G., 2014. Wave-induced transport and vertical mixing of pelagic eggs and larvae. Limnol. Oceanogr. 59(4), 1213–1227. [https://doi.org/10.4319/lo.2014.59.4.1213](https://doi.org/10.4319/lo.2014.59.4.1213)

Idžanović, M., Ophaug, V., Andersen, O.B., 2017. The coastal mean dynamic topography in Norway observed by CryoSat-2 and GOCE. Geophysical Research Letters 44, 5609–5617. [https://doi.org/10.1002/2017GL073777](https://doi.org/10.1002/2017GL073777)

Myksvoll, M.S., Sandvik, A.D., Albretsen, J., Asplin, L., Johnsen, I.A., Karlsen, Ø., Kristensen, N.M., Melsom, A., Skardhamar, J., Ådlandsvik, B., 2018. Evaluation of a national operational salmon lice monitoring system—From physics to fish. PLOS ONE 13, e0201338. [https://doi.org/10.1371/journal.pone.0201338](https://doi.org/10.1371/journal.pone.0201338)

Asplin, L., Albretsen, J., Johnsen, I.A., Sandvik, A.D., 2020. The hydrodynamic foundation for salmon lice dispersion modeling along the Norwegian coast. Ocean Dynamics 70, 1151–1167. [https://doi.org/10.1007/s10236-020-01378-0](https://doi.org/10.1007/s10236-020-01378-0)

Röhrs, J., Sperrevik, A.K., Christensen, K.H., 2018. NorShelf: An ocean reanalysis and data-assimilative forecast model for the Norwegian Shelf Sea (No. ISSN 2387-4201 04/2018), MET Report. Norwegian Meteorological Institute, Oslo, Norway. [https://doi.org/10.5281/zenodo.2384124](https://doi.org/10.5281/zenodo.2384124)

Sperrevik, A.K., Christensen, K.H., Röhrs, J., 2015. Constraining energetic slope currents through assimilation of high-frequency radar observations. Ocean Sci 11, 237–249. [https://doi.org/10.5194/os-11-237-2015](https://doi.org/10.5194/os-11-237-2015)

Sperrevik, A.K., Röhrs, J., Christensen, K.H., 2017. Impact of data assimilation on Eulerian versus Lagrangian estimates of upper ocean transport. J. Geophys. Res. Oceans 122, 5445–5457. [https://doi.org/10.1002/2016JC012640](https://doi.org/10.1002/2016JC012640)

Röhrs, J., Sutherland, G., Jeans, G., Bedington, M., Sperrevik, A.K., Dagestad, K.-F., Gusdal, Y., Mauritzen, C., Dale, A., LaCasce, J.H., 2021. Surface currents in operational oceanography: Key applications, mechanisms, and methods. Journal of Operational Oceanography 0, 1–29. [https://doi.org/10.1080/1755876X.2021.1903221](https://doi.org/10.1080/1755876X.2021.1903221)

### Pan-Arctic

Along with the Nansen Environmental and Remote Sensing Center ( [NERSC](https://www.nersc.no/)) and the Institute of Marine Research (Havforskningsinstituttet - [HI](https://www.hi.no/en)), the Norwegian Meteorological Institute produces forecasts which are disseminated by the pan-European [Copernicus Marine Service](https://marine.copernicus.eu/). The collaboration with NERSC and HI takes place in the Service' Arctic Monitoring and Forecasting Center (Arctic MFC). The [Arctic MFC](https://cmems.met.no/ARC-MFC/index.html) nominal forecast system is the TOPAZ system based on an advanced sequential data assimilation method (the Deterministic Ensemble Kalman Filter, DEnKF; Sakov and Oke, 2009) and the Hybrid Coordinate Ocean Model (HYCOM; Chassignet et a., 2007), coupled to a sea ice model.

![topaz](https://ocean.met.no/sites/ocean.met.no/files/inline-images/topaz_area.png)

**TOPAZ general circulation forecasts**

The operational system uses the HYCOM model and a 100-member Ensemble Kalman Filter (EnKF) assimilation scheme, available from the Copernicus Marine Service's catalog as product: [ARCTIC\_ANALYSISFORECAST\_PHY\_002\_001](https://data.marine.copernicus.eu/product/ARCTIC_ANALYSISFORECAST_PHY_002_001/description) (registration required, access is free of charge). It is run daily to provide 10 days of forecast (from an average of 10 ensemble members) of the 3D physical ocean, including sea ice. In addition, the system provides a 10-day forecast of the ocean biogeochemical variables. Data assimilation is performed weekly to provide 7 days of analysis (ensemble average). Output products are interpolated on a grid of 6 km resolution at the North Pole on a polar stereographic projection.

Data from the following observational products are assimilated:

- Sea Ice Concentration from OSISAF passive microwave data
- Thickness of thin sea ice from SMOS
- Blended Optimum Interpolation SST data
- Temperature and salinity profiles from Argo drifters
- Sea Level from multiple altimeter missions

**TOPAZ forecasts for surface currents and sea level**

A higher horizontal grid resolution version of the TOPAZ system at ~3km forced with astronomical tides is run daily to provide a product consisting of 10-day forecasts of the ocean tides and surface currents for the pan-Arctic region. These forecasts are given at 15 minutes instantaneous profiles and can be accessed from the Copernicus Marine Service's catalog as product: [ARCTIC\_ANALYSISFORECAST\_PHY\_TIDE\_002\_015](https://resources.marine.copernicus.eu/?option=com_csw&view=details&product_id=ARCTIC_ANALYSISFORECAST_PHY_TIDE_002_015), where documentation and information on how to download the product are given.

### Nordic Seas stormsurge

The Stormsurge model is MET Norway’s main forecasting model for sea level and stormsurge. It is based on the ROMS model in barotropic mode (2D), covering the area from Bretagne in France, through the North Sea, around the British Isles, the Norwegian coast, the Barents Sea and parts of the eastern coast of Greenland and the Nordic Sea.

![stormsurge](https://ocean.met.no/sites/ocean.met.no/files/inline-images/nordic4_stormsurge.png)

The model has a horizontal resolution of 4km and is forced by atmospheric forcing from the MEPS 2.5km atmospheric model. Five days Forecasts (120 hours) produced and updated every 6 hour. The Forecasts are postprocessed and nudged towards observations from Norwegian coastal stations.

In addition to this setup, a similar setup is run in ensemble mode (EPS). This produces a 50+1 forecast for +120h twice per day based on the full ECMWF ensemble forecast system. Results are made available through [api.met.no](https://api.met.no/) (https://api.met.no/weatherapi/tidalwater/1.1/documentation) and can also be viewed on [SeHavnivå](https://www.kartverket.no/sehavniva/).

**Reference:**

Kristensen, N.M., Røed, L.P., Sætra, Ø., 2022. A forecasting and warning system of storm surge events along the Norwegian coast. Environmental Fluid Mechanics. [https://doi.org/10.1007/s10652-022-09871-4](https://doi.org/10.1007/s10652-022-09871-4)

## Hindcast

### SVIM (1960 - )

The SVIM archive is distributed on [THREDDS](https://thredds.met.no/thredds/catalog/nansen-legacy-ocean/SVIM/catalog.html). Results are available on a polar stereographic grid projection, with a horizontal resolution of 4 km and a vertical resolution of 32 layers. The simulation originally covered the period 1960-2011, and results have been stored as daily averaged values. The archive has subsequently been updated several times for later years, on a somewhat irregular basis.

![svim](https://ocean.met.no/sites/ocean.met.no/files/inline-images/svimarea.png)

The SVIM archive was originally produced in a [project](https://prosjektbanken.forskningsradet.no/en/project/FORISS/196685) funded by the Norwegian Research Council. The project's primary objective was "To better understand how and why the survival of fish larvae varies spatially and temporally through their first months of life, and to quantify uncertainty in drift trajectories in ocean circulation models". The Centre for Ecological and Evolutionary Synthesis ( [CEES](https://www.mn.uio.no/cees/english/)) was leading the project, while the production of the SVIM archive was performed jointly by project partners at the Institute of Marine Research ( [IMR](https://www.hi.no/hi/en)) and Met Norway. The Regional Ocean Modeling System (ROMS) was used for this purpose.

![HI_logo](https://ocean.met.no/sites/ocean.met.no/files/inline-images/HI_logo.png)![favicon_met](https://ocean.met.no/sites/ocean.met.no/files/inline-images/favicon.png)

The SVIM archive was configured with atmospheric forcing from a [regional reanalysis](https://agupubs.onlinelibrary.wiley.com/doi/10.1029/2010JC006402) which is a high-resolution downscaling of global reanalysis results from the European Centre for Medium-Range Weather Forecasts. Results from the Simple Ocean Data Assimilation (SODA) dataset were used for initial and boundary values. For sea ice, initial and boundary values were taken from a [regional simulation](https://agupubs.onlinelibrary.wiley.com/doi/10.1029/2012JC008177). The sea ice model used is similar to the sea ice implementation in the configuration of SVIM. Tidal forcing was applied based on a global ocean tides model. Freshwater from river discharges was based on monthly climatological runoff values, modified to take inter-annual variability into account.

The results from the original SVIM archive was thoroughly evaluated by Lien et al. (2013). An analysis of results for currents (Melsom and Gusdal, 2015) revealed that the predictive skill for the situation at specific days are poor. Given the scales of a few km that dominate instantaneous distribution of circulation features, and the fact that there is no assimilation of observational data in SVIM, this is not surprising. It should be added that observations at these fine scales are lacking.

We also investigated the distribution of progressive vectors from model results and observations at selected positions. We concluded that the intensity of the Norwegian Atlantic Current in the vicinity of the shelf break is much too strong in the SVIM results. Elsewhere, the ocean circulation statistics given by the model results are fair to good representations of the observed statistical distributions.

Finally, we can add that the present sources for flow across open boundaries don't cover the most recent period. Consequently, monthly climatology for the years 2000-2008 from SODA has been applied after 2008. The corresponding situation for sea ice is that the climatology was computed from 2000-2007 results, and applied for the years after that period. Hence, inter-annual variability and trends are not described, and may give rise to discrepancies in the model results for years after 2007.

**Reference:**

Lien, V.S., Y. Gusdal, J. Albretsen, A. Melsom, F. Vikebø, 2013: Evaluation of a Nordic Seas 4 km numerical ocean model hindcast archive (SVIM), 1960-2011. [Fisken og havet, 7-2013](https://imr.brage.unit.no/imr-xmlui/bitstream/handle/11250/113861/FoH_7-2013.pdf), 82pp.

Melsom, A. and Y. Gusdal, 2015: Evaluation of ocean currents from model simulations. [MET report 14/2015](https://www.met.no/publikasjoner/met-report/met-report-2015/_/attachment/download/7a426159-a457-4f93-a455-d7ada2aff652:bc3b0f0c051bda864105dd35a19ed20ac756986a/MET-report-14-2015.pdf), 30pp.

Lien, V.S., Y. Gusdal, F. Vikebø, 2014: Along-shelf hydrographic anomalies in the Nordic Seas (1960–2011): locally generated or advective signals?. [Ocean Dynamics volume 64](https://link.springer.com/article/10.1007/s10236-014-0736-3), 1047–1059.

**Adress Oslo:**

Meteorological institute's head office:

[Henrik Mohns plass 1](https://goo.gl/maps/VM62SkSX39YfH9DC9)

0371 OSLO

**Adress Oslo:**

R & D department for ocean and ice are located in Forskningsparken:

[Gaustadalléen 21](https://goo.gl/maps/JCr1i8x1EZCRxGdH7)

0349 Oslo

**Adress Bergen:**

R & D department for Oceanography and Marine Meteorology:

[Allégaten 70](https://goo.gl/maps/sSkhe2SZo6M65uCa9)

5007 Bergen

**Phone:**

+47 22 96 30 00

**E-mail:**

ocean<at>met.no