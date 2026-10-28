import QtQuick
import QtQuick.Controls
import QtLocation
import QtPositioning

Item {
    id: root

    Theme {
        id: theme
    }

    signal backClicked()

    Plugin {
        id: mapPlugin
        name: "osm"

        PluginParameter {
            name: "osm.useragent"
            value: "InVehicleVirtualAssistant/0.1"
        }

        PluginParameter {
            name: "osm.routing.host"
            value: "http://router.project-osrm.org/route/v1/driving/"
        }
    }

    RouteQuery {
        id: routeQuery
        travelModes: RouteQuery.CarTravel
        routeOptimizations: RouteQuery.FastestRoute
    }

    RouteModel {
        id: routeModel
        plugin: mapPlugin
        query: routeQuery
        autoUpdate: false

        onStatusChanged: {
            if (status === RouteModel.Error) {
                console.warn("Route error:", errorString)
            }
        }
    }

    Map {
        id: map
        anchors.fill: parent
        plugin: mapPlugin
        center: QtPositioning.coordinate(53.44701694345204, 14.492347537788525)
        zoomLevel: 12

        MapItemView {
            model: routeModel

            delegate: MapRoute {
                route: routeData
                line.width: 6
                line.color: theme.accent
            }
        }
    }

    Connections {
        target: car.navigation

        function onRoutePointsChanged() {
            root.rebuildRoute(car.navigation.routePoints)
        }
    }

    function rebuildRoute(points) {
        routeQuery.clearWaypoints()

        for (let i = 0; i < points.length; i++) {
            routeQuery.addWaypoint(
                QtPositioning.coordinate(points[i].lat, points[i].lon)
            )
        }

        if (points.length >= 2) {
            map.center = QtPositioning.coordinate(points[0].lat, points[0].lon)
            routeModel.update()
        } else {
            routeModel.reset()
        }
    }

    Component.onCompleted: {
        root.rebuildRoute(car.navigation.routePoints)
    }

    Rectangle {
        id: stopsPanel
        anchors.top: parent.top
        anchors.right: parent.right
        anchors.margins: 24
        width: 420
        height: 250
        radius: theme.radius
        color: theme.surface
        border.color: theme.border
        border.width: 1
        z: 10

        Column {
            anchors.fill: parent
            anchors.margins: 16
            spacing: 10

            Text {
                text: "PRZYSTANKI"
                color: theme.text
                font.bold: true
                font.pixelSize: 20
            }

            Row {
                width: parent.width
                spacing: 8

                TextField {
                    id: stopAddressField
                    width: parent.width - addStopButton.width - 8
                    placeholderText: "ul. Stacyjna 10, Szczecin"
                    color: theme.text
                    placeholderTextColor: theme.textMuted
                    padding: 12

                    background: Rectangle {
                        radius: theme.smallRadius
                        color: theme.background
                        border.color: stopAddressField.activeFocus ? theme.accent : theme.border
                        border.width: 1
                    }
                }

                AppButton {
                    id: addStopButton
                    width: 90
                    text: "DODAJ"
                    onClicked: {
                        const accepted = sessionControls.performTouch("navigation", "add_stop", [stopAddressField.text])
                        stopStatus.text = accepted
                            ? "Przystanek dodany."
                            : "Wpisz dokładny adres z bazy testowej."
                        if (accepted) {
                            stopAddressField.clear()
                        }
                    }
                }
            }

            ListView {
                width: parent.width
                height: 90
                clip: true
                model: car.navigation.stops

                delegate: Row {
                    width: ListView.view.width
                    spacing: 8

                    Text {
                        width: parent.width - removeButton.width - 8
                        text: modelData.address
                        color: theme.text
                        elide: Text.ElideRight
                    }

                    AppButton {
                        height: 36
                        id: removeButton
                        text: "USUŃ"
                        onClicked: sessionControls.performTouch("navigation", "remove_stop", [modelData.address])
                    }
                }
            }

            Text {
                id: stopStatus
                text: ""
                color: theme.error
            }
        }
    }

    AppButton {
        anchors.left: parent.left
        anchors.bottom: parent.bottom
        anchors.margins: 24
        text: "BACK"
        onClicked: root.backClicked()
    }
}
