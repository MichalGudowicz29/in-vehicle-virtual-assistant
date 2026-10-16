import QtQuick
import QtQuick.Controls

Button {
    id: root

    Theme {
        id: theme
    }

    implicitWidth: 150
    implicitHeight: 48
    leftPadding: 18
    rightPadding: 18

    contentItem: Text {
        text: root.text
        color: theme.text
        font.pixelSize: 15
        font.bold: true
        horizontalAlignment: Text.AlignHCenter
        verticalAlignment: Text.AlignVCenter
        elide: Text.ElideRight
    }

    background: Rectangle {
        radius: theme.smallRadius
        color: root.down
            ? theme.accentPressed
            : root.hovered
                ? theme.surfacePressed
                : theme.surfaceRaised
        border.color: root.hovered ? theme.accent : theme.border
        border.width: 1
    }
}
