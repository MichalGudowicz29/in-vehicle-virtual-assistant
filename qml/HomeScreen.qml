import QtQuick
import QtQuick.Controls

Item {
    id: root

    signal musicClicked()
    signal navigationClicked()
    signal contactsClicked()

    function openMusicScreen() {
        console.log("Opening music screen")
        musicClicked()
    }

    function openNavigationScreen() {
        console.log("Opening navigation screen")
        navigationClicked()
    }

    function openContactsScreen() {
        console.log("Opening contacts screen")
        contactsClicked()
    }

    Rectangle {
        anchors.fill: parent
        color: "#101216"
    }

    Column {
        anchors.centerIn: parent
        width: Math.min(parent.width - 80, 900)
        spacing: 18

        Text {
            width: parent.width
            text: "CAR ASSISTANT"
            color: "white"
            font.pixelSize: 42
            font.bold: true
            horizontalAlignment: Text.AlignHCenter
        }

        Text {
            width: parent.width
            text: "Wybierz funkcję"
            color: "#9aa4b2"
            font.pixelSize: 20
            horizontalAlignment: Text.AlignHCenter
        }

        Row {
            anchors.horizontalCenter: parent.horizontalCenter
            spacing: 20

            Button {
                width: 250
                height: 140
                text: "MUSIC"

                onClicked: root.openMusicScreen()
            }

            Button {
                width: 250
                height: 140
                text: "NAVIGATION"

                onClicked: root.openNavigationScreen()
            }

            Button {
                width: 250
                height: 140
                text: "CONTACTS"

                onClicked: root.openContactsScreen()
            }
        }
    }
}
