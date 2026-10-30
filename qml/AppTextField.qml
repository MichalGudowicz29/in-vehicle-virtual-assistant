import QtQuick
import QtQuick.Controls

TextField {
    function dismissKeyboard() {
        Qt.inputMethod.commit()
        focus = false
        Qt.inputMethod.hide()
    }

    onAccepted: dismissKeyboard()
}
