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

        onHangUpClicked: car.contacts.end_call()
    }

    StackView {
        id: stackView
        anchors.fill: parent
        initialItem: homeScreen
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
        onClicked: shutdownController.request_shutdown()
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
            onMusicClicked: stackView.push(musicScreen)
            onNavigationClicked: stackView.push(navigationScreen)
            onContactsClicked: stackView.push(contactsScreen)
        }
    }

    Component {
        id: musicScreen

        MusicScreen {
            onBackClicked: stackView.pop()
        }
    }

    Component {
        id: navigationScreen

        NavigationScreen {
            onBackClicked: stackView.pop()
        }
    }

    Component {
        id: mapScreen

        MapScreen {
            onBackClicked: stackView.pop()
        }
    }

    Component {
        id: contactsScreen

        ContactsScreen {
            onBackClicked: stackView.pop()
        }
    }

    
}
