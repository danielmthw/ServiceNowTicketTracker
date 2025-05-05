# ServiceNow Ticket Tracker

![License](https://img.shields.io/badge/license-Free-brightgreen)
![Python](https://img.shields.io/badge/Python-3.9%2B-blue)
![GUI](https://img.shields.io/badge/GUI-Tkinter-informational)
![Platform](https://img.shields.io/badge/Platform-Windows-lightgrey)
![Status](https://img.shields.io/badge/Status-Active-success)
![AutoUpdate](https://img.shields.io/badge/Auto--Update-Enabled-yellow)

Ticket Tracker is a lightweight desktop app built to help IT staff stay on top of their ServiceNow ticket submissions — because we've all done the work, but forgot to put in the ticket.

In fast-moving IT environments, it's common for technicians to get caught up in urgent work, forget to open tickets, or skip logging altogether — leading to gaps in analytics, reduced visibility into completed tasks, and missed accountability.

Whether you're in a solo IT role or part of a larger team, Ticket Tracker helps turn “I’ll log it later” into “Already done.”

## Screenshots

![ ](assets/screenshot.png)

## Features

- A simple, fast entry form to capture ticket details while they're fresh
- A visual checklist to track which tickets have or haven’t been submitted
- Customizable reminder alerts so tickets don’t fall through the cracks
- Local storage with CSV export for reporting
- Runs entirely on your desktop
- Built for future enhancements like ServiceNow API integration or shared team logs


## Install/Clone

### Option 1: Install via Installer

You can download the pre-built Windows installer from the Releases page.

Just download and run the installer — no Python setup required.

### Option 2: Run from Source

- Python 3.7 or higher installed on your system.

1. **Clone the Repository**

   ```bash
   git clone https://github.com/yourusername/TicketTrackerApp.git
   cd TicketTrackerApp
   ```

## Data Storage

The application stores user data in:

- **Windows**: `C:\Users\<Username>\AppData\Roaming\TicketTracker\`

Files:

- `appdata.json`: Stores ticket information.
- `settings.json`: Stores user preferences.

## License

Free for personal, business and educational use.
This project is licensed under the MIT License.

## Credits

Credits
Ticket Tracker App was proudly built using:

- Python 3.9+ – The core programming language
- Tkinter – For crafting a native and responsive desktop GUI
- winsound – Enables system-native audio alerts on Windows
- JSON – For local data and settings persistence
- Threading – Enables reminders and autosave in the background
- Inno Setup – Used to package the app into a Windows installer
