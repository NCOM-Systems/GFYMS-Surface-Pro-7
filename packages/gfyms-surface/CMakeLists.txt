cmake_minimum_required(VERSION 3.16)
project(gfyms_surface VERSION 0.1.0 LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

find_package(ECM 6.0 REQUIRED NO_MODULE)
set(CMAKE_MODULE_PATH ${ECM_MODULE_PATH})

include(KDEInstallDirs)
include(KDECompilerSettings NO_POLICY_SCOPE)
include(KDECMakeSettings)

find_package(Qt6 REQUIRED COMPONENTS Core Gui Quick Widgets Network)
find_package(KF6 REQUIRED COMPONENTS KCMUtils CoreAddons I18n)

add_subdirectory(src)
add_subdirectory(center)
