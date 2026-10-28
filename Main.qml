import QtQuick
import QtQuick.Controls
import "qml"

ApplicationWindow {
    id: window

    visible: true
    width: 1280
    height: 720
    title: "Car Assistant"

    onClosing: function(close) {
        sessionControls.recordTouch("close_window")
        close.accepted = false
        shutdownController.request_shutdown()
    }

    Theme {
        id: theme
    }

    color: theme.background

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
        anchors.fill: parent
        initialItem: homeScreen
        onCurrentItemChanged: {
            if (currentItem) sessionControls.recordScreen(currentItem.objectName)
        }
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
