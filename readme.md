# photo-renamer

photo-renamer is a desktop GUI tool that renames photos and videos by capture time.

It uses the first available time source in this order:

1. A usable timestamp found in the file name, unless that option is disabled.
2. Photo EXIF `DateTimeOriginal`.
3. Video metadata `Creation date`.
4. Filesystem timestamps.

If the target filename already exists, photo-renamer keeps the timestamp prefix, appends the original filename, and adds a numeric suffix if needed to avoid collisions.

`python 3.14`

## Getting Started

### As Users

Download the latest release [here](https://github.com/gymgle/photo-renamer/releases)

Current builds are GUI-only:

- Double-click the executable, or run `python photo_renamer.py`, to open the app.
- The app includes Simple and Pro modes, a progress bar, result statistics, and error summaries.
- You can switch the interface language between Simplified Chinese and English in the top-right corner.
- On Windows, if `windnd` is available, you can drag folders or files into the window.
- You can optionally save logs to a file and open the log folder from the app after a run.

#### Usage

Double-click the executable or run `python photo_renamer.py` to open the app.

The app puts all options in the window, so you do not need to remember commands.

What you can do in the window:

- Choose the folder to process.
- Choose a custom filename format.
- Preview the new names before changing anything.
- Limit processing to photos, videos, or specific file formats.
- Include subfolders.
- Turn off filename timestamp detection when needed.
- Force files to be renamed again even if the name already looks correct.
- Save logs to a file, using either a selected log folder or the current working folder.
- See progress, current file, results, and errors in real time.

Supported formats:

- Photos: `jpg`, `jpeg`, `heic`, `png`, `gif`, `nef`
- Videos: `mp4`, `mov`

Windows drag-and-drop:

- Drag a folder into the window to fill the folder box.
- Dragging a file also works. The app will use the file's folder.

#### How it works

![Flowchat](./assets/flowchart.drawio.svg)

photo-renamer chooses a time in this order:

1. Time found in the file name, unless you turn that option off.
2. Photo EXIF `DateTimeOriginal`.
3. Video metadata `Creation date`.
4. File system time.

Notes about reading time from file names:

- Supports names such as `IMG_20240316_101520.jpg`, `VID_20240316_101520.mp4`, and `20240316_101520666_iOS.heic`.
- A 3-digit fraction in the file name is treated as milliseconds.
- “File name offset” only affects time read from the file name.

Preview mode:

- When you enable preview, the app shows what will be renamed without changing files.
- Preview uses the same duplicate-name handling as the real rename process.

Logging:

- You can enable file logging from the window.
- If you do not select a log folder, the log file is created in the current working folder.
- After a run finishes, you can use the `Open Log Folder` button to open the folder that contains the latest log file.

#### Common usage

1. First use:
    Open the app, choose your folder, keep Preview enabled, and review the results.
2. If times in file names are in UTC:
    Set the filename time offset to `8` or another offset that matches your local time.
3. If you only want photos:
    Change the scope to Images only.
4. If you only want some formats:
    Enter values like `jpg, png` or `heic, mov` in the extension filter.
5. If you want subfolders too:
    Enable Include subfolders.
6. If you are sure the preview looks right:
    Turn off Preview only and run again to rename files for real.
7. If some files already start with a timestamp but you still want to rename them:
    Enable Force rename.

### As Developers

```shell
# 1. Clone the repository.
$ git clone https://github.com/gymgle/photo-renamer.git

# 2. Install pip requirements.
$ cd photo-renamer
$ pip3 install -r requirements.txt

# 3. Try it.
$ python photo_renamer.py
```

Notes:

- `windnd` is only used on Windows for drag-and-drop support.
- Please do not use `ExifRead 3.0.0` due to `exifread.heic.NoParser: hdlr`.

Details: https://github.com/ianare/exif-py/issues/184

### How to Build?

Build Windows/Linux/macOS executable binary file via PyInstaller.

1. Install PyInstaller
    ``` shell
    $ pip install pyinstaller
    ```

2. Prepare UPX (Optional)

    Download UPX [Here](https://github.com/upx/upx/releases), put `upx.exe` (Windows) to project root directory or your Python Virtual Env dir, e.g. `venv\Scripts` for Windows.

3. Build python script to executable binary file
    ```shell
    $ pyinstaller photo_renamer.spec
    ```

You can find the packaged `photo-renamer` in `dist` dir.

### Filesystem fallback notes

- Windows: prefer creation time, then modification time.
- macOS: prefer birth time, then modification time.
- Linux: use modification time when embedded metadata is unavailable because `ctime` is not a reliable creation time.
