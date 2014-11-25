import ogr

def main():

    gpsPoints = [(28.97533,41.02221),(28.97599,41.02204),(28.97739,41.02281),(28.97787,41.02283)]
    tableName = "extractistanbul"
    databaseName = "test"
    databaseUser = "ustroetz"
    databasePW = ""
    connString = "PG: dbname=%s user=%s password=%s" %(databaseName,databaseUser,databasePW)

    conn = ogr.Open(connString)
    g = conn.GetLayer(tableName)

    # Get first segment
    distDict = {}
    gpsPoint = ogr.Geometry(ogr.wkbPoint)
    gpsPoint.AddPoint_2D(gpsPoints[0][0],gpsPoints[0][1])
    
    for e in g:
        geom = e.GetGeometryRef()
        id = e.GetField("id")
        distDict[id] = geom.Distance(gpsPoint)

    id = min(distDict, key=distDict.get)
    print id

    # Next point
    iterPoints = iter(gpsPoints)
    next(iterPoints)
    for point in iterPoints:
        distDict = {}
        g.SetAttributeFilter("id = %s" %id)
        feat = g.GetNextFeature()
        currentLine = feat.GetGeometryRef()
        g.SetAttributeFilter(None)
        g.ResetReading()
        for e in g:
            geom = e.GetGeometryRef()
            if geom.Intersect(currentLine):         # Select only adjacent features
                gpsPoint2 = ogr.Geometry(ogr.wkbPoint)
                gpsPoint2.AddPoint_2D(point[0],point[1])

                id = e.GetField("id")
                distDict[id] = geom.Distance(gpsPoint2)

        id = min(distDict, key=distDict.get)
        print id




if __name__ == '__main__':
    main()



                                                                            ;
# import GPS track
ogr2ogr -f "PostgreSQL" PG:"host=localhost user=ustroetz dbname=test" sample.geojson

# buffer GPS track
CREATE TABLE bufferGPS AS SELECT ogc_fid, ST_Transform(ST_Buffer(wkb_geometry,10),4326) FROM ogrgeojson

# intersect GPS buffer with roads
CREATE TABLE extractISTANBUL AS
SELECT
    a.id,
    b.geom_way
FROM
    osm_2po_4pgr as a,
    bufferGPS as b
WHERE
    ST_Intersects(a.geom_way,b.st_transform);
