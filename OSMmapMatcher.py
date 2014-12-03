import ogr, osr
import sys
import math

def bearing(origin, destination):
    lon1, lat1, z = origin
    lon2, lat2, z = destination

    rlat1 = math.radians(lat1)
    rlat2 = math.radians(lat2)
    rlon1 = math.radians(lon1)
    rlon2 = math.radians(lon2)
    dlon = math.radians(lon2-lon1)

    b = math.atan2(math.sin(dlon)*math.cos(rlat2),math.cos(rlat1)*math.sin(rlat2)-math.sin(rlat1)*math.cos(rlat2)*math.cos(dlon)) # bearing calc
    bd = math.degrees(b)
    br,bn = divmod(bd+360,360) # the bearing remainder and final bearing

    return bn

def main():

    osmTable = "osmextractsplit"
    gpsTable = "ogrgeojson"

    databaseName = "test"
    databaseUser = "ustroetz"
    databasePW = ""
    connString = "PG: dbname=%s user=%s password=%s" %(databaseName,databaseUser,databasePW)

    source = osr.SpatialReference()
    source.ImportFromEPSG(4326)
    target = osr.SpatialReference()
    target.ImportFromEPSG(3857)
    transform3857 = osr.CoordinateTransformation(source, target)
    transform4326 = osr.CoordinateTransformation(target, source)


    conn = ogr.Open(connString)

    oLayer = conn.GetLayer(osmTable)
    qLayer = conn.GetLayer(gpsTable)
    qFeatureCount = qLayer.GetFeatureCount()

    print "Total GPS points to match:", qFeatureCount

    oDict = {}
    rList = []


    # Find first matching OSM segment o1 for q1
    qFeature = qLayer.GetFeature(1)
    q1Geom = qFeature.GetGeometryRef()
    for oFeature in oLayer:
        oGeom = oFeature.GetGeometryRef()
        oIDcurrent = oFeature.GetField("id")
        oDict[oIDcurrent] = oGeom.Distance(q1Geom)

    oIDselected = min(oDict, key=oDict.get)
    rList.append(oIDselected)
    print "##########################"
    print "First matching OSM segment ID =", oIDselected


    for count in range(1,qFeatureCount):
        # Loop over remaing OSM segments for all qn

        print "##################################################"
        print "Point ID", count, "of", qFeatureCount
        oDict = {}

        # construct current GPS point
        qFeature = qLayer.GetFeature(count)
        qGeom = qFeature.GetGeometryRef()

        # get selected line
        oLayer.SetAttributeFilter("id = %s" %oIDselected)
        oSFeature = oLayer.GetNextFeature()
        oSGeom = oSFeature.GetGeometryRef()
        oSGeomPointCount = oSGeom.GetPointCount()
        oSPointF = oSGeom.GetPoint(0)
        oSPointP = oSGeom.GetPoint(oSGeomPointCount-1)

        # clear filter and reset reading
        oLayer.SetAttributeFilter(None)
        oLayer.ResetReading()

        #loop through all segments in OSM layer
        for oFeature in oLayer:

            oGeom = oFeature.GetGeometryRef()
            oIDcurrent = oFeature.GetField("id")

            # check if first or last point intersects with last selected line
            oGeomPointCount = oGeom.GetPointCount()
            oPointD = oGeom.GetPoint(0)
            oPointO = oGeom.GetPoint(oGeomPointCount-1)
            if oPointO == oSPointF or oPointO == oSPointP or oPointD == oSPointF or oPointD == oSPointP:

                # get bearing weight
                if oFeature.GetField("reverse_co"):
                    oPointO = (oFeature.GetField("x1"), oFeature.GetField("y1"), 0.0)
                    oPointD = (oFeature.GetField("x2"), oFeature.GetField("y2"), 0.0)
                oB = bearing(oPointO, oPointD)
                qB = qFeature.GetField("course")
                dob = abs(oB - float(qB))
                wB = 1.0-float(qB)*dob/100.0/100.0
                if wB < 0:
                    wB = 0.0

                # get distance weight
                oGeom.Transform(transform3857)
                qGeom.Transform(transform3857)
                d = oGeom.Distance(qGeom)
                qGeom.Transform(transform4326)

                if d >= 50.0:                 # normalize distance weight
                    wD = 0
                elif d < 50.0 and d > 0.0:
                    wD = 1-d/50.0
                elif d == 0.00:
                    wD = 1.0

                # final weight
                w = (wD+(wB/10.0))/2.0

                print oIDcurrent, "connects to", oIDselected, "with weight", w, "(B",wB,"D",wD,")"


                oDict[oIDcurrent] = w

        oIDselected = max(oDict, key=oDict.get)
        if oDict[oIDselected] == 0: sys.exit("Error weight is 0") 

        print "selectedLine ID", oIDselected
        if oIDselected not in rList:
            rList.append(oIDselected)

        count += 1

        # if count > 1237:
        #     quit()





    print rList



if __name__ == '__main__':
    main()
