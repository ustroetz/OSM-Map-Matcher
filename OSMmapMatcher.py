import ogr
import sys

def checkGPSBuffer(q2,geom):
    # check if selected OSM segments are withing 50m GPS Buffer

    q2Buffer= q2.Buffer(0.02)
    if q2Buffer.Intersect(geom):
        return True
    else:
        print "OSM segment not in GPS buffer"
        sys.exit()
        return False



def main():

    osmTable = "OSMextract"
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
        idSelected = e.GetField("id")
        distDict[idSelected] = geom.Distance(q1)

    idSelected = min(distDict, key=distDict.get)
    s.append(idSelected)
    print "First matching segment id =", idSelected

    # Loop over remaing segments e for all qn
    for count in range(qCount):
        distDict = {}

        #get selected line
        g.SetAttributeFilter("id = %s" %idSelected)
        feat = g.GetNextFeature()
        selectedLine = feat.GetGeometryRef()

        # clear filter and reset reading
        g.SetAttributeFilter(None)
        g.ResetReading()

        #loop through all segments in graph
        for e in g:
            geom = e.GetGeometryRef()

            if geom.Intersect(selectedLine):         # Select only adjacent features

                idSelected = e.GetField("id")

                # construct current GPS point
                q2Coords = qGeom.GetPoint(count)
                q2 = ogr.Geometry(ogr.wkbPoint)
                q2.AddPoint_2D(q2Coords[0],q2Coords[1])

                # get distance between current GPS poitn and current osm segment
                distDict[idSelected] = geom.Distance(q2)


        idSelected = min(distDict, key=distDict.get)
        print "selectedLine ID", idSelected
        if idSelected not in s:
            s.append(idSelected)

        count += 1
    print s



if __name__ == '__main__':
    main()
