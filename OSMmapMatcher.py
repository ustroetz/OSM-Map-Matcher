import ogr

def main():

    osmTable = "extractistanbul"
    gpsTable = "ogrgeojson"

    databaseName = "test"
    databaseUser = "ustroetz"
    databasePW = ""
    connString = "PG: dbname=%s user=%s password=%s" %(databaseName,databaseUser,databasePW)


    conn = ogr.Open(connString)

    g = conn.GetLayer(osmTable)
    qLayer = conn.GetLayer(gpsTable)
    qFeature = qLayer.GetNextFeature()
    qGeom = qFeature.GetGeometryRef()
    qCount = qGeom.GetPointCount()
    print "Total GPS to match:", qCount

    distDict = {}
    s = []

    # Find first matching segment e for q1
    q1Coords = qGeom.GetPoint(0)
    q1 = ogr.Geometry(ogr.wkbPoint)
    q1.AddPoint(q1Coords[0], q1Coords[1])

    for e in g:
        geom = e.GetGeometryRef()
        id = e.GetField("id")
        distDict[id] = geom.Distance(q1)

    id = min(distDict, key=distDict.get)
    s.append(id)
    print "First matching segment id =", id

    # Loop over remaing segments e for all qn
    distDict = {}

    for count in range(qCount):    # loop over gps points

        #get last selected line
        g.SetAttributeFilter("id = %s" %id)
        feat = g.GetNextFeature()
        currentLine = feat.GetGeometryRef()

        g.SetAttributeFilter(None)
        g.ResetReading()
        for e in g:
            geom = e.GetGeometryRef()
            if geom.Intersect(currentLine):         # Select only adjacent features
                q2Coords = qGeom.GetPoint(count)
                q2 = ogr.Geometry(ogr.wkbPoint)
                q2.AddPoint_2D(q2Coords[0],q2Coords[1])

                id = e.GetField("id")
                distDict[id] = geom.Distance(q2)

        id = min(distDict, key=distDict.get)
        if id not in s:
            s.append(id)

        count += 1

    print s



if __name__ == '__main__':
    main()
