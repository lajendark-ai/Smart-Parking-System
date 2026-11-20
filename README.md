# Smart Parking System

Software Engineering (CT-365) - Complex Computing Problem

**Team:** Regan (TCT-016), Muhammad Aman (TCT-033), Lajinder (TCT-034), Allahjuddo (TCT-035)

A desktop application (Python, Tkinter, SQLite) for slot reservation, vehicle entry and exit, fee calculation,
payments and reporting, with separate Manager, Staff and User areas.

## Run
```
cd SourceCode
pip install -r requirements.txt
python app.py
```
On Linux install Tkinter first: `sudo apt install python3-tk`.
The database `smart_parking.db` with demo data is created on first start (delete the file to reset).

## Demo accounts
| Role | Username | Password |
|------|----------|----------|
| Manager | manager | manager123 |
| Staff | staff | staff123 |
| User | user | user123 |

## Tests
```
python -m unittest discover -s Tests -v
```
41 automated tests of the business rules.

## Folders
`Proposal/` D1 - `SRS/` D2 - `Design/` D3 - `SourceCode/` D4 - `Tests/` and `TestReports/` D5 - `FinalReport/` D6 -
`Screenshots/` - `InputData/` demo data (CSV) - `TaskBoard.md` task tracker.
