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
        spacing: 24

        Text {
            text: "MUSIC"
            color: "white"
            font.pixelSize: 42
            font.bold: true
            anchors.horizontalCenter: parent.horizontalCenter
        }

        Text {
            text: "Mockup odtwarzacza muzyki"
            color: "#9aa4b2"
            font.pixelSize: 20
            anchors.horizontalCenter: parent.horizontalCenter
        }

        Row {
            spacing: 16
            anchors.horizontalCenter: parent.horizontalCenter

            Button {
                text: "PREVIOUS"
                onClicked: backend.previousTrack()
            }

            Button {
                text: "PLAY / PAUSE"
                onClicked: backend.playPause()
            }

            Button {
                text: "NEXT"
                onClicked: backend.nextTrack()
            }
        }

        Button {
            text: "BACK"
            anchors.horizontalCenter: parent.horizontalCenter
            onClicked: root.backClicked()
        }
    }
}
