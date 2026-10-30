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
        width: Math.min(parent.width - 80, 700)
        spacing: 24

        Text {
            width: parent.width
            text: "NAVIGATION"
            color: theme.text
            font.pixelSize: theme.titleSize
            font.bold: true
            horizontalAlignment: Text.AlignHCenter
        }

        AddressField {
            id: addressField
            width: parent.width
            placeholderText: "ul. Żołnierska 47, Szczecin"
            color: theme.text
            placeholderTextColor: theme.textMuted
            padding: 14

            background: Rectangle {
                radius: theme.smallRadius
                color: theme.surface
                border.color: addressField.activeFocus ? theme.accent : theme.border
                border.width: 1
            }
        }

        AppButton {
            text: "START NAVIGATION"
            anchors.horizontalCenter: parent.horizontalCenter
            onClicked: {
                addressField.dismissKeyboard()
                const accepted = sessionControls.performTouch("navigation", "set_destination", [addressField.text])
                statusText.text = accepted
                    ? "Cel ustawiony."
                    : "Brak jednoznacznego adresu. Wybierz podpowiedź."
            }
        }

        Text {
            id: statusText
            width: parent.width
            color: theme.error
            horizontalAlignment: Text.AlignHCenter
        }

        AppButton {
            text: "BACK"
            anchors.horizontalCenter: parent.horizontalCenter
            onClicked: root.backClicked()
        }
    }
}
