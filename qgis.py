canvas = qgis.utils.iface.mapCanvas()
canvas.mapRenderer().setLabelingEngine(QgsPalLabeling())

def al(id):
    uri = QgsDataSourceURI()
    uri.setConnection("localhost", "5432", "istanbul", "ustroetz", "")
    way_name = "ways_match_" + str(id)
    uri.setDataSource("public", way_name, "wkb_geometry")
    way_layer = QgsVectorLayer(uri.uri(), way_name, "postgres")
    way_layer.loadNamedStyle("/Users/ustroetz/projects/OSM-Map-Matcher/ways_match_style.qml")
    point_name = "track_points_" + str(id)
    uri.setDataSource("public", point_name, "geom")
    point_layer = QgsVectorLayer(uri.uri(), point_name, "postgres")
    point_layer.loadNamedStyle("/Users/ustroetz/projects/OSM-Map-Matcher/track_points_style.qml")
    QgsMapLayerRegistry.instance().addMapLayer(way_layer)
    QgsMapLayerRegistry.instance().addMapLayer(point_layer)







def z(qID):
    qID = qID - 10
    cLayer = iface.mapCanvas().currentLayer()
    expr = QgsExpression( "\"ogc_fid\"=%s" %qID)
    it = cLayer.getFeatures( QgsFeatureRequest( expr ) )
    ids = [i.id() for i in it]
    cLayer.setSelectedFeatures( ids )
    canvas.zoomToSelected()
    canvas.zoomScale(500)
    cLayer.deselect(ids)
