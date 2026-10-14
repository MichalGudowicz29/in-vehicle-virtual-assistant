
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
        anchors.fill: parent
        anchors.margins: 40
        spacing: 20

        Text {
            text: "CONTACTS"
            color: "white"
            font.pixelSize: 42
            font.bold: true
        }

        ListView {
            width: parent.width
            height: parent.height - 140
            spacing: 16
            clip: true

            model: car.contacts.contacts

            delegate: Rectangle {
                width: ListView.view.width
                height: 100
                color: "#20242b"
                radius: 12

                Column {
                    anchors.fill: parent
                    anchors.margins: 16
                    spacing: 8

                    Text {
                        text: modelData.name
                        color: "white"
                        font.pixelSize: 22
                    }

                    Row {
                        spacing: 10

                        Button {
                            visible: modelData.mobile !== undefined
                            text: "MOBILE"
                            onClicked: {
                                car.contacts.call_contact(
                                    modelData.name,
                                    "mobile"
                                )
                            }
                        }

                        Button {
                            visible: modelData.work !== undefined
                            text: "WORK"
                            onClicked: {
                                car.contacts.call_contact(
                                    modelData.name,
                                    "work"
                                )
                            }
                        }
                    }
                }
            }
        }

        Button {
            text: "BACK"
            onClicked: root.backClicked()
        }
    }
}