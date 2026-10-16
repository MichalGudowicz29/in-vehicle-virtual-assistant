import QtQuick
import QtQuick.Controls

Item {
    id: root

    Theme {
        id: theme
    }

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
        color: theme.background
    }

    Column {
        anchors.centerIn: parent
        width: Math.min(parent.width - 80, 900)
        spacing: 18

        Text {
            width: parent.width
            text: "CAR ASSISTANT"
            color: theme.text
            font.pixelSize: theme.titleSize
            font.bold: true
            horizontalAlignment: Text.AlignHCenter
        }

        Text {
            width: parent.width
            text: "Wybierz funkcję"
            color: theme.textMuted
            font.pixelSize: theme.bodySize
            horizontalAlignment: Text.AlignHCenter
        }

        Row {
            anchors.horizontalCenter: parent.horizontalCenter
            spacing: 20

            AppButton {
                width: 250
                height: 140
                text: "MUSIC"

                onClicked: root.openMusicScreen()
            }

            AppButton {
                width: 250
                height: 140
                text: "NAVIGATION"

                onClicked: root.openNavigationScreen()
            }

            AppButton {
                width: 250
                height: 140
                text: "CONTACTS"

                onClicked: root.openContactsScreen()
            }
        }
    }
}
