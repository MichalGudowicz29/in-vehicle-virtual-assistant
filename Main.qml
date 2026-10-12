import QtQuick
import QtQuick.Controls
import "qml"

ApplicationWindow {
    id: window

    visible: true
    width: 1280
    height: 720
    title: "Car Assistant"

    StackView {
        id: stackView
        anchors.fill: parent
        initialItem: homeScreen
    }

    Connections {
        target: car
                 
        function onNavigationScreenRequested() {
            stackView.push(navigationScreen)
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
        id: contactsScreen

        ContactsScreen {
            onBackClicked: stackView.pop()
        }
    }

    
}
