# Autoname

Autoname is a tool that renames files based on the EXIF `DateTimeOriginal` metadata of photos and video metadata timestamps. If the media files do not contain embedded metadata, it will fall back to filesystem timestamps for renaming.

If the filename contains a usable timestamp, it will take priority over other methods and be used for renaming.

If the target filename already exists, Autoname will keep the timestamp prefix and append the original filename, and if needed, add a numeric suffix to avoid collisions.

`python 3.11+`

## Getting Started

### As Users

Download the latest release [here](https://github.com/gymgle/autoname/releases)

Current builds are GUI-only:

- Double-click the executable, or run `python autoname.py`, to open the app.
- The app includes a progress bar, drag-and-drop folder selection on Windows, result statistics, and error summaries.
- You can switch the interface language between Simplified Chinese and English in the top-right corner.

#### Usage

Desktop application:

```shell
python autoname.py
autoname.exe
```

The app puts all options in the window, so you do not need to remember commands.

What you can do in the window:

- Choose the folder to process.
- Preview the new names before changing anything.
- Limit processing to photos, videos, or specific file formats.
- Include subfolders.
- See progress, current file, results, and errors in real time.

Windows drag-and-drop:

- Drag a folder into the window to fill the folder box.
- Dragging a file also works. The app will use the file's folder.

#### How it works

![Flowchat](./assets/flowchart.drawio.svg)

Autoname chooses a time in this order:

1. Time found in the file name, unless you turn that option off.
2. Photo EXIF `DateTimeOriginal`.
3. Video metadata `Creation date`.
4. File system time.

Notes about reading time from file names:

- Supports names such as `IMG_20240316_101520.jpg`, `VID_20240316_101520.mp4`, and `20240316_101520666_iOS.heic`.
- A 3-digit fraction in the file name is treated as milliseconds.
- “文件名时间偏移” only affects time read from the file name.

Preview mode:

- When you enable preview, the app shows what will be renamed without changing files.
- Preview uses the same duplicate-name handling as the real rename process.

#### Common usage

1. First use:
    Open the app, choose your folder, keep “先预览，不改文件” checked, and review the results.
2. If times in file names are in UTC:
    Set “文件名时间偏移” to `8` or another offset that matches your local time.
3. If you only want photos:
    Change “处理范围” to “仅图片”.
4. If you only want some formats:
    Enter values like `jpg, png` or `heic, mov` in “只处理这些格式”.
5. If you want subfolders too:
    Enable “包含子文件夹”.
6. If you are sure the preview looks right:
    Turn off “先预览，不改文件” and run again to rename files for real.

### As Developers

```shell
# 1. Clone the repository.
$ git clone https://github.com/gymgle/autoname.git

# 2. Install pip requirements.
$ cd autoname
$ pip3 install -r requirements.txt

# 3. Try it!
$ python autoname.py
```

Please **DO NOT** use `exifread 3.0.0` due to `exifread.heic.NoParser: hdlr` issue.
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
    $ pyinstaller -F -w -i ./assets/icon.ico autoname.py
    ```

You can find the packaged `autoname` in `dist` dir.

### Filesystem fallback notes

- Windows: prefer creation time, then modification time.
- macOS: prefer birth time, then modification time.
- Linux: use modification time when embedded metadata is unavailable because `ctime` is not a reliable creation time.
