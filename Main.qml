import QtQuick
import QtQuick.Controls

ApplicationWindow {
    visible: true

    width: 1280
    height: 720

    title: "Car Assistant"

    Rectangle {
        anchors.fill: parent
        color: "#101216"

        Column {
            anchors.centerIn: parent
            spacing: 30

            Text {
                text: "CAR ASSISTANT"
                color: "white"
                font.pixelSize: 42
                anchors.horizontalCenter: parent.horizontalCenter
            }

            Row {
                spacing: 20

                Button {
                    text: "NAVIGATION"

                    width: 220
                    height: 100

                    onClicked: {
                        backend.setDestination("Zolnierska 47, Szczecin, Poland")
                    }
                }

                Button {
                    text: "MUSIC"

                    width: 220
                    height: 100

                    onClicked: {
                        backend.playPause()
                    }
                }

                Button {
                    text: "PHONE"

                    width: 220
                    height: 100

                    onClicked: {
                        backend.callContact("Robert Lewandowski", "mobile")
                    }
                }
            }
        }
    }
}