import QtQuick
import QtQuick.Controls
import QtLocation
import QtPositioning

Item {
    id: root

    signal backClicked()

    Plugin {
        id: mapPlugin
        name: "osm"
    }

    Map {
        anchors.fill: parent
        plugin: mapPlugin
        center: QtPositioning.coordinate(52.2297, 21.0122)
        zoomLevel: 12
    }

    Button {
        anchors.left: parent.left
        anchors.bottom: parent.bottom
        anchors.margins: 24
        text: "BACK"
        onClicked: root.backClicked()
    }
}