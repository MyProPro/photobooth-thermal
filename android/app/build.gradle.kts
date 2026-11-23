plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
    id("com.chaquo.python")
}

android {
    namespace = "id.adsbooth.kiosk"
    compileSdk = 34

    defaultConfig {
        applicationId = "id.adsbooth.kiosk"
        minSdk = 26
        targetSdk = 34
        versionCode = 1
        versionName = "0.1"

        ndk {
            // tablet nyata = arm64; armeabi-v7a utk tablet lama; x86_64 utk emulator
            abiFilters += listOf("arm64-v8a", "armeabi-v7a", "x86_64")
        }

        python {
            version = "3.12"
            pip {
                install("Flask")
                install("waitress")
            }
        }
    }

    buildTypes {
        release { isMinifyEnabled = false }
    }
    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    kotlinOptions { jvmTarget = "17" }
    buildFeatures { viewBinding = false }
}

dependencies {
    implementation("androidx.core:core-ktx:1.13.1")
    implementation("androidx.activity:activity-ktx:1.9.3")
}
