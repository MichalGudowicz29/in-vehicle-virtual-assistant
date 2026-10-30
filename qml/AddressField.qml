import QtQuick
import QtQuick.Controls

AppTextField {
    id: root
    property bool suggestionsDismissed: false
    readonly property var matches: car.navigation.search_places(text)
    onTextEdited: suggestionsDismissed = false
    onActiveFocusChanged: {
        if (activeFocus) suggestionsDismissed = false
    }

    Theme { id: theme }

    Popup {
        id: suggestions
        parent: Overlay.overlay
        x: parent ? (parent.width - width) / 2 : 0
        y: Math.max(0, (Qt.inputMethod.visible
            ? Qt.inputMethod.keyboardRectangle.y : (parent ? parent.height : 0)) - height)
        width: parent ? Math.min(700, parent.width - 48) : root.width
        height: Math.min(root.matches.length, 3) * 48 + 16
        padding: 8
        visible: root.activeFocus && root.matches.length > 0 && !root.suggestionsDismissed
        focus: false
        modal: false
        closePolicy: Popup.NoAutoClose

        background: Rectangle {
            color: theme.surface
            radius: theme.smallRadius
            border.color: theme.border
        }

        contentItem: ListView {
            clip: true
            model: root.matches
            ScrollIndicator.vertical: ScrollIndicator { }
            delegate: AppButton {
                required property var modelData
                width: ListView.view.width
                height: 48
                text: modelData.address
                focusPolicy: Qt.NoFocus
                onClicked: {
                    Qt.inputMethod.commit()
                    root.text = modelData.address
                    root.cursorPosition = root.length
                    root.suggestionsDismissed = true
                }
            }
        }
    }
}
