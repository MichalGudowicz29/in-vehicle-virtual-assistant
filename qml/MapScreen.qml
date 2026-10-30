import QtQuick
import QtQuick.Controls

Item {
    id: root

    Theme { id: theme }
    signal backClicked()

    readonly property var routePoints: car.navigation.routePoints
    readonly property var knownPoints: [routePoints[0]].concat(Object.values(car.navigation.places_list))
    readonly property var bounds: {
        const lat = knownPoints.map(p => p.lat)
        const lon = knownPoints.map(p => p.lon)
        return { north: Math.max(...lat), south: Math.min(...lat),
                 east: Math.max(...lon), west: Math.min(...lon) }
    }

    Rectangle {
        anchors.fill: parent
        color: theme.background
    }

    Text {
        anchors.top: parent.top
        anchors.left: parent.left
        anchors.margins: 24
        text: "MAPA SCHEMATYCZNA · OFFLINE"
        color: theme.text
        font.pixelSize: 22
        font.bold: true
    }

    Item {
        id: map
        anchors.left: parent.left
        anchors.right: stopsPanel.left
        anchors.top: parent.top
        anchors.bottom: parent.bottom
        anchors.leftMargin: 24
        anchors.rightMargin: 24
        anchors.topMargin: 84
        anchors.bottomMargin: 100

        function pointX(point) {
            return 50 + (point.lon - root.bounds.west)
                / Math.max(0.001, root.bounds.east - root.bounds.west) * Math.max(0, width - 100)
        }
        function pointY(point) {
            return 50 + (root.bounds.north - point.lat)
                / Math.max(0.001, root.bounds.north - root.bounds.south) * Math.max(0, height - 100)
        }

        Canvas {
            id: drawing
            anchors.fill: parent
            onWidthChanged: requestPaint()
            onHeightChanged: requestPaint()
            onPaint: {
                const ctx = getContext("2d")
                ctx.reset()
                // Decorative streets stay local; the route shows order, not road geometry.
                ctx.strokeStyle = theme.border
                ctx.lineWidth = 14
                ctx.lineCap = "round"
                for (let i = 1; i <= 4; i++) {
                    ctx.beginPath()
                    ctx.moveTo(0, height * i / 5)
                    ctx.lineTo(width, height * i / 5)
                    ctx.stroke()
                    ctx.beginPath()
                    ctx.moveTo(width * i / 5, 0)
                    ctx.lineTo(width * i / 5, height)
                    ctx.stroke()
                }
                ctx.strokeStyle = theme.accent
                ctx.lineWidth = 6
                ctx.beginPath()
                for (let i = 0; i < root.routePoints.length; i++) {
                    const point = root.routePoints[i]
                    if (i === 0) ctx.moveTo(map.pointX(point), map.pointY(point))
                    else ctx.lineTo(map.pointX(point), map.pointY(point))
                }
                ctx.stroke()
            }
        }

        Repeater {
            model: root.knownPoints
            delegate: Item {
                required property var modelData
                x: map.pointX(modelData)
                y: map.pointY(modelData)
                Rectangle {
                    width: 12
                    height: 12
                    radius: 6
                    x: -6
                    y: -6
                    color: theme.textMuted
                }
                Text {
                    x: Math.min(10, map.width - parent.x - width)
                    y: 24
                    text: modelData.address
                    color: theme.text
                    font.pixelSize: 15
                    style: Text.Outline
                    styleColor: theme.background
                }
            }
        }

        Repeater {
            objectName: "routeMarkers"
            model: root.routePoints
            delegate: Text {
                required property var modelData
                required property int index
                x: map.pointX(modelData) - width / 2
                y: map.pointY(modelData) - height / 2
                width: index === 0 ? 66 : 36
                height: 36
                text: index === 0 ? "START" : String(index)
                color: theme.text
                font.bold: true
                font.pixelSize: 16
                horizontalAlignment: Text.AlignHCenter
                verticalAlignment: Text.AlignVCenter
                Rectangle {
                    anchors.fill: parent
                    z: -1
                    radius: 18
                    color: theme.surfaceRaised
                    border.width: 2
                    border.color: theme.accent
                }
            }
        }
    }

    onRoutePointsChanged: drawing.requestPaint()

    Rectangle {
        id: stopsPanel
        anchors.top: parent.top
        anchors.right: parent.right
        anchors.margins: 24
        width: Math.min(420, root.width * 0.38)
        height: 250
        radius: theme.radius
        color: theme.surface
        border.color: theme.border
        border.width: 1
        z: 10

        Column {
            anchors.fill: parent
            anchors.margins: 16
            spacing: 10

            Text {
                text: "PRZYSTANKI"
                color: theme.text
                font.bold: true
                font.pixelSize: 20
            }

            Row {
                width: parent.width
                spacing: 8

                AddressField {
                    id: stopAddressField
                    width: parent.width - addStopButton.width - 8
                    placeholderText: "ul. Stacyjna 10, Szczecin"
                    color: theme.text
                    placeholderTextColor: theme.textMuted
                    padding: 12

                    background: Rectangle {
                        radius: theme.smallRadius
                        color: theme.background
                        border.color: stopAddressField.activeFocus ? theme.accent : theme.border
                        border.width: 1
                    }
                }

                AppButton {
                    id: addStopButton
                    width: 90
                    text: "DODAJ"
                    onClicked: {
                        stopAddressField.dismissKeyboard()
                        const accepted = sessionControls.performTouch("navigation", "add_stop", [stopAddressField.text])
                        stopStatus.text = accepted
                            ? "Przystanek dodany."
                            : "Brak jednoznacznego adresu. Wybierz podpowiedź."
                        if (accepted) {
                            stopAddressField.clear()
                        }
                    }
                }
            }

            ListView {
                width: parent.width
                height: 90
                clip: true
                model: car.navigation.stops

                delegate: Row {
                    width: ListView.view.width
                    spacing: 8

                    Text {
                        width: parent.width - removeButton.width - 8
                        text: modelData.address
                        color: theme.text
                        elide: Text.ElideRight
                    }

                    AppButton {
                        height: 36
                        id: removeButton
                        text: "USUŃ"
                        onClicked: sessionControls.performTouch("navigation", "remove_stop", [modelData.address])
                    }
                }
            }

            Text {
                id: stopStatus
                text: ""
                color: theme.error
            }
        }
    }

    AppButton {
        anchors.left: parent.left
        anchors.bottom: parent.bottom
        anchors.margins: 24
        text: "BACK"
        onClicked: root.backClicked()
    }
}
