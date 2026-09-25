import QtQuick
import QtQuick.Controls as Controls
import QtQuick.Layouts
import org.kde.kirigami as Kirigami
import org.kde.kcmutils as KCMUtils

KCMUtils.SimpleKCM {
    ScrollView {
        anchors.fill: parent
        ColumnLayout {
            width: parent.width
            spacing: Kirigami.Units.largeSpacing

            Kirigami.Card {
                Layout.fillWidth: true
                contentItem: ColumnLayout {
                    Controls.Label {
                        text: qsTr("GFYMS Surface Pro 7")
                        font.bold: true
                    }
                    Controls.Label {
                        text: kcm.productName() + " — " + kcm.kernelVersion()
                        wrapMode: Text.WordWrap
                    }
                    Controls.Label {
                        text: kcm.isSurfacePro7() ? qsTr("Surface Pro 7 profile detected") : qsTr("Surface profile not recognized")
                    }
                }
            }

            Kirigami.Card {
                Layout.fillWidth: true
                contentItem: ColumnLayout {
                    Controls.Label { text: qsTr("Surface Pen"); font.bold: true }
                    Controls.Label { text: qsTr("Pressure response") }
                    Controls.Slider {
                        Layout.fillWidth: true
                        from: 0
                        to: 100
                        value: kcm.penPressure()
                        onMoved: kcm.setPenPressure(Math.round(value))
                    }
                    Controls.Label { text: qsTr("Writing hand") }
                    Controls.ComboBox {
                        Layout.fillWidth: true
                        model: [qsTr("Right handed"), qsTr("Left handed")]
                        Component.onCompleted: currentIndex = kcm.penHand()
                        onActivated: kcm.setPenHand(currentIndex)
                    }
                    Controls.Label { text: qsTr("Top button") }
                    Controls.ComboBox {
                        Layout.fillWidth: true
                        model: [qsTr("Open GFYMS Center"), qsTr("Show launcher"), qsTr("Screenshot"), qsTr("Do nothing")]
                        Component.onCompleted: currentIndex = kcm.penTopButton()
                        onActivated: kcm.setPenTopButton(currentIndex)
                    }
                    Controls.Label { text: qsTr("Side button") }
                    Controls.ComboBox {
                        Layout.fillWidth: true
                        model: [qsTr("Right click"), qsTr("Middle click"), qsTr("Do nothing")]
                        Component.onCompleted: currentIndex = kcm.penSideButton()
                        onActivated: kcm.setPenSideButton(currentIndex)
                    }
                    Controls.Label {
                        text: qsTr("These preferences are stored by GFYMS and are consumed by the native Surface input backend when available.")
                        wrapMode: Text.WordWrap
                    }
                }
            }

            Kirigami.Card {
                Layout.fillWidth: true
                contentItem: ColumnLayout {
                    Controls.Label { text: qsTr("GFYMS shell") ; font.bold: true }
                    Controls.Label {
                        text: qsTr("The GFYMS Plasma theme targets a 24px visual language. The KWin rounded-corners effect applies that shell policy to windows without changing arbitrary third-party application code.")
                        wrapMode: Text.WordWrap
                    }
                }
            }
        }
    }
}
