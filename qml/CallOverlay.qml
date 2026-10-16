import QtQuick
import QtQuick.Controls

Rectangle {
    id: root

    Theme {
        id: theme
    }

    property string contactName: ""
    signal hangUpClicked()

    width: 360
    height: 70
    radius: theme.radius
    color: theme.surfaceRaised
    border.color: theme.accent
    border.width: 1

    Row {
        anchors.centerIn: parent
        spacing: 20

        Text {
            text: "Rozmowa z " + root.contactName
            color: theme.text
            font.pixelSize: 16
            font.bold: true
        }

        AppButton {
            height: 38
            text: "ROZŁĄCZ"
            onClicked: root.hangUpClicked()
        }
    }
}
