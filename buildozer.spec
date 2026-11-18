[app]

# TIMER MAXDIS - Kivy Android application

title = TIMER MAXDIS
package.name = timermaxdis
package.domain = id.arinex
source.dir = .
source.include_exts = py,kv,png,mp3,json,xml,txt,md
version = 1.0.0

# Runtime
requirements = python3,kivy==2.3.1,pyjnius
orientation = portrait
fullscreen = 0

# Custom app icon and Android notification icon
icon.filename = assets/icon.png
android.add_resources = android_resources/drawable/ic_stat_maxdis.png:drawable/ic_stat_maxdis.png
android.add_src = android_src
android.service_class_name = id.arinex.timermaxdis.MaxdisPythonService

# Foreground Python service for background countdown + alarm
services = timer:services/timer_service.py:foreground:sticky:foregroundServiceType=specialUse

# Android platform configuration
android.api = 35
android.minapi = 23
android.ndk = 28c
android.archs = arm64-v8a,armeabi-v7a
android.accept_sdk_license = True
android.permissions = android.permission.INTERNET,android.permission.POST_NOTIFICATIONS,android.permission.FOREGROUND_SERVICE,android.permission.FOREGROUND_SERVICE_SPECIAL_USE,android.permission.WAKE_LOCK,android.permission.VIBRATE
android.extra_manifest_application_arguments = android_resources/extra_manifest_application_arguments.xml

# Pin p4a release with support for foregroundServiceType.
p4a.branch = v2026.05.09

[buildozer]
log_level = 2
warn_on_root = 1
