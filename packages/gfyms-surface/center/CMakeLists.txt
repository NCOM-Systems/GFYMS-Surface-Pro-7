add_executable(gfyms-center main.cpp)
target_link_libraries(gfyms-center PRIVATE Qt6::Core Qt6::Gui Qt6::Widgets Qt6::Network)
install(TARGETS gfyms-center RUNTIME DESTINATION bin)
install(FILES gfyms-center.desktop DESTINATION share/applications)
