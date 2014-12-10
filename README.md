# OSM Map Matcher
OSM Map Matcher matches GPS coordinates to existing OSM highways. Currently it returns solely the id of the matched highways.

## Requires
* python-gdal
* psycopg2
* PostgreSQL with PostGIS and pgRouting

## OSM Data Preperation
##### 1. Download OSM Metro Extracts
```
wget https://s3.amazonaws.com/metro-extracts.mapzen.com/istanbul_turkey.osm.pbf
```
##### 2. Import OSM data into DB
Modify osm2po config file as described [here](http://gis.stackexchange.com/questions/41276/how-to-include-highways-type-track-or-service-in-osm2po).
```
java -jar osm2po-core-4.9.1-signed.jar istanbul_turkey.osm.pbf
psql -d test -q -f osm/osm_2po_4pgr.sql
psql -d test -q -f osm/osm_2po_vertex.sql
```
##### 3. Apply Explode lines in QGIS
##### 4. Reload into PostGIS
```
ogr2ogr -f "PostgreSQL" PG:"host=localhost user=postgres dbname=omm" -nln ways_split temp.shp
```


## Run script
```
python OSMmapMatcher.py
```


## Background
* first OSM segment is found by closest distance
* all further features need to connect to previously selected feature
* feature is selected based on weighted distance and bearing
