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
        center: QtPositioning.coordinate(53.44701694345204, 14.492347537788525)
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