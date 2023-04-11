from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QAction, QMessageBox, QWidget, QProgressBar
from qgis.PyQt.QtCore import QVariant, Qt

from qgis.core import (
    Qgis,  # type: ignore
    QgsProject,  # type: ignore
    QgsError,  # type: ignore
    QgsCoordinateReferenceSystem,  # type: ignore
    QgsFeature,  # type: ignore
    QgsDistanceArea,  # type: ignore
    QgsGeometry,  # type: ignore
    QgsPointXY,  # type: ignore
    QgsMemoryProviderUtils,  # type: ignore
    QgsField,  # type: ignore
    QgsFields,  # type: ignore
    QgsProcessingFeedback, # type: ignore
)
from qgis.gui import QgsErrorDialog, QgsProjectionSelectionDialog  # type: ignore

import processing  # type: ignore


class GpuDataChecker:
    def __init__(self, iface):
        self.iface = iface

    def initGui(self):
        # create reprojection action
        self.reprojectAction = self.createAction(
            "Reprojeter couche",
            "reprojection",
            "Reprojete la couche de données en WGS84",
        )
        self.reprojectAction.triggered.connect(self.reprojectLayer)

        # create validity check action
        self.checkValidityAction = self.createAction(
            "Vérifie la validité des géométries de la couche", "checkvalidity"
        )
        self.checkValidityAction.triggered.connect(self.checkGpuValidity)

    def createAction(self, description, objectName, whatsThis=""):
        action = QAction(
            QIcon(":/plugins/gpudatachecker/img/gpu_icon.png"),
            description,
            self.iface.mainWindow(),
        )
        action.setObjectName(objectName)
        action.setWhatsThis(whatsThis if whatsThis else description)
        self.iface.addPluginToMenu("&Contrôles GPU", action)
        return action

    def unload(self):
        # remove plugin menu item
        self.iface.removePluginMenu("&Contrôles GPU", self.reprojectAction)
        self.iface.removePluginMenu("&Contrôles GPU", self.checkValidityAction)

    def reprojectLayer(self):
        currentLayer = self.iface.mapCanvas().currentLayer()
        if not currentLayer:
            self.showError(
                "Sélectionner une couche",
                "Aucune couche active. Sélectionner une couche.",
            )
            return
        layerResultName = currentLayer.name() + "_4326"
        try:
            feedback = QgsProcessingFeedback()
            feedback.pushInfo(str(currentLayer.crs().toWkt()))
            crs = currentLayer.crs() if QMessageBox.question(
                None,
                "Projection de la couche",
                "La projection définie pour cette couche est "+currentLayer.crs().authid()+". Confirmer ?",
                QMessageBox.Yes | QMessageBox.No
            ) == QMessageBox.Yes else None
            if not crs:
                dialog = QgsProjectionSelectionDialog()
                dialog.exec_()
                crs = dialog.crs()
                currentLayer.setCrs(crs)
            result = processing.run(
                "native:reprojectlayer",
                {
                    "INPUT": currentLayer,
                    "TARGET_CRS": "EPSG:4326",
                    "OUTPUT": "memory:" + layerResultName,
                },
            )
            QgsProject.instance().addMapLayer(result["OUTPUT"])
        except ValueError:
            print(ValueError)

    def checkGpuValidity(self):
        # Retrieve active layer
        currentLayer = self.iface.mapCanvas().currentLayer()
        if not currentLayer:
            self.showError(
                "Sélectionner une couche",
                "Aucune couche active. Sélectionner une couche.",
            )
            return

        # Check layer CRS
        if currentLayer.sourceCrs() != QgsCoordinateReferenceSystem("EPSG:4326"):
            self.showError(
                "Projection non conforme",
                "La projection de la couche doit être en WGS84, actuellement en {}. "
                "Reprojeter la couche au préalable.".format(
                    currentLayer.sourceCrs().description()
                ),
            )
            return

        # Get layer type (zonage/secteur or not)
        zonageOrSecteur = True if QMessageBox.question(
                None,
                "Type de couche",
                "La couche à tester est-elle un zonage ou un secteur ?",
                QMessageBox.Yes | QMessageBox.No
            ) == QMessageBox.Yes else False

        # Create result layer
        errorTableFields = QgsFields()
        errorTableFields.append(QgsField("fid", QVariant.Int))
        errorTableFields.append(QgsField("level", QVariant.String))
        errorTableFields.append(QgsField("type", QVariant.String))
        errorTableFields.append(QgsField("message", QVariant.String))
        crs = QgsCoordinateReferenceSystem("EPSG:4326")
        self.errorLayer = QgsMemoryProviderUtils.createMemoryLayer(
            currentLayer.name() + "_error",
            errorTableFields,
            1,  # geometry type : Point
            crs,
        )
        fbck = QgsProcessingFeedback()
        fbck.pushInfo(str(zonageOrSecteur))
        progressCount = currentLayer.featureCount()*3 if zonageOrSecteur else currentLayer.featureCount()*2
        progressMessageBar = self.iface.messageBar().createMessage("Check GPU validity layer...")
        progress = QProgressBar()
        progress.setMaximum(progressCount)
        progress.setAlignment(Qt.AlignVCenter)
        progressMessageBar.layout().addWidget(progress)
        self.iface.messageBar().pushWidget(progressMessageBar, Qgis.Info)
        progress.setValue(0)

        # check geos validity
        self.checkOgcValidity(currentLayer, progress)

        # check complexity
        self.checkComplexity(currentLayer, progress)
        if zonageOrSecteur:
            # check duplicates
            self.checkDuplicates(currentLayer, progress)
            
            # check boundary
            self.checkBoundary(currentLayer, progress)


        # Add result layer to map
        QgsProject.instance().addMapLayer(self.errorLayer)

        self.iface.messageBar().clearWidgets()

    def checkOgcValidity(self, layer, progress):
        featuresIterator = layer.getFeatures()
        feature = QgsFeature()
        featuresIterator.nextFeature(feature)
        self.errorLayer.startEditing()
        while not featuresIterator.isClosed():
            # Update progression
            progress.setValue(progress.value()+1)
            # search geos validity errors
            geosErrors = feature.geometry().validateGeometry(QgsGeometry.ValidatorGeos)
            for geosError in geosErrors:
                # create error feature
                errorFeature = QgsFeature(self.errorLayer.fields())
                errorFeature["fid"] = feature["gid"]
                errorFeature["level"] = "ERROR"
                errorFeature["type"] = "invalid"
                errorFeature["message"] = geosError.what()
                errorFeature.setGeometry(QgsGeometry.fromPointXY(geosError.where()))
                # add to error layer
                self.errorLayer.addFeature(errorFeature)
            featuresIterator.nextFeature(feature)
        self.errorLayer.commitChanges()

    def checkComplexity(self, layer, progress):
        featuresIterator = layer.getFeatures()
        feature = QgsFeature()
        featuresIterator.nextFeature(feature)
        self.errorLayer.startEditing()
        while not featuresIterator.isClosed():
            # Update progression
            progress.setValue(progress.value()+1)
            # Check number of vertices in geometry
            numVertices = self.countVertices(feature.geometry())
            if  numVertices > 200000:
                # create error feature
                errorFeature = QgsFeature(self.errorLayer.fields())
                errorFeature["fid"] = feature["gid"]
                errorFeature["type"] = "complex"
                errorFeature["level"] = "ERROR"
                errorFeature["message"] = "Nombre de sommets supérieur à 200000"
                errorFeature.setGeometry(feature.geometry().centroid())
                # add to error layer
                self.errorLayer.addFeature(errorFeature)

            # Check number of interior rings in geometry
            innerRings = self.countInnerRings(feature.geometry())
            if innerRings > 500:
                # create error feature
                errorFeature = QgsFeature(self.errorLayer.fields())
                errorFeature["fid"] = feature["gid"]
                errorFeature["type"] = "complex"
                errorFeature["level"] = "ERROR" if innerRings > 1000 else "WARNING"
                errorFeature["message"] = "Nombre de trous supérieur à {}".format("1000" if innerRings > 1000 else "500" )
                errorFeature.setGeometry(feature.geometry().centroid())
                # add to error layer
                self.errorLayer.addFeature(errorFeature)
                
            # Check number of parts in geometry
            numParts = self.countParts(feature.geometry())
            if numParts > 500:
                # create error feature
                errorFeature = QgsFeature(self.errorLayer.fields())
                errorFeature["fid"] = feature["gid"]
                errorFeature["type"] = "complex"
                errorFeature["level"] = "ERROR" if numParts > 1000 else "WARNING"
                errorFeature["message"] = "Nombre de parts supérieur à {}".format("1000" if numParts > 1000 else "500" )
                errorFeature.setGeometry(feature.geometry().centroid())
                # add to error layer
                self.errorLayer.addFeature(errorFeature)

            # Check vertices density
            hugeVerticesNumberRings = self.getHugeVerticesNumberRings(feature.geometry(), 50000)
            for hugeVerticesNumberRing in hugeVerticesNumberRings:
                verticesDensity = self.computeVerticesDensity(hugeVerticesNumberRing)
                if  verticesDensity > 0.1:
                    # create error feature
                    errorFeature = QgsFeature(self.errorLayer.fields())
                    errorFeature["fid"] = feature["gid"]
                    errorFeature["type"] = "complex"
                    errorFeature["level"] = "ERROR" if verticesDensity > 10 else "WARNING"
                    errorFeature["message"] = "Anneau avec plus de 50000 points et plus de {} points/mètre".format(10 if verticesDensity > 10 else 0.1)
                    errorFeature.setGeometry(hugeVerticesNumberRing.centroid())
                    # add to error layer
                    self.errorLayer.addFeature(errorFeature)

            featuresIterator.nextFeature(feature)
        self.errorLayer.commitChanges()

    def checkDuplicates(self, layer, progress):
        feedback = QgsProcessingFeedback()
        featuresIterator = layer.getFeatures()
        feature = QgsFeature()
        featuresIterator.nextFeature(feature)
        self.errorLayer.startEditing()
        seenGeometries = []
        while not featuresIterator.isClosed():
            # Update progression
            progress.setValue(progress.value()+1)
            # check duplicate
            featureValid = feature.geometry().isGeosValid()
            for geometry in seenGeometries:
                isDuplicate = feature.geometry().isGeosEqual(geometry) if featureValid else feature.geometry().equals(geometry)
                if isDuplicate:
                    # create error feature
                    errorFeature = QgsFeature(self.errorLayer.fields())
                    errorFeature["fid"] = feature["gid"]
                    errorFeature["level"] = "ERROR"
                    errorFeature["type"] = "duplicate"
                    errorFeature["message"] = "Géométrie dupliquée"
                    errorFeature.setGeometry(feature.geometry().centroid())
                    # add to error layer
                    self.errorLayer.addFeature(errorFeature)
                    break
            seenGeometries.append(feature.geometry())
            featuresIterator.nextFeature(feature)
        self.errorLayer.commitChanges()

    def checkBoundary(self, layer, progress):
        self.errorLayer.startEditing()
        self.errorLayer.commitChanges()

    def countVertices(self, geometry):
        return sum([part.vertexCount() for part in geometry.constParts()]) if geometry else 0

    def countInnerRings(self, geometry):
        return sum([part.numInteriorRings() for part in geometry.constParts()]) if geometry else 0

    def countParts(self, geometry):
        return geometry.constGet().partCount() if geometry else 0

    def computeVerticesDensity(self, geometry):
        if geometry:
            measure = QgsDistanceArea()
            measure.setEllipsoid("WGS84")
            if measure.measureLength(geometry) > 0:
                return self.countVertices(geometry) / measure.measureLength(geometry)
        return 0

    def getHugeVerticesNumberRings(self, geometry, maxVertices):
        # TODO check if geometry is polygon
        hugeVerticesNumberRings = []
        for part in geometry.constParts():
            # check exterior ring
            exteriorRing = part.exteriorRing()
            geom = QgsGeometry()
            if exteriorRing.wkbType() == 1:
                geom = QgsGeometry.fromPointXY(QgsPointXY(exteriorRing.x(), exteriorRing.y()))
            elif exteriorRing.wkbType() == 2:
                geom = QgsGeometry.fromPolyline(exteriorRing)
            else:
                # TODO check this case
                break
            if geom.constGet().vertexCount() > maxVertices:
                hugeVerticesNumberRings.append(geom)

            # check interior rings
            for interiorRing in [
                part.interiorRing(i) for i in range(part.numInteriorRings())
            ]:
                geom = QgsGeometry()
                if interiorRing.wkbType() == 1:
                    geom = QgsGeometry.fromPointXY(QgsPointXY(interiorRing.x(), interiorRing.y()))
                elif interiorRing.wkbType() == 2:
                    geom = QgsGeometry.fromPolyline(interiorRing)
                else:
                    # TODO check this case
                    break
                if geom.constGet().vertexCount() > maxVertices:
                    hugeVerticesNumberRings.append(geom)
        return hugeVerticesNumberRings

    def showError(self, title, msg):
        QgsErrorDialog.show(QgsError(msg, "GPU DATA CHECKER"), title)
