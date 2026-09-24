kcmutils_add_qml_kcm(kcm_gfyms_surface SOURCES kcm_gfyms_surface.cpp)

target_link_libraries(kcm_gfyms_surface
    PRIVATE
    Qt6::Core
    Qt6::Gui
    Qt6::Quick
    KF6::CoreAddons
    KF6::KCMUtils
    KF6::KCMUtilsQuick
    KF6::I18n
)
