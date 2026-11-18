import QtQuick
import QtQuick.Controls
import QtQuick.VirtualKeyboard
import QtQuick.VirtualKeyboard.Settings
import "qml"

ApplicationWindow {
    id: window

    visible: true
    width: 1280
    height: 720
    title: "Car Assistant"
    contentItem.enabled: sessionControls.touchEnabled

    onClosing: function(close) {
        sessionControls.recordTouch("close_window")
        close.accepted = false
        shutdownController.request_shutdown()
    }

    Theme {
        id: theme
    }

    color: theme.background

    Rectangle {
        id: userMessageBanner
        objectName: "userMessageBanner"
        anchors.bottom: screenKeyboard.top
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.bottomMargin: 24
        width: Math.min(parent.width - 48, 760)
        height: Math.max(userMessageText.implicitHeight + 32, dismissUserMessage.height + 24)
        visible: sessionControls.userMessage.length > 0
        color: theme.surfaceRaised
        border.color: theme.error
        radius: theme.radius
        z: 250

        Text {
            id: userMessageText
            objectName: "userMessageText"
            anchors.left: parent.left
            anchors.right: dismissUserMessage.left
            anchors.verticalCenter: parent.verticalCenter
            anchors.margins: 16
            text: sessionControls.userMessage
            color: theme.text
            font.pixelSize: theme.bodySize
            wrapMode: Text.WordWrap
            Accessible.role: Accessible.AlertMessage
            Accessible.name: text
        }

        AppButton {
            id: dismissUserMessage
            objectName: "dismissUserMessage"
            anchors.right: parent.right
            anchors.verticalCenter: parent.verticalCenter
            anchors.rightMargin: 12
            text: "Zamknij"
            onClicked: sessionControls.showUserMessage("")
        }
    }

    Timer {
        id: userMessageTimer
        objectName: "userMessageTimer"
        interval: 8000
        onTriggered: sessionControls.showUserMessage("")
    }

    Connections {
        target: sessionControls
        function onUserMessageChanged() {
            if (sessionControls.userMessage.length > 0) userMessageTimer.restart()
            else userMessageTimer.stop()
        }
    }

    CallOverlay {
        anchors.top: parent.top
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.topMargin: 12
        z: 100

        visible: car.contacts.isCalling

        contactName: car.contacts.currentContactName

        onHangUpClicked: sessionControls.performTouch("contacts", "end_call", [])
    }

    StackView {
        id: stackView
        anchors.top: parent.top
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.bottom: screenKeyboard.top
        initialItem: homeScreen
        onCurrentItemChanged: {
            Qt.inputMethod.hide()
            if (currentItem) sessionControls.recordScreen(currentItem.objectName)
        }
    }

    InputPanel {
        id: screenKeyboard
        objectName: "screenKeyboard"
        anchors.horizontalCenter: parent.horizontalCenter
        width: Math.min(parent.width, 900)
        y: active ? parent.height - height : parent.height
        visible: active
        z: 300
        Component.onCompleted: VirtualKeyboardSettings.locale = "pl_PL"
    }

    Button {
        objectName: "shutdownButton"
        anchors.top: parent.top
        anchors.right: parent.right
        anchors.margins: 12
        z: 200
        text: shutdownController.closing ? "Kończenie…" : "Zakończ"
        enabled: !shutdownController.closing
        Accessible.name: text
        onClicked: {
            sessionControls.recordTouch("shutdown")
            shutdownController.request_shutdown()
        }
    }

    Connections {
        target: car.navigation

        function onMapScreenRequested() {
            stackView.push(mapScreen)
        }

    }

    Component {
        id: homeScreen

        HomeScreen {
            objectName: "home"
            onMusicClicked: {
                sessionControls.recordTouch("open_music")
                stackView.push(musicScreen)
            }
            onNavigationClicked: {
                sessionControls.recordTouch("open_navigation")
                stackView.push(navigationScreen)
            }
            onContactsClicked: {
                sessionControls.recordTouch("open_contacts")
                stackView.push(contactsScreen)
            }
        }
    }

    Component {
        id: musicScreen

        MusicScreen {
            objectName: "music"
            onBackClicked: {
                sessionControls.recordTouch("back")
                stackView.pop()
            }
        }
    }

    Component {
        id: navigationScreen

        NavigationScreen {
            objectName: "navigation"
            onBackClicked: {
                sessionControls.recordTouch("back")
                stackView.pop()
            }
        }
    }

    Component {
        id: mapScreen

        MapScreen {
            objectName: "map"
            onBackClicked: {
                sessionControls.recordTouch("back")
                stackView.pop()
            }
        }
    }

    Component {
        id: contactsScreen

        ContactsScreen {
            objectName: "contacts"
            onBackClicked: {
                sessionControls.recordTouch("back")
                stackView.pop()
            }
        }
    }

    
}
