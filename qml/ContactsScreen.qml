
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
        anchors.fill: parent
        anchors.margins: theme.pagePadding
        spacing: 20

        Text {
            text: "CONTACTS"
            color: theme.text
            font.pixelSize: theme.titleSize
            font.bold: true
        }

        Text {
            visible: car.contacts.current_contact_index != -1
            text: "Calling:" + (car.contacts.current_contact_index >= 0 ? car.contacts.contacts[car.contacts.current_contact_index].name : "No contact selected")
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
                color: theme.surface
                radius: theme.radius
                border.color: theme.border
                border.width: 1

                Column {
                    anchors.fill: parent
                    anchors.margins: 16
                    spacing: 8

                    Text {
                        text: modelData.name
                        color: theme.text
                        font.pixelSize: 22
                    }

                    Row {
                        spacing: 10

                        AppButton {
                            height: 38
                            visible: modelData.mobile !== undefined
                            text: "MOBILE"
                            onClicked: {
                                car.contacts.call_contact(
                                    modelData.name,
                                    "mobile"
                                )
                            }
                        }

                        AppButton {
                            height: 38
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

        AppButton {
            text: "BACK"
            onClicked: root.backClicked()
        }
    }
}
