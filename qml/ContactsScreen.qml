import QtQuick
import QtQuick.Controls

Item {
    id: root

    signal backClicked()

    Rectangle {
        anchors.fill: parent
        color: "#101216"
    }

    Column {
        anchors.centerIn: parent
        spacing: 20

        Text {
            text: "CONTACTS"
            color: "white"
            font.pixelSize: 42
            font.bold: true
            anchors.horizontalCenter: parent.horizontalCenter
        }

        Button {
            text: "Robert Lewandowski"
            anchors.horizontalCenter: parent.horizontalCenter
            onClicked: car.call_contact("Robert Lewandowski", "mobile")
        }

        Button {
            text: "BACK"
            anchors.horizontalCenter: parent.horizontalCenter
            onClicked: root.backClicked()
        }
    }
}
