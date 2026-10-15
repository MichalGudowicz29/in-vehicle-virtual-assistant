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
        width: Math.min(parent.width - 80, 700)
        spacing: 24

        Text {
            width: parent.width
            text: "NAVIGATION"
            color: "white"
            font.pixelSize: 42
            font.bold: true
            horizontalAlignment: Text.AlignHCenter
        }

        TextField {
            id: addressField
            width: parent.width
            placeholderText: "ul. Końcowa 5, Szczecin"
        }

        Button {
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
            color: "#ffb4ab"
            horizontalAlignment: Text.AlignHCenter
        }

        Button {
            text: "BACK"
            anchors.horizontalCenter: parent.horizontalCenter
            onClicked: root.backClicked()
        }
    }
}
