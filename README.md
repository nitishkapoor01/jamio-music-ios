# 🎵 Beatify — Premium Spotify-Tier Android Music Streaming App

**Beatify** is a high-fidelity, fluidly animated Android music streaming and offline caching application engineered for academic demonstration, college viva presentation, and portfolio showcase.

Built using modern **Kotlin**, **Jetpack Compose**, **Android Jetpack Media3 (ExoPlayer)**, and **Room SQLite Database**, Beatify delivers a true Spotify-class experience across all Android devices (Android 7.0 to Android 15, API 24–35+), including budget Android Go smartphones.

---

## 🌟 Key Features

### 1. ⚡ Complete Music Catalog in High Definition (320 kbps & Opus 160 kbps)
- Direct integration with open high-fidelity media endpoints.
- Access to global and regional tracks (Billboard, Bollywood, Punjabi, EDM, Lo-Fi, Pop, Rock).
- High-resolution album artwork with automated ambient background tinting.

### 2. 📥 Spotify-Tier Offline Downloads (Zero Internet Playback)
- **One-Tap Download**: Tapping the download arrow downloads the pure 320 kbps audio file and high-res cover art into secure app-private storage.
- **Room SQLite Tracking**: Tracks downloaded status, file paths, file sizes, and date added.
- **Offline Mode**: Automatically switches to local file playback when internet is disconnected or in Airplane Mode.

### 3. 🎨 Fluid Spotify-Style UI & Physics Animations
- **Dark Aesthetic (`#121212`)**: Vibrant Spotify Green (`#1DB954`) accents, glassmorphic cards, and dynamic gradients.
- **Interactive Mini-Player**: Floats above bottom navigation with smooth progress bar, real-time marquee text, and instant play/pause.
- **Full-Screen Player**: Slides up smoothly with spring physics, large glowing album artwork, scrubber slider, shuffle, repeat, and like controls.

### 4. 🎧 Android Jetpack Media3 Foreground Playback
- Runs as an Android `MediaSessionService` with persistent foreground notification.
- Lock screen playback controls, Bluetooth headphone button support, and Android Auto integration.
- Handles audio focus automatically (pauses seamlessly on incoming phone calls and resumes afterwards).

---

## 🏗️ Architecture & Tech Stack

```
com.beatify.music/
├── BeatifyApp.kt                     # Application class & Notification channel setup
├── data/
│   ├── model/
│   │   └── Song.kt                   # Domain Song model (playback URI, formatted duration)
│   ├── local/
│   │   ├── AppDatabase.kt            # Room Database definition
│   │   ├── DownloadDao.kt            # Room DAO for offline downloaded tracks
│   │   ├── FavoriteDao.kt            # Room DAO for liked/starred tracks
│   │   └── entity/
│   │       ├── DownloadedSong.kt     # Offline song entity with file paths & byte size
│   │       └── FavoriteSong.kt       # Liked song entity
│   ├── remote/
│   │   └── MusicApiService.kt        # High-bitrate search & stream resolver
│   └── repository/
│       ├── DownloadManagerRepository.kt # OkHttp byte-streaming download engine with progress
│       └── MusicRepository.kt        # Single source of truth (Remote + Room Local DB)
├── service/
│   └── PlaybackService.kt            # Jetpack Media3 MediaSessionService with ExoPlayer
└── ui/
    ├── MainActivity.kt               # Entry point, Scaffold, and Screen Coordinator
    ├── theme/                        # Colors, typography, and dark theme
    ├── components/
    │   ├── MiniPlayer.kt             # Floating mini player
    │   ├── FullScreenPlayer.kt       # Expandable full-screen modal player
    │   ├── SongListItem.kt           # Song item with download & favorite actions
    │   └── BottomNavBar.kt           # Bottom navigation (Home, Search, Library, Offline)
    ├── screens/
    │   ├── HomeScreen.kt             # Trending music & curated playlists
    │   ├── SearchScreen.kt           # Instant search with category filters
    │   ├── LibraryScreen.kt          # Liked songs & downloads shortcut
    │   └── OfflineDownloadsScreen.kt # Dedicated offline mode manager
    └── viewmodel/
        ├── PlayerViewModel.kt        # Controls MediaController & playback progress
        ├── MusicViewModel.kt         # Search queries & favorites
        └── DownloadViewModel.kt      # Download operations & progress states
```

---

## 🚀 How to Run & Build the Project

### Option A: Open in Android Studio
1. Launch **Android Studio**.
2. Select **Open** and choose this directory: `c:\Users\nitis\Desktop\Music`.
3. Let Gradle sync and press **Run (Shift + F10)** on any physical Android device or Emulator.

### Option B: Build APK via Terminal (Gradle Wrapper)
```bash
# In the Music directory:
.\gradlew.bat assembleDebug
```
The compiled debug APK will be generated at:
`app/build/outputs/apk/debug/app-debug.apk`

### Option C: Run Unit Tests
```bash
.\gradlew.bat test
```

---

## 🎓 Viva & Presentation Talking Points

When presenting this project to professors and external examiners:
1. **Explain the Media Architecture:**
   > *"We implemented Android Jetpack Media3, the official successor to ExoPlayer, encapsulating playback within a Foreground `MediaSessionService`. This ensures playback resilience against OEM aggressive RAM management on budget devices."*
2. **Explain the Offline Caching Strategy:**
   > *"The app implements an OkHttp chunked byte-streaming engine. When a user requests offline storage, audio streams and album art are asynchronously downloaded to private app storage, indexed via Room SQLite with indexed primary keys, allowing instant playback without cellular data."*
3. **Explain Legal & Open Media Streaming:**
   > *"The application adheres to educational non-commercial streaming guidelines, leveraging open public APIs and adaptive bitrates (320 kbps MP3 / 160 kbps Opus) for high-fidelity audio reproduction without proprietary DRM encumbrance."*

