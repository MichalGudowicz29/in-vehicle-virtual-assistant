import QtQuick
import QtQuick.Controls

Item {
    id: root

    Theme {
        id: theme
    }

    signal backClicked()

    Rectangle {
        anchors.fill: parent
        color: theme.background
    }

    Column {
        anchors.centerIn: parent
        spacing: 24

        Text {
            text: "MUSIC"
            color: theme.text
            font.pixelSize: theme.titleSize
            font.bold: true
            anchors.horizontalCenter: parent.horizontalCenter
        }

        Text {
            text: car.music.isPlaying ? "Playing" : "Paused"
            color: car.music.isPlaying ? theme.accent : theme.textMuted
            font.pixelSize: theme.bodySize
            anchors.horizontalCenter: parent.horizontalCenter
        }

        Text {
            text: car.music.currentTrackIndex >= 0 ? car.music.currentTrackIndex : "No track selected"
            color: theme.textMuted
            font.pixelSize: theme.bodySize
            anchors.horizontalCenter: parent.horizontalCenter
        }

        Row {
            spacing: 16
            anchors.horizontalCenter: parent.horizontalCenter

            AppButton {
                text: "PREVIOUS"
                onClicked: sessionControls.performTouch("music", "previous_track", [])
            }

            AppButton {
                text: car.music.isPlaying ? "PAUSE" : "PLAY"
                onClicked: sessionControls.performTouch("music", "play_pause", [])
            }

            AppButton {
                text: "NEXT"
                onClicked: sessionControls.performTouch("music", "next_track", [])
            }
        }

        AppButton {
            text: "BACK"
            anchors.horizontalCenter: parent.horizontalCenter
            onClicked: root.backClicked()
        }
    }
}
