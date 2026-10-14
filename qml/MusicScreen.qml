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
            text: car.music.isPlaying ? "Playing" : "Paused"
            color: "#9aa4b2"
            font.pixelSize: 18
            anchors.horizontalCenter: parent.horizontalCenter
        }

        Text {
            text: car.music.currentTrackIndex >= 0 ? car.music.currentTrackIndex : "No track selected"
            color: "#9aa4b2"
            font.pixelSize: 18
            anchors.horizontalCenter: parent.horizontalCenter
        }

        Row {
            spacing: 16
            anchors.horizontalCenter: parent.horizontalCenter

            Button {
                text: "PREVIOUS"
                onClicked: car.music.previous_track()
            }

            Button {
                text: car.music.isPlaying ? "PAUSE" : "PLAY"
                onClicked: car.music.play_pause()
            }

            Button {
                text: "NEXT"
                onClicked: car.music.next_track()
            }
        }

        Button {
            text: "BACK"
            anchors.horizontalCenter: parent.horizontalCenter
            onClicked: root.backClicked()
        }
    }
}
