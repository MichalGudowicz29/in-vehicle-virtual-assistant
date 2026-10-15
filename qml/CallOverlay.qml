import QtQuick
import QtQuick.Controls

Rectangle {
    id: root

    property string contactName: ""
    signal hangUpClicked()

    width: 360
    height: 70
    radius: 12
    color: "#252a33"

    Row {
        anchors.centerIn: parent
        spacing: 20

        Text {
            text: "Rozmowa z " + root.contactName
            color: "white"
        }

        Button {
            text: "ROZŁĄCZ"
            onClicked: root.hangUpClicked()
        }
    }
}
