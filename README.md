# VALORANT Companion

A Windows app for checking player stats, choosing agents, saving skin loadouts and using features like Appear Offline.

**Disclaimer: Use this app at your own risk. I am in no way responsible for any cooldowns, restrictions, suspensions or bans imposed by Riot Games as a result of using this app.**

You do not need any coding knowledge to use it.

## What you need

- A Windows 10 or Windows 11 PC (64-bit).
- An internet connection.
- Riot Client and VALORANT for the game features.

## How to set it up

1. At the top of this GitHub page, click **Code**, then **Download ZIP**.
2. Find the downloaded ZIP file. Right-click it and choose **Extract All**, then **Extract**.
3. Open the extracted folder. Find **build_exe.bat** and double-click it. If you only see **build_exe**, that is the same file.
4. A setup window will open. Leave it open while it downloads what it needs and creates the app. This can take several minutes.
5. When setup finishes, a folder will open with your new app selected. **Double-click the selected app to open it.**

You do not need to install Python or type any commands. Setup handles that for you.

**The app will have a random name. This is expected.** If you cannot find it, open the **dist** folder inside the extracted folder and look for a file whose type is **Application**.

## Using it after setup

Open the same app in the **dist** folder whenever you want to use it. You do not need to run **build_exe.bat** every time.

Follow any instructions shown when the app starts. Some social features need to restart Riot Client. If you skip that restart, those features will be unavailable for that session.

Keep an internet connection available so the app can load live information and skin images.

## Keeping your settings

The app saves your settings and loadouts in folders beside it.

If you move the app, move the **whole dist folder** so your saved settings stay with it.

To update, download the latest ZIP and follow the setup steps again. Before opening the new app, copy the **agent_selection** and **loadouts** folders from your old **dist** folder into the new **dist** folder. These hold your saved settings and loadouts.

## If something goes wrong

- **It says to extract the ZIP:** Right-click the ZIP and choose **Extract All**. Run setup from the extracted folder.
- **Setup seems slow:** Leave the window open. The first setup can take several minutes.
- **A download fails:** Check your internet connection, then double-click **build_exe.bat** again.
- **You cannot find the app:** Look in the **dist** folder for a randomly named **Application** file.
- **Setup still fails:** Open the **build** folder, then **setup.log**. Include the error near the bottom when asking for help.
