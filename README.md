# OSM Map Matcher
OSM Map Matcher matches GPS coordinates to existing OSM highways. Currently it returns solely the id of the matched highways.

## Requires
* python-gdal

## Data Preperation
1. Import GPS track
```
ogr2ogr -f "PostgreSQL" PG:"host=localhost user=ustroetz dbname=test" sample.geojson
```
![alt tag](images/gps.jpg)


2. Buffer GPS track
```
CREATE TABLE bufferGPS AS SELECT ogc_fid, ST_Transform(ST_Buffer(wkb_geometry,10),4326) FROM ogrgeojson
```
![alt tag](images/buffer.jpg)

3. Intersect GPS buffer with roads
```
CREATE TABLE OSMextract AS
SELECT
    a.id,
    b.geom_way
FROM
    osm_2po_4pgr as a,
    bufferGPS as b
WHERE
    ST_Intersects(a.geom_way,b.st_transform);
```
![alt tag](images/istanbulExtract.jpg)

## Run script
```
python OSMmapMatcher.py
```
Matching Results currently only list with OSM segment IDs
![alt tag](images/match.jpg)

## Improvements
* Add OSM database import to docs
* Return final match layer instead of ID list
* Exclude parts of intersections
![alt tag](images/improvements.jpg)


## Background
Marchal,F., Hackney, J. and K.W. Axhausen (2005) "Efficient map-matching of large GPS data sets - Tests on a speed monitoring experiment in Zurich". Presented at TRB annual meeting, Washington D.C., Jan. 2005, to appear in Transportation Research Record.
http://www.strc.ch/conferences/2005/Marchal.pdf
