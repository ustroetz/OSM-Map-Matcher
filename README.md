# OSM Map Matcher
OSM Map Matcher matches GPS coordinates to existing OSM highways. Currently it returns solely the id of the matched highways.

## Requires
* python-gdal
* psycopg2
* PostgreSQL with PostGIS and pgRouting

## Data Preperation
### OSM Data Preperation
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
ogr2ogr -f "PostgreSQL" PG:"host=localhost user=postgres dbname=omm" -nln ways_extract_split temp.shp
```

### GPS Data Preperation
##### 1. Import GPS track
```
ogr2ogr -f "PostgreSQL" PG:"host=localhost user=postgres dbname=omm" sample.gpx track_vertex tracks
```

##### 2. Buffer GPS track
```
CREATE TABLE tracks_buffer AS SELECT ogc_fid, ST_Transform(ST_Buffer(wkb_geometry,0.0005),4326) FROM tracks
```

##### 3. Intersect GPS buffer with roads
```
CREATE TABLE ways_extract AS
SELECT
    a.id,
    a.geom_way,
    a.x1,
    a.y1,
    a.x2,
    a.y2,
    a.reverse_cost
FROM
    osm_2po_4pgr as a,
    tracks_buffer as b
WHERE
    ST_Intersects(a.geom_way,b.st_transform);
```


## Run script
```
python OSMmapMatcher.py
```
![alt tag](images/match.jpg)

## Improvements
* Add KML reader based on http://www.gpsvisualizer.com/convert?output
* Return final match layer instead of ID list


## Background
* first OSM segment is found by closest distance
* all further features need to connect to previously selected feature
* feature is selected based on weighted distance (1.0) and bearing (0.1).
