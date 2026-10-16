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

        TextField {
            id: addressField
            width: parent.width
            placeholderText: "ul. Końcowa 5, Szczecin"
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
                const accepted = car.navigation.set_destination(addressField.text)
                statusText.text = accepted
                    ? "Cel ustawiony."
                    : "Wpisz dokładny adres z bazy testowej."
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
