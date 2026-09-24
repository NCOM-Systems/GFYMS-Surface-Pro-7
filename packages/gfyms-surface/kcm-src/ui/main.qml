import QtQuick
import QtQuick.Controls as Controls
import org.kde.kirigami as Kirigami
import org.kde.kcmutils as KCMUtils

KCMUtils.SimpleKCM {
    Kirigami.FormLayout {
        wideMode: true
        Controls.Label {
            Kirigami.FormData.label: i18n("Platform")
            text: kcm.productName()
        }
        Controls.Label {
            Kirigami.FormData.label: i18n("Profile")
            text: kcm.isSurfacePro7() ? i18n("Microsoft Surface Pro 7") : i18n("Surface profile not recognized")
        }
        Controls.Label {
            Kirigami.FormData.label: i18n("Kernel")
            text: kcm.kernelVersion()
        }
        Controls.Label {
            Kirigami.FormData.label: i18n("Integration")
            text: i18n("GFYMS native Linux integration is installed")
        }
        Controls.Label {
            Kirigami.FormData.label: i18n("Diagnostics")
            text: i18n("Run gfyms doctor for a non-destructive hardware report.")
            wrapMode: Text.WordWrap
        }
    }
}
