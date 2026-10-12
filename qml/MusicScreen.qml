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
                onClicked: car.previous_track()
            }

            Button {
                text: "PLAY / PAUSE"
                onClicked: car.play_pause()
            }

            Button {
                text: "NEXT"
                onClicked: car.next_track()
            }
        }

        Button {
            text: "BACK"
            anchors.horizontalCenter: parent.horizontalCenter
            onClicked: root.backClicked()
        }
    }
}
