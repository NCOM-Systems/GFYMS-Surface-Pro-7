kcmutils_add_qml_kcm(kcm_gfyms_surface)

target_sources(kcm_gfyms_surface PRIVATE kcm_gfyms_surface.cpp)

target_link_libraries(kcm_gfyms_surface
    PRIVATE
    Qt6::Core
    Qt6::Gui
    Qt6::Quick
    KF6::CoreAddons
    KF6::KCMUtils
    KF6::I18n
)
